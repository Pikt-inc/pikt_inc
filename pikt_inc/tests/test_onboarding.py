from __future__ import annotations

import sys
from types import SimpleNamespace
import types
import unittest
from unittest.mock import MagicMock, patch

if "frappe" not in sys.modules:
    fake_frappe = types.SimpleNamespace(
        utils=types.SimpleNamespace(now=lambda: "2026-03-24 13:00:00", today=lambda: "2026-03-24"),
        db=types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            get_value=lambda *args, **kwargs: None,
            set_value=lambda *args, **kwargs: None,
        ),
        get_doc=lambda *args, **kwargs: None,
        session=types.SimpleNamespace(user="manager@example.com"),
        throw=lambda message, **_kwargs: (_ for _ in ()).throw(Exception(message)),
        whitelist=lambda **kwargs: (lambda fn: fn),
    )
    sys.modules["frappe"] = fake_frappe

if not hasattr(sys.modules["frappe"], "session"):
    sys.modules["frappe"].session = types.SimpleNamespace(user="manager@example.com")
if not hasattr(sys.modules["frappe"], "utils"):
    sys.modules["frappe"].utils = types.SimpleNamespace()
if not hasattr(sys.modules["frappe"].utils, "today"):
    sys.modules["frappe"].utils.today = lambda: "2026-03-24"
if not hasattr(sys.modules["frappe"].utils, "now"):
    sys.modules["frappe"].utils.now = lambda: "2026-03-24 13:00:00"

from pikt_inc import hooks as app_hooks
from pikt_inc.services import onboarding


class FakeDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value

    def append(self, fieldname, value):
        self.setdefault(fieldname, []).append(SimpleNamespace(**value))

    def set(self, fieldname, value):
        self[fieldname] = value


class FakeSaveDoc(FakeDoc):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.insert_called = False
        self.save_called = False
        self.reload_called = False

    def insert(self, ignore_permissions=False):
        self.insert_called = True
        self.insert_ignore_permissions = ignore_permissions
        if not self.get("name"):
            self.name = self.get("email") or self.get("user_id") or self.get("employee") or "DOC-0001"
        return self

    def save(self, ignore_permissions=False):
        self.save_called = True
        self.save_ignore_permissions = ignore_permissions
        return self

    def reload(self):
        self.reload_called = True
        return self


