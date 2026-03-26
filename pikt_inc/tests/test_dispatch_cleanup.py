from __future__ import annotations

import html
from datetime import date, datetime, timedelta
import sys
from types import SimpleNamespace
import types
import unittest
from unittest.mock import patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

if "frappe" not in sys.modules:
    def _to_datetime(value=None):
        if value is None:
            return datetime(2026, 3, 25, 0, 0, 0)
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace(" ", "T"))

    def _add_to_date(value, hours=0, minutes=0, days=0, as_string=False, as_datetime=False):
        dt_value = _to_datetime(value) + timedelta(days=days, hours=hours, minutes=minutes)
        if as_datetime:
            return dt_value
        if as_string:
            return dt_value.strftime("%Y-%m-%d %H:%M:%S")
        return dt_value

    def _add_days(value, days):
        if isinstance(value, date) and not isinstance(value, datetime):
            return value + timedelta(days=days)
        return (_to_datetime(value) + timedelta(days=days)).date()

    fake_frappe = types.SimpleNamespace(
        utils=types.SimpleNamespace(
            get_datetime=_to_datetime,
            add_to_date=_add_to_date,
            add_days=_add_days,
            now=lambda: "2026-03-25 00:00:00",
            nowdate=lambda: "2026-03-25",
            getdate=lambda value: date.fromisoformat(str(value)),
            get_datetime_in_timezone=lambda _tz: datetime(2026, 3, 25, 0, 0, 0),
            escape_html=lambda value: html.escape(str(value or "")),
            format_datetime=lambda value: str(value),
            format_date=lambda value: str(value),
        ),
        db=types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            get_value=lambda *args, **kwargs: None,
            get_single_value=lambda *args, **kwargs: None,
            set_value=lambda *args, **kwargs: None,
            set_single_value=lambda *args, **kwargs: None,
            sql=lambda *args, **kwargs: [],
        ),
        get_all=lambda *args, **kwargs: [],
        get_doc=lambda *args, **kwargs: None,
        log_error=lambda *args, **kwargs: None,
        sendmail=lambda *args, **kwargs: None,
        clear_cache=lambda: None,
        throw=lambda message, **_kwargs: (_ for _ in ()).throw(Exception(message)),
        whitelist=lambda **kwargs: (lambda fn: fn),
    )
    sys.modules["frappe"] = fake_frappe

from pikt_inc import hooks as app_hooks
from pikt_inc.api import dispatch as dispatch_api
from pikt_inc.jobs import dispatch as dispatch_jobs
from pikt_inc.services.dispatch import planning, routing


