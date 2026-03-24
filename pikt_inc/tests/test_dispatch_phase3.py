from __future__ import annotations

import html
from datetime import date, datetime, timedelta
from types import SimpleNamespace
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

if "frappe" not in sys.modules:
    def _to_datetime(value=None):
        if value is None:
            return datetime(2026, 3, 24, 0, 0, 0)
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

    fake_frappe = types.SimpleNamespace(
        utils=types.SimpleNamespace(
            get_datetime=_to_datetime,
            add_to_date=_add_to_date,
            add_days=lambda value, days: date.fromisoformat(str(value)) + timedelta(days=days),
            now=lambda: "2026-03-24 00:00:00",
            nowdate=lambda: "2026-03-24",
            getdate=lambda value: date.fromisoformat(str(value)),
            get_datetime_in_timezone=lambda _tz: datetime(2026, 3, 24, 0, 0, 0),
            escape_html=lambda value: html.escape(str(value or "")),
            format_datetime=lambda value: str(value),
            format_date=lambda value: str(value),
        ),
        db=types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            get_value=lambda *args, **kwargs: None,
            set_value=lambda *args, **kwargs: None,
            set_single_value=lambda *args, **kwargs: None,
            sql=lambda *args, **kwargs: [],
        ),
        get_all=lambda *args, **kwargs: [],
        get_doc=lambda *args, **kwargs: None,
        log_error=lambda *args, **kwargs: None,
        sendmail=lambda *args, **kwargs: None,
        clear_cache=lambda: None,
        throw=lambda message: (_ for _ in ()).throw(Exception(message)),
        whitelist=lambda **kwargs: (lambda fn: fn),
    )
    sys.modules["frappe"] = fake_frappe

from pikt_inc import hooks as app_hooks
from pikt_inc.jobs import dispatch as dispatch_jobs
from pikt_inc.services.dispatch import incidents


class FakeDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