class TestOnboarding(unittest.TestCase):
    def test_hook_wiring_adds_onboarding_events(self):
        self.assertEqual(
            app_hooks.doc_events["Employee Onboarding Request"]["before_insert"],
            "pikt_inc.events.employee_onboarding_request.before_insert",
        )
        self.assertEqual(
            app_hooks.doc_events["Employee Onboarding Packet"]["before_save"],
            "pikt_inc.events.employee_onboarding_packet.before_save",
        )

    @patch.object(onboarding.frappe.utils, "today", return_value="2026-03-24")
    @patch.object(onboarding.frappe.utils, "now", return_value="2026-03-24 13:00:00")
    @patch.object(onboarding.frappe.db, "set_value")
    @patch.object(onboarding.frappe.db, "get_value")
    @patch.object(onboarding.frappe.db, "exists")
    @patch.object(onboarding.frappe, "get_doc")
    def test_provision_employee_onboarding_request_creates_user_employee_and_packet(
        self,
        mock_get_doc,
        mock_exists,
        mock_get_value,
        mock_set_value,
        _mock_now,
        _mock_today,
    ):
        user_doc = FakeSaveDoc(
            {
                "doctype": "User",
                "email": "qa.onboarding@example.com",
                "name": "qa.onboarding@example.com",
                "roles": [SimpleNamespace(role="Employee Onboarding User"), SimpleNamespace(role="Employee")],
            }
        )
        employee_doc = FakeSaveDoc(
            {
                "doctype": "Employee",
                "name": "HR-EMP-TEST-0001",
                "employee_name": "QA Onboarding",
            }
        )
        packet_doc = FakeSaveDoc({"doctype": "Employee Onboarding Packet", "name": "EOP-TEST-0001"})

        def fake_exists(doctype, name=None):
            if doctype in {"Company", "Department", "Designation"}:
                return True
            return False

        def fake_get_doc(arg1, arg2=None):
            if isinstance(arg1, dict):
                if arg1.get("doctype") == "User":
                    return user_doc
                if arg1.get("doctype") == "Employee":
                    return employee_doc
                if arg1.get("doctype") == "Employee Onboarding Packet":
                    return packet_doc
            if arg1 == "User" and arg2 == "qa.onboarding@example.com":
                return user_doc
            raise AssertionError(f"Unexpected get_doc call: {arg1}, {arg2}")

        mock_exists.side_effect = fake_exists
        mock_get_value.side_effect = [None, None, None]
        mock_get_doc.side_effect = fake_get_doc

        doc = FakeDoc(
            {
                "employee_email": "QA.ONBOARDING@example.com",
                "full_name": " QA   Onboarding ",
                "start_date": "2026-04-01",
            }
        )

        result = onboarding.provision_employee_onboarding_request(doc)

        self.assertEqual(result["user"], "qa.onboarding@example.com")
        self.assertEqual(result["employee"], "HR-EMP-TEST-0001")
        self.assertEqual(result["packet"], "EOP-TEST-0001")
        self.assertEqual(doc.employee_email, "qa.onboarding@example.com")
        self.assertEqual(doc.full_name, "QA Onboarding")
        self.assertEqual(doc.manager_email, "manager@example.com")
        self.assertEqual(doc.request_status, "Invited")
        self.assertEqual(doc.user, "qa.onboarding@example.com")
        self.assertEqual(doc.employee, "HR-EMP-TEST-0001")
        self.assertEqual(doc.onboarding_packet, "EOP-TEST-0001")
        self.assertTrue(user_doc.insert_called)
        self.assertTrue(employee_doc.insert_called)
        self.assertTrue(user_doc.save_called)
        self.assertEqual(user_doc.roles, [{"role": "Employee Onboarding User"}])
        mock_set_value.assert_any_call("Employee Onboarding Packet", "EOP-TEST-0001", "owner", "qa.onboarding@example.com", update_modified=False)
        mock_set_value.assert_any_call("Employee", "HR-EMP-TEST-0001", "custom_onboarding_packet", "EOP-TEST-0001", update_modified=False)

    @patch.object(onboarding.frappe.db, "exists", return_value=True)
    def test_provision_employee_onboarding_request_rejects_existing_user(self, _mock_exists):
        doc = FakeDoc(
            {
                "employee_email": "qa.onboarding@example.com",
                "full_name": "QA Onboarding",
                "start_date": "2026-04-01",
            }
        )

        with self.assertRaisesRegex(Exception, "A User already exists for this email address."):
            onboarding.provision_employee_onboarding_request(doc)

    @patch.object(onboarding.frappe.db, "get_value", return_value="REQ-TEST-0001")
    @patch.object(onboarding.frappe.db, "set_value")
    @patch.object(onboarding.frappe.db, "exists", return_value=True)
    @patch.object(onboarding.frappe.utils, "now", return_value="2026-03-24 14:00:00")
    @patch.object(onboarding.frappe.utils, "today", return_value="2026-03-24")
    def test_sync_employee_onboarding_packet_marks_submitted_and_updates_related_records(
        self,
        _mock_today,
        _mock_now,
        mock_exists,
        mock_set_value,
        _mock_get_value,
    ):
        mock_exists.side_effect = lambda doctype, name=None: True if doctype in {"Employee", "User"} else False
        doc = FakeDoc(
            {
                "name": "EOP-TEST-0001",
                "user_id": "qa.onboarding@example.com",
                "employee": "HR-EMP-TEST-0001",
                "employee_email": "qa.onboarding@example.com",
                "start_date": "2026-04-01",
                "packet_status": "Invited",
                "first_name": " QA ",
                "last_name": " Onboarding ",
                "mobile_number": "5125551000",
                "personal_email": "QA.Personal@example.com",
                "street_address": "123 Main St",
                "city": "Austin",
                "state": "TX",
                "postal_code": "78701",
                "emergency_contact_name": "Casey Contact",
                "emergency_contact_phone": "5125552000",
                "emergency_contact_relationship": "Sibling",
                "transportation_status": "Reliable Transportation",
                "preferred_shift_preference": "Night Clean",
                "availability_notes": "Weeknights",
                "government_id_upload": "/private/files/id.pdf",
                "acknowledge_attendance_policy": 1,
                "acknowledge_site_safety_policy": 1,
                "acknowledge_communication_policy": 1,
                "acknowledge_data_handling_policy": 1,
                "invited_on": None,
                "submitted_on": None,
                "completed_on": None,
            }
        )

        result = onboarding.sync_employee_onboarding_packet(doc)

        self.assertEqual(result["packet_status"], "Submitted")
        self.assertEqual(doc.first_name, "QA")
        self.assertEqual(doc.last_name, "Onboarding")
        self.assertEqual(doc.employee_name, "QA Onboarding")
        self.assertEqual(doc.personal_email, "qa.personal@example.com")
        self.assertEqual(doc.packet_status, "Submitted")
        self.assertEqual(doc.invited_on, "2026-03-24")
        self.assertEqual(doc.submitted_on, "2026-03-24 14:00:00")
        mock_set_value.assert_any_call(
            "Employee",
            "HR-EMP-TEST-0001",
            {
                "first_name": "QA",
                "last_name": "Onboarding",
                "personal_email": "qa.personal@example.com",
                "prefered_contact_email": "Personal Email",
                "cell_number": "5125551000",
                "current_address": "123 Main St\nAustin, TX 78701",
                "person_to_be_contacted": "Casey Contact",
                "emergency_phone_number": "5125552000",
                "relation": "Sibling",
                "user_id": "qa.onboarding@example.com",
                "date_of_joining": "2026-04-01",
                "custom_onboarding_packet": "EOP-TEST-0001",
            },
            update_modified=False,
        )
        mock_set_value.assert_any_call(
            "User",
            "qa.onboarding@example.com",
            {
                "first_name": "QA",
                "last_name": "Onboarding",
                "phone": "5125551000",
                "mobile_no": "5125551000",
            },
            update_modified=False,
        )
        mock_set_value.assert_any_call(
            "Employee Onboarding Request",
            "REQ-TEST-0001",
            {
                "request_status": "Submitted",
                "employee": "HR-EMP-TEST-0001",
                "user": "qa.onboarding@example.com",
                "error_message": "",
            },
            update_modified=False,
        )

    def test_sync_employee_onboarding_packet_blocks_owner_edit_after_complete(self):
        doc = FakeDoc(
            {
                "name": "EOP-TEST-0002",
                "user_id": "manager@example.com",
                "packet_status": "Complete",
            }
        )

        with self.assertRaisesRegex(Exception, "already complete"):
            onboarding.sync_employee_onboarding_packet(doc)


if __name__ == "__main__":
    unittest.main()
