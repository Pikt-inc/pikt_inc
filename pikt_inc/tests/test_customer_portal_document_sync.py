from __future__ import annotations

import unittest
from types import SimpleNamespace

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

import frappe

from pikt_inc import migrate
from pikt_inc.permissions import customer_portal as portal_permissions


class TestCustomerPortalDocumentSync(unittest.TestCase):
    def test_building_custom_docperm_includes_portal_write_access(self):
        row = next(row for row in migrate._BUILDING_CUSTOM_DOCPERMS if row["role"] == "Customer Portal User")

        self.assertEqual(row["select"], 1)
        self.assertEqual(row["read"], 1)
        self.assertEqual(row["write"], 1)
        self.assertEqual(row["create"], 0)
        self.assertEqual(row["delete"], 0)

    def test_agreement_and_checklist_docperms_are_read_only_for_portal_users(self):
        for rows in (
            migrate._SERVICE_AGREEMENT_CUSTOM_DOCPERMS,
            migrate._SERVICE_AGREEMENT_ADDENDUM_CUSTOM_DOCPERMS,
            migrate._BUILDING_SOP_CUSTOM_DOCPERMS,
        ):
            with self.subTest(rows=rows):
                row = next(row for row in rows if row["role"] == "Customer Portal User")
                self.assertEqual(row["select"], 1)
                self.assertEqual(row["read"], 1)
                self.assertEqual(row["write"], 0)
                self.assertEqual(row["create"], 0)
                self.assertEqual(row["delete"], 0)

    def test_customer_portal_doctype_metadata_sync_updates_expected_doctypes(self):
        set_value_calls = []
        clear_cache_calls = []

        frappe.db.exists = lambda doctype, name=None: doctype == "DocType"
        frappe.db.get_value = lambda doctype, name, fields, as_dict=False: {}
        frappe.db.set_value = (
            lambda doctype, name, values, update_modified=False: set_value_calls.append(
                (doctype, name, values, update_modified)
            )
        )
        frappe.clear_cache = lambda **kwargs: clear_cache_calls.append(kwargs)

        migrate.ensure_customer_portal_doctype_metadata()

        self.assertEqual(
            {name for _doctype, name, _values, _update_modified in set_value_calls},
            {"Building", "Building SOP", "Service Agreement", "Service Agreement Addendum"},
        )
        self.assertEqual(
            {kwargs["doctype"] for kwargs in clear_cache_calls},
            {"Building", "Building SOP", "Service Agreement", "Service Agreement Addendum"},
        )

    def test_portal_settings_menu_reference_cleanup_drops_missing_doctypes(self):
        saved = []
        cleared = []

        class MenuRow:
            def __init__(self, title, reference_doctype=""):
                self.title = title
                self.reference_doctype = reference_doctype

        class FakePortalSettings:
            def __init__(self):
                self.menu = [MenuRow("Projects", "Project"), MenuRow("Newsletter", "Newsletter")]
                self.custom_menu = [MenuRow("Buildings", "Building")]

            def set(self, fieldname, value):
                setattr(self, fieldname, value)

            def save(self, ignore_permissions=False):
                saved.append(ignore_permissions)

        fake_doc = FakePortalSettings()

        def fake_exists(doctype, name=None):
            return (doctype, name) in {
                ("DocType", "Portal Settings"),
                ("DocType", "Project"),
                ("DocType", "Building"),
            }

        frappe.db.exists = fake_exists
        frappe.get_doc = lambda doctype, name=None: fake_doc if doctype == "Portal Settings" else None
        frappe.clear_cache = lambda *args, **kwargs: cleared.append((args, kwargs))

        migrate.ensure_portal_settings_menu_references()

        self.assertEqual([row.title for row in fake_doc.menu], ["Projects"])
        self.assertEqual([row.title for row in fake_doc.custom_menu], ["Buildings"])
        self.assertEqual(saved, [True])
        self.assertEqual(len(cleared), 1)


class TestCustomerPortalPermissionHooks(unittest.TestCase):
    def setUp(self):
        self._original_get_portal_contact_links = portal_permissions._get_portal_contact_links
        portal_permissions._get_portal_contact_links = lambda user: [{"customer_name": "CUST-1"}]
        frappe.session.user = "portal@example.com"
        frappe.get_roles = lambda user=None: ["Customer Portal User"]
        frappe.db.get_value = lambda doctype, name, field: "CUST-1"

    def tearDown(self):
        portal_permissions._get_portal_contact_links = self._original_get_portal_contact_links

    def test_query_conditions_scope_portal_user_to_linked_customer(self):
        condition = portal_permissions.get_building_permission_query_conditions("portal@example.com")

        self.assertEqual(condition, "`tabBuilding`.`customer` = 'CUST-1'")

    def test_query_conditions_fail_closed_without_customer_link(self):
        portal_permissions._get_portal_contact_links = lambda user: []

        condition = portal_permissions.get_service_agreement_permission_query_conditions("portal@example.com")

        self.assertEqual(condition, "1=0")

    def test_has_permission_allows_matching_customer_documents(self):
        doc = {"name": "BLDG-0001", "customer": "CUST-1"}

        self.assertTrue(portal_permissions.has_building_permission(doc, "portal@example.com", "read"))

    def test_has_permission_denies_other_customer_documents(self):
        doc = SimpleNamespace(name="SAA-0001", customer="CUST-2")

        self.assertFalse(
            portal_permissions.has_service_agreement_addendum_permission(doc, "portal@example.com", "read")
        )

    def test_has_permission_defers_for_non_portal_users(self):
        frappe.get_roles = lambda user=None: ["System Manager"]

        result = portal_permissions.has_service_agreement_permission(
            {"name": "SA-0001", "customer": "CUST-1"},
            "admin@example.com",
            "read",
        )

        self.assertIsNone(result)
