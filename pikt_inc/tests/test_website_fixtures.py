from __future__ import annotations

import json
from pathlib import Path
import unittest

from pikt_inc import hooks as app_hooks


BUILDER_PAGE_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "builder_page.json"
CUSTOM_FIELD_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "custom_field.json"
CUSTOM_DOCPERM_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "custom_docperm.json"
INSTANT_QUOTE_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "instant-quote.html"
INSTANT_QUOTE_CONTROLLER_PATH = Path(__file__).resolve().parents[1] / "www" / "instant_quote.py"
SITE_SHELL_MACROS_PATH = Path(__file__).resolve().parents[1] / "templates" / "includes" / "site_shell_macros.html"


class TestWebsiteFixtures(unittest.TestCase):
    def test_home_page_is_explicit(self):
        self.assertEqual(app_hooks.home_page, "home")

    def test_home_alias_redirects_to_root(self):
        self.assertIn(
            {"source": "/home", "target": "/", "redirect_http_status": "301"},
            app_hooks.website_redirects,
        )

    def test_builder_page_fixture_contains_home_route(self):
        builder_pages = json.loads(BUILDER_PAGE_FIXTURE_PATH.read_text(encoding="utf-8"))
        home_page = next(doc for doc in builder_pages if doc["name"] == "page-c6c8b9f1")

        self.assertEqual(home_page["route"], "home")
        self.assertEqual(home_page["page_name"], "page-c6c8b9f1")
        self.assertEqual(home_page["page_title"], "Home")

    def test_quote_route_is_app_owned(self):
        self.assertIn(
            {"from_route": "/quote", "to_route": "instant-quote"},
            app_hooks.website_route_rules,
        )

    def test_instant_quote_template_contains_submission_contract(self):
        template = INSTANT_QUOTE_TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn('/api/method/create_instant_quote_opportunity', template)
        self.assertIn("window.location.assign('/thank-you?'", template)
        for field_name in (
            "prospect_name",
            "contact_email",
            "phone",
            "prospect_company",
            "building_type",
            "building_size",
            "service_frequency",
            "service_interest",
            "bathroom_count_range",
        ):
            self.assertIn(f'name="{field_name}"', template)

    def test_instant_quote_files_exist(self):
        self.assertTrue(INSTANT_QUOTE_CONTROLLER_PATH.exists())
        self.assertTrue(INSTANT_QUOTE_TEMPLATE_PATH.exists())
        self.assertTrue(SITE_SHELL_MACROS_PATH.exists())

    def test_quote_schema_fixtures_are_exported(self):
        fixture_doctypes = [row["dt"] for row in app_hooks.fixtures]

        self.assertIn("Custom Field", fixture_doctypes)
        self.assertIn("Custom DocPerm", fixture_doctypes)

    def test_quote_schema_fixture_files_contain_funnel_records(self):
        custom_fields = json.loads(CUSTOM_FIELD_FIXTURE_PATH.read_text(encoding="utf-8"))
        custom_docperms = json.loads(CUSTOM_DOCPERM_FIXTURE_PATH.read_text(encoding="utf-8"))

        field_names = {(row["dt"], row["fieldname"]) for row in custom_fields}
        docperm_keys = {(row["parent"], row["role"]) for row in custom_docperms}

        self.assertIn(("Opportunity", "public_funnel_token"), field_names)
        self.assertIn(("Quotation", "custom_accept_token"), field_names)
        self.assertIn(("Sales Order", "custom_access_method"), field_names)
        self.assertIn(("Digital Walkthrough Submission", "opportunity"), field_names)
        self.assertIn(("Quotation", "Customer"), docperm_keys)
        self.assertIn(("Opportunity", "Digital Walkthrough Reviewer"), docperm_keys)
