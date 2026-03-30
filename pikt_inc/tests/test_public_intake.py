from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc.services import public_intake
from pikt_inc.services.contracts import public_intake as public_intake_contracts


class FakeDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


class FakeInsertDoc(FakeDoc):
    def __init__(
        self,
        *args,
        generated_name="CRM-OPP-TEST-0001",
        before_insert=None,
        on_insert=None,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.generated_name = generated_name
        self.before_insert = before_insert
        self.on_insert = on_insert
        self.insert_called = False
        self.insert_completed = False
        self.save_called = False

    def insert(self, ignore_permissions=False):
        self.insert_called = True
        if callable(self.before_insert):
            self.before_insert(self)
        self.name = self.get("name") or self.generated_name
        if callable(self.on_insert):
            self.on_insert(self)
        self.insert_completed = True
        return self

    def save(self, ignore_permissions=False):
        self.save_called = True
        return self


class FakeUploadedFile:
    def __init__(self, filename, content):
        self.filename = filename
        self._content = content

    def read(self):
        return self._content


class TestPublicIntake(unittest.TestCase):
    def test_quote_request_contract_normalizes_payload(self):
        payload = public_intake_contracts.InstantQuoteRequestInput.model_validate(
            {
                "prospect_name": "  Patten Whiting  ",
                "phone": " 555-0100 ",
                "contact_email": " PATTEN@EXAMPLE.COM ",
                "prospect_company": " Pikt ",
                "building_type": "Office",
                "building_size": "1,500",
                "service_frequency": "3x/week",
                "service_interest": "Recurring standard cleaning",
                "bathroom_count_range": "1-2",
            }
        )

        self.assertEqual(payload.prospect_name, "Patten Whiting")
        self.assertEqual(payload.contact_email, "patten@example.com")
        self.assertEqual(payload.building_size, 1500)
        self.assertEqual(payload.bathroom_count_range.value, "Light")

    def test_walkthrough_upload_contract_requires_file(self):
        with self.assertRaisesRegex(Exception, "Please choose your walkthrough file before submitting."):
            public_intake_contracts.WalkthroughUploadInput.model_validate(
                {
                    "request": "IQR-2026-00001",
                    "token": "valid-token",
                    "uploaded": None,
                }
            )

    def test_normalize_bathroom_traffic_level(self):
        self.assertEqual(public_intake.normalize_bathroom_traffic_level("1-2"), "Light")
        self.assertEqual(public_intake.normalize_bathroom_traffic_level("medium"), "Medium")
        self.assertEqual(public_intake.normalize_bathroom_traffic_level("11+"), "Heavy")
        self.assertEqual(public_intake.normalize_bathroom_traffic_level(""), "None")

    def test_apply_instant_quote_pricing_sets_expected_fields(self):
        doc = FakeDoc(
            {
                "building_type": "Office",
                "service_frequency": "3x/week",
                "service_interest": "Recurring standard cleaning",
                "building_size": "1500",
                "bathroom_count_range": "1-2",
            }
        )

        result = public_intake.apply_instant_quote_pricing(doc)

        self.assertEqual(doc.bathroom_count_range, "Light")
        self.assertEqual(doc.custom_estimate_low, 600.0)
        self.assertEqual(doc.custom_estimate_high, 755.95)
        self.assertEqual(doc.opportunity_amount, 700.0)
        self.assertEqual(doc.risk_level, "Green")
        self.assertEqual(doc.status, "Open")
        self.assertEqual(doc.company, public_intake.DEFAULT_COMPANY)
        self.assertEqual(doc.currency, public_intake.DEFAULT_CURRENCY)
        self.assertEqual(doc.naming_series, "CRM-OPP-.YYYY.-")
        self.assertEqual(result["final_price"], 700.0)

    def test_normalize_instant_quote_request_doc_applies_contract_to_doc(self):
        doc = FakeDoc(
            {
                "prospect_name": "  Patten Whiting  ",
                "phone": " 555-0100 ",
                "contact_email": " PATTEN@EXAMPLE.COM ",
                "prospect_company": " Pikt ",
                "building_type": "Office",
                "building_size": "1,500",
                "service_frequency": "3x/week",
                "service_interest": "Recurring standard cleaning",
                "bathroom_count_range": "1-2",
            }
        )

        result = public_intake.normalize_instant_quote_request_doc(doc)

        self.assertEqual(result.prospect_name, "Patten Whiting")
        self.assertEqual(doc.prospect_name, "Patten Whiting")
        self.assertEqual(doc.contact_email, "patten@example.com")
        self.assertEqual(doc.building_size, "1500")
        self.assertEqual(doc.bathroom_count_range, "Light")
        self.assertEqual(doc.currency, "USD")

    def test_validate_public_funnel_opportunity_rejects_legacy_links(self):
        result = public_intake.validate_public_funnel_opportunity(
            opportunity="CRM-OPP-TEST-0001",
            token="expected-token",
        )

        self.assertEqual(result["valid"], 0)
        self.assertIn("no longer supported", result["message"])

    @patch.object(public_intake.tokens, "make_public_token", return_value="new-token")
    @patch.object(public_intake.intake, "add_to_date", return_value="2099-01-01 00:00:00")
    @patch.object(public_intake.intake, "now_datetime", return_value="2026-03-22 00:00:00")
    @patch.object(public_intake.intake, "nowdate", return_value="2026-03-22")
    @patch.object(public_intake.frappe, "get_doc")
    def test_create_instant_quote_opportunity_creates_new_request_and_opportunity(
        self,
        mock_get_doc,
        _mock_nowdate,
        _mock_now_datetime,
        _mock_add_to_date,
        _mock_make_public_token,
    ):
        counters = {"request": 0, "lead": 0, "opportunity": 0}
        created_docs = {"requests": [], "leads": [], "opportunities": []}

        def fake_get_doc(payload):
            doctype = payload.get("doctype")
            if doctype == "Instant Quote Request":
                counters["request"] += 1
                doc = FakeInsertDoc(
                    payload,
                    generated_name=f"IQR-2026-0000{counters['request']}",
                    before_insert=public_intake.prepare_instant_quote_request,
                )
                created_docs["requests"].append(doc)
                return doc
            if doctype == "Lead":
                counters["lead"] += 1
                doc = FakeInsertDoc(
                    payload,
                    generated_name=f"CRM-LEAD-TEST-000{counters['lead']}",
                )
                created_docs["leads"].append(doc)
                return doc
            if doctype == "Opportunity":
                counters["opportunity"] += 1
                doc = FakeInsertDoc(
                    payload,
                    generated_name=f"CRM-OPP-TEST-000{counters['opportunity']}",
                    on_insert=public_intake.apply_instant_quote_pricing,
                )
                created_docs["opportunities"].append(doc)
                return doc
            raise AssertionError(f"Unexpected get_doc payload: {payload}")

        mock_get_doc.side_effect = fake_get_doc

        result = public_intake.create_instant_quote_opportunity(
            {
                "prospect_name": "Patten Whiting",
                "phone": "555-0100",
                "contact_email": "patten@example.com",
                "prospect_company": "Pikt",
                "building_type": "Office",
                "building_size": "1500",
                "service_frequency": "3x/week",
                "service_interest": "Recurring standard cleaning",
                "bathroom_count_range": "1-2",
            }
        )

        request_doc = created_docs["requests"][0]
        lead_doc = created_docs["leads"][0]
        opportunity_doc = created_docs["opportunities"][0]

        self.assertTrue(request_doc.insert_called)
        self.assertTrue(request_doc.insert_completed)
        self.assertTrue(lead_doc.insert_called)
        self.assertTrue(opportunity_doc.insert_called)
        self.assertEqual(request_doc["lead"], "CRM-LEAD-TEST-0001")
        self.assertEqual(request_doc["opportunity"], "CRM-OPP-TEST-0001")
        self.assertEqual(
            result,
            {
                "request": "IQR-2026-00001",
                "name": "CRM-OPP-TEST-0001",
                "opp": "CRM-OPP-TEST-0001",
                "low": 600.0,
                "high": 755.95,
                "risk": "Green",
                "currency": "USD",
                "final_price": 700.0,
                "token": "new-token",
                "duplicate": 0,
            },
        )

    @patch.object(public_intake.tokens, "make_public_token", side_effect=["token-one", "token-two"])
    @patch.object(public_intake.intake, "add_to_date", return_value="2099-01-01 00:00:00")
    @patch.object(public_intake.intake, "now_datetime", return_value="2026-03-22 00:00:00")
    @patch.object(public_intake.intake, "nowdate", return_value="2026-03-22")
    @patch.object(public_intake.frappe, "get_doc")
    def test_create_instant_quote_opportunity_always_creates_new_internal_records(
        self,
        mock_get_doc,
        _mock_nowdate,
        _mock_now_datetime,
        _mock_add_to_date,
        _mock_make_public_token,
    ):
        counters = {"request": 0, "lead": 0, "opportunity": 0}

        def fake_get_doc(payload):
            doctype = payload.get("doctype")
            if doctype == "Instant Quote Request":
                counters["request"] += 1
                return FakeInsertDoc(
                    payload,
                    generated_name=f"IQR-2026-0000{counters['request']}",
                    before_insert=public_intake.prepare_instant_quote_request,
                )
            if doctype == "Lead":
                counters["lead"] += 1
                return FakeInsertDoc(payload, generated_name=f"CRM-LEAD-TEST-000{counters['lead']}")
            if doctype == "Opportunity":
                counters["opportunity"] += 1
                return FakeInsertDoc(
                    payload,
                    generated_name=f"CRM-OPP-TEST-000{counters['opportunity']}",
                    on_insert=public_intake.apply_instant_quote_pricing,
                )
            raise AssertionError(f"Unexpected get_doc payload: {payload}")

        mock_get_doc.side_effect = fake_get_doc
        payload = {
            "prospect_name": "Patten Whiting",
            "phone": "555-0100",
            "contact_email": "patten@example.com",
            "prospect_company": "Pikt",
            "building_type": "Office",
            "building_size": "1500",
            "service_frequency": "3x/week",
            "service_interest": "Recurring standard cleaning",
            "bathroom_count_range": "1-2",
        }

        first = public_intake.create_instant_quote_opportunity(payload)
        second = public_intake.create_instant_quote_opportunity(payload)

        self.assertEqual(first["request"], "IQR-2026-00001")
        self.assertEqual(second["request"], "IQR-2026-00002")
        self.assertEqual(first["opp"], "CRM-OPP-TEST-0001")
        self.assertEqual(second["opp"], "CRM-OPP-TEST-0002")
        self.assertEqual(first["token"], "token-one")
        self.assertEqual(second["token"], "token-two")

    @patch.object(public_intake.frappe.db, "get_value")
    def test_load_public_quote_request_state_accepts_valid_request_token(self, mock_get_value):
        mock_get_value.return_value = {
            "name": "IQR-2026-00001",
            "opportunity": "CRM-OPP-TEST-0001",
            "public_funnel_token": "expected-token",
            "public_funnel_token_expires_on": "2099-01-01 00:00:00",
            "estimate_low": 600,
            "estimate_high": 900,
            "risk_level": "Yellow",
            "currency": "USD",
            "final_price": 750,
        }

        result = public_intake.load_public_quote_request_state(
            request="IQR-2026-00001",
            token="expected-token",
        )

        self.assertEqual(
            result,
            {
                "valid": 1,
                "request": "IQR-2026-00001",
                "low": 600.0,
                "high": 900.0,
                "risk": "Yellow",
                "currency": "USD",
                "final_price": 750.0,
                "token": "expected-token",
            },
        )

    @patch.object(public_intake.frappe.db, "get_value")
    def test_load_public_quote_request_state_rejects_invalid_token(self, mock_get_value):
        mock_get_value.return_value = {
            "name": "IQR-2026-00001",
            "opportunity": "CRM-OPP-TEST-0001",
            "public_funnel_token": "expected-token",
            "public_funnel_token_expires_on": "2099-01-01 00:00:00",
            "estimate_low": 600,
            "estimate_high": 900,
            "risk_level": "Yellow",
            "currency": "USD",
            "final_price": 750,
        }

        result = public_intake.load_public_quote_request_state(
            request="IQR-2026-00001",
            token="bad-token",
        )

        self.assertEqual(result["valid"], 0)
        self.assertIn("no longer valid", result["message"])

    @patch.object(public_intake.walkthrough, "now", return_value="2026-03-22 00:00:00")
    @patch.object(
        public_intake.walkthrough.intake,
        "require_valid_public_quote_request",
        return_value={"name": "IQR-2026-00001", "opportunity": "CRM-OPP-TEST-0001"},
    )
    @patch.object(public_intake.frappe, "get_all")
    @patch.object(public_intake.frappe, "get_doc")
    def test_save_opportunity_walkthrough_upload_updates_opportunity(
        self,
        mock_get_doc,
        mock_get_all,
        _mock_require_valid,
        _mock_now,
    ):
        file_doc = FakeInsertDoc(
            {
                "doctype": "File",
                "file_url": "/private/files/walkthrough.pdf",
                "name": "FILE-TEST-0001",
            },
            generated_name="FILE-TEST-0001",
        )
        opportunity_doc = FakeInsertDoc({"doctype": "Opportunity", "name": "CRM-OPP-TEST-0001"})
        old_file_doc = MagicMock()

        def fake_get_doc(*args, **kwargs):
            if len(args) == 1 and isinstance(args[0], dict) and args[0].get("doctype") == "File":
                return file_doc
            if args == ("Opportunity", "CRM-OPP-TEST-0001"):
                return opportunity_doc
            if args == ("File", "FILE-OLD-0001"):
                return old_file_doc
            raise AssertionError(f"Unexpected get_doc call: args={args}, kwargs={kwargs}")

        mock_get_doc.side_effect = fake_get_doc
        mock_get_all.return_value = [
            {"name": "FILE-OLD-0001", "file_url": "/private/files/old.pdf"},
        ]

        result = public_intake.save_opportunity_walkthrough_upload(
            request="IQR-2026-00001",
            token="valid-token",
            uploaded=FakeUploadedFile("walkthrough.pdf", b"pdf-bytes"),
        )

        self.assertTrue(file_doc.save_called)
        self.assertTrue(opportunity_doc.save_called)
        self.assertEqual(result["request"], "IQR-2026-00001")
        self.assertEqual(result["digital_walkthrough_file"], "/private/files/walkthrough.pdf")
        self.assertEqual(result["digital_walkthrough_status"], "Submitted")
        self.assertEqual(result["digital_walkthrough_received_on"], "2026-03-22 00:00:00")
        old_file_doc.delete.assert_called_once_with(ignore_permissions=True)

    @patch.object(public_intake.tokens, "make_public_token", return_value="new-token")
    @patch.object(public_intake.intake, "add_to_date", return_value="2099-01-01 00:00:00")
    @patch.object(public_intake.intake, "now_datetime", return_value="2026-03-22 00:00:00")
    @patch.object(public_intake.intake, "nowdate", return_value="2026-03-22")
    @patch.object(public_intake.frappe, "log_error")
    @patch.object(public_intake.frappe, "get_doc")
    def test_create_instant_quote_request_aborts_when_opportunity_creation_fails(
        self,
        mock_get_doc,
        _mock_log_error,
        _mock_nowdate,
        _mock_now_datetime,
        _mock_add_to_date,
        _mock_make_public_token,
    ):
        class FailingInsertDoc(FakeInsertDoc):
            def insert(self, ignore_permissions=False):
                self.insert_called = True
                raise RuntimeError("boom")

        created_docs = {}

        def fake_get_doc(payload):
            doctype = payload.get("doctype")
            if doctype == "Instant Quote Request":
                doc = FakeInsertDoc(
                    payload,
                    generated_name="IQR-2026-00001",
                    before_insert=public_intake.prepare_instant_quote_request,
                )
                created_docs["request"] = doc
                return doc
            if doctype == "Lead":
                doc = FakeInsertDoc(payload, generated_name="CRM-LEAD-TEST-0001")
                created_docs["lead"] = doc
                return doc
            if doctype == "Opportunity":
                doc = FailingInsertDoc(payload, generated_name="CRM-OPP-TEST-0001")
                created_docs["opportunity"] = doc
                return doc
            raise AssertionError(f"Unexpected get_doc payload: {payload}")

        mock_get_doc.side_effect = fake_get_doc

        with self.assertRaisesRegex(Exception, "We could not create your estimate right now. Please try again."):
            public_intake.create_instant_quote_request(
                {
                    "prospect_name": "Patten Whiting",
                    "phone": "555-0100",
                    "contact_email": "patten@example.com",
                    "prospect_company": "Pikt",
                    "building_type": "Office",
                    "building_size": "1500",
                    "service_frequency": "3x/week",
                    "service_interest": "Recurring standard cleaning",
                    "bathroom_count_range": "1-2",
                }
            )

        self.assertTrue(created_docs["request"].insert_called)
        self.assertFalse(created_docs["request"].insert_completed)
        self.assertTrue(created_docs["lead"].insert_called)
        self.assertTrue(created_docs["opportunity"].insert_called)
