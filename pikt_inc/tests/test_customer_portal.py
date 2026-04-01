from __future__ import annotations

import importlib
from datetime import datetime
from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch
import types

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()


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
    portal_contracts = importlib.import_module("pikt_inc.services.contracts.customer_portal")
    portal_payloads = importlib.import_module("pikt_inc.services.customer_portal.payloads")
    portal_page_helper = importlib.import_module("pikt_inc.www._portal_page")
    portal_www_index = importlib.import_module("pikt_inc.www.portal.index")
    portal_www_agreements = importlib.import_module("pikt_inc.www.portal.agreements")
    portal_www_billing = importlib.import_module("pikt_inc.www.portal.billing")
    portal_www_billing_info = importlib.import_module("pikt_inc.www.portal.billing_info")
    portal_www_locations = importlib.import_module("pikt_inc.www.portal.locations")
except ModuleNotFoundError:
    app_hooks = importlib.import_module("pikt_inc.pikt_inc.hooks")
    portal = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal")
    portal_api = importlib.import_module("pikt_inc.pikt_inc.api.customer_portal")
    portal_contracts = importlib.import_module("pikt_inc.pikt_inc.services.contracts.customer_portal")
    portal_payloads = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal.payloads")
    portal_page_helper = importlib.import_module("pikt_inc.pikt_inc.www._portal_page")
    portal_www_index = importlib.import_module("pikt_inc.pikt_inc.www.portal.index")
    portal_www_agreements = importlib.import_module("pikt_inc.pikt_inc.www.portal.agreements")
    portal_www_billing = importlib.import_module("pikt_inc.pikt_inc.www.portal.billing")
    portal_www_billing_info = importlib.import_module("pikt_inc.pikt_inc.www.portal.billing_info")
    portal_www_locations = importlib.import_module("pikt_inc.pikt_inc.www.portal.locations")


