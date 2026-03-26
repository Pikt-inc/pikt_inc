from __future__ import annotations

import unittest

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc.services import public_quote
from pikt_inc.services.public_quote import (
    acceptance,
    access_setup,
    agreements,
    billing,
)
from pikt_inc.services.public_quote.models import (
    AccessSetupInput,
    AgreementSignatureInput,
    BillingSetupInput,
)


class TestPublicQuotePackage(unittest.TestCase):
    def test_facade_exports_stage_entrypoints(self):
        self.assertIs(public_quote.prepare_public_quotation_acceptance, acceptance.prepare_public_quotation_acceptance)
        self.assertIs(public_quote.accept_public_quote, acceptance.accept_public_quote)
        self.assertIs(
            public_quote.complete_public_service_agreement_signature,
            agreements.complete_public_service_agreement_signature,
        )
        self.assertIs(
            public_quote.complete_public_quote_billing_setup_v2,
            billing.complete_public_quote_billing_setup_v2,
        )
        self.assertIs(
            public_quote.complete_public_quote_access_setup_v2,
            access_setup.complete_public_quote_access_setup_v2,
        )

    def test_agreement_signature_input_normalizes_request_values(self):
        public_quote.frappe.form_dict = {
            "quote": " SAL-QTN-0001 ",
            "token": " token-1 ",
            "signer_name": " Patten Whiting ",
            "signer_title": " Owner ",
            "signer_email": " TEST@EXAMPLE.COM ",
            "assent_confirmed": "yes",
            "term_model": " Fixed ",
            "fixed_term_months": " 6 ",
            "start_date": " 2026-04-01 ",
        }

        payload = AgreementSignatureInput.from_request()

        self.assertEqual(payload.quote, "SAL-QTN-0001")
        self.assertEqual(payload.token, "token-1")
        self.assertEqual(payload.signer_email, "test@example.com")
        self.assertEqual(payload.assent_confirmed, 1)
        self.assertEqual(payload.fixed_term_months, "6")

    def test_billing_and_access_inputs_normalize_request_values(self):
        public_quote.frappe.form_dict = {
            "quote": " SAL-QTN-0001 ",
            "token": " token-1 ",
            "billing_contact_name": " Patten Whiting ",
            "billing_email": " BILLING@EXAMPLE.COM ",
            "billing_address_line_1": " 123 Main ",
            "billing_city": " Dallas ",
            "billing_state": " TX ",
            "billing_postal_code": " 75001 ",
            "billing_country": " United States ",
            "service_address_line_1": " 123 Main ",
            "service_city": " Dallas ",
            "service_state": " TX ",
            "service_postal_code": " 75001 ",
            "access_method": " Door code / keypad ",
            "access_entrance": " Front ",
            "access_details_confirmed": "true",
        }

        billing_payload = BillingSetupInput.from_request()
        access_payload = AccessSetupInput.from_request()

        self.assertEqual(billing_payload.billing_email, "billing@example.com")
        self.assertEqual(billing_payload.billing_country, "United States")
        self.assertEqual(access_payload.access_method, "Door code / keypad")
        self.assertEqual(access_payload.access_details_confirmed, 1)
