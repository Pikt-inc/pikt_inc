from __future__ import annotations

import html
from datetime import datetime, timedelta
from datetime import date
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
            return datetime(2026, 3, 23, 0, 0, 0)
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
            now=lambda: "2026-03-23 00:00:00",
            nowdate=lambda: "2026-03-23",
            getdate=lambda value: date.fromisoformat(str(value)),
            get_datetime_in_timezone=lambda _tz: datetime(2026, 3, 23, 0, 0, 0),
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

from pikt_inc.api import dispatch as dispatch_api
from pikt_inc.jobs import dispatch as dispatch_jobs
from pikt_inc.services.dispatch import planning, routing, shared


class FakeDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


class TestDispatchPhase1(unittest.TestCase):
    @patch.object(planning.frappe.db, "exists", return_value=False)
    @patch.object(planning.frappe, "get_all", return_value=[])
    def test_normalize_site_shift_requirement_sets_defaults_and_subject(
        self,
        _mock_get_all,
        _mock_exists,
    ):
        doc = FakeDoc(
            {
                "name": "SSR-0001",
                "call_out_record": "CALL-0001",
                "slot_index": 0,
                "grace_period_minutes": None,
                "recurring_service_rule": "RSR-0001",
                "service_date": "2026-03-23",
                "status": "Open",
                "completion_status": "Completed",
                "completed_at": "2026-03-20 10:00:00",
                "current_employee": "",
                "auto_assignment_status": "Auto Assigned",
                "arrival_window_start": "2026-03-23 18:00:00",
                "arrival_window_end": "2026-03-23 20:00:00",
                "building": "BLDG-0001",
                "shift_type": "Evening",
                "service_timezone": "America/Chicago",
                "superseded_at": None,
                "superseded_reason": None,
            }
        )

        planning.normalize_site_shift_requirement(doc)

        self.assertIsNone(doc.call_out_record)
        self.assertEqual(doc.slot_index, 1)
        self.assertEqual(doc.grace_period_minutes, shared.DEFAULT_GRACE_MINUTES)
        self.assertIsNone(doc.completion_status)
        self.assertIsNone(doc.completed_at)
        self.assertEqual(doc.auto_assignment_status, "Not Evaluated")
        self.assertTrue(doc.no_show_cutoff.startswith("2026-03-23 18:15"))
        self.assertIn("BLDG-0001", doc.custom_calendar_subject)
        self.assertIn("Open", doc.custom_calendar_subject)

    @patch.object(planning.shared, "get_local_today", return_value=date(2026, 3, 23))
    @patch.object(planning.frappe.db, "get_value", return_value=1)
    def test_build_desired_slots_expands_headcount_for_rule(
        self,
        _mock_building_active,
        _mock_local_today,
    ):
        rule = SimpleNamespace(
            name="RSR-0001",
            active=1,
            building="BLDG-0001",
            shift_type="Evening",
            shift_location="On Site",
            service_timezone="America/Chicago",
            start_time="18:00:00",
            estimated_hours=2,
            required_headcount=2,
            priority="High",
            must_fill=1,
            days_of_week="Mon",
            effective_from=None,
            effective_to=None,
            generation_horizon_days=0,
            default_grace_period_minutes=20,
            service_notes_template="Lock the front door.",
        )

        desired = planning.build_desired_slots(
            rule,
            "manual",
            {
                "default_grace_minutes": shared.DEFAULT_GRACE_MINUTES,
                "max_overtime_hours": shared.DEFAULT_MAX_OVERTIME_HOURS,
                "max_distance_miles": shared.DEFAULT_MAX_DISTANCE_MILES,
                "escalation_role": shared.DEFAULT_ESCALATION_ROLE,
                "sender_email": shared.DEFAULT_SENDER_EMAIL,
                "unfilled_close_delay_minutes": 120,
            },
        )

        self.assertEqual(sorted(desired), [("2026-03-23", 1), ("2026-03-23", 2)])
        first = desired[("2026-03-23", 1)]
        self.assertEqual(first["building"], "BLDG-0001")
        self.assertEqual(first["shift_type"], "Evening")
        self.assertEqual(first["required_headcount"], 1)
        self.assertEqual(first["grace_period_minutes"], 20)
        self.assertEqual(first["service_notes_snapshot"], "Lock the front door.")

    def test_determine_ordered_requirement_names_preserves_existing_order(self):
        assigned_rows = [
            {"name": "SSR-2", "arrival_window_start": "2026-03-24 18:30:00", "creation": "2026-03-23 10:05:00"},
            {"name": "SSR-1", "arrival_window_start": "2026-03-24 18:00:00", "creation": "2026-03-23 10:00:00"},
        ]
        existing_index_map = {"SSR-1": 1, "SSR-2": 2}

        result = routing.determine_ordered_requirement_names(existing_index_map, assigned_rows, membership_changed=False)

        self.assertEqual(result, ["SSR-1", "SSR-2"])

    def test_determine_ordered_requirement_names_resets_when_membership_changes(self):
        assigned_rows = [
            {"name": "SSR-2", "arrival_window_start": "2026-03-24 18:00:00", "creation": "2026-03-23 10:00:00"},
            {"name": "SSR-3", "arrival_window_start": "2026-03-24 18:30:00", "creation": "2026-03-23 10:05:00"},
        ]

        result = routing.determine_ordered_requirement_names({"SSR-2": 2}, assigned_rows, membership_changed=True)

        self.assertEqual(result, ["SSR-2", "SSR-3"])

    def test_compute_route_window_recomputes_notify_at(self):
        route_start, route_end, notify_at = routing.compute_route_window(
            [
                {
                    "arrival_window_start": "2026-03-24 19:00:00",
                    "arrival_window_end": "2026-03-24 20:00:00",
                },
                {
                    "arrival_window_start": "2026-03-24 17:30:00",
                    "arrival_window_end": "2026-03-24 18:15:00",
                },
            ]
        )

        self.assertEqual(route_start, "2026-03-24 17:30:00")
        self.assertEqual(route_end, "2026-03-24 20:00:00")
        self.assertEqual(notify_at, "2026-03-24 15:30:00")

    def test_build_route_signature_changes_when_building_notes_change(self):
        stops = [
            {
                "stop_index": 1,
                "site_shift_requirement": "SSR-0001",
                "building": "BLDG-0001",
                "arrival_window_start": "2026-03-24 18:00:00",
                "arrival_window_end": "2026-03-24 19:00:00",
            }
        ]
        base_buildings = {
            "BLDG-0001": {
                "building_name": "North Office",
                "address_line_1": "123 Main",
                "address_line_2": "",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78701",
                "site_notes": "Use rear entrance.",
                "access_notes": "",
                "alarm_notes": "",
                "site_supervisor_name": "Pat",
                "site_supervisor_phone": "555-0001",
            }
        }
        changed_buildings = {
            "BLDG-0001": {
                **base_buildings["BLDG-0001"],
                "site_notes": "Use front entrance.",
            }
        }

        first = routing.build_route_signature(stops, base_buildings)
        second = routing.build_route_signature(stops, changed_buildings)

        self.assertNotEqual(first, second)

    def test_choose_route_recipient_precedence(self):
        with self.subTest("enabled user id wins"):
            with patch.object(routing.frappe.db, "exists", return_value=True), patch.object(
                routing.frappe.db,
                "get_value",
                return_value=1,
            ):
                self.assertEqual(
                    routing.choose_route_recipient(
                        {
                            "user_id": "cleaner@example.com",
                            "company_email": "company@example.com",
                            "personal_email": "personal@example.com",
                        }
                    ),
                    "cleaner@example.com",
                )

        with self.subTest("company email wins when user is disabled"):
            with patch.object(routing.frappe.db, "exists", return_value=True), patch.object(
                routing.frappe.db,
                "get_value",
                return_value=0,
            ):
                self.assertEqual(
                    routing.choose_route_recipient(
                        {
                            "user_id": "cleaner@example.com",
                            "company_email": "company@example.com",
                            "personal_email": "personal@example.com",
                        }
                    ),
                    "company@example.com",
                )

        with self.subTest("personal email is last fallback"):
            with patch.object(routing.frappe.db, "exists", return_value=False), patch.object(
                routing.frappe.db,
                "get_value",
                return_value=0,
            ):
                self.assertEqual(
                    routing.choose_route_recipient(
                        {
                            "user_id": "",
                            "company_email": "",
                            "personal_email": "personal@example.com",
                        }
                    ),
                    "personal@example.com",
                )

    @patch.object(planning, "supersede_requirement")
    @patch.object(planning.shared, "today", return_value=date(2026, 3, 23))
    @patch.object(planning.shared, "now_datetime", return_value=planning.shared.to_datetime("2026-03-23 12:00:00"))
    @patch.object(planning.frappe, "get_all")
    def test_sync_paused_buildings_only_supersedes_future_rows(
        self,
        mock_get_all,
        _mock_now,
        _mock_today,
        mock_supersede,
    ):
        mock_get_all.side_effect = [
            [{"name": "BLDG-0001"}],
            [
                {
                    "name": "SSR-PAST",
                    "building": "BLDG-0001",
                    "shift_type": "Evening",
                    "slot_index": 1,
                    "service_timezone": "America/Chicago",
                    "arrival_window_start": "2026-03-23 10:00:00",
                },
                {
                    "name": "SSR-FUTURE",
                    "building": "BLDG-0001",
                    "shift_type": "Evening",
                    "slot_index": 1,
                    "service_timezone": "America/Chicago",
                    "arrival_window_start": "2026-03-23 18:00:00",
                },
            ],
        ]

        result = planning.sync_paused_buildings()

        self.assertEqual(result, {"status": "ok", "processed": 1})
        mock_supersede.assert_called_once_with(
            {
                "name": "SSR-FUTURE",
                "building": "BLDG-0001",
                "shift_type": "Evening",
                "slot_index": 1,
                "service_timezone": "America/Chicago",
                "arrival_window_start": "2026-03-23 18:00:00",
            },
            "Superseded by building pause: building marked inactive",
        )

    @patch.object(dispatch_jobs.routing, "send_due_route_emails", return_value={"sent": 1})
    @patch.object(dispatch_jobs.routing, "reconcile_routes", return_value={"updated": 2})
    def test_dispatch_route_email_orchestrator_runs_reconcile_then_email(
        self,
        mock_reconcile,
        mock_send,
    ):
        result = dispatch_jobs.dispatch_route_email_orchestrator()

        self.assertEqual(result, {"reconcile": {"updated": 2}, "email": {"sent": 1}})
        mock_reconcile.assert_called_once_with(trigger_source="route_email_scheduler")
        mock_send.assert_called_once()

    @patch.object(dispatch_jobs.shared, "now", return_value="2026-03-23 02:30:00")
    @patch.object(dispatch_jobs.planning, "sync_paused_buildings", return_value={"processed": 3})
    @patch.object(dispatch_jobs.planning, "reconcile_rule", side_effect=[{"rule": "RSR-1"}, {"rule": "RSR-2"}])
    @patch.object(dispatch_jobs.frappe.db, "set_single_value")
    @patch.object(dispatch_jobs.frappe.db, "exists", return_value=True)
    @patch.object(dispatch_jobs.frappe, "get_all", return_value=[{"name": "RSR-1"}, {"name": "RSR-2"}])
    def test_nightly_dispatch_orchestrator_reconciles_rules_and_updates_last_run(
        self,
        _mock_get_all,
        _mock_exists,
        mock_set_single_value,
        mock_reconcile_rule,
        mock_sync_paused,
        _mock_now,
    ):
        result = dispatch_jobs.nightly_dispatch_orchestrator()

        self.assertEqual(result["rules"], 2)
        self.assertEqual(result["results"], [{"rule": "RSR-1"}, {"rule": "RSR-2"}])
        self.assertEqual(mock_reconcile_rule.call_count, 2)
        mock_sync_paused.assert_called_once_with()
        mock_set_single_value.assert_called_once_with(
            "Dispatch Automation Settings",
            "last_orchestrator_run_on",
            "2026-03-23 02:30:00",
        )

    @patch.object(dispatch_api.routing, "reconcile_routes", return_value={"updated": 4})
    def test_dispatch_reconcile_routes_api_uses_existing_method_name(self, mock_reconcile):
        result = dispatch_api.dispatch_reconcile_routes(site_shift_requirement="SSR-0001", trigger_source="manual")

        self.assertEqual(result, {"updated": 4})
        mock_reconcile.assert_called_once_with(site_shift_requirement="SSR-0001", trigger_source="manual")

    @patch.object(dispatch_api.planning, "reconcile_rule", return_value={"rule": "RSR-0001"})
    def test_dispatch_reconcile_rule_api_normalizes_run_assignment(self, mock_reconcile):
        result = dispatch_api.dispatch_reconcile_rule(rule="RSR-0001", run_assignment="true", trigger_source="after_save")

        self.assertEqual(result, {"rule": "RSR-0001"})
        mock_reconcile.assert_called_once_with(
            rule_name="RSR-0001",
            trigger_source="after_save",
            run_assignment=True,
        )
