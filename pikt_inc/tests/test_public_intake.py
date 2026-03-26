from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc.services import public_intake


class FakeDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


class FakeInsertDoc(FakeDoc):
    def __init__(self, *args, generated_name="CRM-OPP-TEST-0001", on_insert=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.generated_name = generated_name
        self.on_insert = on_insert
        self.insert_called = False
        self.save_called = False

    def insert(self, ignore_permissions=False):
        self.insert_called = True
        if callable(self.on_insert):
            self.on_insert(self)
        self.name = self.get("name") or self.generated_name
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

    @patch.object(public_intake.frappe.db, "get_value")
    def test_validate_public_funnel_opportunity_rejects_invalid_token(self, mock_get_value):
        mock_get_value.return_value = {
            "name": "CRM-OPP-TEST-0001",
            "public_funnel_token": "expected-token",
            "public_funnel_token_expires_on": "2099-01-01 00:00:00",
        }

        result = public_intake.validate_public_funnel_opportunity(
            opportunity="CRM-OPP-TEST-0001",
            token="bad-token",
        )

        self.assertEqual(result["valid"], 0)
        self.assertIn("no longer valid", result["message"])

    @patch.object(public_intake.frappe.db, "get_value")
    def test_validate_public_funnel_opportunity_accepts_valid_token(self, mock_get_value):
        mock_get_value.return_value = {
            "name": "CRM-OPP-TEST-0001",
            "public_funnel_token": "expected-token",
            "public_funnel_token_expires_on": "2099-01-01 00:00:00",
        }

        result = public_intake.validate_public_funnel_opportunity(
            opportunity="CRM-OPP-TEST-0001",
            token="expected-token",
        )

        self.assertEqual(result, {"valid": 1, "opportunity": "CRM-OPP-TEST-0001"})

    @patch.object(public_intake, "ensure_public_token", return_value="renewed-token")
    @patch.object(public_intake, "add_to_date", return_value="2026-03-22 00:00:00")
    @patch.object(public_intake, "now", return_value="2026-03-22 00:00:00")
    @patch.object(public_intake.frappe, "get_all")
    def test_create_instant_quote_opportunity_reuses_recent_duplicate(
        self,
        mock_get_all,
        _mock_now,
        _mock_add_to_date,
        _mock_ensure_token,
    ):
        mock_get_all.return_value = [
            {
                "name": "CRM-OPP-TEST-0001",
                "custom_estimate_low": 600,
                "custom_estimate_high": 900,
                "risk_level": "Yellow",
                "currency": "USD",
                "opportunity_amount": 750,
                "public_funnel_token": "old-token",
                "public_funnel_token_expires_on": "2099-01-01 00:00:00",
            }
        ]

        result = public_intake.create_instant_quote_opportunity(
            {
                "prospect_name": "Patten Whiting",
                "phone": "555-0100",
                "contact_email": "patten@example.com",
                "prospect_company": "Pikt",
                "building_type": "Office",
                "building_size": "2000",
                "service_frequency": "Weekly",
                "service_interest": "Recurring standard cleaning",
                "bathroom_count_range": "1-2",
            }
        )

        self.assertEqual(
            result,
            {
                "name": "CRM-OPP-TEST-0001",
                "opp": "CRM-OPP-TEST-0001",
                "low": 600,
                "high": 900,
                "risk": "Yellow",
                "currency": "USD",
                "final_price": 750,
                "token": "renewed-token",
                "duplicate": 1,
            },
        )

    @patch.object(public_intake, "make_public_token", return_value="new-token")
    @patch.object(public_intake, "add_to_date", side_effect=["2026-03-22 00:00:00", "2099-01-01 00:00:00"])
    @patch.object(public_intake, "now_datetime", return_value="2026-03-22 00:00:00")
    @patch.object(public_intake, "nowdate", return_value="2026-03-22")
    @patch.object(public_intake, "now", return_value="2026-03-22 00:00:00")
    @patch.object(public_intake, "upsert_lead_for_quote_request")
    @patch.object(public_intake.frappe, "get_all", return_value=[])
    @patch.object(public_intake.frappe, "get_doc")
    def test_create_instant_quote_opportunity_creates_new_record(
        self,
        mock_get_doc,
        _mock_get_all,
        mock_upsert_lead,
        _mock_now,
        _mock_nowdate,
        _mock_now_datetime,
        _mock_add_to_date,
        _mock_make_public_token,
    ):
        mock_upsert_lead.return_value = SimpleNamespace(name="CRM-LEAD-TEST-0001")
        created_docs = []

        def fake_get_doc(payload):
            opportunity = FakeInsertDoc(
                payload,
                on_insert=public_intake.apply_instant_quote_pricing,
            )
            created_docs.append(opportunity)
            return opportunity

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

        opportunity = created_docs[0]
        self.assertTrue(opportunity.insert_called)
        self.assertEqual(
            result,
            {
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

    @patch.object(public_intake, "now", return_value="2026-03-22 00:00:00")
    @patch.object(public_intake, "require_valid_public_funnel_opportunity")
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
            opportunity="CRM-OPP-TEST-0001",
            token="valid-token",
            uploaded=FakeUploadedFile("walkthrough.pdf", b"pdf-bytes"),
        )

        self.assertTrue(file_doc.save_called)
        self.assertTrue(opportunity_doc.save_called)
        self.assertEqual(result["opportunity"], "CRM-OPP-TEST-0001")
        self.assertEqual(result["digital_walkthrough_file"], "/private/files/walkthrough.pdf")
        self.assertEqual(result["digital_walkthrough_status"], "Submitted")
        self.assertEqual(result["digital_walkthrough_received_on"], "2026-03-22 00:00:00")
        old_file_doc.delete.assert_called_once_with(ignore_permissions=True)
