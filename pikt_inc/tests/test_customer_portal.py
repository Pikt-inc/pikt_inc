from __future__ import annotations

import importlib
import json
from datetime import datetime
from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch
import types


APP_ROOT = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

if "frappe" not in sys.modules:
    fake_frappe = types.ModuleType("frappe")
    fake_utils = types.ModuleType("frappe.utils")
    fake_utils.get_url = lambda path="": f"https://example.test{path}"
    fake_utils.now_datetime = lambda: datetime(2026, 3, 25, 12, 0, 0)
    fake_utils.get_datetime = lambda value: value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    fake_utils.getdate = lambda value: value.date() if hasattr(value, "date") else value
    fake_utils.nowdate = lambda: "2026-03-25"
    fake_utils.add_to_date = lambda value, **_kwargs: value
    fake_frappe.db = types.SimpleNamespace(
        sql=lambda *args, **kwargs: [],
        get_value=lambda *args, **kwargs: None,
        exists=lambda *args, **kwargs: False,
    )
    fake_frappe.get_all = lambda *args, **kwargs: []
    fake_frappe.get_doc = lambda *args, **kwargs: None
    fake_frappe.get_print = lambda *args, **kwargs: "<html></html>"
    fake_frappe.get_roles = lambda _user=None: []
    fake_frappe.local = types.SimpleNamespace(
        response={},
        request=types.SimpleNamespace(get_json=lambda silent=True: None),
    )
    fake_frappe.request = types.SimpleNamespace(data=None)
    fake_frappe.form_dict = {}
    fake_frappe.session = types.SimpleNamespace(user="Guest")
    fake_frappe.throw = lambda message, **_kwargs: (_ for _ in ()).throw(Exception(message))
    fake_frappe.whitelist = lambda **_kwargs: (lambda fn: fn)
    fake_frappe.utils = fake_utils
    sys.modules["frappe"] = fake_frappe
    sys.modules["frappe.utils"] = fake_utils
    sys.modules["frappe.utils.pdf"] = types.SimpleNamespace(get_pdf=lambda html: html.encode("utf-8"))


try:
    app_hooks = importlib.import_module("pikt_inc.hooks")
    portal = importlib.import_module("pikt_inc.services.customer_portal")
    portal_api = importlib.import_module("pikt_inc.api.customer_portal")
except ModuleNotFoundError:
    app_hooks = importlib.import_module("pikt_inc.pikt_inc.hooks")
    portal = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal")
    portal_api = importlib.import_module("pikt_inc.pikt_inc.api.customer_portal")


PORTAL_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "customer_portal_builder_page.json"
PORTAL_COMPONENT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "customer_portal_builder_component.json"
PATCHES_PATH = Path(__file__).resolve().parents[1] / "patches.txt"


class FakeDB:
    def __init__(self, dataset):
        self.dataset = dataset

    def sql(self, _query, params=None, as_dict=False):
        session_user = (params or [""])[0]
        return [dict(row) for row in self.dataset.get("contact_links", []) if row.get("session_user") == session_user]

    def get_value(self, doctype, name, fields, as_dict=False):
        source = self.dataset.get(doctype, {})
        row = source.get(name)
        if row is None:
            return None
        if isinstance(fields, list):
            result = {field: row.get(field) for field in fields}
            return result if as_dict else result
        return row.get(fields)

    def exists(self, doctype, name):
        return name in self.dataset.get(doctype, {})


def fake_get_all_factory(dataset):
    def fake_get_all(doctype, filters=None, fields=None, order_by=None, **_kwargs):
        rows = [dict(row) for row in dataset.get(doctype, [])]
        filters = filters or {}

        def matches(row):
            for key, value in filters.items():
                if isinstance(value, list) and value and value[0] == "!=":
                    if row.get(key) == value[1]:
                        return False
                    continue
                if row.get(key) != value:
                    return False
            return True

        filtered = [row for row in rows if matches(row)]
        if order_by:
            clauses = [clause.strip() for clause in order_by.split(",")]
            for clause in reversed(clauses):
                parts = clause.split()
                field = parts[0]
                direction = parts[1].lower() if len(parts) > 1 else "asc"
                filtered.sort(key=lambda row: str(row.get(field) or ""), reverse=(direction == "desc"))
        if fields:
            return [{field: row.get(field) for field in fields} for row in filtered]
        return filtered

    return fake_get_all


