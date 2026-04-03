from __future__ import annotations

import json
import sys
import types
import unittest
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

if "frappe" not in sys.modules:
    fake_frappe = types.SimpleNamespace(
        utils=types.SimpleNamespace(now_datetime=lambda: "2026-04-02 10:00:00"),
        db=types.SimpleNamespace(get_value=lambda *args, **kwargs: None),
        get_all=lambda *args, **kwargs: [],
        get_doc=lambda payload: payload,
        get_roles=lambda _user=None: [],
        session=types.SimpleNamespace(user="Guest"),
        throw=lambda message: (_ for _ in ()).throw(Exception(message)),
    )
    sys.modules["frappe"] = fake_frappe

try:
    account_service = import_module("pikt_inc.services.customer_portal.account.service")
except ModuleNotFoundError:
    account_service = import_module("pikt_inc.pikt_inc.services.customer_portal.account.service")


class TestAccountService(unittest.TestCase):
    def setUp(self):
        account_service.frappe.session = SimpleNamespace(user="employee@example.com")

    def test_get_portal_access_for_customer_role_requires_linked_customer(self):
        with patch.object(account_service.repo, "get_roles", return_value=["Customer"]), patch.object(
            account_service.repo,
            "get_user",
            return_value=SimpleNamespace(name="employee@example.com", custom_customer="CUST-1"),
        ):
            access = account_service.get_portal_access()

        self.assertEqual(access.user_id, "employee@example.com")
        self.assertEqual(access.roles, ["Customer"])
        self.assertEqual(access.portal_persona, "customer")
        self.assertEqual(access.allowed_sections, ["client", "account"])
        self.assertEqual(access.home_path, "/portal/client")

    def test_get_portal_access_for_customer_role_without_link_returns_none(self):
        with patch.object(account_service.repo, "get_roles", return_value=["Customer"]), patch.object(
            account_service.repo,
            "get_user",
            return_value=SimpleNamespace(name="employee@example.com", custom_customer=""),
        ):
            access = account_service.get_portal_access()

        self.assertEqual(access.roles, ["Customer"])
        self.assertEqual(access.portal_persona, "none")
        self.assertEqual(access.allowed_sections, [])
        self.assertEqual(access.home_path, "/desk")

    def test_get_portal_access_for_cleaner_role_keeps_non_portal_roles(self):
        with patch.object(account_service.repo, "get_roles", return_value=["Employee", "Cleaner"]):
            access = account_service.get_portal_access()

        self.assertEqual(access.roles, ["Employee", "Cleaner"])
        self.assertEqual(access.portal_persona, "cleaner")
        self.assertEqual(access.allowed_sections, ["checklist", "account"])
        self.assertEqual(access.home_path, "/portal/checklist")

    def test_get_portal_access_for_system_manager_role(self):
        with patch.object(account_service.repo, "get_roles", return_value=["System Manager"]):
            access = account_service.get_portal_access()

        self.assertEqual(access.portal_persona, "system_manager")
        self.assertEqual(access.allowed_sections, ["admin", "account"])
        self.assertEqual(access.home_path, "/portal/admin")

    def test_get_portal_access_for_non_portal_role_redirects_to_desk(self):
        with patch.object(account_service.repo, "get_roles", return_value=["Employee"]):
            access = account_service.get_portal_access()

        self.assertEqual(access.portal_persona, "none")
        self.assertEqual(access.allowed_sections, [])
        self.assertEqual(access.home_path, "/desk")

    def test_get_portal_access_for_customer_role_without_link_does_not_force_mixed_persona(self):
        with patch.object(account_service.repo, "get_roles", return_value=["Customer", "Cleaner"]), patch.object(
            account_service.repo,
            "get_user",
            return_value=SimpleNamespace(name="employee@example.com", custom_customer=""),
        ):
            access = account_service.get_portal_access()

        self.assertEqual(access.portal_persona, "cleaner")
        self.assertEqual(access.allowed_sections, ["checklist", "account"])
        self.assertEqual(access.home_path, "/portal/checklist")

    def test_get_portal_access_for_linked_customer_and_cleaner_role_redirects_to_desk(self):
        with patch.object(account_service.repo, "get_roles", return_value=["Customer", "Cleaner"]), patch.object(
            account_service.repo,
            "get_user",
            return_value=SimpleNamespace(name="employee@example.com", custom_customer="CUST-1"),
        ):
            access = account_service.get_portal_access()

        self.assertEqual(access.portal_persona, "mixed")
        self.assertEqual(access.allowed_sections, [])
        self.assertEqual(access.home_path, "/desk")

    def test_get_account_summary_for_non_employee_user_omits_clock_state(self):
        with patch.object(account_service.repo, "get_roles", return_value=["System Manager"]), patch.object(
            account_service.repo,
            "get_user",
            return_value=SimpleNamespace(name="employee@example.com", full_name="Pat Example", email="employee@example.com"),
        ), patch.object(
            account_service.repo,
            "get_employee_for_user",
            return_value=None,
        ):
            summary = account_service.get_account_summary()

        self.assertEqual(summary.full_name, "Pat Example")
        self.assertEqual(summary.roles, ["System Manager"])
        self.assertFalse(summary.has_employee_role)
        self.assertFalse(summary.can_clock)
        self.assertIsNone(summary.clock_state)
        self.assertEqual(summary.recent_checkins, [])

    def test_get_account_summary_for_employee_includes_clock_state_and_recent_history(self):
        with patch.object(account_service.repo, "get_roles", return_value=["Employee", "Cleaner"]), patch.object(
            account_service.repo,
            "get_user",
            return_value=SimpleNamespace(name="employee@example.com", full_name="Pat Example", email="employee@example.com"),
        ), patch.object(
            account_service.repo,
            "get_employee_for_user",
            return_value=SimpleNamespace(
                name="HR-EMP-0001",
                employee_name="Pat Example",
                company="Pikt",
                designation="Cleaner",
                department="Operations",
                status="Active",
            ),
        ), patch.object(
            account_service.repo,
            "list_recent_checkins",
            return_value=[
                SimpleNamespace(
                    name="CHKIN-2",
                    log_type="IN",
                    time="2026-04-02 08:00:00",
                    latitude=30.25,
                    longitude=-97.75,
                    device_id="Web Account Page",
                )
            ],
        ):
            summary = account_service.get_account_summary()

        self.assertTrue(summary.has_employee_role)
        self.assertTrue(summary.can_clock)
        self.assertEqual(summary.employee.id, "HR-EMP-0001")
        self.assertEqual(summary.clock_state.status, "clocked_in")
        self.assertEqual(summary.clock_state.next_action, "clock_out")
        self.assertEqual(len(summary.recent_checkins), 1)
        self.assertTrue(summary.recent_checkins[0].has_geolocation)

    def test_log_employee_checkin_requires_exact_employee_role(self):
        with patch.object(account_service.repo, "get_roles", return_value=["Cleaner"]):
            with self.assertRaisesRegex(Exception, "Only users with the Employee role"):
                account_service.log_employee_checkin(
                    action="clock_in",
                    latitude=30.25,
                    longitude=-97.75,
                )

    def test_log_employee_checkin_requires_linked_employee_record(self):
        with patch.object(account_service.repo, "get_roles", return_value=["Employee"]), patch.object(
            account_service.repo,
            "get_employee_for_user",
            return_value=None,
        ):
            with self.assertRaisesRegex(Exception, "No Employee record is linked"):
                account_service.log_employee_checkin(
                    action="clock_in",
                    latitude=30.25,
                    longitude=-97.75,
                )

    def test_log_employee_checkin_enforces_alternating_in_and_out(self):
        with patch.object(account_service.repo, "get_roles", return_value=["Employee"]), patch.object(
            account_service.repo,
            "get_employee_for_user",
            return_value=SimpleNamespace(name="HR-EMP-0001"),
        ), patch.object(
            account_service.repo,
            "list_recent_checkins",
            return_value=[
                SimpleNamespace(
                    name="CHKIN-2",
                    log_type="IN",
                    time="2026-04-02 08:00:00",
                    latitude=30.25,
                    longitude=-97.75,
                    device_id="Web Account Page",
                )
            ],
        ):
            with self.assertRaisesRegex(Exception, "Clock out first"):
                account_service.log_employee_checkin(
                    action="clock_in",
                    latitude=30.25,
                    longitude=-97.75,
                )

    def test_log_employee_checkin_creates_native_checkin_with_geolocation_payload(self):
        recent_rows = [
            SimpleNamespace(
                name="CHKIN-0001",
                log_type="IN",
                time="2026-04-02 10:00:00",
                latitude=30.25,
                longitude=-97.75,
                device_id="Web Account Page",
            )
        ]

        with patch.object(account_service.repo, "get_roles", return_value=["Employee"]), patch.object(
            account_service.repo,
            "get_employee_for_user",
            return_value=SimpleNamespace(name="HR-EMP-0001"),
        ), patch.object(
            account_service.repo,
            "list_recent_checkins",
            side_effect=[[], recent_rows],
        ), patch.object(
            account_service.repo,
            "insert_employee_checkin",
            return_value=recent_rows[0],
        ) as insert_employee_checkin, patch.object(
            account_service.frappe.utils,
            "now_datetime",
            return_value="2026-04-02 10:00:00",
        ):
            result = account_service.log_employee_checkin(
                action="clock_in",
                latitude=30.25,
                longitude=-97.75,
            )

        payload = insert_employee_checkin.call_args.kwargs
        self.assertEqual(payload["employee_name"], "HR-EMP-0001")
        self.assertEqual(payload["log_type"], "IN")
        self.assertEqual(payload["device_id"], "Web Account Page")

        geolocation = json.loads(payload["geolocation"])
        self.assertEqual(geolocation["type"], "FeatureCollection")
        self.assertEqual(geolocation["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(geolocation["features"][0]["geometry"]["coordinates"], [-97.75, 30.25])

        self.assertEqual(result.clock_state.status, "clocked_in")
        self.assertEqual(result.clock_state.next_action, "clock_out")
        self.assertEqual(result.checkin.id, "CHKIN-0001")


if __name__ == "__main__":
    unittest.main()