PATCHES_PATH = Path(__file__).resolve().parents[1] / "patches.txt"
PORTAL_MACROS_PATH = Path(__file__).resolve().parents[1] / "templates" / "includes" / "customer_portal_macros.html"
PORTAL_CSS_PATH = Path(__file__).resolve().parents[1] / "public" / "css" / "customer_portal.css"
PORTAL_FORMS_JS_PATH = Path(__file__).resolve().parents[1] / "public" / "js" / "customer_portal_forms.js"
PORTAL_OVERVIEW_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "portal" / "index.html"
PORTAL_AGREEMENTS_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "portal" / "agreements.html"
PORTAL_BILLING_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "portal" / "billing.html"
PORTAL_BILLING_INFO_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "portal" / "billing-info.html"
PORTAL_LOCATIONS_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "portal" / "locations.html"


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
                "BUILD-1": {"name": "BUILD-1", "customer": "CUST-1", "access_details_completed_on": None, "current_sop": "BSOP-1"},
                "BUILD-OTHER": {"name": "BUILD-OTHER", "customer": "CUST-2", "access_details_completed_on": None},
            },
            "Building SOP": {
                "BSOP-1": {
                    "name": "BSOP-1",
                    "building": "BUILD-1",
                    "customer": "CUST-1",
                    "version_number": 2,
                    "supersedes": "BSOP-0",
                    "modified": datetime(2026, 3, 7, 8, 30, 0),
                    "owner": "ops@example.com",
                }
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
                    "current_sop": "BSOP-1",
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
            "Building SOP Item_list": [
                {
                    "name": "BSOP-ITEM-1",
                    "parent": "BSOP-1",
                    "parenttype": "Building SOP",
                    "parentfield": "items",
                    "idx": 1,
                    "sop_item_id": "restrooms",
                    "item_title": "Restrooms sanitized",
                    "item_description": "Disinfect all restroom touchpoints and restock consumables.",
                    "requires_photo_proof": 1,
                    "active": 1,
                },
                {
                    "name": "BSOP-ITEM-2",
                    "parent": "BSOP-1",
                    "parenttype": "Building SOP",
                    "parentfield": "items",
                    "idx": 2,
                    "sop_item_id": "trash",
                    "item_title": "Trash removed",
                    "item_description": "Empty all cans and replace liners.",
                    "requires_photo_proof": 0,
                    "active": 1,
                },
            ],
            "Site Shift Requirement_list": [
                {
                    "name": "SSR-0001",
                    "building": "BUILD-1",
                    "service_date": datetime(2026, 3, 9, 0, 0, 0),
                    "arrival_window_start": datetime(2026, 3, 9, 18, 0, 0),
                    "arrival_window_end": datetime(2026, 3, 9, 20, 0, 0),
                    "status": "Completed",
                    "completion_status": "Completed With Exception",
                    "current_employee": "Jordan Tech",
                    "custom_building_sop": "BSOP-1",
                    "modified": datetime(2026, 3, 9, 21, 0, 0),
                },
                {
                    "name": "SSR-0000",
                    "building": "BUILD-1",
                    "service_date": datetime(2026, 2, 28, 0, 0, 0),
                    "arrival_window_start": datetime(2026, 2, 28, 18, 0, 0),
                    "arrival_window_end": datetime(2026, 2, 28, 20, 0, 0),
                    "status": "Completed",
                    "completion_status": "",
                    "current_employee": "Jordan Tech",
                    "custom_building_sop": "",
                    "modified": datetime(2026, 2, 28, 21, 0, 0),
                },
            ],
            "Site Shift Requirement": {
                "SSR-0001": {"name": "SSR-0001", "building": "BUILD-1"},
                "SSR-0000": {"name": "SSR-0000", "building": "BUILD-1"},
            },
            "Site Shift Requirement Checklist Item_list": [
                {
                    "name": "SSR-ITEM-1",
                    "parent": "SSR-0001",
                    "parenttype": "Site Shift Requirement",
                    "parentfield": "custom_checklist_items",
                    "idx": 1,
                    "sop_item_id": "restrooms",
                    "item_title": "Restrooms sanitized",
                    "item_description": "Disinfect all restroom touchpoints and restock consumables.",
                    "requires_photo_proof": 1,
                    "item_status": "Completed",
                    "exception_note": "",
                },
                {
                    "name": "SSR-ITEM-2",
                    "parent": "SSR-0001",
                    "parenttype": "Site Shift Requirement",
                    "parentfield": "custom_checklist_items",
                    "idx": 2,
                    "sop_item_id": "trash",
                    "item_title": "Trash removed",
                    "item_description": "Empty all cans and replace liners.",
                    "requires_photo_proof": 0,
                    "item_status": "Exception",
                    "exception_note": "Front office can was inaccessible during lockout.",
                },
            ],
            "Site Shift Requirement Checklist Proof": {
                "PROOF-1": {
                    "name": "PROOF-1",
                    "parent": "SSR-0001",
                    "proof_file": "/private/files/restroom-proof.jpg",
                    "proof_caption": "Restroom finish photo",
                }
            },
            "Site Shift Requirement Checklist Proof_list": [
                {
                    "name": "PROOF-1",
                    "parent": "SSR-0001",
                    "parenttype": "Site Shift Requirement",
                    "parentfield": "custom_checklist_proofs",
                    "idx": 1,
                    "checklist_item_id": "restrooms",
                    "proof_file": "/private/files/restroom-proof.jpg",
                    "proof_caption": "Restroom finish photo",
                    "modified": datetime(2026, 3, 9, 20, 15, 0),
                }
            ],
            "File_list": [
                {
                    "name": "FILE-1",
                    "file_url": "/private/files/restroom-proof.jpg",
                    "file_name": "restroom-proof.jpg",
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
                "Building SOP": list(self.dataset["Building SOP"].values()),
                "Building SOP Item": self.dataset["Building SOP Item_list"],
                "Site Shift Requirement": self.dataset["Site Shift Requirement_list"],
                "Site Shift Requirement Checklist Item": self.dataset["Site Shift Requirement Checklist Item_list"],
                "Site Shift Requirement Checklist Proof": self.dataset["Site Shift Requirement Checklist Proof_list"],
                "File": self.dataset["File_list"],
            }
        )
        portal.frappe.session.user = "portal@example.com"
        portal.frappe.local.response = {}
        portal.frappe.form_dict = {}
        portal.frappe.utils.get_url = lambda path="": f"https://example.test{path}"
        portal.frappe.utils.get_datetime = lambda value: value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        portal.now_datetime = lambda: datetime(2026, 3, 25, 12, 0, 0)

    def _portal_scope(self, **overrides):
        payload = {
            "session_user": "portal@example.com",
            "customer_name": "CUST-1",
            "customer_display": "Portal Customer LLC",
            "portal_contact_name": "CONTACT-1",
            "portal_contact_email": "portal@example.com",
            "portal_contact_phone": "512-555-0101",
            "portal_contact_designation": "Office Manager",
            "portal_address_name": "ADDR-PORTAL",
            "billing_contact_name": "CONTACT-BILLING",
            "billing_contact_email": "billing@example.com",
            "billing_contact_phone": "512-555-0133",
            "billing_contact_designation": "Accounts Payable",
            "billing_address_name": "ADDR-1",
            "tax_id": "99-1234567",
        }
        payload.update(overrides)
        return portal.PortalScope(**payload)

    def test_dashboard_data_is_scoped_to_customer(self):
        with patch.object(portal.public_quote_service, "find_contact_for_customer", return_value="CONTACT-BILLING"), patch.object(
            portal.public_quote_service, "find_address_for_customer", return_value="ADDR-1"
        ):
            data = portal.get_customer_portal_dashboard_data()

        self.assertFalse(data["access_denied"])
        self.assertEqual(data["customer_display"], "Portal Customer LLC")
        self.assertEqual(data["summary_cards"][0]["label"], "Agreement status")
        self.assertEqual(data["summary_cards"][0]["value"], "Active")
        self.assertEqual(data["summary_cards"][0]["meta"], "Signed Mar 01, 2026 09:00 AM")
        self.assertEqual(data["summary_cards"][1]["value"], "1")
        self.assertEqual(data["latest_invoices"][0]["download_url"], "/api/method/pikt_inc.api.customer_portal.download_customer_portal_invoice?invoice=SINV-0001")
        self.assertEqual(data["active_master"]["title"], "Portal Customer Master Agreement")
        self.assertEqual(data["latest_locations"][0]["title"], "Headquarters")
        self.assertEqual(data["latest_locations"][0]["agreement_status_label"], "Location exhibit on file")

    def test_agreements_page_shapes_addenda_around_location_identity(self):
        data = portal.get_customer_portal_agreements_data()

        self.assertFalse(data["access_denied"])
        self.assertEqual(data["active_master"]["title"], "Portal Customer Master Agreement")
        self.assertEqual(data["addenda"][0]["title"], "Headquarters")
        self.assertEqual(data["addenda"][0]["document_title"], "Portal Addendum")
        self.assertEqual(data["addenda"][0]["location_address"], "123 Market St, Suite 300, Austin, TX 78701")

    def test_locations_page_defaults_to_list_view(self):
        data = portal.get_customer_portal_locations_data()

        self.assertFalse(data["access_denied"])
        self.assertEqual(data["buildings"][0]["title"], "Headquarters")
        self.assertEqual(data["buildings"][0]["detail_url"], "/portal/locations?building=BUILD-1")
        self.assertEqual(data["buildings"][0]["agreement_status_label"], "Location exhibit on file")
        self.assertIsNone(data["selected_building"])
        self.assertEqual(data["selected_building_checklist"], [])
        self.assertEqual(data["service_history"], [])

    def test_locations_page_can_select_a_single_building_for_editing(self):
        portal.frappe.form_dict = {"building": "BUILD-1"}

        data = portal.get_customer_portal_locations_data()

        self.assertFalse(data["access_denied"])
        self.assertEqual(data["selected_building"]["name"], "BUILD-1")
        self.assertEqual(data["selected_building"]["title"], "Headquarters")
        self.assertEqual(data["selected_building_sop"]["name"], "BSOP-1")
        self.assertEqual(data["selected_building_sop"]["version_number"], 2)
        self.assertEqual(data["selected_building_checklist"][0]["title"], "Restrooms sanitized")
        self.assertTrue(data["selected_building_checklist"][0]["requires_photo_proof"])
        self.assertEqual(data["service_history"][0]["name"], "SSR-0001")
        self.assertTrue(data["service_history"][0]["has_checklist"])
        self.assertEqual(data["service_history"][0]["checklist_items"][0]["proofs"][0]["name"], "PROOF-1")

    def test_portal_billing_contract_requires_address_fields(self):
        with self.assertRaisesRegex(Exception, "Field required|at least 1 character"):
            portal_contracts.CustomerPortalBillingInput.model_validate(
                {
                    "billing_contact_name": "Billing Team",
                    "billing_email": "billing@example.com",
                    "billing_country": "United States",
                }
            )

    def test_portal_location_contract_accepts_alias_and_tracks_updates(self):
        payload = portal_contracts.CustomerPortalLocationUpdateInput.model_validate(
            {
                "building": "BUILD-1",
                "access_method": "Door code / keypad",
                "access_details_confirmed": "1",
            }
        )

        self.assertEqual(payload.building_name, "BUILD-1")
        self.assertEqual(payload.updates()["access_method"], "Door code / keypad")
        self.assertTrue(payload.updates()["access_details_confirmed"])

    def test_portal_building_sop_contract_accepts_flat_items(self):
        payload = portal_contracts.CustomerPortalBuildingSopUpdateInput.model_validate(
            {
                "building": "BUILD-1",
                "items": [
                    {
                        "item_id": "restrooms",
                        "title": "Restrooms sanitized",
                        "description": "Disinfect touchpoints.",
                        "requires_photo_proof": "1",
                    }
                ],
            }
        )

        self.assertEqual(payload.building_name, "BUILD-1")
        self.assertEqual(payload.items[0].item_id, "restrooms")
        self.assertTrue(payload.items[0].requires_photo_proof)

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
        self.assertEqual(data["login_path"], "")

    def test_guest_scope_returns_sign_in_path(self):
        portal.frappe.session.user = "Guest"

        data = portal.get_customer_portal_dashboard_data()

        self.assertTrue(data["access_denied"])
        self.assertEqual(data["error_message"], "Sign in to access your customer portal.")
        self.assertEqual(portal.frappe.local.response["http_status_code"], 302)
        self.assertEqual(data["login_path"], "/login?redirect-to=/portal")
        self.assertEqual(data["redirect_to"], "/login?redirect-to=/portal")
        self.assertIsInstance(data["metatags"], dict)
        self.assertIsInstance(data["portal_nav"][0], dict)

    def test_portal_access_error_response_serializes_nested_models(self):
        with patch.object(portal_payloads, "_is_guest_session", return_value=True):
            data = portal_payloads._portal_access_error_response(
                "overview",
                portal.PortalAccessError("Sign in to access your customer portal."),
            )

        self.assertIsInstance(data["metatags"], dict)
        self.assertEqual(data["metatags"]["title"], "Account Overview | Customer Portal")
        self.assertTrue(all(isinstance(item, dict) for item in data["portal_nav"]))

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

        with patch.object(portal.billing, "_require_portal_scope", return_value=scope), patch.object(
            portal.billing, "_portal_contact_payload", return_value=types.SimpleNamespace(display_name="Pat Portal")
        ), patch.object(portal.public_quote_service, "valid_email", return_value=True), patch.object(
            portal.public_quote_service, "ensure_address", return_value="ADDR-UPDATED"
        ) as ensure_address, patch.object(
            portal.public_quote_service, "ensure_contact", return_value="CONTACT-UPDATED"
        ) as ensure_contact, patch.object(
            portal.public_quote_service, "sync_customer"
        ) as sync_customer, patch.object(
            portal.public_quote_service, "doc_db_set_values"
        ) as doc_db_set_values:
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

    def test_billing_update_splits_shared_contact_when_roles_diverge(self):
        scope = portal.PortalScope(
            session_user="portal@example.com",
            customer_name="CUST-1",
            customer_display="Portal Customer LLC",
            portal_contact_name="CONTACT-1",
            portal_contact_email="portal@example.com",
            portal_contact_phone="512-555-0101",
            portal_contact_designation="Office Manager",
            portal_address_name="ADDR-PORTAL",
            billing_contact_name="CONTACT-1",
            billing_contact_email="portal@example.com",
            billing_contact_phone="512-555-0101",
            billing_contact_designation="Office Manager",
            billing_address_name="ADDR-1",
            tax_id="99-1234567",
        )

        with patch.object(portal.billing, "_require_portal_scope", return_value=scope), patch.object(
            portal.billing, "_portal_contact_payload", return_value=types.SimpleNamespace(display_name="Pat Portal")
        ), patch.object(portal.public_quote_service, "valid_email", return_value=True), patch.object(
            portal.public_quote_service, "ensure_address", return_value="ADDR-UPDATED"
        ), patch.object(
            portal.public_quote_service, "ensure_contact", return_value="CONTACT-BILLING"
        ) as mock_ensure_contact, patch.object(
            portal.public_quote_service, "sync_customer"
        ), patch.object(
            portal.public_quote_service, "doc_db_set_values"
        ) as doc_db_set_values:
            portal.update_customer_portal_billing(
                portal_contact_name="Pat Portal",
                portal_contact_phone="512-555-0111",
                portal_contact_title="Facilities Lead",
                billing_contact_name="Billing Team",
                billing_email="portal@example.com",
                billing_contact_phone="512-555-0222",
                billing_contact_title="Controller",
                billing_address_line_1="456 Billing Ave",
                billing_city="Austin",
                billing_state="TX",
                billing_postal_code="78702",
                billing_country="United States",
                tax_id="12-3456789",
            )

        mock_ensure_contact.assert_called_once_with(
            "CUST-1",
            "Portal Customer LLC",
            "Billing Team",
            "portal@example.com",
            exclude_contact_name="CONTACT-1",
        )
        final_update = doc_db_set_values.call_args_list[-1].args
        self.assertEqual(final_update[0], "Contact")
        self.assertEqual(final_update[1], "CONTACT-1")
        self.assertEqual(final_update[2]["phone"], "512-555-0111")
        self.assertEqual(final_update[2]["designation"], "Facilities Lead")
        self.assertEqual(final_update[2]["address"], "ADDR-PORTAL")

    def test_billing_update_clears_explicit_blank_billing_phone(self):
        scope = self._portal_scope()

        with patch.object(portal.billing, "_require_portal_scope", return_value=scope), patch.object(
            portal.billing, "_portal_contact_payload", return_value=types.SimpleNamespace(display_name="Pat Portal")
        ), patch.object(portal.public_quote_service, "valid_email", return_value=True), patch.object(
            portal.public_quote_service, "ensure_address", return_value="ADDR-UPDATED"
        ), patch.object(
            portal.public_quote_service, "ensure_contact", return_value="CONTACT-UPDATED"
        ), patch.object(
            portal.public_quote_service, "sync_customer"
        ), patch.object(
            portal.public_quote_service, "doc_db_set_values"
        ) as doc_db_set_values:
            portal.update_customer_portal_billing(
                portal_contact_name="Pat Portal",
                billing_contact_name="Billing Team",
                billing_email="billing@example.com",
                billing_contact_phone="",
                billing_contact_title="Controller",
                billing_address_line_1="456 Billing Ave",
                billing_city="Austin",
                billing_state="TX",
                billing_postal_code="78702",
                billing_country="United States",
                tax_id="12-3456789",
            )

        billing_update = next(call.args for call in doc_db_set_values.call_args_list if call.args[1] == "CONTACT-UPDATED")
        self.assertEqual(billing_update[2]["phone"], "")
        self.assertEqual(billing_update[2]["mobile_no"], "")

    def test_billing_update_clears_explicit_blank_portal_phone(self):
        scope = self._portal_scope()

        with patch.object(portal.billing, "_require_portal_scope", return_value=scope), patch.object(
            portal.billing, "_portal_contact_payload", return_value=types.SimpleNamespace(display_name="Pat Portal")
        ), patch.object(portal.public_quote_service, "valid_email", return_value=True), patch.object(
            portal.public_quote_service, "ensure_address", return_value="ADDR-UPDATED"
        ), patch.object(
            portal.public_quote_service, "ensure_contact", return_value="CONTACT-UPDATED"
        ), patch.object(
            portal.public_quote_service, "sync_customer"
        ), patch.object(
            portal.public_quote_service, "doc_db_set_values"
        ) as doc_db_set_values:
            portal.update_customer_portal_billing(
                portal_contact_name="Pat Portal",
                portal_contact_phone="",
                portal_contact_title="Facilities Lead",
                billing_contact_name="Billing Team",
                billing_email="billing@example.com",
                billing_address_line_1="456 Billing Ave",
                billing_city="Austin",
                billing_state="TX",
                billing_postal_code="78702",
                billing_country="United States",
                tax_id="12-3456789",
            )

        portal_update = next(call.args for call in doc_db_set_values.call_args_list if call.args[1] == "CONTACT-1")
        self.assertEqual(portal_update[2]["phone"], "")
        self.assertEqual(portal_update[2]["mobile_no"], "")

    def test_billing_update_clears_shared_contact_phone_when_roles_match(self):
        scope = self._portal_scope(
            billing_contact_name="CONTACT-1",
            billing_contact_email="portal@example.com",
            billing_contact_phone="512-555-0101",
            billing_contact_designation="Office Manager",
        )

        with patch.object(portal.billing, "_require_portal_scope", return_value=scope), patch.object(
            portal.billing, "_portal_contact_payload", return_value=types.SimpleNamespace(display_name="Pat Portal")
        ), patch.object(portal.public_quote_service, "valid_email", return_value=True), patch.object(
            portal.public_quote_service, "ensure_address", return_value="ADDR-UPDATED"
        ), patch.object(
            portal.public_quote_service, "ensure_contact", return_value="CONTACT-1"
        ), patch.object(
            portal.public_quote_service, "sync_customer"
        ), patch.object(
            portal.public_quote_service, "doc_db_set_values"
        ) as doc_db_set_values:
            portal.update_customer_portal_billing(
                portal_contact_name="Pat Portal",
                portal_contact_phone="",
                portal_contact_title="Office Manager",
                billing_contact_name="Pat Portal",
                billing_email="portal@example.com",
                billing_contact_phone="",
                billing_contact_title="Office Manager",
                billing_address_line_1="456 Billing Ave",
                billing_city="Austin",
                billing_state="TX",
                billing_postal_code="78702",
                billing_country="United States",
                tax_id="12-3456789",
            )

        shared_update = doc_db_set_values.call_args_list[-1].args
        self.assertEqual(shared_update[1], "CONTACT-1")
        self.assertEqual(shared_update[2]["phone"], "")
        self.assertEqual(shared_update[2]["mobile_no"], "")

    def test_billing_update_uses_scope_phones_when_fields_are_omitted(self):
        scope = self._portal_scope()

        with patch.object(portal.billing, "_require_portal_scope", return_value=scope), patch.object(
            portal.billing, "_portal_contact_payload", return_value=types.SimpleNamespace(display_name="Pat Portal")
        ), patch.object(portal.public_quote_service, "valid_email", return_value=True), patch.object(
            portal.public_quote_service, "ensure_address", return_value="ADDR-UPDATED"
        ), patch.object(
            portal.public_quote_service, "ensure_contact", return_value="CONTACT-UPDATED"
        ), patch.object(
            portal.public_quote_service, "sync_customer"
        ), patch.object(
            portal.public_quote_service, "doc_db_set_values"
        ) as doc_db_set_values:
            portal.update_customer_portal_billing(
                portal_contact_name="Pat Portal",
                billing_contact_name="Billing Team",
                billing_email="billing@example.com",
                billing_address_line_1="456 Billing Ave",
                billing_city="Austin",
                billing_state="TX",
                billing_postal_code="78702",
                billing_country="United States",
                tax_id="12-3456789",
            )

        billing_update = next(call.args for call in doc_db_set_values.call_args_list if call.args[1] == "CONTACT-UPDATED")
        portal_update = next(call.args for call in doc_db_set_values.call_args_list if call.args[1] == "CONTACT-1")
        self.assertEqual(billing_update[2]["phone"], "512-555-0133")
        self.assertEqual(billing_update[2]["mobile_no"], "512-555-0133")
        self.assertEqual(portal_update[2]["phone"], "512-555-0101")
        self.assertEqual(portal_update[2]["mobile_no"], "512-555-0101")

    def test_location_update_marks_routes_dirty_after_save(self):
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

        with patch.object(portal.locations, "_require_portal_scope", return_value=scope), patch.object(
            portal.locations.public_quote_service,
            "doc_db_set_values",
        ) as doc_db_set_values, patch.object(
            portal.locations.dispatch_routing,
            "mark_routes_dirty_for_building",
        ) as mark_routes_dirty:
            response = portal.update_customer_portal_location(
                building_name="BUILD-1",
                access_method="Door code / keypad",
                allowed_entry_time="After 7 PM",
                site_notes="Manual site note",
            )

        doc_db_set_values.assert_called_once()
        mark_routes_dirty.assert_called_once_with("BUILD-1")
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

        with patch.object(portal.locations, "_require_portal_scope", return_value=scope):
            with self.assertRaisesRegex(Exception, "not available in this portal account"):
                portal.update_customer_portal_location(building_name="BUILD-OTHER", access_notes="Test note")

    def test_building_sop_update_creates_new_version_for_in_scope_building(self):
        scope = self._portal_scope()

        with patch.object(portal.locations, "_require_portal_scope", return_value=scope), patch.object(
            portal.locations.building_sop_service,
            "create_building_sop_version",
            return_value=({"name": "BSOP-2"}, []),
        ) as create_version:
            response = portal.update_customer_portal_building_sop(
                building_name="BUILD-1",
                items=[
                    {
                        "item_id": "restrooms",
                        "title": "Restrooms sanitized",
                        "description": "Disinfect touchpoints.",
                        "requires_photo_proof": True,
                    }
                ],
            )

        create_version.assert_called_once()
        self.assertEqual(response["status"], "updated")
        self.assertEqual(response["message"], "Building checklist updated.")

    def test_building_sop_update_logs_and_surfaces_clean_message_on_unexpected_save_error(self):
        scope = self._portal_scope()

        with patch.object(portal.locations, "_require_portal_scope", return_value=scope), patch.object(
            portal.locations.building_sop_service,
            "create_building_sop_version",
            side_effect=TypeError("boom"),
        ), patch.object(
            portal.locations.frappe,
            "get_traceback",
            return_value="traceback",
        ), patch.object(
            portal.locations.frappe,
            "log_error",
        ) as log_error:
            with self.assertRaisesRegex(Exception, "Unable to save the building checklist right now"):
                portal.update_customer_portal_building_sop(building_name="BUILD-1", items=[])

        log_error.assert_called_once()

    def test_locations_response_formats_service_history_when_history_loader_uses_safe_strings(self):
        history_payload = {
            "page": 1,
            "has_more": False,
            "visits": [
                {
                    "name": "SSR-0001",
                    "service_date": "2026-04-02",
                    "arrival_window_start": "",
                    "arrival_window_end": "",
                    "status": "Open",
                    "employee_label": "Crew A",
                    "sop_name": "",
                    "has_checklist": False,
                    "checklist_items": [],
                }
            ],
        }

        portal.frappe.form_dict = {"building": "BUILD-1"}

        with patch.object(portal.payloads.building_sop_service, "shape_portal_sop_payload", return_value={"version": None, "items": []}), patch.object(
            portal.payloads.building_sop_service,
            "get_building_service_history",
            return_value=history_payload,
        ):
            response = portal.get_customer_portal_locations_data()

        self.assertEqual(response["service_history"][0]["name"], "SSR-0001")
        self.assertEqual(response["service_history"][0]["service_date_label"], "Apr 02, 2026")
        self.assertEqual(response["service_history"][0]["arrival_window_label"], "")

    def test_building_sop_update_rejects_out_of_scope_building(self):
        scope = self._portal_scope()

        with patch.object(portal.locations, "_require_portal_scope", return_value=scope):
            with self.assertRaisesRegex(Exception, "not available in this portal account"):
                portal.update_customer_portal_building_sop(building_name="BUILD-OTHER", items=[])

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
        with patch.object(portal.downloads, "_require_portal_scope", return_value=scope), patch.object(
            portal.downloads, "render_invoice_pdf", return_value=b"PDF"
        ):
            portal.download_customer_portal_invoice("SINV-0001")

        self.assertEqual(portal.frappe.local.response["filename"], "SINV-0001.pdf")
        self.assertEqual(portal.frappe.local.response["type"], "download")
        self.assertEqual(portal.frappe.local.response["content_type"], "application/pdf")

    def test_checklist_proof_download_sets_scoped_response(self):
        scope = self._portal_scope()
        portal.frappe.local.response = {}

        with patch.object(portal.downloads, "_require_portal_scope", return_value=scope), patch.object(
            portal.downloads.building_sop_service,
            "get_proof_file_content",
            return_value=("restroom-proof.jpg", b"IMG", "image/jpeg"),
        ):
            portal.download_customer_portal_checklist_proof("PROOF-1")

        self.assertEqual(portal.frappe.local.response["filename"], "restroom-proof.jpg")
        self.assertEqual(portal.frappe.local.response["type"], "download")
        self.assertEqual(portal.frappe.local.response["content_type"], "image/jpeg")

    def test_render_invoice_pdf_uses_scoped_print_bypass(self):
        portal.frappe.local.flags = types.SimpleNamespace(ignore_print_permissions=False)
        observed = []

        def fake_get_print(*_args, **_kwargs):
            observed.append(portal.frappe.local.flags.ignore_print_permissions)
            return "<html>invoice</html>"

        with patch.object(portal.frappe, "get_print", side_effect=fake_get_print):
            pdf = portal.render_invoice_pdf("SINV-0001")

        self.assertEqual(observed, [True])
        self.assertFalse(portal.frappe.local.flags.ignore_print_permissions)
        self.assertEqual(pdf, b"<html>invoice</html>")

    def test_hooks_include_customer_portal_home_and_patch(self):
        self.assertEqual(app_hooks.role_home_page["Customer Portal User"], "orders")
        builder_fixture = next(fixture for fixture in app_hooks.fixtures if fixture["dt"] == "Builder Page")
        routes = builder_fixture["filters"][0][2]
        self.assertNotIn("portal", routes)
        self.assertNotIn("portal/agreements", routes)
        self.assertNotIn("portal/billing", routes)
        self.assertNotIn("portal/billing-info", routes)
        self.assertNotIn("portal/locations", routes)
        component_fixture = next(fixture for fixture in app_hooks.fixtures if fixture["dt"] == "Builder Component")
        component_names = component_fixture["filters"][0][2]
        self.assertNotIn("Portal Shell Header", component_names)
        self.assertNotIn("Portal Summary Stat Card", component_names)
        self.assertNotIn("Portal Record List Card", component_names)
        self.assertNotIn("Portal Invoice Row Card", component_names)
        self.assertNotIn("Portal Agreement Preview Card", component_names)
        self.assertNotIn("Portal Location Edit Card", component_names)
        self.assertNotIn("Portal Empty State Block", component_names)
        patches = PATCHES_PATH.read_text(encoding="utf-8")
        self.assertIn("pikt_inc.patches.post_model_sync.ensure_customer_portal_role", patches)
        self.assertIn("pikt_inc.patches.post_model_sync.remove_legacy_customer_portal_builder_artifacts", patches)

    def test_portal_www_templates_use_shared_shell_and_assets(self):
        macros = PORTAL_MACROS_PATH.read_text(encoding="utf-8")
        overview = PORTAL_OVERVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        agreements = PORTAL_AGREEMENTS_TEMPLATE_PATH.read_text(encoding="utf-8")
        billing = PORTAL_BILLING_TEMPLATE_PATH.read_text(encoding="utf-8")
        billing_info = PORTAL_BILLING_INFO_TEMPLATE_PATH.read_text(encoding="utf-8")
        locations = PORTAL_LOCATIONS_TEMPLATE_PATH.read_text(encoding="utf-8")
        css = PORTAL_CSS_PATH.read_text(encoding="utf-8")
        js = PORTAL_FORMS_JS_PATH.read_text(encoding="utf-8")

        self.assertIn("customer_portal_header", macros)
        self.assertIn("customer_portal_footer", macros)
        self.assertIn("/assets/pikt_inc/css/customer_portal.css", macros)
        self.assertIn("site_shell_head", macros)
        self.assertIn("site_shell_mobile_menu", macros)
        self.assertIn("data-portal-mobile-nav", macros)
        self.assertIn("portal-shell-header", css)
        self.assertIn(".portal-shell-menu__backdrop", css)
        self.assertIn("position:absolute", css)
        self.assertIn("data-portal-endpoint", js)
        self.assertIn("closeOpenPortalMenus", js)
        self.assertIn("data-portal-mobile-nav", js)
        self.assertIn("site-shell-mobile[open]", js)
        self.assertIn("setFormBusy", js)
        self.assertIn("portalSubmitting", js)
        self.assertIn("function boot()", js)
        self.assertIn("hasBooted", js)
        self.assertIn("document.readyState==='loading'", js)
        self.assertIn("document.addEventListener('DOMContentLoaded',boot,{once:true});", js)
        self.assertNotIn("window.location.reload()", js)

        for template in (overview, agreements, billing, billing_info, locations):
            self.assertIn("customer_portal_header", template)
            self.assertIn("customer_portal_footer", template)
            self.assertIn("customer_portal_head", template)

        self.assertIn("/assets/pikt_inc/js/customer_portal_forms.js", billing_info)
        self.assertIn("/assets/pikt_inc/js/customer_portal_forms.js", locations)
        self.assertIn("/api/method/pikt_inc.api.customer_portal.update_customer_portal_billing", billing_info)
        self.assertNotIn("/api/method/pikt_inc.api.customer_portal.update_customer_portal_billing", billing)
        self.assertIn("/api/method/pikt_inc.api.customer_portal.update_customer_portal_location", locations)
        self.assertIn("/api/method/pikt_inc.api.customer_portal.update_customer_portal_building_sop", locations)
        self.assertIn("data-portal-checklist-form", locations)
        self.assertIn("Load older visits", locations)
        self.assertNotIn("buildings_json", locations)
        self.assertNotIn("portal-locations-data", locations)
        self.assertIn("building-specific schedules and exhibits", agreements)
        self.assertIn("Documents by service location", agreements)
        self.assertIn("Download master agreement", agreements)
        self.assertIn("Download exhibit", agreements)
        self.assertIn("portal-section portal-section--documents", agreements)
        self.assertNotIn("Service locations on agreement", agreements)
        self.assertIn("serializeChecklistForm", js)
        self.assertIn("setMessage(messageBox,error.message||'Unable to save changes.',true);", js)
        self.assertIn("portal-checklist-item", css)
        self.assertIn("portal-history-visit", css)
        self.assertIn("portal-document-meta", css)
        self.assertIn("portal-section--documents", css)
        self.assertIn(".portal-section--documents,\n  .portal-stack--documents{", css)
        self.assertIn("align-items:stretch;", css)

    def test_portal_www_controllers_proxy_to_service(self):
        context = types.SimpleNamespace()
        with patch.object(portal_www_index, "build_context", return_value=context) as overview_helper:
            result = portal_www_index.get_context(context)

        self.assertIs(result, context)
        overview_helper.assert_called_once()

        context = types.SimpleNamespace()
        with patch.object(portal_www_agreements, "build_context", return_value=context) as agreements_helper:
            result = portal_www_agreements.get_context(context)
        self.assertIs(result, context)
        agreements_helper.assert_called_once()

        context = types.SimpleNamespace()
        with patch.object(portal_www_billing, "build_context", return_value=context) as billing_helper:
            result = portal_www_billing.get_context(context)
        self.assertIs(result, context)
        billing_helper.assert_called_once()

        context = types.SimpleNamespace()
        with patch.object(portal_www_billing_info, "build_context", return_value=context) as billing_info_helper:
            result = portal_www_billing_info.get_context(context)
        self.assertIs(result, context)
        billing_info_helper.assert_called_once()

        context = types.SimpleNamespace()
        with patch.object(portal_www_locations, "build_context", return_value=context) as locations_helper:
            result = portal_www_locations.get_context(context)
        self.assertIs(result, context)
        locations_helper.assert_called_once()

    def test_portal_page_helper_shapes_shell_context(self):
        context = types.SimpleNamespace()
        result = portal_page_helper.build_context(
            context,
            page_loader=lambda: {
                "page_title": "Billing",
                "portal_title": "Customer Portal",
                "portal_description": "Desc",
                "portal_nav": [
                    {"key": "overview", "label": "Overview", "url": "/portal", "is_active": True},
                    {"key": "contact", "label": "Contact", "url": "/contact", "is_active": False},
                    {"key": "logout", "label": "Log out", "url": "/logout", "is_active": False},
                ],
                "metatags": {"title": "Billing | Customer Portal", "description": "Secure portal"},
            },
        )

        self.assertIs(result, context)
        self.assertEqual(context.page_title, "Billing | Customer Portal")
        self.assertEqual(context.meta_description, "Secure portal")
        self.assertEqual(context.description, "Secure portal")
        self.assertEqual(context.body_class, "no-web-page-sections")
        self.assertEqual(context.http_status_code, 200)
        self.assertEqual([item["key"] for item in context.primary_nav], ["overview"])
        self.assertEqual([item["key"] for item in context.utility_nav], ["contact", "logout"])

    def test_portal_page_helper_preserves_http_status_code(self):
        context = types.SimpleNamespace()
        result = portal_page_helper.build_context(
            context,
            page_loader=lambda: {
                "page_title": "Billing",
                "portal_title": "Customer Portal",
                "portal_description": "Desc",
                "portal_nav": [],
                "metatags": {"title": "Billing | Customer Portal", "description": "Secure portal"},
                "http_status_code": 403,
            },
        )

        self.assertIs(result, context)
        self.assertEqual(context.http_status_code, 403)

    def test_portal_page_helper_sets_redirect_response(self):
        context = types.SimpleNamespace()
        portal_page_helper.frappe.local.response = {}
        portal_page_helper.frappe.local.flags = types.SimpleNamespace(redirect_location="")

        with self.assertRaises(portal_page_helper.frappe.Redirect) as exc:
            portal_page_helper.build_context(
                context,
                page_loader=lambda: {
                    "page_title": "Overview",
                    "portal_title": "Customer Portal",
                    "portal_description": "Desc",
                    "portal_nav": [],
                    "metatags": {"title": "Customer Portal", "description": "Secure portal"},
                    "http_status_code": 302,
                    "redirect_to": "/login?redirect-to=/portal",
                },
            )

        self.assertEqual(exc.exception.http_status_code, 302)
        self.assertEqual(portal_page_helper.frappe.local.response["type"], "redirect")
        self.assertEqual(portal_page_helper.frappe.local.response["location"], "/login?redirect-to=/portal")
        self.assertEqual(portal_page_helper.frappe.local.response["http_status_code"], 302)
        self.assertEqual(portal_page_helper.frappe.local.flags.redirect_location, "/login?redirect-to=/portal")

    def test_portal_page_helper_normalizes_model_like_context_values(self):
        context = types.SimpleNamespace()

        result = portal_page_helper.build_context(
            context,
            page_loader=lambda: {
                "page_title": "Overview",
                "portal_title": "Customer Portal",
                "portal_description": "Secure portal",
                "portal_nav": [
                    portal_contracts.PortalNavItem(key="overview", label="Overview", url="/portal", is_active=True),
                    portal_contracts.PortalNavItem(key="contact", label="Contact", url="/contact", is_active=False),
                ],
                "metatags": portal_contracts.PortalMetaTags(
                    title="Customer Portal",
                    description="Secure portal",
                    canonical="https://example.test/portal",
                ),
            },
        )

        self.assertIs(result, context)
        self.assertEqual(context.page_title, "Customer Portal")
        self.assertEqual([item["key"] for item in context.primary_nav], ["overview"])
        self.assertEqual([item["key"] for item in context.utility_nav], ["contact"])

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
        ) as locations, patch.object(
            portal_api.customer_portal_service,
            "update_customer_portal_building_sop",
            return_value={"status": "updated"},
        ) as update_sop, patch.object(
            portal_api.customer_portal_service,
            "download_customer_portal_checklist_proof",
            return_value=None,
        ) as download_proof:
            self.assertEqual(portal_api.get_customer_portal_dashboard_data(), {"page_key": "overview"})
            self.assertEqual(portal_api.get_customer_portal_agreements_data(), {"page_key": "agreements"})
            self.assertEqual(portal_api.get_customer_portal_billing_data(), {"page_key": "billing"})
            self.assertEqual(portal_api.get_customer_portal_locations_data(), {"page_key": "locations"})
            self.assertEqual(portal_api.update_customer_portal_building_sop(building_name="BUILD-1"), {"status": "updated"})
            self.assertIsNone(portal_api.download_customer_portal_checklist_proof(proof="PROOF-1"))

        dashboard.assert_called_once_with()
        agreements.assert_called_once_with()
        billing.assert_called_once_with()
        locations.assert_called_once_with()
        update_sop.assert_called_once()
        download_proof.assert_called_once()
