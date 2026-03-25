from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from pikt_inc.services import public_quote


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
        self.insert_called = False
        self.submit_called = False
        self.flags = SimpleNamespace()

    def insert(self, ignore_permissions=False):
        self.insert_called = True
        self.insert_ignore_permissions = ignore_permissions
        self.name = self.get("name") or self.get("agreement_name") or self.get("addendum_name") or "DOC-0001"
        return self

    def submit(self):
        self.submit_called = True
        self.docstatus = 1
        return self


class TestPublicQuotePortal(unittest.TestCase):
    @patch.object(public_quote, "link_quote_agreement_records")
    @patch.object(public_quote, "get_addendum_row")
    @patch.object(public_quote, "get_customer_row", return_value={"customer_name": "Pikt Inc"})
    @patch.object(public_quote, "get_sales_order_row", return_value={"name": "SO-0001", "customer": "CUST-0001"})
    @patch.object(
        public_quote,
        "ensure_quote_is_valid_for_portal_write",
        return_value={"name": "SAL-QTN-0001", "custom_accepted_sales_order": "SO-0001"},
    )
    @patch.object(public_quote.frappe.db, "exists", return_value=True)
    def test_complete_public_service_agreement_signature_reuses_existing_addendum(
        self,
        _mock_exists,
        _mock_valid_quote,
        _mock_sales_order,
        _mock_customer,
        mock_get_addendum,
        mock_link_records,
    ):
        mock_get_addendum.return_value = {
            "name": "SAA-0001",
            "service_agreement": "SA-0001",
            "status": "Pending Billing",
            "start_date": "2026-04-01",
            "end_date": "",
            "term_model": "Month-to-month",
            "fixed_term_months": "",
        }

        result = public_quote.complete_public_service_agreement_signature(
            quote="SAL-QTN-0001",
            token="token-1",
            signer_name="Patten Whiting",
            signer_title="Owner",
            signer_email="test@example.com",
            assent_confirmed=1,
            term_model="Month-to-month",
            start_date="2026-04-01",
        )

        self.assertEqual(
            result,
            {
                "status": "ok",
                "service_agreement": "SA-0001",
                "addendum": "SAA-0001",
                "addendum_status": "Pending Billing",
                "start_date": "2026-04-01",
                "end_date": "",
                "term_model": "Month-to-month",
                "fixed_term_months": "",
            },
        )
        mock_link_records.assert_called_once()

    @patch.object(public_quote, "render_template_html", side_effect=["MASTER HTML", "ADDENDUM HTML"])
    @patch.object(public_quote, "make_unique_name", side_effect=["SA-0001", "SAA-0001"])
    @patch.object(public_quote, "calculate_end_date", return_value="2026-10-01")
    @patch.object(public_quote, "get_user_agent", return_value="agent")
    @patch.object(public_quote, "get_request_ip", return_value="127.0.0.1")
    @patch.object(public_quote, "link_quote_agreement_records")
    @patch.object(public_quote, "get_active_template")
    @patch.object(public_quote, "get_active_master_agreement", return_value={})
    @patch.object(public_quote, "get_addendum_row", return_value={})
    @patch.object(public_quote, "get_customer_row", return_value={"customer_name": "Pikt Inc"})
    @patch.object(public_quote, "get_sales_order_row", return_value={"name": "SO-0001", "customer": "CUST-0001"})
    @patch.object(
        public_quote,
        "ensure_quote_is_valid_for_portal_write",
        return_value={"name": "SAL-QTN-0001", "custom_accepted_sales_order": "SO-0001"},
    )
    @patch.object(public_quote.frappe.db, "exists", return_value=True)
    @patch.object(public_quote.frappe, "get_doc")
    @patch.object(public_quote, "now_datetime", return_value="2026-03-23 10:00:00")
    def test_complete_public_service_agreement_signature_creates_master_and_addendum(
        self,
        _mock_now_datetime,
        mock_get_doc,
        _mock_exists,
        _mock_valid_quote,
        _mock_sales_order,
        _mock_customer,
        _mock_addendum,
        _mock_active_master,
        mock_templates,
        _mock_link_records,
        _mock_request_ip,
        _mock_user_agent,
        _mock_end_date,
        _mock_unique_name,
        _mock_render_html,
    ):
        mock_templates.side_effect = [
            {"name": "MASTER-TPL", "version": "1", "body_html": "master"},
            {"name": "ADD-TPL", "version": "2", "body_html": "addendum"},
        ]
        master_doc = FakeSaveDoc({"doctype": "Service Agreement", "name": "SA-0001"})
        addendum_doc = FakeSaveDoc({"doctype": "Service Agreement Addendum", "name": "SAA-0001"})
        mock_get_doc.side_effect = [master_doc, addendum_doc]

        result = public_quote.complete_public_service_agreement_signature(
            quote="SAL-QTN-0001",
            token="token-1",
            signer_name="Patten Whiting",
            signer_title="Owner",
            signer_email="test@example.com",
            assent_confirmed=1,
            term_model="Fixed",
            fixed_term_months="6",
            start_date="2026-04-01",
        )

        self.assertEqual(
            result,
            {
                "status": "ok",
                "service_agreement": "SA-0001",
                "addendum": "SAA-0001",
                "addendum_status": "Pending Billing",
                "start_date": "2026-04-01",
                "end_date": "2026-10-01",
                "term_model": "Fixed",
                "fixed_term_months": "6",
            },
        )
        self.assertTrue(master_doc.insert_called)
        self.assertTrue(addendum_doc.insert_called)

    @patch.object(public_quote, "update_addendum_after_billing", return_value="Pending Site Access")
    @patch.object(public_quote, "ensure_auto_repeat", return_value="AR-0001")
    @patch.object(public_quote, "update_invoice_links")
    @patch.object(public_quote, "ensure_sales_order_submitted", return_value=FakeDoc({"name": "SO-0001"}))
    @patch.object(public_quote, "update_sales_order_billing")
    @patch.object(public_quote, "sync_customer")
    @patch.object(public_quote, "ensure_address", return_value="ADDR-0001")
    @patch.object(public_quote, "ensure_contact", return_value="CONT-0001")
    @patch.object(public_quote, "get_customer_row", return_value={"customer_name": "Pikt Inc"})
    @patch.object(public_quote, "get_sales_order_row", return_value={"customer": "CUST-0001"})
    @patch.object(
        public_quote,
        "ensure_signed_addendum",
        return_value={"name": "SAA-0001", "service_agreement": "SA-0001", "initial_invoice": "SINV-0001"},
    )
    @patch.object(
        public_quote,
        "ensure_quote_is_valid_for_portal_write",
        return_value={"name": "SAL-QTN-0001", "custom_accepted_sales_order": "SO-0001"},
    )
    @patch.object(public_quote.frappe.db, "get_value", return_value="SINV-0001")
    @patch.object(public_quote.frappe.db, "exists")
    def test_complete_public_quote_billing_setup_v2_reuses_existing_invoice(
        self,
        mock_exists,
        _mock_get_value,
        _mock_valid_quote,
        _mock_addendum,
        _mock_sales_order,
        _mock_customer,
        _mock_contact,
        _mock_address,
        _mock_sync_customer,
        mock_update_sales_order_billing,
        _mock_submit_sales_order,
        _mock_update_invoice_links,
        _mock_auto_repeat,
        _mock_update_addendum,
    ):
        def exists_side_effect(doctype, name=None):
            if doctype == "Sales Order":
                return True
            if doctype == "Customer":
                return True
            if doctype == "Sales Invoice":
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        result = public_quote.complete_public_quote_billing_setup_v2(
            quote="SAL-QTN-0001",
            token="token-1",
            billing_contact_name="Patten Whiting",
            billing_email="billing@example.com",
            billing_address_line_1="123 Main",
            billing_city="Dallas",
            billing_state="TX",
            billing_postal_code="75001",
        )

        self.assertEqual(
            result,
            {
                "status": "ok",
                "quote": "SAL-QTN-0001",
                "sales_order": "SO-0001",
                "invoice": "SINV-0001",
                "auto_repeat": "AR-0001",
                "service_agreement": "SA-0001",
                "addendum": "SAA-0001",
                "addendum_status": "Pending Site Access",
            },
        )
        self.assertEqual(mock_update_sales_order_billing.call_count, 2)

    @patch.object(public_quote.frappe, "log_error")
    @patch.object(public_quote, "send_invoice_email", side_effect=RuntimeError("smtp down"))
    @patch.object(public_quote, "update_addendum_after_billing", return_value="Pending Site Access")
    @patch.object(public_quote, "ensure_auto_repeat", return_value="AR-0001")
    @patch.object(public_quote, "update_invoice_links")
    @patch.object(public_quote, "create_invoice_from_sales_order", return_value=FakeDoc({"name": "SINV-0002"}))
    @patch.object(public_quote, "ensure_sales_order_submitted", return_value=FakeDoc({"name": "SO-0001"}))
    @patch.object(public_quote, "update_sales_order_billing")
    @patch.object(public_quote, "sync_customer")
    @patch.object(public_quote, "ensure_address", return_value="ADDR-0001")
    @patch.object(public_quote, "ensure_contact", return_value="CONT-0001")
    @patch.object(public_quote, "get_customer_row", return_value={"customer_name": "Pikt Inc"})
    @patch.object(public_quote, "get_sales_order_row", return_value={"customer": "CUST-0001", "custom_initial_invoice": ""})
    @patch.object(
        public_quote,
        "ensure_signed_addendum",
        return_value={
            "name": "SAA-0001",
            "service_agreement": "SA-0001",
            "initial_invoice": "",
            "billing_completed_on": "",
        },
    )
    @patch.object(
        public_quote,
        "ensure_quote_is_valid_for_portal_write",
        return_value={"name": "SAL-QTN-0001", "custom_accepted_sales_order": "SO-0001"},
    )
    @patch.object(public_quote.frappe.db, "get_value", return_value="")
    @patch.object(public_quote.frappe.db, "exists")
    def test_complete_public_quote_billing_setup_v2_succeeds_when_invoice_email_fails(
        self,
        mock_exists,
        _mock_get_value,
        _mock_valid_quote,
        _mock_addendum,
        _mock_sales_order,
        _mock_customer,
        _mock_contact,
        _mock_address,
        _mock_sync_customer,
        _mock_update_sales_order_billing,
        _mock_submit_sales_order,
        _mock_create_invoice,
        _mock_update_invoice_links,
        _mock_auto_repeat,
        _mock_update_addendum,
        mock_send_invoice_email,
        mock_log_error,
    ):
        def exists_side_effect(doctype, name=None):
            if doctype in {"Sales Order", "Customer"}:
                return True
            return False

        mock_exists.side_effect = exists_side_effect

        result = public_quote.complete_public_quote_billing_setup_v2(
            quote="SAL-QTN-0001",
            token="token-1",
            billing_contact_name="Patten Whiting",
            billing_email="billing@example.com",
            billing_address_line_1="123 Main",
            billing_city="Dallas",
            billing_state="TX",
            billing_postal_code="75001",
        )

        self.assertEqual(
            result,
            {
                "status": "ok",
                "quote": "SAL-QTN-0001",
                "sales_order": "SO-0001",
                "invoice": "SINV-0002",
                "auto_repeat": "AR-0001",
                "service_agreement": "SA-0001",
                "addendum": "SAA-0001",
                "addendum_status": "Pending Site Access",
            },
        )
        mock_send_invoice_email.assert_called_once()
        mock_log_error.assert_called_once()

    @patch.object(public_quote, "doc_db_set_values")
    @patch.object(public_quote.frappe.db, "get_value", return_value="AR-0001")
    def test_ensure_auto_repeat_clears_empty_end_date_on_existing_record(
        self,
        _mock_get_value,
        mock_doc_db_set_values,
    ):
        result = public_quote.ensure_auto_repeat(
            "SINV-0001",
            "billing@example.com",
            {"start_date": "2026-04-01", "end_date": ""},
        )

        self.assertEqual(result, "AR-0001")
        self.assertEqual(mock_doc_db_set_values.call_count, 2)
        self.assertEqual(
            mock_doc_db_set_values.call_args_list[0].args,
            (
                "Auto Repeat",
                "AR-0001",
                {
                    "frequency": "Monthly",
                    "start_date": "2026-04-01",
                    "disabled": 0,
                    "submit_on_creation": 1,
                    "notify_by_email": 1,
                    "recipients": "billing@example.com",
                    "end_date": None,
                },
            ),
        )
        self.assertEqual(
            mock_doc_db_set_values.call_args_list[1].args,
            ("Sales Invoice", "SINV-0001", {"auto_repeat": "AR-0001"}),
        )

    @patch.object(public_quote, "fail", side_effect=RuntimeError("stop"))
    @patch.object(public_quote, "get_addendum_row", return_value={"name": "SAA-0001", "status": "Pending Billing"})
    @patch.object(public_quote, "get_sales_order_row", return_value={"docstatus": 1, "custom_initial_invoice": ""})
    @patch.object(
        public_quote,
        "ensure_quote_is_valid_for_portal_write",
        return_value={"name": "SAL-QTN-0001", "custom_accepted_sales_order": "SO-0001"},
    )
    @patch.object(public_quote.frappe.db, "exists", return_value=True)
    def test_complete_public_quote_access_setup_v2_requires_billing_first(
        self,
        _mock_exists,
        _mock_valid_quote,
        _mock_sales_order,
        _mock_addendum,
        mock_fail,
    ):
        with self.assertRaises(RuntimeError):
            public_quote.complete_public_quote_access_setup_v2(
                quote="SAL-QTN-0001",
                token="token-1",
                service_address_line_1="123 Main",
                service_city="Dallas",
                service_state="TX",
                service_postal_code="75001",
                access_method="Door code / keypad",
                access_entrance="Front",
                has_alarm_system="No",
                allowed_entry_time="After 6pm",
                primary_site_contact="Patten Whiting",
                access_details_confirmed=1,
            )

        self.assertEqual(
            mock_fail.call_args[0][0],
            "Complete billing setup before submitting access details.",
        )

    @patch.object(public_quote, "update_addendum_after_access", return_value="Active")
    @patch.object(public_quote, "update_sales_order_access_snapshot")
    @patch.object(public_quote, "update_linked_portal_records")
    @patch.object(public_quote, "create_or_update_building", return_value=("BLDG-0001", "2026-03-23 11:00:00"))
    @patch.object(
        public_quote,
        "get_addendum_row",
        return_value={
            "name": "SAA-0001",
            "status": "Pending Site Access",
            "initial_invoice": "SINV-0001",
            "billing_completed_on": "2026-03-23 10:00:00",
            "service_agreement": "SA-0001",
        },
    )
    @patch.object(public_quote, "get_sales_order_row", return_value={"docstatus": 1, "custom_initial_invoice": "SINV-0001"})
    @patch.object(
        public_quote,
        "ensure_quote_is_valid_for_portal_write",
        return_value={"name": "SAL-QTN-0001", "custom_accepted_sales_order": "SO-0001"},
    )
    @patch.object(public_quote.frappe.db, "exists", return_value=True)
    def test_complete_public_quote_access_setup_v2_returns_exact_success_contract(
        self,
        _mock_exists,
        _mock_valid_quote,
        _mock_sales_order,
        _mock_addendum,
        _mock_create_or_update_building,
        _mock_update_links,
        _mock_update_snapshot,
        _mock_update_addendum,
    ):
        result = public_quote.complete_public_quote_access_setup_v2(
            quote="SAL-QTN-0001",
            token="token-1",
            service_address_line_1="123 Main",
            service_city="Dallas",
            service_state="TX",
            service_postal_code="75001",
            access_method="Door code / keypad",
            access_entrance="Front",
            access_entry_details="Suite 100",
            has_alarm_system="No",
            allowed_entry_time="After 6pm",
            primary_site_contact="Patten Whiting",
            access_details_confirmed=1,
        )

        self.assertEqual(
            result,
            {
                "status": "ok",
                "quote": "SAL-QTN-0001",
                "sales_order": "SO-0001",
                "invoice": "SINV-0001",
                "building": "BLDG-0001",
                "service_agreement": "SA-0001",
                "addendum": "SAA-0001",
                "addendum_status": "Active",
                "access_completed_on": "2026-03-23 11:00:00",
            },
        )

    @patch.object(public_quote, "create_or_update_building")
    @patch.object(
        public_quote,
        "get_addendum_row",
        return_value={
            "name": "SAA-0001",
            "status": "Active",
            "initial_invoice": "SINV-0001",
            "billing_completed_on": "2026-03-23 10:00:00",
            "access_completed_on": "2026-03-23 11:00:00",
            "service_agreement": "SA-0001",
            "building": "BLDG-0001",
        },
    )
    @patch.object(
        public_quote,
        "get_sales_order_row",
        return_value={
            "docstatus": 1,
            "custom_initial_invoice": "SINV-0001",
            "custom_building": "BLDG-0001",
            "custom_access_details_completed_on": "2026-03-23 11:00:00",
        },
    )
    @patch.object(
        public_quote,
        "ensure_quote_is_valid_for_portal_write",
        return_value={"name": "SAL-QTN-0001", "custom_accepted_sales_order": "SO-0001"},
    )
    @patch.object(public_quote.frappe.db, "exists", return_value=True)
    def test_complete_public_quote_access_setup_v2_reuses_existing_completed_state(
        self,
        _mock_exists,
        _mock_valid_quote,
        _mock_sales_order,
        _mock_addendum,
        mock_create_or_update_building,
    ):
        result = public_quote.complete_public_quote_access_setup_v2(
            quote="SAL-QTN-0001",
            token="token-1",
            service_address_line_1="123 Main",
            service_city="Dallas",
            service_state="TX",
            service_postal_code="75001",
            access_method="Door code / keypad",
            access_entrance="Front",
            access_entry_details="Suite 100",
            has_alarm_system="No",
            allowed_entry_time="After 6pm",
            primary_site_contact="Patten Whiting",
            access_details_confirmed=1,
        )

        self.assertEqual(
            result,
            {
                "status": "ok",
                "quote": "SAL-QTN-0001",
                "sales_order": "SO-0001",
                "invoice": "SINV-0001",
                "building": "BLDG-0001",
                "service_agreement": "SA-0001",
                "addendum": "SAA-0001",
                "addendum_status": "Active",
                "access_completed_on": "2026-03-23 11:00:00",
            },
        )
        mock_create_or_update_building.assert_not_called()

    @patch.object(public_quote, "doc_db_set_values")
    @patch.object(public_quote.frappe.db, "exists", return_value=True)
    def test_create_or_update_building_reuses_existing_sales_order_building(
        self,
        _mock_exists,
        mock_db_set_values,
    ):
        building_name, completed_on = public_quote.create_or_update_building(
            {"custom_building": "BLDG-0001", "customer": "CUST-0001", "customer_name": "Pikt Inc"},
            "123 Main",
            "",
            "Dallas",
            "TX",
            "75001",
            "Door code / keypad",
            "Front",
            "Suite 100",
            "No",
            "",
            "After 6pm",
            "Patten Whiting",
            "",
            "",
            "",
            "",
            "",
            "",
            1,
            "SA-0001",
            "SAA-0001",
        )

        self.assertEqual(building_name, "BLDG-0001")
        self.assertTrue(completed_on)
        mock_db_set_values.assert_called_once()

    def test_build_billing_setup_response_matches_contract(self):
        self.assertEqual(
            public_quote.build_billing_setup_response(
                "SAL-QTN-0001",
                "SO-0001",
                "SINV-0001",
                "AR-0001",
                "SA-0001",
                "SAA-0001",
                "Pending Site Access",
            ),
            {
                "status": "ok",
                "quote": "SAL-QTN-0001",
                "sales_order": "SO-0001",
                "invoice": "SINV-0001",
                "auto_repeat": "AR-0001",
                "service_agreement": "SA-0001",
                "addendum": "SAA-0001",
                "addendum_status": "Pending Site Access",
            },
        )
