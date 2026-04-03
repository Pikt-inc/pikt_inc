from __future__ import annotations

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
        db=types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            get_value=lambda *args, **kwargs: None,
            set_value=lambda *args, **kwargs: None,
        ),
        get_all=lambda *args, **kwargs: [],
        delete_doc=lambda *args, **kwargs: None,
        session=types.SimpleNamespace(user="Guest"),
        local=types.SimpleNamespace(response={}, request=types.SimpleNamespace(get_json=lambda silent=True: None)),
        request=types.SimpleNamespace(data=None),
        form_dict={},
        throw=lambda message, **_kwargs: (_ for _ in ()).throw(Exception(message)),
        whitelist=lambda **_kwargs: (lambda fn: fn),
    )
    sys.modules["frappe"] = fake_frappe

try:
    admin_api = import_module("pikt_inc.api.admin_portal")
    admin_service = import_module("pikt_inc.services.admin_portal")
except ModuleNotFoundError:
    admin_api = import_module("pikt_inc.pikt_inc.api.admin_portal")
    admin_service = import_module("pikt_inc.pikt_inc.services.admin_portal")


def fake_get_all_factory(dataset):
    def fake_get_all(doctype, filters=None, fields=None, order_by=None, limit=None, **_kwargs):
        rows = [dict(row) for row in dataset.get(f"{doctype}_list", [])]
        filters_value = filters or {}

        def matches_operator(actual, operator, expected):
            if operator in {"=", "=="}:
                return actual == expected
            if operator == "!=":
                return actual != expected
            if operator == "in":
                return actual in {item for item in expected or []}
            raise AssertionError(f"Unsupported filter operator in test harness: {operator}")

        def matches(row):
            if isinstance(filters_value, list):
                for clause in filters_value:
                    if len(clause) != 3:
                        raise AssertionError(f"Unsupported filter clause in test harness: {clause}")
                    field, operator, expected = clause
                    if not matches_operator(row.get(field), str(operator), expected):
                        return False
                return True

            for key, value in filters_value.items():
                if isinstance(value, list) and value:
                    operator = str(value[0])
                    expected = value[1] if len(value) > 1 else None
                    if not matches_operator(row.get(key), operator, expected):
                        return False
                    continue
                if row.get(key) != value:
                    return False
            return True

        filtered = [row for row in rows if matches(row)]
        if limit is not None:
            filtered = filtered[: int(limit)]
        if fields:
            return [{field: row.get(field) for field in fields} for row in filtered]
        return filtered

    return fake_get_all


