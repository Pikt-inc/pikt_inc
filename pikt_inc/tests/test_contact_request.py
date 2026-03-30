from __future__ import annotations

import importlib
from unittest import TestCase
from unittest.mock import patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()


try:
    contact_request = importlib.import_module("pikt_inc.services.contact_request")
    contact_request_api = importlib.import_module("pikt_inc.api.contact_request")
    contact_contracts = importlib.import_module("pikt_inc.services.contracts.contact_request")
except ModuleNotFoundError:
    contact_request = importlib.import_module("pikt_inc.pikt_inc.services.contact_request")
    contact_request_api = importlib.import_module("pikt_inc.pikt_inc.api.contact_request")
    contact_contracts = importlib.import_module("pikt_inc.pikt_inc.services.contracts.contact_request")


class FakeContactRequestDoc:
    def __init__(self, payload):
        self.payload = payload
        self.name = "CR-2026-00001"
        self.ignore_permissions = False

    def insert(self, ignore_permissions=False):
        self.ignore_permissions = ignore_permissions
        return self


class ContactRequestDict(dict):
    __getattr__ = dict.get
    __setattr__ = dict.__setitem__


class TestContactRequest(TestCase):
    def test_contact_request_contract_normalizes_and_validates_email(self):
        payload = contact_contracts.ContactRequestInput.model_validate(
            {
                "first_name": " Codex ",
                "last_name": " Review ",
                "email_id": " CODEX.REVIEW@EXAMPLE.COM ",
                "company_name": " Codex Review LLC ",
                "city": " Austin ",
                "request_type": "Walkthrough request",
                "message": " Please tell me more. ",
            }
        )

        self.assertEqual(payload.first_name, "Codex")
        self.assertEqual(payload.email_id, "codex.review@example.com")
        self.assertEqual(payload.request_type.value, "Walkthrough request")

    def test_contact_request_contract_rejects_missing_required_field(self):
        with self.assertRaisesRegex(Exception, "Field required|at least 1 character"):
            contact_contracts.ContactRequestInput.model_validate(
                {
                    "last_name": "Review",
                    "email_id": "codex.review@example.com",
                    "company_name": "Codex Review LLC",
                    "city": "Austin",
                    "request_type": "Walkthrough request",
                    "message": "Please tell me more.",
                }
            )

    def test_prepare_contact_request_normalizes_doc_fields(self):
        doc = ContactRequestDict(
            first_name=" Codex ",
            last_name=" Review ",
            email_id=" CODEX.REVIEW@EXAMPLE.COM ",
            mobile_no=" 5125550100 ",
            company_name=" Codex Review LLC ",
            city=" Austin ",
            request_type="Walkthrough request",
            message=" Please tell me more about recurring service. ",
            request_status="",
        )

        contact_request.prepare_contact_request(doc)

        self.assertEqual(doc.first_name, "Codex")
        self.assertEqual(doc.last_name, "Review")
        self.assertEqual(doc.email_id, "codex.review@example.com")
        self.assertEqual(doc.mobile_no, "5125550100")
        self.assertEqual(doc.company_name, "Codex Review LLC")
        self.assertEqual(doc.city, "Austin")
        self.assertEqual(doc.request_type, "Walkthrough request")
        self.assertEqual(doc.message, "Please tell me more about recurring service.")
        self.assertEqual(doc.request_status, "New")

    def test_submit_contact_request_creates_contact_request_only(self):
        created_doc = None
        request_payload = None

        def build_contact_request_doc(payload):
            nonlocal created_doc, request_payload
            request_payload = payload
            created_doc = FakeContactRequestDoc(payload)
            return created_doc

        with patch.object(contact_request.frappe, "get_doc", side_effect=build_contact_request_doc):
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
        self.assertEqual(result["request"], "CR-2026-00001")
        self.assertEqual(request_payload["doctype"], "Contact Request")
        self.assertEqual(request_payload["request_type"], "Walkthrough request")
        self.assertEqual(request_payload["message"], "Please tell me more about recurring service.")
        self.assertEqual(request_payload["request_status"], "New")
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