class TestDispatchPhase3(unittest.TestCase):
    def test_dispatch_phase3_hook_wiring(self):
        self.assertEqual(
            app_hooks.doc_events["Call Out"]["after_insert"],
            "pikt_inc.events.call_out.after_insert",
        )
        self.assertEqual(
            app_hooks.doc_events["Call Out"]["on_update"],
            "pikt_inc.events.call_out.on_update",
        )
        self.assertEqual(
            app_hooks.doc_events["Dispatch Recommendation"]["on_update"],
            "pikt_inc.events.dispatch_recommendation.on_update",
        )
        self.assertIn(
            "pikt_inc.jobs.dispatch.monitor_no_show_site_shift_requirements",
            app_hooks.scheduler_events["all"],
        )

    @patch.object(incidents.frappe.db, "exists", return_value=True)
    @patch.object(incidents.frappe, "get_doc")
    def test_sync_from_call_out_updates_ssr_state(self, mock_get_doc, _mock_exists):
        ssr_doc = FakeDoc(
            {
                "name": "SSR-0001",
                "call_out_record": None,
                "status": "Completed",
                "incident_type": "None",
                "building": "",
                "completion_status": "Completed",
                "completed_at": "2026-03-24 10:00:00",
            }
        )
        ssr_doc.flags = SimpleNamespace()
        ssr_doc.save = MagicMock()
        mock_get_doc.return_value = ssr_doc

        call_out_doc = SimpleNamespace(
            name="CO-0001",
            site_shift_requirement="SSR-0001",
            incident_origin="System No-show",
            building="BLDG-0001",
        )

        result = incidents.sync_from_call_out(call_out_doc=call_out_doc)

        self.assertEqual(result, {"status": "updated", "call_out": "CO-0001", "site_shift_requirement": "SSR-0001"})
        self.assertEqual(ssr_doc.call_out_record, "CO-0001")
        self.assertEqual(ssr_doc.status, "Called Out")
        self.assertEqual(ssr_doc.incident_type, "No-show")
        self.assertEqual(ssr_doc.building, "BLDG-0001")
        self.assertIsNone(ssr_doc.completed_at)
        self.assertIsNone(ssr_doc.completion_status)
        ssr_doc.save.assert_called_once_with(ignore_permissions=True)

    @patch.object(incidents.frappe.db, "exists", return_value=True)
    @patch.object(incidents.frappe.db, "set_value")
    @patch.object(incidents, "create_or_update_escalation")
    @patch.object(incidents.frappe, "get_doc")
    @patch.object(incidents.shared, "get_dispatch_settings", return_value={"max_overtime_hours": 2.0, "max_distance_miles": 25.0, "escalation_role": "HR Manager", "sender_email": "ops@example.com", "unfilled_close_delay_minutes": 120})
    @patch("pikt_inc.services.dispatch.staffing.build_candidates", return_value=[])
    def test_generate_recommendations_escalates_when_no_candidate(
        self,
        _mock_candidates,
        _mock_settings,
        mock_get_doc,
        mock_create_escalation,
        mock_set_value,
        _mock_exists,
    ):
        ssr_doc = FakeDoc(
            {
                "name": "SSR-0002",
                "service_date": "2026-03-24",
                "building": "BLDG-0002",
                "status": "Called Out",
                "arrival_window_start": "2026-03-24 18:00:00",
                "arrival_window_end": "2026-03-24 19:00:00",
                "estimated_hours": 1,
                "shift_type": "Evening",
                "shift_location": "Pilot Site 3",
                "slot_index": 1,
                "priority": "Medium",
            }
        )
        mock_get_doc.return_value = ssr_doc
        call_out_doc = SimpleNamespace(
            name="CO-0002",
            site_shift_requirement="SSR-0002",
            call_out_date="2026-03-24",
            replacement_status="Replacement Pending",
            incident_origin="Supervisor Entered",
            employee="HR-EMP-00001",
        )

        result = incidents.generate_recommendations(call_out_doc=call_out_doc)

        self.assertEqual(result["status"], "escalated")
        mock_create_escalation.assert_called_once()
        mock_set_value.assert_any_call(
            "Site Shift Requirement",
            "SSR-0002",
            {
                "status": "Reassignment In Progress",
                "auto_assignment_status": "Escalated",
                "exception_reason": "No valid replacement candidate found for requirement SSR-0002 on 2026-03-24.",
            },
        )
        mock_set_value.assert_any_call("Call Out", "CO-0002", "replacement_status", "Replacement Pending")

    @patch.object(incidents.frappe.db, "exists", return_value=True)
    @patch.object(incidents.frappe.db, "set_value")
    @patch.object(incidents, "resolve_open_escalations")
    @patch.object(incidents.frappe, "get_doc")
    @patch.object(incidents.shared, "get_dispatch_settings", return_value={"max_overtime_hours": 2.0, "max_distance_miles": 25.0, "escalation_role": "HR Manager", "sender_email": "ops@example.com", "unfilled_close_delay_minutes": 120})
    @patch("pikt_inc.services.dispatch.staffing.sync_from_shift_assignment")
    @patch("pikt_inc.services.dispatch.staffing.create_recommendation_batch")
    @patch("pikt_inc.services.dispatch.staffing.ensure_active_shift_assignment_for_requirement")
    @patch("pikt_inc.services.dispatch.staffing.build_candidates")
    def test_generate_recommendations_auto_assigns_best_candidate(
        self,
        mock_candidates,
        mock_ensure_assignment,
        mock_create_batch,
        mock_sync_assignment,
        _mock_settings,
        mock_get_doc,
        mock_resolve_escalations,
        mock_set_value,
        _mock_exists,
    ):
        mock_candidates.return_value = [
            {"employee": "HR-EMP-00002", "total_score": 90, "drive_time_minutes": 10, "distance_miles": 2, "familiarity_score": 8, "availability_score": 40, "overtime_penalty": 0, "priority_score": 20},
            {"employee": "HR-EMP-00003", "total_score": 70, "drive_time_minutes": 12, "distance_miles": 3, "familiarity_score": 5, "availability_score": 30, "overtime_penalty": 2, "priority_score": 20},
        ]
        mock_ensure_assignment.return_value = SimpleNamespace(name="HR-SHA-0001")
        ssr_doc = FakeDoc(
            {
                "name": "SSR-0003",
                "service_date": "2026-03-24",
                "building": "BLDG-0003",
                "status": "Called Out",
                "arrival_window_start": "2026-03-24 18:00:00",
                "arrival_window_end": "2026-03-24 19:00:00",
                "estimated_hours": 1,
                "shift_type": "Evening",
                "shift_location": "Pilot Site 3",
                "slot_index": 1,
                "priority": "Medium",
                "shift_assignment": None,
            }
        )
        mock_get_doc.return_value = ssr_doc
        call_out_doc = SimpleNamespace(
            name="CO-0003",
            site_shift_requirement="SSR-0003",
            call_out_date="2026-03-24",
            replacement_status="Replacement Pending",
            incident_origin="System No-show",
            employee="HR-EMP-00001",
        )

        result = incidents.generate_recommendations(call_out_doc=call_out_doc)

        self.assertEqual(result["status"], "assigned")
        mock_ensure_assignment.assert_called_once()
        mock_create_batch.assert_called_once()
        mock_sync_assignment.assert_called_once()
        mock_set_value.assert_any_call(
            "Call Out",
            "CO-0003",
            "replacement_status",
            "Replaced",
        )
        mock_resolve_escalations.assert_called_once_with("SSR-0003")

    @patch.object(incidents.frappe.db, "exists")
    @patch.object(incidents.frappe.db, "set_value")
    @patch.object(incidents, "resolve_open_escalations")
    @patch.object(incidents.frappe, "get_doc")
    @patch("pikt_inc.services.dispatch.staffing.sync_from_shift_assignment")
    @patch("pikt_inc.services.dispatch.staffing.ensure_active_shift_assignment_for_requirement")
    def test_approve_reassignment_assigns_candidate_for_escalated_requirement(
        self,
        mock_ensure_assignment,
        mock_sync_assignment,
        mock_get_doc,
        mock_resolve_escalations,
        mock_set_value,
        mock_exists,
    ):
        mock_exists.side_effect = lambda doctype, name=None: True
        ssr_doc = FakeDoc(
            {
                "name": "SSR-0004",
                "auto_assignment_status": "Escalated",
                "call_out_record": "CO-0004",
            }
        )
        mock_get_doc.return_value = ssr_doc
        mock_ensure_assignment.return_value = SimpleNamespace(name="HR-SHA-0002")
        recommendation_doc = SimpleNamespace(
            name="DR-0001",
            decision_status="Approved",
            site_shift_requirement="SSR-0004",
            candidate_employee="HR-EMP-00004",
        )

        result = incidents.approve_reassignment(recommendation_doc=recommendation_doc)

        self.assertEqual(result["status"], "assigned")
        mock_sync_assignment.assert_called_once()
        mock_set_value.assert_any_call(
            "Site Shift Requirement",
            "SSR-0004",
            {
                "status": "Assigned",
                "current_employee": "HR-EMP-00004",
                "shift_assignment": "HR-SHA-0002",
                "auto_assignment_status": "Auto Assigned",
                "exception_reason": None,
            },
        )
        mock_set_value.assert_any_call("Call Out", "CO-0004", "replacement_status", "Replaced")
        mock_resolve_escalations.assert_called_once_with("SSR-0004")

    @patch.object(incidents.frappe, "get_all")
    @patch.object(incidents.frappe, "get_doc")
    def test_monitor_no_shows_marks_likely_and_creates_callout(self, mock_get_doc, mock_get_all):
        ssr_doc = FakeDoc(
            {
                "name": "SSR-0005",
                "status": "Assigned",
                "checked_in_at": None,
                "current_employee": "HR-EMP-00005",
                "incident_type": "None",
            }
        )
        ssr_doc.flags = SimpleNamespace()
        ssr_doc.save = MagicMock()

        call_out_doc = FakeDoc({"name": "CO-0005"})
        call_out_doc.insert = MagicMock()
        mock_get_doc.side_effect = [ssr_doc, call_out_doc]
        mock_get_all.side_effect = [
            [
                {
                    "name": "SSR-0005",
                    "current_employee": "HR-EMP-00005",
                    "call_out_record": None,
                    "service_date": "2026-03-24",
                    "building": "BLDG-0005",
                    "arrival_window_start": "2026-03-24 18:00:00",
                    "arrival_window_end": "2026-03-24 19:00:00",
                    "grace_period_minutes": 15,
                    "no_show_cutoff": "2026-03-24 18:15:00",
                }
            ],
            [],
        ]

        result = incidents.monitor_no_shows(now_value="2026-03-24 18:20:00")

        self.assertEqual(result, {"processed": 1, "now": "2026-03-24 18:20:00"})
        self.assertEqual(ssr_doc.status, "Likely No-show")
        self.assertEqual(ssr_doc.incident_type, "No-show")
        ssr_doc.save.assert_called_once_with(ignore_permissions=True)
        call_out_doc.insert.assert_called_once_with(ignore_permissions=True)

    @patch.object(dispatch_jobs.shared, "now", return_value="2026-03-24 18:20:00")
    @patch.object(dispatch_jobs.incidents, "monitor_no_shows", return_value={"processed": 1, "now": "2026-03-24 18:20:00"})
    def test_no_show_monitor_job_delegates_to_incidents(self, mock_monitor, _mock_now):
        result = dispatch_jobs.monitor_no_show_site_shift_requirements()

        self.assertEqual(result, {"processed": 1, "now": "2026-03-24 18:20:00"})
        mock_monitor.assert_called_once_with(now_value="2026-03-24 18:20:00")


if __name__ == "__main__":
    unittest.main()
