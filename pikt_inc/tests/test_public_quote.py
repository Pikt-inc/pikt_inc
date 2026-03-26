from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc.services import public_quote
from pikt_inc.services.public_quote import acceptance, payloads, portal


class FakeDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


class FakeSaveDoc(FakeDoc):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.save_called = False
        self.insert_called = False
        self.submit_called = False

    def save(self, ignore_permissions=False):
        self.save_called = True
        self.ignore_permissions = ignore_permissions
        return self

    def insert(self, ignore_permissions=False):
        self.insert_called = True
        self.insert_ignore_permissions = ignore_permissions
        self.name = self.get("name") or "SO-TEST-0001"
        return self

    def submit(self):
        self.submit_called = True
        self.docstatus = 1
        return self


class FailingInsertDoc(FakeDoc):
    def insert(self, ignore_permissions=False):
        raise RuntimeError("duplicate insert")


class TestPublicQuote(unittest.TestCase):
    @patch.object(acceptance, "make_accept_token", return_value="accept-token")
    @patch.object(acceptance, "add_to_date", return_value="2026-04-30 23:59:59")
    @patch.object(public_quote.frappe.db, "exists", return_value=True)
    def test_prepare_public_quotation_acceptance_sets_token_and_expiry(
        self,
        _mock_exists,
        _mock_add_to_date,
        _mock_make_accept_token,
    ):
        doc = FakeDoc(
            {
                "name": "SAL-QTN-TEST-0001",
                "quotation_to": "Lead",
                "party_name": "CRM-LEAD-TEST-0001",
                "contact_email": "TEST@EXAMPLE.COM",
                "valid_till": "2026-04-30",
                "custom_accepted_sales_order": "SO-OLD",
            }
        )

        public_quote.prepare_public_quotation_acceptance(doc)

        self.assertEqual(doc.contact_email, "test@example.com")
        self.assertEqual(doc.custom_accepted_sales_order, "")
        self.assertEqual(doc.custom_accept_token, "accept-token")
        self.assertEqual(doc.custom_accept_token_expires_on, "2026-04-30 23:59:59")

    @patch.object(public_quote.frappe.db, "exists", return_value=True)
    @patch.object(public_quote.frappe, "get_all")
    @patch.object(public_quote.frappe, "get_doc")
    def test_mark_opportunity_reviewed_on_quotation_updates_opportunity_and_submission(
        self,
        mock_get_doc,
        mock_get_all,
        _mock_exists,
    ):
        opp = FakeSaveDoc(
            {
                "name": "CRM-OPP-TEST-0001",
                "status": "Open",
                "digital_walkthrough_file": "/private/files/walkthrough.png",
                "latest_digital_walkthrough": "DWS-TEST-0001",
                "digital_walkthrough_status": "Submitted",
            }
        )
        submission = FakeSaveDoc({"name": "DWS-TEST-0001", "status": "Submitted"})

        def fake_get_doc(*args, **kwargs):
            if args == ("Opportunity", "CRM-OPP-TEST-0001"):
                return opp
            if args == ("Digital Walkthrough Submission", "DWS-TEST-0001"):
                return submission
            raise AssertionError(f"Unexpected get_doc call: args={args}, kwargs={kwargs}")

        mock_get_doc.side_effect = fake_get_doc
        mock_get_all.return_value = []

        public_quote.mark_opportunity_reviewed_on_quotation(FakeDoc({"opportunity": "CRM-OPP-TEST-0001"}))

        self.assertEqual(opp.status, "Quotation")
        self.assertEqual(opp.digital_walkthrough_status, "Reviewed")
        self.assertTrue(opp.save_called)
        self.assertEqual(submission.status, "Reviewed")
        self.assertTrue(submission.save_called)

    @patch.object(portal, "get_quote_row")
    def test_get_public_quote_access_result_rejects_invalid_token(self, mock_get_quote_row):
        mock_get_quote_row.return_value = {
            "name": "SAL-QTN-TEST-0001",
            "custom_accept_token": "expected-token",
            "custom_accept_token_expires_on": "2099-01-01 00:00:00",
            "docstatus": 1,
            "status": "Open",
            "quotation_to": "Lead",
            "party_name": "CRM-LEAD-TEST-0001",
        }

        result = public_quote.get_public_quote_access_result(
            quote_name="SAL-QTN-TEST-0001",
            token="bad-token",
        )

        self.assertEqual(result["state"], "invalid")
        self.assertIn("no longer valid", result["message"])

    @patch.object(portal, "now_datetime", return_value=public_quote.get_datetime("2026-05-01 00:00:00"))
    @patch.object(portal, "get_quote_row")
    def test_get_public_quote_access_result_rejects_expired_quote(self, mock_get_quote_row, _mock_now_datetime):
        mock_get_quote_row.return_value = {
            "name": "SAL-QTN-TEST-0001",
            "custom_accept_token": "expected-token",
            "custom_accept_token_expires_on": "2026-04-30 23:59:59",
            "docstatus": 1,
            "status": "Open",
            "quotation_to": "Lead",
            "party_name": "CRM-LEAD-TEST-0001",
        }

        result = public_quote.get_public_quote_access_result(
            quote_name="SAL-QTN-TEST-0001",
            token="expected-token",
        )

        self.assertEqual(result["state"], "expired")
        self.assertIn("has expired", result["message"])

    @patch.object(payloads, "get_building_row", return_value={})
    @patch.object(payloads, "get_sales_order_row", return_value={})
    @patch.object(
        payloads,
        "get_lead_row",
        return_value={
            "first_name": "Patten",
            "last_name": "Whiting",
            "company_name": "Pikt Inc",
            "email_id": "lead@example.com",
        },
    )
    @patch.object(portal, "load_review_items", return_value=[{"item_code": "ITEM-1", "qty": 1}])
    @patch.object(
        portal,
        "get_public_quote_access_result",
        return_value={
            "state": "ready",
            "message": "",
            "row": {
                "name": "SAL-QTN-TEST-0001",
                "quotation_to": "Lead",
                "party_name": "CRM-LEAD-TEST-0001",
                "contact_email": "lead@example.com",
                "customer_name": "Pikt Inc",
                "currency": "USD",
                "grand_total": 1250,
                "rounded_total": 1250,
                "transaction_date": "2026-03-22",
                "valid_till": "2026-04-21",
                "terms": "Net 30",
                "custom_accepted_sales_order": "",
            },
        },
    )
    def test_validate_public_quote_ready_payload_matches_contract(
        self,
        _mock_access_result,
        _mock_items,
        _mock_lead_row,
        _mock_sales_order_row,
        _mock_building_row,
    ):
        result = public_quote.validate_public_quote(
            quote="SAL-QTN-TEST-0001",
            token="expected-token",
        )

        self.assertEqual(
            result,
            {
                "state": "ready",
                "message": "",
                "quote": "SAL-QTN-TEST-0001",
                "lead": "CRM-LEAD-TEST-0001",
                "company_name": "Pikt Inc",
                "contact_name": "Patten Whiting",
                "contact_email": "lead@example.com",
                "currency": "USD",
                "grand_total": 1250,
                "rounded_total": 1250,
                "transaction_date": "2026-03-22",
                "valid_till": "2026-04-21",
                "terms": "Net 30",
                "sales_order": "",
                "initial_invoice": "",
                "billing_setup_completed_on": "",
                "billing_recipient_email": "",
                "building": "",
                "building_name": "",
                "service_address_line_1": "",
                "service_address_line_2": "",
                "service_city": "",
                "service_state": "",
                "service_postal_code": "",
                "access_method": "",
                "access_entrance": "",
                "access_entry_details": "",
                "has_alarm_system": "No",
                "alarm_instructions": "",
                "allowed_entry_time": "",
                "primary_site_contact": "",
                "lockout_emergency_contact": "",
                "key_fob_handoff_details": "",
                "areas_to_avoid": "",
                "closing_instructions": "",
                "parking_elevator_notes": "",
                "first_service_notes": "",
                "access_details_confirmed": 0,
                "access_details_completed_on": "",
                "items": [{"item_code": "ITEM-1", "qty": 1}],
            },
        )

    @patch.object(acceptance, "get_customer_row", return_value={"customer_primary_contact": "CONTACT-1", "customer_primary_address": "ADDR-1", "email_id": "billing@example.com"})
    @patch.object(public_quote.frappe, "get_doc")
    def test_build_sales_order_copies_item_and_tax_linkage(self, mock_get_doc, _mock_customer_row):
        created_docs = []

        def fake_get_doc(payload):
            doc = FakeSaveDoc({**payload, "docstatus": 0})
            created_docs.append(doc)
            return doc

        mock_get_doc.side_effect = fake_get_doc

        result = public_quote.build_sales_order(
            {
                "name": "SAL-QTN-TEST-0001",
                "company": "Pikt, inc.",
                "order_type": "Sales",
                "currency": "USD",
                "conversion_rate": 1,
                "selling_price_list": "Standard Selling",
                "price_list_currency": "USD",
                "plc_conversion_rate": 1,
                "taxes_and_charges": "SALES-TAX",
                "terms": "Net 30",
                "contact_email": "quote@example.com",
                "custom_building": "BLDG-1",
                "valid_till": "2026-04-21",
            },
            [
                {
                    "name": "QTI-1",
                    "item_code": "ITEM-1",
                    "qty": 2,
                    "rate": 350,
                    "warehouse": "",
                    "uom": "Each",
                    "stock_uom": "Each",
                    "conversion_factor": 1,
                    "description": "Service item",
                    "item_tax_template": "ITEM-TAX",
                    "item_tax_rate": "{\"VAT\": 7}",
                }
            ],
            [
                {
                    "charge_type": "On Net Total",
                    "row_id": 1,
                    "account_head": "Tax - PI",
                    "description": "Sales Tax",
                    "rate": 7,
                    "tax_amount": 49,
                    "tax_amount_after_discount_amount": 49,
                    "total": 749,
                }
            ],
            "CUST-TEST-0001",
        )

        sales_order_doc = created_docs[0]
        self.assertTrue(sales_order_doc.insert_called)
        self.assertTrue(sales_order_doc.submit_called)
        self.assertEqual(result, sales_order_doc)
        self.assertEqual(sales_order_doc["items"][0]["prevdoc_docname"], "SAL-QTN-TEST-0001")
        self.assertEqual(sales_order_doc["items"][0]["quotation_item"], "QTI-1")
        self.assertEqual(sales_order_doc["items"][0]["warehouse"], public_quote.DEFAULT_WAREHOUSE)
        self.assertEqual(sales_order_doc["taxes"][0]["account_head"], "Tax - PI")

    @patch.object(acceptance, "build_accept_payload", side_effect=lambda *args, **kwargs: {"args": args, "kwargs": kwargs})
    @patch.object(acceptance, "mark_opportunity_converted")
    @patch.object(acceptance, "load_accept_items", return_value=[{"name": "QTI-1"}])
    @patch.object(
        acceptance,
        "get_public_quote_access_result",
        return_value={
            "state": "accepted",
            "message": "This quotation has already been accepted.",
            "row": {"name": "SAL-QTN-TEST-0001", "opportunity": "CRM-OPP-TEST-0001"},
            "sales_order": "SO-TEST-0001",
        },
    )
    def test_accept_public_quote_reuses_existing_sales_order(
        self,
        _mock_access_result,
        _mock_items,
        mock_mark_converted,
        _mock_build_payload,
    ):
        result = public_quote.accept_public_quote(
            quote="SAL-QTN-TEST-0001",
            token="expected-token",
        )

        mock_mark_converted.assert_called_once_with("CRM-OPP-TEST-0001")
        self.assertEqual(result["args"][0], "accepted")
        self.assertEqual(result["kwargs"]["sales_order_name"], "SO-TEST-0001")

    @patch.object(acceptance, "build_accept_payload", side_effect=lambda *args, **kwargs: {"args": args, "kwargs": kwargs})
    @patch.object(acceptance, "mark_opportunity_converted")
    @patch.object(acceptance, "build_sales_order", return_value=SimpleNamespace(name="SO-TEST-0001"))
    @patch.object(acceptance, "load_quote_taxes", return_value=[{"account_head": "Tax - PI"}])
    @patch.object(acceptance, "load_accept_items", return_value=[{"name": "QTI-1"}])
    @patch.object(acceptance, "ensure_customer", return_value="CUST-TEST-0001")
    @patch.object(acceptance, "get_lead_row", return_value={"company_name": "Pikt Inc", "email_id": "lead@example.com"})
    @patch.object(acceptance, "get_quote_row")
    @patch.object(public_quote.frappe.db, "set_value")
    @patch.object(public_quote.frappe.db, "get_value", side_effect=["Pikt Inc", ""])
    @patch.object(
        acceptance,
        "get_public_quote_access_result",
        return_value={
            "state": "ready",
            "message": "",
            "row": {
                "name": "SAL-QTN-TEST-0001",
                "quotation_to": "Lead",
                "party_name": "CRM-LEAD-TEST-0001",
                "opportunity": "CRM-OPP-TEST-0001",
            },
        },
    )
    def test_accept_public_quote_converts_lead_and_creates_sales_order(
        self,
        _mock_access_result,
        _mock_db_get_value,
        mock_db_set_value,
        mock_get_quote_row,
        _mock_get_lead_row,
        _mock_ensure_customer,
        _mock_load_items,
        _mock_load_taxes,
        _mock_build_sales_order,
        mock_mark_converted,
        _mock_build_payload,
    ):
        mock_get_quote_row.side_effect = [
            {
                "name": "SAL-QTN-TEST-0001",
                "quotation_to": "Customer",
                "party_name": "CUST-TEST-0001",
                "opportunity": "CRM-OPP-TEST-0001",
                "custom_accepted_sales_order": "",
            },
            {
                "name": "SAL-QTN-TEST-0001",
                "quotation_to": "Customer",
                "party_name": "CUST-TEST-0001",
                "opportunity": "CRM-OPP-TEST-0001",
                "custom_accepted_sales_order": "SO-TEST-0001",
            },
        ]

        result = public_quote.accept_public_quote(
            quote="SAL-QTN-TEST-0001",
            token="expected-token",
        )

        self.assertEqual(result["args"][0], "accepted")
        self.assertEqual(result["kwargs"]["sales_order_name"], "SO-TEST-0001")
        mock_mark_converted.assert_called_once_with("CRM-OPP-TEST-0001")
        self.assertEqual(mock_db_set_value.call_count, 2)
        self.assertEqual(mock_db_set_value.call_args_list[0].args[0], "Quotation")
        self.assertEqual(mock_db_set_value.call_args_list[1].args[0], "Quotation")
        self.assertEqual(mock_db_set_value.call_args_list[0].args[2]["quotation_to"], "Customer")
        self.assertEqual(mock_db_set_value.call_args_list[1].args[2]["custom_accepted_sales_order"], "SO-TEST-0001")

    @patch.object(payloads, "build_accept_payload", side_effect=lambda *args, **kwargs: {"args": args, "kwargs": kwargs})
    @patch.object(acceptance, "build_accept_payload", side_effect=lambda *args, **kwargs: {"args": args, "kwargs": kwargs})
    @patch.object(acceptance, "mark_opportunity_converted")
    @patch.object(acceptance, "build_sales_order", side_effect=RuntimeError("duplicate submit"))
    @patch.object(acceptance, "load_quote_taxes", return_value=[{"account_head": "Tax - PI"}])
    @patch.object(acceptance, "load_accept_items", return_value=[{"name": "QTI-1"}])
    @patch.object(payloads, "load_accept_items", return_value=[{"name": "QTI-1"}])
    @patch.object(payloads, "get_quote_row")
    @patch.object(acceptance, "get_quote_row")
    @patch.object(public_quote.frappe.db, "get_value", return_value="")
    @patch.object(public_quote.frappe.db, "exists")
    @patch.object(
        acceptance,
        "get_public_quote_access_result",
        return_value={
            "state": "ready",
            "message": "",
            "row": {
                "name": "SAL-QTN-TEST-0001",
                "quotation_to": "Customer",
                "party_name": "CUST-TEST-0001",
                "opportunity": "CRM-OPP-TEST-0001",
            },
        },
    )
    def test_accept_public_quote_returns_existing_sales_order_after_retry_race(
        self,
        _mock_access_result,
        mock_exists,
        _mock_db_get_value,
        mock_get_quote_row,
        mock_get_quote_row_payloads,
        _mock_payload_items,
        _mock_load_items,
        _mock_load_taxes,
        _mock_build_sales_order,
        mock_mark_converted,
        _mock_build_payload,
        _mock_payload_build,
    ):
        def exists_side_effect(doctype, name=None):
            if doctype == "Customer" and (name or "") == "CUST-TEST-0001":
                return True
            if doctype == "Sales Order" and (name or "") == "SO-TEST-0002":
                return True
            if doctype == "Sales Order":
                return False
            return False

        mock_exists.side_effect = exists_side_effect
        mock_get_quote_row.side_effect = [
            {
                "name": "SAL-QTN-TEST-0001",
                "quotation_to": "Customer",
                "party_name": "CUST-TEST-0001",
                "opportunity": "CRM-OPP-TEST-0001",
                "custom_accepted_sales_order": "",
            },
            {
                "name": "SAL-QTN-TEST-0001",
                "quotation_to": "Customer",
                "party_name": "CUST-TEST-0001",
                "opportunity": "CRM-OPP-TEST-0001",
                "custom_accepted_sales_order": "SO-TEST-0002",
            },
        ]
        mock_get_quote_row_payloads.return_value = {
            "name": "SAL-QTN-TEST-0001",
            "quotation_to": "Customer",
            "party_name": "CUST-TEST-0001",
            "opportunity": "CRM-OPP-TEST-0001",
            "custom_accepted_sales_order": "SO-TEST-0002",
        }

        result = public_quote.accept_public_quote(
            quote="SAL-QTN-TEST-0001",
            token="expected-token",
        )

        self.assertEqual(result["args"][0], "accepted")
        self.assertEqual(result["kwargs"]["sales_order_name"], "SO-TEST-0002")
        mock_mark_converted.assert_called_once_with("CRM-OPP-TEST-0001")

    @patch.object(payloads, "get_active_template")
    @patch.object(payloads, "get_addendum_row")
    @patch.object(payloads, "get_active_master_agreement")
    @patch.object(payloads, "get_customer_row", return_value={"customer_name": "Pikt Inc"})
    def test_build_agreement_payload_stage_selection(
        self,
        _mock_customer_row,
        mock_active_master,
        mock_addendum,
        mock_template,
    ):
        row = {"name": "SAL-QTN-TEST-0001", "quotation_to": "Customer", "party_name": "CUST-TEST-0001"}
        sales_order_row = {"name": "SO-TEST-0001", "customer": "CUST-TEST-0001"}

        scenarios = [
            (
                "master",
                {},
                {},
                {"name": "MASTER-TPL", "template_type": "Master", "version": "1"},
                {
                    "agreement_mode": "master",
                    "agreement_step_complete": 0,
                    "billing_step_complete": 0,
                    "access_step_complete": 0,
                },
            ),
            (
                "addendum",
                {"name": "SA-0001", "status": "Active"},
                {},
                {"name": "ADD-TPL", "template_type": "Addendum", "version": "2"},
                {
                    "agreement_mode": "addendum",
                    "agreement_step_complete": 0,
                    "billing_step_complete": 0,
                    "access_step_complete": 0,
                },
            ),
            (
                "signed-pending",
                {"name": "SA-0001", "status": "Active"},
                {"name": "SAA-0001", "status": "Pending Billing", "term_model": "Month-to-month"},
                {},
                {
                    "agreement_mode": "signed",
                    "agreement_step_complete": 1,
                    "billing_step_complete": 0,
                    "access_step_complete": 0,
                },
            ),
            (
                "signed-complete",
                {"name": "SA-0001", "status": "Active"},
                {
                    "name": "SAA-0001",
                    "status": "Active",
                    "term_model": "Fixed",
                    "fixed_term_months": "12",
                    "billing_completed_on": "2026-03-22",
                    "access_completed_on": "2026-03-23",
                },
                {},
                {
                    "agreement_mode": "signed",
                    "agreement_step_complete": 1,
                    "billing_step_complete": 1,
                    "access_step_complete": 1,
                },
            ),
        ]

        for label, active_master, addendum, template, expected in scenarios:
            with self.subTest(label=label):
                mock_active_master.return_value = active_master
                mock_addendum.return_value = addendum
                mock_template.return_value = template

                result = public_quote.build_agreement_payload(row, sales_order_row)

                self.assertEqual(result["agreement_mode"], expected["agreement_mode"])
                self.assertEqual(result["agreement_step_complete"], expected["agreement_step_complete"])
                self.assertEqual(result["billing_step_complete"], expected["billing_step_complete"])
                self.assertEqual(result["access_step_complete"], expected["access_step_complete"])

    @patch.object(acceptance, "get_customer_row", return_value={"lead_name": "", "email_id": ""})
    @patch.object(acceptance, "find_customer_for_quote", side_effect=["", "CUST-EXISTING"])
    @patch.object(public_quote.frappe, "get_doc", return_value=FailingInsertDoc({"doctype": "Customer"}))
    @patch.object(public_quote.frappe.db, "set_value")
    @patch.object(public_quote.frappe.db, "exists", return_value=True)
    def test_ensure_customer_reuses_existing_customer_after_insert_race(
        self,
        _mock_exists,
        mock_set_value,
        _mock_get_doc,
        _mock_find_customer,
        _mock_get_customer_row,
    ):
        result = public_quote.ensure_customer(
            {"party_name": "CRM-LEAD-TEST-0001", "contact_email": "lead@example.com"},
            {"company_name": "Pikt Inc", "email_id": "lead@example.com"},
        )

        self.assertEqual(result, "CUST-EXISTING")
        mock_set_value.assert_called_once_with(
            "Customer",
            "CUST-EXISTING",
            {"lead_name": "CRM-LEAD-TEST-0001", "email_id": "lead@example.com"},
            update_modified=False,
        )
