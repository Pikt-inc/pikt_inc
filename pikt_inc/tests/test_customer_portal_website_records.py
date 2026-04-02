from __future__ import annotations

import sys
import types
import unittest
from types import SimpleNamespace

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

import frappe

from pikt_inc.permissions import customer_portal as portal_permissions
from pikt_inc.services.customer_portal import website_records


class TestCustomerPortalWebsiteRecordPages(unittest.TestCase):
    def setUp(self):
        self._original_portal_module = sys.modules.get("frappe.www.portal")
        self._original_portal_package = sys.modules.get("frappe.www")
        self._original_has_service_agreement_permission = portal_permissions.has_service_agreement_permission
        self._original_has_service_agreement_addendum_permission = (
            portal_permissions.has_service_agreement_addendum_permission
        )
        self._original_has_building_permission = portal_permissions.has_building_permission

    def tearDown(self):
        if self._original_portal_module is None:
            sys.modules.pop("frappe.www.portal", None)
        else:
            sys.modules["frappe.www.portal"] = self._original_portal_module

        if self._original_portal_package is None:
            sys.modules.pop("frappe.www", None)
        else:
            sys.modules["frappe.www"] = self._original_portal_package

        portal_permissions.has_service_agreement_permission = self._original_has_service_agreement_permission
        portal_permissions.has_service_agreement_addendum_permission = (
            self._original_has_service_agreement_addendum_permission
        )
        portal_permissions.has_building_permission = self._original_has_building_permission

    def install_fake_portal_module(self):
        portal_module = types.ModuleType("frappe.www.portal")

        def fake_get_context(context, **kwargs):
            context.doctype = kwargs.get("doctype")
            context.show_sidebar = True
            return context

        portal_module.get_context = fake_get_context
        portal_package = types.ModuleType("frappe.www")
        portal_package.portal = portal_module
        sys.modules["frappe.www"] = portal_package
        sys.modules["frappe.www.portal"] = portal_module

    def test_build_portal_list_context_uses_stock_portal_list_shell(self):
        self.install_fake_portal_module()
        context = SimpleNamespace()

        result = website_records.build_portal_list_context(context, "agreements")

        self.assertIs(result, context)
        self.assertEqual(context.doctype, "Service Agreement")
        self.assertEqual(context.title, "Master Service Agreements")
        self.assertEqual(context.list_template, "templates/includes/list/list.html")
        self.assertEqual(context.row_template, "templates/includes/list/row_template.html")
        self.assertEqual(context.no_breadcrumbs, 1)
        self.assertEqual(context.home_page, "/orders")

    def test_build_portal_detail_context_builds_agreement_snapshot_view(self):
        frappe.session.user = "portal@example.com"
        portal_permissions.has_service_agreement_permission = lambda doc, user=None, permission_type=None: True
        frappe.get_doc = lambda doctype, name: SimpleNamespace(
            name=name,
            agreement_name="Master Agreement",
            customer="CUST-1",
            status="Signed",
            template="Standard",
            template_version="v3",
            signed_by_name="QA Portal",
            signed_by_title="Owner",
            signed_by_email="portal@example.com",
            signed_on="2026-03-30",
            rendered_html_snapshot="<h1>Agreement</h1>",
        )
        context = SimpleNamespace()

        result = website_records.build_portal_detail_context(context, "agreements", "SA-0001")

        self.assertIs(result, context)
        self.assertEqual(context.page_title, "Master Agreement")
        self.assertEqual(context.record_name, "SA-0001")
        self.assertEqual(context.snapshot_download_url, "/api/method/pikt_inc.api.customer_portal.download_customer_portal_agreement_snapshot?agreement=SA-0001")
        self.assertEqual(context.back_to_url, "/agreements")
        self.assertIn({"label": "Business Agreements", "url": "/business-agreements"}, context.related_links)
        self.assertEqual(context.summary_items[0]["label"], "Customer")

    def test_build_portal_detail_context_rejects_guest_access(self):
        frappe.session.user = "Guest"
        portal_permissions.has_building_permission = lambda doc, user=None, permission_type=None: None
        frappe.get_doc = lambda doctype, name: SimpleNamespace(name=name, building_name="North Campus")

        with self.assertRaises(Exception) as exc:
            website_records.build_portal_detail_context(SimpleNamespace(), "buildings", "BLDG-0001")

        self.assertEqual(str(exc.exception), "Login to view")

    def test_build_portal_detail_context_denies_portal_user_without_matching_customer(self):
        frappe.session.user = "portal@example.com"
        portal_permissions.has_service_agreement_addendum_permission = (
            lambda doc, user=None, permission_type=None: False
        )
        frappe.get_doc = lambda doctype, name: SimpleNamespace(name=name, addendum_name="Addendum A")

        with self.assertRaises(Exception) as exc:
            website_records.build_portal_detail_context(SimpleNamespace(), "business_agreements", "SAA-0001")

        self.assertEqual(str(exc.exception), "Not permitted")

    def test_building_summary_accepts_yes_no_flags_from_live_records(self):
        summary = website_records._build_building_summary(
            {
                "active": 1,
                "customer": "CUST-1",
                "primary_site_contact": "Jane Doe",
                "site_supervisor_name": "John Smith",
                "site_supervisor_phone": "512-555-0100",
                "access_method": "Lockbox",
                "allowed_entry_time": "After 8:00 PM",
                "has_alarm_system": "No",
                "access_details_confirmed": "Yes",
            }
        )

        values_by_label = {row["label"]: row["value"] for row in summary}
        self.assertEqual(values_by_label["Status"], "Active")
        self.assertEqual(values_by_label["Alarm System"], "No")
        self.assertEqual(values_by_label["Access Confirmed"], "Yes")