class TestDispatchCleanup(unittest.TestCase):
    def test_hook_wiring_adds_cleanup_scheduler_jobs_and_api_override(self):
        self.assertIn(
            "pikt_inc.jobs.dispatch.dispatch_orchestrator_hour_gate",
            app_hooks.scheduler_events["all"],
        )
        self.assertIn(
            "pikt_inc.jobs.dispatch.dispatch_calendar_subject_sync",
            app_hooks.scheduler_events["all"],
        )
        self.assertNotIn("daily", app_hooks.scheduler_events)
        self.assertEqual(
            app_hooks.override_whitelisted_methods["dispatch_data_integrity_migration"],
            "pikt_inc.api.dispatch.dispatch_data_integrity_migration",
        )

    @patch.object(routing.shared, "now_datetime", return_value=routing.shared.to_datetime("2026-03-25 10:00:00"))
    @patch.object(routing.frappe.db, "set_value")
    @patch.object(routing.frappe.db, "get_value")
    @patch.object(routing.frappe, "get_all")
    def test_mark_routes_dirty_for_building_marks_future_emailed_ready_routes(
        self,
        mock_get_all,
        mock_get_value,
        mock_set_value,
        _mock_now,
    ):
        mock_get_all.return_value = [
            {"parent": "DROUTE-1"},
            {"parent": "DROUTE-2"},
            {"parent": "DROUTE-3"},
        ]
        mock_get_value.side_effect = [
            {"status": "Ready", "route_start": "2026-03-25 18:00:00", "last_emailed_hash": "abc", "needs_resend": 0},
            {"status": "Ready", "route_start": "2026-03-25 09:00:00", "last_emailed_hash": "abc", "needs_resend": 0},
            {"status": "Ready", "route_start": "2026-03-25 18:00:00", "last_emailed_hash": "", "needs_resend": 0},
        ]

        result = routing.mark_routes_dirty_for_building("BLDG-0001")

        self.assertEqual(result, {"building": "BLDG-0001", "routes": 3, "marked": 1})
        mock_set_value.assert_called_once_with("Dispatch Route", "DROUTE-1", "needs_resend", 1)

    @patch.object(planning.frappe.db, "set_value")
    @patch.object(planning.frappe, "get_all")
    def test_sync_calendar_subjects_updates_labels_and_clears_stale_supersede(
        self,
        mock_get_all,
        mock_set_value,
    ):
        mock_get_all.return_value = [
            {
                "name": "SSR-0001",
                "building": "BLDG-1",
                "shift_type": "Float Coverage",
                "slot_index": 1,
                "current_employee": "HR-EMP-00001",
                "status": "Assigned",
                "service_timezone": "America/Chicago",
                "custom_calendar_subject": "old",
                "superseded_at": "2026-03-24 10:00:00",
                "superseded_reason": "stale",
            }
        ]

        result = planning.sync_calendar_subjects(clear_stale_superseded=True)

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["updated"], 1)
        mock_set_value.assert_called_once_with(
            "Site Shift Requirement",
            "SSR-0001",
            {
                "custom_calendar_subject": "BLDG-1 | Float Coverage | S1 | HR-EMP-00001 | Assigned | America/Chicago",
                "superseded_at": None,
                "superseded_reason": None,
            },
        )

    @patch.object(dispatch_jobs.frappe, "get_doc")
    def test_should_run_dispatch_orchestrator_respects_hour_and_last_run(self, mock_get_doc):
        mock_get_doc.return_value = SimpleNamespace(
            last_orchestrator_run_on=None,
            orchestrator_hour="06:15",
        )
        self.assertTrue(dispatch_jobs.should_run_dispatch_orchestrator(now_value="2026-03-25 06:16:00"))
        self.assertFalse(dispatch_jobs.should_run_dispatch_orchestrator(now_value="2026-03-25 06:14:00"))

        mock_get_doc.return_value = SimpleNamespace(
            last_orchestrator_run_on="2026-03-25 06:16:00",
            orchestrator_hour="06:15",
        )
        self.assertFalse(dispatch_jobs.should_run_dispatch_orchestrator(now_value="2026-03-25 08:00:00"))

    @patch.object(dispatch_jobs, "nightly_dispatch_orchestrator", return_value={"rules": 2})
    @patch.object(dispatch_jobs, "should_run_dispatch_orchestrator", return_value=True)
    def test_dispatch_orchestrator_hour_gate_runs_nightly_when_due(self, mock_should_run, mock_nightly):
        result = dispatch_jobs.dispatch_orchestrator_hour_gate(now_value="2026-03-25 06:20:00")

        self.assertEqual(
            result,
            {"status": "ran", "now": "2026-03-25 06:20:00", "result": {"rules": 2}},
        )
        mock_should_run.assert_called_once_with(now_value="2026-03-25 06:20:00")
        mock_nightly.assert_called_once_with()

    @patch.object(dispatch_jobs, "nightly_dispatch_orchestrator")
    @patch.object(dispatch_jobs, "should_run_dispatch_orchestrator", return_value=False)
    def test_dispatch_orchestrator_hour_gate_skips_when_not_due(self, mock_should_run, mock_nightly):
        result = dispatch_jobs.dispatch_orchestrator_hour_gate(now_value="2026-03-25 05:30:00")

        self.assertEqual(result, {"status": "skipped", "now": "2026-03-25 05:30:00"})
        mock_should_run.assert_called_once_with(now_value="2026-03-25 05:30:00")
        mock_nightly.assert_not_called()

    @patch.object(dispatch_api.planning, "dispatch_data_integrity_migration", return_value={"updated_slot_index": 2})
    def test_dispatch_data_integrity_migration_api_delegates(self, mock_migration):
        result = dispatch_api.dispatch_data_integrity_migration()

        self.assertEqual(result, {"updated_slot_index": 2})
        mock_migration.assert_called_once_with()

    @patch.object(planning, "sync_calendar_subjects", return_value={"updated": 3})
    @patch.object(planning.frappe.db, "set_value")
    @patch.object(planning.frappe.db, "sql")
    @patch.object(planning.frappe, "get_all")
    def test_dispatch_data_integrity_migration_normalizes_existing_rows(
        self,
        mock_get_all,
        mock_sql,
        mock_set_value,
        mock_sync_subjects,
    ):
        mock_get_all.side_effect = [
            [{"name": "SSR-COMP"}],
            [{"name": "SSR-SLOT", "slot_index": 0}],
            [{"name": "CO-1", "incident_origin": "Supervisor Entered", "notes": "System-generated likely no-show event"}],
            [{"name": "SSR-AUTO"}],
        ]
        mock_sql.side_effect = [
            [],
            [{"cnt": 1}],
        ]

        result = planning.dispatch_data_integrity_migration()

        self.assertEqual(
            result,
            {
                "updated_ssr_completion": 1,
                "updated_slot_index": 1,
                "updated_system_no_show_callouts": 1,
                "updated_auto_assignment_status": 1,
                "deduped_rows": 0,
                "calendar_synced": 3,
                "index_exists": 1,
                "index_error": None,
            },
        )
        mock_set_value.assert_any_call(
            "Site Shift Requirement",
            "SSR-COMP",
            {"completion_status": None, "completed_at": None},
        )
        mock_set_value.assert_any_call("Site Shift Requirement", "SSR-SLOT", "slot_index", 1)
        mock_set_value.assert_any_call("Call Out", "CO-1", "incident_origin", "System No-show")
        mock_set_value.assert_any_call("Site Shift Requirement", "SSR-AUTO", "auto_assignment_status", "Auto Assigned")
        mock_sync_subjects.assert_called_once()


if __name__ == "__main__":
    unittest.main()
