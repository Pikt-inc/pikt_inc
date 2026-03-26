from __future__ import annotations

import unittest
from unittest.mock import patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc.services.public_quote.models import PublicQuoteSmokeArtifacts
from pikt_inc.services.public_quote import qa


class TestPublicQuoteSmoke(unittest.TestCase):
    def test_resolve_public_quote_smoke_config_generates_defaults(self):
        config = qa.resolve_public_quote_smoke_config(smoke_id="20260326123045")

        self.assertEqual(config.smoke_id, "20260326123045")
        self.assertEqual(config.prospect_name, "QA Portal Smoke 20260326123045")
        self.assertEqual(config.prospect_company, "QA Portal Smoke Customer 20260326123045")
        self.assertEqual(config.contact_email, "qa.portal.smoke.20260326123045@example.com")
        self.assertEqual(config.billing_email, "billing.portal.smoke.20260326123045@example.com")
        self.assertEqual(config.signer_email, "qa.portal.smoke.20260326123045@example.com")

    @patch.object(qa, "cleanup_public_quote_smoke_records", return_value={"deleted": ["Quotation/SAL-QTN-0001"], "missing": [], "errors": []})
    @patch.object(qa, "get_customer_row", return_value={"customer_primary_contact": "CONTACT-0001", "customer_primary_address": "ADDR-0001"})
    @patch.object(qa, "get_sales_order_row", return_value={"customer": "CUST-0001"})
    @patch.object(qa, "complete_public_quote_access_setup_v2", side_effect=[{"status": "ok", "building": "BLDG-0001"}, {"status": "ok", "building": "BLDG-0001"}])
    @patch.object(qa, "complete_public_quote_billing_setup_v2", side_effect=[{"status": "ok", "invoice": "SINV-0001", "auto_repeat": "AR-0001", "service_agreement": "SA-0001", "addendum": "SAA-0001"}, {"status": "ok", "invoice": "SINV-0001", "auto_repeat": "AR-0001", "service_agreement": "SA-0001", "addendum": "SAA-0001"}])
    @patch.object(qa, "complete_public_service_agreement_signature", return_value={"status": "ok", "service_agreement": "SA-0001", "addendum": "SAA-0001", "addendum_status": "Pending Billing"})
    @patch.object(qa, "load_public_quote_portal_state", return_value={"state": "accepted", "quote": "SAL-QTN-0001", "sales_order": "SO-0001"})
    @patch.object(qa, "accept_public_quote", return_value={"status": "accepted", "quote": "SAL-QTN-0001", "sales_order": "SO-0001", "portal": {}})
    @patch.object(qa, "validate_public_quote", return_value={"state": "ready", "quote": "SAL-QTN-0001"})
    @patch.object(qa, "create_public_quote_smoke_artifacts", return_value=PublicQuoteSmokeArtifacts(lead="LEAD-0001", opportunity="OPP-0001", quote="SAL-QTN-0001", token="token-1"))
    def test_run_public_quote_smoke_test_orchestrates_and_cleans_up(
        self,
        _mock_artifacts,
        _mock_validate,
        _mock_accept,
        _mock_portal_state,
        _mock_agreement,
        mock_billing,
        mock_access,
        _mock_sales_order_row,
        _mock_customer_row,
        mock_cleanup,
    ):
        result = qa.run_public_quote_smoke_test(smoke_id="20260326123045", cleanup=True)

        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["cleanup_performed"])
        self.assertEqual(result["artifacts"]["sales_order"], "SO-0001")
        self.assertEqual(result["artifacts"]["invoice"], "SINV-0001")
        self.assertEqual(result["artifacts"]["building"], "BLDG-0001")
        self.assertEqual(mock_billing.call_count, 2)
        self.assertEqual(mock_access.call_count, 2)
        mock_cleanup.assert_called_once()

    @patch.object(qa, "raw_purge_public_quote_smoke_doc", side_effect=lambda doctype, name: ("deleted", name))
    @patch.object(qa, "delete_public_quote_smoke_doc")
    @patch.object(qa, "set_public_quote_smoke_backlinks")
    @patch.object(qa.frappe.db, "exists", return_value=True)
    def test_cleanup_public_quote_smoke_records_falls_back_to_raw_purge_for_submitted_cycle(
        self,
        _mock_exists,
        _mock_set_backlinks,
        mock_delete_doc,
        mock_raw_purge,
    ):
        mock_delete_doc.side_effect = [
            Exception("invoice linked"),
            Exception("sales order linked"),
            Exception("quotation linked"),
        ]
        artifacts = PublicQuoteSmokeArtifacts(
            quote="SAL-QTN-0001",
            sales_order="SO-0001",
            invoice="SINV-0001",
        )

        result = qa.cleanup_public_quote_smoke_records(artifacts)

        self.assertEqual(
            [call.args[:2] for call in mock_raw_purge.call_args_list],
            [
                ("Sales Invoice", "SINV-0001"),
                ("Sales Order", "SO-0001"),
                ("Quotation", "SAL-QTN-0001"),
            ],
        )
        self.assertEqual(
            result["deleted"],
            [
                "Sales Invoice/SINV-0001",
                "Sales Order/SO-0001",
                "Quotation/SAL-QTN-0001",
            ],
        )
        self.assertEqual(result["errors"], [])

    @patch.object(qa, "delete_public_quote_smoke_doc", side_effect=lambda doctype, name, cancel_first=False: ("deleted", name))
    @patch.object(qa, "set_public_quote_smoke_backlinks")
    @patch.object(qa.frappe.db, "exists", return_value=True)
    def test_cleanup_public_quote_smoke_records_uses_dependency_order(
        self,
        _mock_exists,
        mock_set_backlinks,
        mock_delete_doc,
    ):
        artifacts = PublicQuoteSmokeArtifacts(
            lead="LEAD-0001",
            opportunity="OPP-0001",
            quote="SAL-QTN-0001",
            sales_order="SO-0001",
            invoice="SINV-0001",
            auto_repeat="AR-0001",
            building="BLDG-0001",
            service_agreement="SA-0001",
            addendum="SAA-0001",
            contact="CONTACT-0001",
            address="ADDR-0001",
            customer="CUST-0001",
        )

        result = qa.cleanup_public_quote_smoke_records(artifacts)

        self.assertEqual(
            [call.args[:2] for call in mock_delete_doc.call_args_list],
            [
                ("Auto Repeat", "AR-0001"),
                ("Sales Invoice", "SINV-0001"),
                ("Service Agreement Addendum", "SAA-0001"),
                ("Service Agreement", "SA-0001"),
                ("Building", "BLDG-0001"),
                ("Sales Order", "SO-0001"),
                ("Quotation", "SAL-QTN-0001"),
                ("Address", "ADDR-0001"),
                ("Contact", "CONTACT-0001"),
                ("Customer", "CUST-0001"),
                ("Opportunity", "OPP-0001"),
                ("Lead", "LEAD-0001"),
            ],
        )
        self.assertEqual(len(result["deleted"]), 12)
        self.assertEqual(mock_set_backlinks.call_count, 3)


if __name__ == "__main__":
    unittest.main()
