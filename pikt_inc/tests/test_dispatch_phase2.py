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
from pikt_inc.services.dispatch import staffing


class FakeDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


class TestDispatchPhase2(unittest.TestCase):
    def test_dispatch_hook_wiring_uses_real_frappe_doc_events(self):
        self.assertEqual(
            app_hooks.doc_events["Shift Assignment"]["on_submit"],
            "pikt_inc.events.shift_assignment.on_submit",
        )
        self.assertEqual(
            app_hooks.doc_events["Shift Assignment"]["on_update_after_submit"],
            "pikt_inc.events.shift_assignment.on_update_after_submit",
        )
        self.assertEqual(
            app_hooks.doc_events["Recurring Service Rule"]["on_update"],
            "pikt_inc.events.recurring_service_rule.on_update",
        )
        self.assertEqual(
            app_hooks.doc_events["Building"]["on_update"],
            "pikt_inc.events.building.on_update",
        )
        self.assertEqual(
            app_hooks.doc_events["Site Shift Requirement"]["on_update"],
            "pikt_inc.events.site_shift_requirement.on_update",
        )
        self.assertNotIn("after_save", app_hooks.doc_events["Shift Assignment"])

    @patch.object(staffing.frappe.db, "exists", return_value=True)
    @patch.object(staffing.frappe, "get_doc")
    def test_sync_from_shift_assignment_updates_safe_requirement(self, mock_get_doc, _mock_exists):
        ssr_doc = FakeDoc(
            {
                "name": "SSR-0001",
                "shift_assignment": None,
                "current_employee": None,
                "status": "Open",
                "auto_assignment_status": "Escalated",
                "shift_location": "",
                "shift_type": "",
                "completion_status": "Unfilled Closed",
                "completed_at": "2026-03-20 10:00:00",
            }
        )
        ssr_doc.flags = SimpleNamespace()
        ssr_doc.save = MagicMock()
        mock_get_doc.return_value = ssr_doc

        assignment_doc = FakeDoc(
            {
                "name": "SASSIGN-0001",
                "custom_site_shift_requirement": "SSR-0001",
                "status": "Active",
                "docstatus": 1,
                "employee": "EMP-0001",
                "shift_location": "On Site",
                "shift_type": "Evening",
            }
        )

        result = staffing.sync_from_shift_assignment(assignment_doc=assignment_doc)

        self.assertEqual(result["status"], "updated")
        self.assertEqual(ssr_doc.shift_assignment, "SASSIGN-0001")
        self.assertEqual(ssr_doc.current_employee, "EMP-0001")
        self.assertEqual(ssr_doc.status, "Assigned")
        self.assertEqual(ssr_doc.shift_location, "On Site")
        self.assertEqual(ssr_doc.shift_type, "Evening")
        self.assertEqual(ssr_doc.auto_assignment_status, "Auto Assigned")
        self.assertIsNone(ssr_doc.completion_status)
        self.assertIsNone(ssr_doc.completed_at)
        ssr_doc.save.assert_called_once_with(ignore_permissions=True)

    @patch.object(staffing.frappe, "get_all")
    @patch.object(staffing.frappe.db, "set_value")
    @patch.object(staffing.incidents, "resolve_open_escalations")
    @patch.object(staffing.incidents, "close_callout_if_open")
    def test_apply_employee_checkin_matches_requirement_and_resolves_incidents(
        self,
        mock_close_callout,
        mock_resolve_escalations,
        mock_set_value,
        mock_get_all,
    ):
        mock_get_all.return_value = [
            {
                "name": "SSR-0001",
                "arrival_window_start": "2026-03-24 18:00:00",
                "arrival_window_end": "2026-03-24 19:00:00",
                "call_out_record": "CALL-0001",
            },
            {
                "name": "SSR-0002",
                "arrival_window_start": "2026-03-24 08:00:00",
                "arrival_window_end": "2026-03-24 09:00:00",
                "call_out_record": None,
            },
        ]
        checkin_doc = FakeDoc(
            {
                "name": "CHKIN-0001",
                "employee": "EMP-0001",
                "time": "2026-03-24 18:10:00",
                "log_type": "IN",
            }
        )

        result = staffing.apply_employee_checkin(checkin_doc=checkin_doc)

        self.assertEqual(result, {"status": "updated", "checkin": "CHKIN-0001", "site_shift_requirement": "SSR-0001"})
        mock_set_value.assert_called_once_with(
            "Site Shift Requirement",
            "SSR-0001",
            {"checked_in_at": "2026-03-24 18:10:00", "status": "Checked In"},
        )
        mock_close_callout.assert_called_once_with("CALL-0001")
        mock_resolve_escalations.assert_called_once_with("SSR-0001")

    @patch.object(staffing.incidents, "has_open_callout_for_ssr", return_value=False)
    @patch.object(staffing.incidents, "has_open_escalation_for_ssr", return_value=False)
    @patch.object(staffing.frappe, "get_all")
    @patch.object(staffing.frappe.db, "set_value")
    @patch.object(staffing.shared, "now", return_value="2026-03-24 21:00:00")
    def test_finalize_completed_requirements_marks_done_after_window(
        self,
        _mock_now,
        mock_set_value,
        mock_get_all,
        _mock_has_open_escalation,
        _mock_has_open_callout,
    ):
        mock_get_all.return_value = [
            {
                "name": "SSR-0001",
                "building": "BLDG-0001",
                "shift_type": "Evening",
                "slot_index": 1,
                "current_employee": "EMP-0001",
                "service_timezone": "America/Chicago",
                "arrival_window_end": "2026-03-24 20:00:00",
            }
        ]

        result = staffing.finalize_completed_requirements(now_dt="2026-03-24 21:00:00")

        self.assertEqual(result, 1)
        mock_set_value.assert_called_once_with(
            "Site Shift Requirement",
            "SSR-0001",
            {
                "status": "Completed",
                "completion_status": "Completed",
                "completed_at": "2026-03-24 21:00:00",
                "exception_reason": None,
                "custom_calendar_subject": "BLDG-0001 | Evening | S1 | EMP-0001 | Completed | America/Chicago",
            },
        )

    @patch.object(staffing.frappe, "get_all")
    @patch.object(staffing.frappe.db, "set_value")
    @patch.object(staffing.incidents, "create_or_update_escalation")
    @patch.object(staffing.shared, "now", return_value="2026-03-24 21:00:00")
    def test_close_unfilled_requirements_escalates_and_closes_policy_breach(
        self,
        _mock_now,
        mock_create_escalation,
        mock_set_value,
        mock_get_all,
    ):
        mock_get_all.return_value = [
            {
                "name": "SSR-0002",
                "building": "BLDG-0002",
                "shift_type": "Morning",
                "slot_index": 2,
                "current_employee": None,
                "service_timezone": "America/Chicago",
                "arrival_window_end": "2026-03-24 18:00:00",
            }
        ]
        settings = {
            "unfilled_close_delay_minutes": 120,
            "escalation_role": "HR Manager",
            "sender_email": "ops@example.com",
        }

        result = staffing.close_unfilled_requirements(now_dt="2026-03-24 21:00:00", settings=settings)

        self.assertEqual(result, 1)
        mock_create_escalation.assert_called_once_with(
            "SSR-0002",
            "BLDG-0002",
            "Manual Override Required",
            "Requirement SSR-0002 closed unfilled after policy window without check-in.",
            settings,
            None,
        )
        mock_set_value.assert_called_once_with(
            "Site Shift Requirement",
            "SSR-0002",
            {
                "status": "Unfilled Closed",
                "completion_status": "Unfilled Closed",
                "completed_at": "2026-03-24 21:00:00",
                "auto_assignment_status": "Escalated",
                "exception_reason": "Requirement SSR-0002 closed unfilled after policy window without check-in.",
                "incident_type": "Unfilled",
                "custom_calendar_subject": "BLDG-0002 | Morning | S2 | Unassigned | Unfilled Closed | America/Chicago",
            },
        )

    @patch.object(dispatch_jobs.shared, "now", return_value="2026-03-24 21:00:00")
    @patch.object(dispatch_jobs.staffing, "finalize_dispatch_completion", return_value={"completed": 1, "unfilled_closed": 2})
    def test_dispatch_completion_finalizer_job_delegates_to_staffing(self, mock_finalize, _mock_now):
        result = dispatch_jobs.dispatch_completion_finalizer()

        self.assertEqual(result, {"completed": 1, "unfilled_closed": 2})
        mock_finalize.assert_called_once_with(now_value="2026-03-24 21:00:00")


if __name__ == "__main__":
    unittest.main()
