from __future__ import annotations

import importlib
from unittest import TestCase
from unittest.mock import patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()


try:
    contact_request = importlib.import_module("pikt_inc.services.contact_request")
    contact_request_api = importlib.import_module("pikt_inc.api.contact_request")
except ModuleNotFoundError:
    contact_request = importlib.import_module("pikt_inc.pikt_inc.services.contact_request")
    contact_request_api = importlib.import_module("pikt_inc.pikt_inc.api.contact_request")


class FakeLeadDoc:
    def __init__(self, payload):
        self.payload = payload
        self.name = "CRM-LEAD-TEST-0001"

    def insert(self, ignore_permissions=False):
        self.ignore_permissions = ignore_permissions
        return self


class TestContactRequest(TestCase):
    def test_submit_contact_request_maps_request_type_to_valid_lead_value(self):
        created_doc = None
        lead_payload = None
        fake_fields = []
        for field in (
            "lead_name",
            "first_name",
            "last_name",
            "email_id",
            "mobile_no",
            "company_name",
            "city",
            "service_interest",
            "source",
        ):
            fake_fields.append(type("DF", (), {"fieldname": field})())
        fake_fields.append(
            type(
                "DF",
                (),
                {
                    "fieldname": "request_type",
                    "options": "\n".join(
                        (
                            "Product Enquiry",
                            "Request for Information",
                            "Suggestions",
                            "Other",
                        )
                    ),
                },
            )()
        )
        fake_meta = type("Meta", (), {"fields": fake_fields})()

        def build_lead_doc(payload):
            nonlocal created_doc, lead_payload
            lead_payload = payload
            created_doc = FakeLeadDoc(payload)
            return created_doc

        with patch.object(contact_request.frappe, "get_meta", return_value=fake_meta, create=True), patch.object(
            contact_request.frappe, "get_doc", side_effect=build_lead_doc
        ):
            result = contact_request.submit_contact_request(
                first_name="Codex",
                last_name="Review",
                email_id="codex.review@example.com",
                mobile_no="5125550100",
                company_name="Codex Review LLC",
                city="Austin",
                request_type="Walkthrough request",
                message="Please tell me more about recurring service.",
            )

        self.assertEqual(result["status"], "submitted")
        self.assertEqual(result["lead"], "CRM-LEAD-TEST-0001")
        self.assertEqual(lead_payload["doctype"], "Lead")
        self.assertEqual(lead_payload["request_type"], "Product Enquiry")
        self.assertIn("Requested contact type: Walkthrough request", lead_payload["service_interest"])
        self.assertIn("Please tell me more about recurring service.", lead_payload["service_interest"])
        self.assertTrue(created_doc.ignore_permissions)

    def test_submit_contact_request_rejects_invalid_email(self):
        with self.assertRaisesRegex(Exception, "valid email"):
            contact_request.submit_contact_request(
                first_name="Codex",
                last_name="Review",
                email_id="not-an-email",
                company_name="Codex Review LLC",
                city="Austin",
                request_type="General service question",
                message="Please tell me more about recurring service.",
            )

    def test_api_wrapper_proxies_to_service(self):
        with patch.object(
            contact_request_api.contact_request_service,
            "submit_contact_request",
            return_value={"status": "submitted"},
        ) as submit_request:
            result = contact_request_api.submit_contact_request(first_name="Codex")

        self.assertEqual(result, {"status": "submitted"})
        submit_request.assert_called_once_with(form_dict={"first_name": "Codex"})