class TestAdminPortalBuildingDeletion(unittest.TestCase):
    def setUp(self):
        self.deleted_docs = []
        self.set_value_calls = []
        self.dataset = {
            "Building": {
                "BUILD-1": {
                    "name": "BUILD-1",
                    "current_checklist_template": "CHK-TPL-PRIMARY",
                }
            },
            "Opportunity_list": [
                {"name": "OPP-1", "custom_building": "BUILD-1"},
            ],
            "Quotation_list": [
                {"name": "QTN-1", "custom_building": "BUILD-1"},
            ],
            "Sales Order_list": [
                {"name": "SO-1", "custom_building": "BUILD-1"},
            ],
            "Sales Invoice_list": [
                {"name": "SI-1", "custom_building": "BUILD-1"},
            ],
            "Service Agreement Addendum_list": [
                {"name": "SAA-1", "building": "BUILD-1"},
            ],
            "Checklist Session_list": [
                {"name": "CS-1", "building": "BUILD-1"},
                {"name": "CS-2", "building": "BUILD-1"},
                {"name": "CS-OTHER", "building": "OTHER"},
            ],
            "Checklist Template_list": [
                {"name": "CHK-TPL-PRIMARY", "building": "BUILD-1"},
                {"name": "CHK-TPL-LEGACY", "building": "BUILD-1"},
            ],
            "Building SOP_list": [
                {"name": "BSOP-1", "building": "BUILD-1"},
            ],
            "Site Shift Requirement_list": [
                {
                    "name": "SSR-1",
                    "building": "BUILD-1",
                    "custom_building_sop": "BSOP-1",
                    "call_out_record": "CO-1",
                },
                {
                    "name": "SSR-2",
                    "building": "BUILD-1",
                    "custom_building_sop": "",
                    "call_out_record": "CO-2",
                },
            ],
            "Dispatch Recommendation_list": [
                {"name": "REC-1", "site_shift_requirement": "SSR-1"},
                {"name": "REC-2", "site_shift_requirement": "SSR-2"},
            ],
            "Call Out_list": [
                {"name": "CO-1", "building": "BUILD-1"},
                {"name": "CO-2", "building": "BUILD-1"},
            ],
            "Recurring Service Rule_list": [
                {"name": "RSR-1", "building": "BUILD-1"},
            ],
            "File_list": [
                {"name": "FILE-1", "attached_to_doctype": "Checklist Session", "attached_to_name": "CS-1"},
                {"name": "FILE-2", "attached_to_doctype": "Checklist Session", "attached_to_name": "CS-2"},
                {"name": "FILE-OTHER", "attached_to_doctype": "Checklist Session", "attached_to_name": "CS-OTHER"},
            ],
        }

        known_names = {}
        for key, value in self.dataset.items():
            if key.endswith("_list"):
                doctype = key[: -len("_list")]
                known_names.setdefault(doctype, set()).update(row.get("name") for row in value if row.get("name"))
            elif isinstance(value, dict):
                known_names.setdefault(key, set()).update(value.keys())
        self.known_names = known_names

        admin_service.frappe.get_all = fake_get_all_factory(self.dataset)
        admin_service.frappe.db.exists = lambda doctype, name: clean_name(name) in self.known_names.get(doctype, set())
        admin_service.frappe.db.get_value = self._fake_get_value
        admin_service.frappe.db.set_value = self._record_set_value
        admin_service.frappe.delete_doc = self._record_delete_doc

    def _fake_get_value(self, doctype, name, fieldname, as_dict=False):
        if doctype == "Building" and fieldname == "current_checklist_template":
            return self.dataset["Building"].get(name, {}).get("current_checklist_template")
        return None

    def _record_set_value(self, doctype, name, fieldname, value, update_modified=False):
        self.set_value_calls.append((doctype, name, fieldname, value, update_modified))

    def _record_delete_doc(self, doctype, name, **kwargs):
        self.deleted_docs.append((doctype, name, kwargs))

    def test_delete_building_requires_admin_access(self):
        with patch.object(
            admin_service,
            "require_portal_section",
            side_effect=admin_api.CustomerPortalAccessError("This account does not have portal access to that section."),
        ):
            with self.assertRaisesRegex(Exception, "portal access to that section"):
                admin_service.delete_admin_building("BUILD-1")

    def test_delete_building_raises_not_found_for_missing_building(self):
        with patch.object(admin_service, "require_portal_section", return_value=SimpleNamespace()):
            with self.assertRaisesRegex(admin_service.CustomerPortalNotFoundError, "could not be found"):
                admin_service.delete_admin_building("BUILD-MISSING")

    def test_delete_building_unlinks_reference_docs_and_purges_owned_records(self):
        with patch.object(admin_service, "require_portal_section", return_value=SimpleNamespace()):
            result = admin_service.delete_admin_building("BUILD-1")

        self.assertEqual(result.building_id, "BUILD-1")
        self.assertEqual(result.redirect_to, "/portal/admin")

        deleted_pairs = [(doctype, name) for doctype, name, _kwargs in self.deleted_docs]
        self.assertEqual(
            deleted_pairs,
            [
                ("File", "FILE-1"),
                ("File", "FILE-2"),
                ("Checklist Session", "CS-1"),
                ("Checklist Session", "CS-2"),
                ("Checklist Template", "CHK-TPL-PRIMARY"),
                ("Checklist Template", "CHK-TPL-LEGACY"),
                ("Building SOP", "BSOP-1"),
                ("Dispatch Recommendation", "REC-1"),
                ("Dispatch Recommendation", "REC-2"),
                ("Call Out", "CO-1"),
                ("Call Out", "CO-2"),
                ("Site Shift Requirement", "SSR-1"),
                ("Site Shift Requirement", "SSR-2"),
                ("Recurring Service Rule", "RSR-1"),
                ("Building", "BUILD-1"),
            ],
        )
        self.assertFalse(any(doctype in {"Opportunity", "Quotation", "Sales Order", "Sales Invoice"} for doctype, _name in deleted_pairs))
        self.assertNotIn(("File", "FILE-OTHER"), deleted_pairs)

        for _doctype, _name, kwargs in self.deleted_docs:
            self.assertEqual(kwargs, {"ignore_permissions": True, "force": True})

        self.assertIn(("Building", "BUILD-1", "current_checklist_template", "", False), self.set_value_calls)
        self.assertIn(("Opportunity", "OPP-1", "custom_building", "", False), self.set_value_calls)
        self.assertIn(("Quotation", "QTN-1", "custom_building", "", False), self.set_value_calls)
        self.assertIn(("Sales Order", "SO-1", "custom_building", "", False), self.set_value_calls)
        self.assertIn(("Sales Invoice", "SI-1", "custom_building", "", False), self.set_value_calls)
        self.assertIn(("Service Agreement Addendum", "SAA-1", "building", "", False), self.set_value_calls)
        self.assertIn(("Site Shift Requirement", "SSR-1", "custom_building_sop", "", False), self.set_value_calls)
        self.assertIn(("Site Shift Requirement", "SSR-1", "call_out_record", "", False), self.set_value_calls)
        self.assertIn(("Site Shift Requirement", "SSR-2", "custom_building_sop", "", False), self.set_value_calls)
        self.assertIn(("Site Shift Requirement", "SSR-2", "call_out_record", "", False), self.set_value_calls)

    def test_api_wrapper_validates_and_returns_delete_payload(self):
        expected = admin_service.AdminBuildingDeleteResult(building_id="BUILD-1")
        with patch.object(admin_api.admin_portal_service, "delete_admin_building", return_value=expected) as delete_admin_building:
            result = admin_api.delete_admin_building(building="BUILD-1")

        self.assertEqual(result, {"building_id": "BUILD-1", "redirect_to": "/portal/admin"})
        self.assertEqual(delete_admin_building.call_args.args, ("BUILD-1",))

        with self.assertRaisesRegex(Exception, "Building is required"):
            admin_api.delete_admin_building()


def clean_name(value):
    return str(value or "").strip()


if __name__ == "__main__":
    unittest.main()