class TestCustomerPortal(TestCase):
    def setUp(self):
        self.dataset = {
            "contact_links": [
                {
                    "session_user": "portal@example.com",
                    "contact_name": "CONTACT-1",
                    "first_name": "Pat",
                    "last_name": "Portal",
                    "email_id": "portal@example.com",
                    "phone": "512-555-0101",
                    "mobile_no": "",
                    "designation": "Office Manager",
                    "address_name": "ADDR-PORTAL",
                    "is_primary_contact": 1,
                    "is_billing_contact": 0,
                    "customer_name": "CUST-1",
                }
            ],
            "Customer": {
                "CUST-1": {
                    "name": "CUST-1",
                    "customer_name": "Portal Customer LLC",
                    "customer_primary_contact": "CONTACT-BILLING",
                    "customer_primary_address": "ADDR-1",
                    "tax_id": "99-1234567",
                }
            },
            "Contact": {
                "CONTACT-1": {
                    "name": "CONTACT-1",
                    "first_name": "Pat",
                    "last_name": "Portal",
                    "email_id": "portal@example.com",
                    "phone": "512-555-0101",
                    "mobile_no": "",
                    "designation": "Office Manager",
                    "address": "ADDR-PORTAL",
                },
                "CONTACT-BILLING": {
                    "name": "CONTACT-BILLING",
                    "first_name": "Bill",
                    "last_name": "Payable",
                    "email_id": "billing@example.com",
                    "phone": "512-555-0133",
                    "mobile_no": "",
                    "designation": "Accounts Payable",
                    "address": "ADDR-1",
                },
            },
            "Address": {
                "ADDR-1": {
                    "name": "ADDR-1",
                    "address_line1": "123 Market St",
                    "address_line2": "Suite 300",
                    "city": "Austin",
                    "state": "TX",
                    "pincode": "78701",
                    "country": "United States",
                },
                "ADDR-PORTAL": {
                    "name": "ADDR-PORTAL",
                    "address_line1": "123 Market St",
                    "address_line2": "",
                    "city": "Austin",
                    "state": "TX",
                    "pincode": "78701",
                    "country": "United States",
                },
            },
            "Sales Invoice": {
                "SINV-0001": {"name": "SINV-0001", "customer": "CUST-1", "docstatus": 1},
                "SINV-OTHER": {"name": "SINV-OTHER", "customer": "CUST-2", "docstatus": 1},
            },
            "Building": {
                "BUILD-1": {"name": "BUILD-1", "customer": "CUST-1", "access_details_completed_on": None},
                "BUILD-OTHER": {"name": "BUILD-OTHER", "customer": "CUST-2", "access_details_completed_on": None},
            },
            "Service Agreement": [
                {
                    "name": "SAG-1",
                    "customer": "CUST-1",
                    "agreement_name": "Portal Customer Master Agreement",
                    "status": "Active",
                    "template": "Master Template",
                    "template_version": "1.0",
                    "signed_by_name": "Pat Portal",
                    "signed_by_title": "Office Manager",
                    "signed_by_email": "portal@example.com",
                    "signed_on": datetime(2026, 3, 1, 9, 0, 0),
                    "rendered_html_snapshot": "<p>Master agreement</p>",
                    "modified": datetime(2026, 3, 1, 9, 0, 0),
                }
            ],
            "Service Agreement Addendum": [
                {
                    "name": "ADD-1",
                    "customer": "CUST-1",
                    "addendum_name": "Portal Addendum",
                    "service_agreement": "SAG-1",
                    "quotation": "QTN-1",
                    "sales_order": "SO-1",
                    "initial_invoice": "SINV-0001",
                    "building": "BUILD-1",
                    "status": "Active",
                    "term_model": "Month-to-month",
                    "fixed_term_months": "",
                    "start_date": datetime(2026, 3, 2, 0, 0, 0),
                    "end_date": None,
                    "template": "Addendum Template",
                    "template_version": "1.0",
                    "signed_by_name": "Pat Portal",
                    "signed_by_title": "Office Manager",
                    "signed_by_email": "portal@example.com",
                    "signed_on": datetime(2026, 3, 2, 9, 0, 0),
                    "billing_completed_on": datetime(2026, 3, 3, 9, 0, 0),
                    "access_completed_on": datetime(2026, 3, 4, 9, 0, 0),
                    "rendered_html_snapshot": "<p>Addendum</p>",
                    "modified": datetime(2026, 3, 4, 9, 0, 0),
                }
            ],
            "Sales Invoice_list": [
                {
                    "name": "SINV-0001",
                    "customer": "CUST-1",
                    "posting_date": datetime(2026, 3, 5, 0, 0, 0),
                    "due_date": datetime(2026, 3, 20, 0, 0, 0),
                    "status": "Unpaid",
                    "currency": "USD",
                    "grand_total": 425.0,
                    "outstanding_amount": 125.0,
                    "docstatus": 1,
                    "customer_name": "Portal Customer LLC",
                    "custom_building": "BUILD-1",
                    "custom_service_agreement": "SAG-1",
                    "custom_service_agreement_addendum": "ADD-1",
                    "modified": datetime(2026, 3, 5, 12, 0, 0),
                }
            ],
            "Building_list": [
                {
                    "name": "BUILD-1",
                    "customer": "CUST-1",
                    "building_name": "Headquarters",
                    "active": 1,
                    "address_line_1": "123 Market St",
                    "address_line_2": "Suite 300",
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": "78701",
                    "site_supervisor_name": "Jordan Lead",
                    "site_supervisor_phone": "512-555-0199",
                    "site_notes": "Front entrance only.",
                    "access_notes": "Badge after 6pm.",
                    "alarm_notes": "Call before arming.",
                    "access_method": "Door code / keypad",
                    "access_entrance": "Main lobby",
                    "access_entry_details": "Use code 1234.",
                    "has_alarm_system": "Yes",
                    "alarm_instructions": "Disarm panel on left.",
                    "allowed_entry_time": "6:00 PM - 11:00 PM",
                    "primary_site_contact": "Jordan Lead",
                    "lockout_emergency_contact": "512-555-0166",
                    "key_fob_handoff_details": "Stored at security desk.",
                    "areas_to_avoid": "Executive suite.",
                    "closing_instructions": "Reset lobby lights.",
                    "parking_elevator_notes": "Garage level 2.",
                    "first_service_notes": "Expect badge handoff at start.",
                    "access_details_confirmed": 1,
                    "access_details_completed_on": datetime(2026, 3, 4, 9, 0, 0),
                    "custom_service_agreement": "SAG-1",
                    "custom_service_agreement_addendum": "ADD-1",
                    "modified": datetime(2026, 3, 6, 12, 0, 0),
                }
            ],
        }

        portal.frappe.db = FakeDB(self.dataset)
        portal.frappe.get_all = fake_get_all_factory(
            {
                "Service Agreement": self.dataset["Service Agreement"],
                "Service Agreement Addendum": self.dataset["Service Agreement Addendum"],
                "Sales Invoice": self.dataset["Sales Invoice_list"],
                "Building": self.dataset["Building_list"],
            }
        )
        portal.frappe.session.user = "portal@example.com"
        portal.frappe.local.response = {}
        portal.frappe.utils.get_url = lambda path="": f"https://example.test{path}"
        portal.frappe.utils.get_datetime = lambda value: value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        portal.now_datetime = lambda: datetime(2026, 3, 25, 12, 0, 0)

    def test_dashboard_data_is_scoped_to_customer(self):
        with patch.object(portal.public_quote_service, "find_contact_for_customer", return_value="CONTACT-BILLING"), patch.object(
            portal.public_quote_service, "find_address_for_customer", return_value="ADDR-1"
        ):
            data = portal.get_customer_portal_dashboard_data()

        self.assertFalse(data["access_denied"])
        self.assertEqual(data["customer_display"], "Portal Customer LLC")
        self.assertEqual(data["summary_cards"][1]["value"], "1")
        self.assertEqual(data["latest_invoices"][0]["download_url"], "/api/method/pikt_inc.api.customer_portal.download_customer_portal_invoice?invoice=SINV-0001")
        self.assertEqual(data["active_master"]["title"], "Portal Customer Master Agreement")
        self.assertEqual(data["latest_locations"][0]["title"], "Headquarters")

    def test_ambiguous_scope_returns_branded_error_page(self):
        self.dataset["contact_links"].append(
            {
                "session_user": "portal@example.com",
                "contact_name": "CONTACT-2",
                "customer_name": "CUST-2",
            }
        )

        data = portal.get_customer_portal_billing_data()

        self.assertTrue(data["access_denied"])
        self.assertIn("multiple customers", data["error_message"])
        self.assertEqual(portal.frappe.local.response["http_status_code"], 403)

    def test_billing_update_uses_scoped_customer_helpers(self):
        scope = portal.PortalScope(
            session_user="portal@example.com",
            customer_name="CUST-1",
            customer_display="Portal Customer LLC",
            portal_contact_name="CONTACT-1",
            portal_contact_email="portal@example.com",
            portal_contact_phone="512-555-0101",
            portal_contact_designation="Office Manager",
            portal_address_name="ADDR-PORTAL",
            billing_contact_name="CONTACT-BILLING",
            billing_contact_email="billing@example.com",
            billing_contact_phone="512-555-0133",
            billing_contact_designation="Accounts Payable",
            billing_address_name="ADDR-1",
            tax_id="99-1234567",
        )

        with patch.object(portal, "_require_portal_scope", return_value=scope), patch.object(
            portal, "_portal_contact_payload", return_value={"display_name": "Pat Portal"}
        ), patch.object(portal.public_quote_service, "valid_email", return_value=True), patch.object(
            portal.public_quote_service, "ensure_address", return_value="ADDR-UPDATED"
        ) as ensure_address, patch.object(
            portal.public_quote_service, "ensure_contact", return_value="CONTACT-UPDATED"
        ) as ensure_contact, patch.object(
            portal.public_quote_service, "sync_customer"
        ) as sync_customer, patch.object(
            portal.public_quote_service, "doc_db_set_values"
        ) as doc_db_set_values, patch.object(
            portal, "get_customer_portal_billing_data", return_value={"page_key": "billing"}
        ):
            response = portal.update_customer_portal_billing(
                portal_contact_name="Pat Portal",
                portal_contact_phone="512-555-0111",
                portal_contact_title="Facilities Lead",
                billing_contact_name="Billing Team",
                billing_email="billing@example.com",
                billing_contact_phone="512-555-0222",
                billing_contact_title="Controller",
                billing_address_line_1="456 Billing Ave",
                billing_city="Austin",
                billing_state="TX",
                billing_postal_code="78702",
                billing_country="United States",
                tax_id="12-3456789",
            )

        ensure_address.assert_called_once()
        ensure_contact.assert_called_once_with("CUST-1", "Portal Customer LLC", "Billing Team", "billing@example.com")
        sync_customer.assert_called_once_with("CUST-1", "billing@example.com", "CONTACT-UPDATED", "ADDR-UPDATED", "12-3456789")
        self.assertGreaterEqual(doc_db_set_values.call_count, 2)
        self.assertEqual(response["status"], "updated")

    def test_location_update_rejects_out_of_scope_building(self):
        scope = portal.PortalScope(
            session_user="portal@example.com",
            customer_name="CUST-1",
            customer_display="Portal Customer LLC",
            portal_contact_name="CONTACT-1",
            portal_contact_email="portal@example.com",
            portal_contact_phone="512-555-0101",
            portal_contact_designation="Office Manager",
            portal_address_name="ADDR-PORTAL",
            billing_contact_name="CONTACT-BILLING",
            billing_contact_email="billing@example.com",
            billing_contact_phone="512-555-0133",
            billing_contact_designation="Accounts Payable",
            billing_address_name="ADDR-1",
            tax_id="99-1234567",
        )

        with patch.object(portal, "_require_portal_scope", return_value=scope):
            with self.assertRaisesRegex(Exception, "not available in this portal account"):
                portal.update_customer_portal_location(building_name="BUILD-OTHER", access_notes="Test note")

    def test_invoice_download_sets_download_response(self):
        scope = portal.PortalScope(
            session_user="portal@example.com",
            customer_name="CUST-1",
            customer_display="Portal Customer LLC",
            portal_contact_name="CONTACT-1",
            portal_contact_email="portal@example.com",
            portal_contact_phone="512-555-0101",
            portal_contact_designation="Office Manager",
            portal_address_name="ADDR-PORTAL",
            billing_contact_name="CONTACT-BILLING",
            billing_contact_email="billing@example.com",
            billing_contact_phone="512-555-0133",
            billing_contact_designation="Accounts Payable",
            billing_address_name="ADDR-1",
            tax_id="99-1234567",
        )

        portal.frappe.local.response = {}
        with patch.object(portal, "_require_portal_scope", return_value=scope), patch.object(
            portal, "render_invoice_pdf", return_value=b"PDF"
        ):
            portal.download_customer_portal_invoice("SINV-0001")

        self.assertEqual(portal.frappe.local.response["filename"], "SINV-0001.pdf")
        self.assertEqual(portal.frappe.local.response["type"], "download")
        self.assertEqual(portal.frappe.local.response["content_type"], "application/pdf")

    def test_hooks_include_customer_portal_home_and_patch(self):
        self.assertEqual(app_hooks.role_home_page["Customer Portal User"], "portal")
        builder_fixture = next(fixture for fixture in app_hooks.fixtures if fixture["dt"] == "Builder Page")
        routes = builder_fixture["filters"][0][2]
        self.assertIn("portal", routes)
        self.assertIn("portal/agreements", routes)
        self.assertIn("portal/billing", routes)
        self.assertIn("portal/locations", routes)
        component_fixture = next(fixture for fixture in app_hooks.fixtures if fixture["dt"] == "Builder Component")
        component_names = component_fixture["filters"][0][2]
        self.assertIn("Portal Shell Header", component_names)
        self.assertIn("Portal Summary Stat Card", component_names)
        self.assertIn("Portal Record List Card", component_names)
        self.assertIn("Portal Invoice Row Card", component_names)
        self.assertIn("Portal Agreement Preview Card", component_names)
        self.assertIn("Portal Location Edit Card", component_names)
        self.assertIn("Portal Empty State Block", component_names)
        patches = PATCHES_PATH.read_text(encoding="utf-8")
        self.assertIn("pikt_inc.patches.post_model_sync.ensure_customer_portal_role", patches)

    def test_portal_fixture_contains_authenticated_portal_pages(self):
        portal_pages = json.loads(PORTAL_FIXTURE_PATH.read_text(encoding="utf-8"))
        routes = {doc["route"] for doc in portal_pages}
        self.assertEqual(routes, {"portal", "portal/agreements", "portal/billing", "portal/locations"})
        self.assertTrue(all(doc["authenticated_access"] == 1 for doc in portal_pages))
        self.assertTrue(all(doc["disable_indexing"] == 1 for doc in portal_pages))
        self.assertEqual(
            {doc["page_data_script"] for doc in portal_pages},
            {
                'data.update(frappe.call("pikt_inc.api.customer_portal.get_customer_portal_dashboard_data"))',
                'data.update(frappe.call("pikt_inc.api.customer_portal.get_customer_portal_agreements_data"))',
                'data.update(frappe.call("pikt_inc.api.customer_portal.get_customer_portal_billing_data"))',
                'data.update(frappe.call("pikt_inc.api.customer_portal.get_customer_portal_locations_data"))',
            },
        )

    def test_portal_component_fixture_contains_expected_components(self):
        components = json.loads(PORTAL_COMPONENT_FIXTURE_PATH.read_text(encoding="utf-8"))
        names = {doc["component_name"] for doc in components}
        self.assertEqual(
            names,
            {
                "Portal Shell Header",
                "Portal Summary Stat Card",
                "Portal Record List Card",
                "Portal Invoice Row Card",
                "Portal Agreement Preview Card",
                "Portal Location Edit Card",
                "Portal Empty State Block",
            },
        )
        for component in components:
            self.assertIsInstance(json.loads(component["block"]), dict)

    def test_api_getters_proxy_to_service(self):
        with patch.object(portal_api.customer_portal_service, "get_customer_portal_dashboard_data", return_value={"page_key": "overview"}) as dashboard, patch.object(
            portal_api.customer_portal_service,
            "get_customer_portal_agreements_data",
            return_value={"page_key": "agreements"},
        ) as agreements, patch.object(
            portal_api.customer_portal_service,
            "get_customer_portal_billing_data",
            return_value={"page_key": "billing"},
        ) as billing, patch.object(
            portal_api.customer_portal_service,
            "get_customer_portal_locations_data",
            return_value={"page_key": "locations"},
        ) as locations:
            self.assertEqual(portal_api.get_customer_portal_dashboard_data(), {"page_key": "overview"})
            self.assertEqual(portal_api.get_customer_portal_agreements_data(), {"page_key": "agreements"})
            self.assertEqual(portal_api.get_customer_portal_billing_data(), {"page_key": "billing"})
            self.assertEqual(portal_api.get_customer_portal_locations_data(), {"page_key": "locations"})

        dashboard.assert_called_once_with()
        agreements.assert_called_once_with()
        billing.assert_called_once_with()
        locations.assert_called_once_with()
