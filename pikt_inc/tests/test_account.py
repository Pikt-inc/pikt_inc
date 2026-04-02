from __future__ import annotations

import json
import sys
import types
import unittest
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

from pikt_inc.services import account as account_service


class FakeInsertedDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def get(self, fieldname, default=None):
        return self[fieldname] if fieldname in self else default

    def insert(self):
        self["name"] = "CHKIN-0001"
        return self


class TestAccountService(unittest.TestCase):
    def setUp(self):
        account_service.frappe.session = SimpleNamespace(user="employee@example.com")

    def test_get_account_summary_for_non_employee_user_omits_clock_state(self):
        with patch.object(account_service, "_get_roles", return_value=["System Manager"]), patch.object(
            account_service,
            "_get_user_row",
            return_value={"name": "employee@example.com", "full_name": "Pat Example", "email": "employee@example.com"},
        ), patch.object(
            account_service,
            "_get_employee_row",
            return_value=None,
        ):
            summary = account_service.get_account_summary()

        self.assertEqual(summary["full_name"], "Pat Example")
        self.assertEqual(summary["roles"], ["System Manager"])
        self.assertFalse(summary["has_employee_role"])
        self.assertFalse(summary["can_clock"])
        self.assertIsNone(summary["clock_state"])
        self.assertEqual(summary["recent_checkins"], [])

    def test_get_account_summary_for_employee_includes_clock_state_and_recent_history(self):
        with patch.object(account_service, "_get_roles", return_value=["Employee", "Cleaner"]), patch.object(
            account_service,
            "_get_user_row",
            return_value={"name": "employee@example.com", "full_name": "Pat Example", "email": "employee@example.com"},
        ), patch.object(
            account_service,
            "_get_employee_row",
            return_value={
                "name": "HR-EMP-0001",
                "employee_name": "Pat Example",
                "company": "Pikt",
                "designation": "Cleaner",
                "department": "Operations",
                "status": "Active",
            },
        ), patch.object(
            account_service,
            "_get_recent_checkin_rows",
            return_value=[
                {
                    "name": "CHKIN-2",
                    "log_type": "IN",
                    "time": "2026-04-02 08:00:00",
                    "latitude": 30.25,
                    "longitude": -97.75,
                    "device_id": "Web Account Page",
                }
            ],
        ):
            summary = account_service.get_account_summary()

        self.assertTrue(summary["has_employee_role"])
        self.assertTrue(summary["can_clock"])
        self.assertEqual(summary["employee"]["id"], "HR-EMP-0001")
        self.assertEqual(summary["clock_state"]["status"], "clocked_in")
        self.assertEqual(summary["clock_state"]["next_action"], "clock_out")
        self.assertEqual(len(summary["recent_checkins"]), 1)
        self.assertTrue(summary["recent_checkins"][0]["has_geolocation"])

    def test_log_employee_checkin_requires_exact_employee_role(self):
        with patch.object(account_service, "_get_roles", return_value=["Cleaner"]):
            with self.assertRaisesRegex(Exception, "Only users with the Employee role"):
                account_service.log_employee_checkin(
                    action="clock_in",
                    latitude=30.25,
                    longitude=-97.75,
                )

    def test_log_employee_checkin_requires_linked_employee_record(self):
        with patch.object(account_service, "_get_roles", return_value=["Employee"]), patch.object(
            account_service,
            "_get_employee_row",
            return_value=None,
        ):
            with self.assertRaisesRegex(Exception, "No Employee record is linked"):
                account_service.log_employee_checkin(
                    action="clock_in",
                    latitude=30.25,
                    longitude=-97.75,
                )

    def test_log_employee_checkin_enforces_alternating_in_and_out(self):
        with patch.object(account_service, "_get_roles", return_value=["Employee"]), patch.object(
            account_service,
            "_get_employee_row",
            return_value={"name": "HR-EMP-0001"},
        ), patch.object(
            account_service,
            "_get_recent_checkin_rows",
            return_value=[
                {
                    "name": "CHKIN-2",
                    "log_type": "IN",
                    "time": "2026-04-02 08:00:00",
                    "latitude": 30.25,
                    "longitude": -97.75,
                    "device_id": "Web Account Page",
                }
            ],
        ):
            with self.assertRaisesRegex(Exception, "Clock out first"):
                account_service.log_employee_checkin(
                    action="clock_in",
                    latitude=30.25,
                    longitude=-97.75,
                )

    def test_log_employee_checkin_creates_native_checkin_with_geolocation_payload(self):
        inserted = FakeInsertedDoc()
        recent_rows = [
            {
                "name": "CHKIN-0001",
                "log_type": "IN",
                "time": "2026-04-02 10:00:00",
                "latitude": 30.25,
                "longitude": -97.75,
                "device_id": "Web Account Page",
            }
        ]

        def fake_get_doc(payload):
            inserted.update(payload)
            return inserted

        with patch.object(account_service, "_get_roles", return_value=["Employee"]), patch.object(
            account_service,
            "_get_employee_row",
            return_value={"name": "HR-EMP-0001"},
        ), patch.object(
            account_service,
            "_get_recent_checkin_rows",
            side_effect=[[], recent_rows],
        ), patch.object(
            account_service.frappe,
            "get_doc",
            side_effect=fake_get_doc,
        ), patch.object(
            account_service.frappe.utils,
            "now_datetime",
            return_value="2026-04-02 10:00:00",
        ):
            result = account_service.log_employee_checkin(
                action="clock_in",
                latitude=30.25,
                longitude=-97.75,
            )

        self.assertEqual(inserted["doctype"], "Employee Checkin")
        self.assertEqual(inserted["employee"], "HR-EMP-0001")
        self.assertEqual(inserted["log_type"], "IN")
        self.assertEqual(inserted["device_id"], "Web Account Page")

        geolocation = json.loads(inserted["geolocation"])
        self.assertEqual(geolocation["type"], "FeatureCollection")
        self.assertEqual(geolocation["features"][0]["geometry"]["type"], "Point")
        self.assertEqual(geolocation["features"][0]["geometry"]["coordinates"], [-97.75, 30.25])

        self.assertEqual(result["clock_state"]["status"], "clocked_in")
        self.assertEqual(result["clock_state"]["next_action"], "clock_out")
        self.assertEqual(result["checkin"]["id"], "CHKIN-0001")


if __name__ == "__main__":
    unittest.main()
