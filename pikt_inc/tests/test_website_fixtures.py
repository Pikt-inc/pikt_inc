from __future__ import annotations

import json
from pathlib import Path
import unittest

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc import hooks as app_hooks


BUILDER_PAGE_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "builder_page.json"
BUILDING_DOCTYPE_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "00_building_doctype.json"
BUILDING_CUSTOM_FIELD_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "01_building_custom_field.json"
CUSTOM_FIELD_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "custom_field.json"
CUSTOM_DOCPERM_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "custom_docperm.json"
BUILDER_COMPONENT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "builder_component.json"
WEB_FORM_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "web_form.json"
INSTANT_QUOTE_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "instant-quote.html"
INSTANT_QUOTE_CONTROLLER_PATH = Path(__file__).resolve().parents[1] / "www" / "instant_quote.py"
SITE_SHELL_MACROS_PATH = Path(__file__).resolve().parents[1] / "templates" / "includes" / "site_shell_macros.html"
QUOTE_FUNNEL_MACROS_PATH = Path(__file__).resolve().parents[1] / "templates" / "includes" / "quote_funnel_macros.html"
BLOG_MACROS_PATH = Path(__file__).resolve().parents[1] / "templates" / "includes" / "blog_macros.html"
BLOG_HOME_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "blog-home.html"
BLOG_POST_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "blog-post.html"
CONTACT_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "contact-page.html"
CONTACT_CONTROLLER_PATH = Path(__file__).resolve().parents[1] / "www" / "contact_page.py"
QUOTE_THANK_YOU_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "quote-thank-you.html"
QUOTE_THANK_YOU_CONTROLLER_PATH = Path(__file__).resolve().parents[1] / "www" / "quote_thank_you.py"
QUOTE_DIGITAL_WALKTHROUGH_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "quote-digital-walkthrough.html"
QUOTE_DIGITAL_WALKTHROUGH_CONTROLLER_PATH = Path(__file__).resolve().parents[1] / "www" / "quote_digital_walkthrough.py"
QUOTE_DIGITAL_WALKTHROUGH_RECEIVED_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "quote-digital-walkthrough-received.html"
QUOTE_DIGITAL_WALKTHROUGH_RECEIVED_CONTROLLER_PATH = Path(__file__).resolve().parents[1] / "www" / "quote_digital_walkthrough_received.py"
QUOTE_REVIEW_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "quote-review.html"
QUOTE_REVIEW_CONTROLLER_PATH = Path(__file__).resolve().parents[1] / "www" / "quote_review.py"
QUOTE_ACCEPTED_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "quote-accepted-portal.html"
QUOTE_ACCEPTED_CONTROLLER_PATH = Path(__file__).resolve().parents[1] / "www" / "quote_accepted_portal.py"
QUOTE_ACCEPTED_ASSET_PATH = Path(__file__).resolve().parents[1] / "public" / "js" / "quote_accepted_portal.js"
QUOTE_ACCEPTED_CSS_PATH = Path(__file__).resolve().parents[1] / "public" / "css" / "quote_accepted_portal.css"
QUOTE_BILLING_COMPLETE_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "www" / "quote-billing-complete.html"
QUOTE_BILLING_COMPLETE_CONTROLLER_PATH = Path(__file__).resolve().parents[1] / "www" / "quote_billing_complete.py"
QUOTE_BILLING_COMPLETE_ASSET_PATH = Path(__file__).resolve().parents[1] / "public" / "js" / "quote_billing_complete.js"
QUOTE_BILLING_COMPLETE_CSS_PATH = Path(__file__).resolve().parents[1] / "public" / "css" / "quote_billing_complete.css"
PATCHES_PATH = Path(__file__).resolve().parents[1] / "patches.txt"
QUOTE_CLEANUP_PATCH_PATH = (
    Path(__file__).resolve().parents[1]
    / "patches"
    / "post_model_sync"
    / "remove_legacy_quote_builder_pages.py"
)
CONTACT_CLEANUP_PATCH_PATH = (
    Path(__file__).resolve().parents[1]
    / "patches"
    / "post_model_sync"
    / "remove_legacy_contact_builder_page.py"
)


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

    def test_contact_route_is_app_owned(self):
        self.assertIn(
            {"from_route": "/contact", "to_route": "contact-page"},
            app_hooks.website_route_rules,
        )

    def test_quote_funnel_routes_are_app_owned(self):
        expected_rules = [
            {"from_route": "/thank-you", "to_route": "quote-thank-you"},
            {"from_route": "/digital-walkthrough", "to_route": "quote-digital-walkthrough"},
            {"from_route": "/digital-walkthrough-received", "to_route": "quote-digital-walkthrough-received"},
            {"from_route": "/review-quote", "to_route": "quote-review"},
            {"from_route": "/quote-accepted", "to_route": "quote-accepted-portal"},
            {"from_route": "/billing-setup-complete", "to_route": "quote-billing-complete"},
        ]

        for rule in expected_rules:
            with self.subTest(rule=rule):
                self.assertIn(rule, app_hooks.website_route_rules)

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

    def test_contact_page_files_exist(self):
        self.assertTrue(CONTACT_CONTROLLER_PATH.exists())
        self.assertTrue(CONTACT_TEMPLATE_PATH.exists())
        self.assertTrue(SITE_SHELL_MACROS_PATH.exists())

    def test_quote_funnel_files_exist(self):
        for path in (
            QUOTE_FUNNEL_MACROS_PATH,
            QUOTE_THANK_YOU_TEMPLATE_PATH,
            QUOTE_THANK_YOU_CONTROLLER_PATH,
            QUOTE_DIGITAL_WALKTHROUGH_TEMPLATE_PATH,
            QUOTE_DIGITAL_WALKTHROUGH_CONTROLLER_PATH,
            QUOTE_DIGITAL_WALKTHROUGH_RECEIVED_TEMPLATE_PATH,
            QUOTE_DIGITAL_WALKTHROUGH_RECEIVED_CONTROLLER_PATH,
            QUOTE_REVIEW_TEMPLATE_PATH,
            QUOTE_REVIEW_CONTROLLER_PATH,
            QUOTE_ACCEPTED_TEMPLATE_PATH,
            QUOTE_ACCEPTED_CONTROLLER_PATH,
            QUOTE_ACCEPTED_ASSET_PATH,
            QUOTE_ACCEPTED_CSS_PATH,
            QUOTE_BILLING_COMPLETE_TEMPLATE_PATH,
            QUOTE_BILLING_COMPLETE_CONTROLLER_PATH,
            QUOTE_BILLING_COMPLETE_ASSET_PATH,
            QUOTE_BILLING_COMPLETE_CSS_PATH,
            QUOTE_CLEANUP_PATCH_PATH,
        ):
            with self.subTest(path=path.name):
                self.assertTrue(path.exists())

    def test_blog_pages_use_canonical_site_shell(self):
        blog_macros = BLOG_MACROS_PATH.read_text(encoding="utf-8")
        blog_home = BLOG_HOME_TEMPLATE_PATH.read_text(encoding="utf-8")
        blog_post = BLOG_POST_TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn('site_shell_head', blog_macros)
        self.assertNotIn('macro blog_header', blog_macros)
        self.assertNotIn('macro blog_footer', blog_macros)
        self.assertIn('site_shell_header', blog_home)
        self.assertIn('site_shell_footer', blog_home)
        self.assertIn('site_shell_header', blog_post)
        self.assertIn('site_shell_footer', blog_post)

    def test_quote_schema_fixtures_are_exported(self):
        fixture_doctypes = [row["dt"] for row in app_hooks.fixtures]

        self.assertIn("DocType", fixture_doctypes)
        self.assertIn("Custom Field", fixture_doctypes)
        self.assertIn("Custom DocPerm", fixture_doctypes)

    def test_master_service_agreement_web_form_fixture_is_exported(self):
        web_form_fixture = next(row for row in app_hooks.fixtures if row["dt"] == "Web Form")

        self.assertEqual(
            web_form_fixture["filters"],
            [["name", "in", ["master-service-agreement", "service-agreement-addendum"]]],
        )

    def test_master_service_agreement_web_form_fixture_file_exists_and_targets_service_agreement(self):
        web_forms = json.loads(WEB_FORM_FIXTURE_PATH.read_text(encoding="utf-8"))
        web_form = next(doc for doc in web_forms if doc["name"] == "master-service-agreement")

        self.assertEqual(web_form["doctype"], "Web Form")
        self.assertEqual(web_form["title"], "Master Service Agreement")
        self.assertEqual(web_form["route"], "master-service-agreement-form")
        self.assertEqual(web_form["doc_type"], "Service Agreement")
        self.assertEqual(web_form["published"], 0)
        self.assertEqual(web_form["login_required"], 1)
        self.assertEqual(web_form["allow_edit"], 1)
        self.assertEqual(web_form["allow_incomplete"], 1)
        self.assertIsNotNone(web_form["custom_css"])
        self.assertIn("MASTER AGREEMENT", web_form["custom_css"])
        self.assertIn(".web-form-header h1", web_form["custom_css"])
        self.assertIn(".btn-primary.submit-btn", web_form["custom_css"])
        self.assertIn(".discard-btn,.web-form-actions .discard-btn,.web-form-footer .discard-btn{display:none !important;}", web_form["custom_css"])
        self.assertIn("[data-doctype='Web Form'] .page-content-wrapper .container .page_content", web_form["custom_css"])
        self.assertIn(".form-column{padding-left:0;padding-right:0;}", web_form["custom_css"])
        self.assertIn(".select-icon{top:50%;right:16px;transform:translateY(-50%);", web_form["custom_css"])
        self.assertIn(".control-input{background:transparent;border:0;padding:0;box-shadow:none;}", web_form["custom_css"])

        fieldnames = {row.get("fieldname") for row in web_form["web_form_fields"] if row.get("fieldname")}
        self.assertIn("agreement_name", fieldnames)
        self.assertIn("customer", fieldnames)
        self.assertIn("template", fieldnames)
        self.assertIn("template_version", fieldnames)
        self.assertIn("rendered_html_snapshot", fieldnames)
        self.assertIn("signed_by_name", fieldnames)
        self.assertIn("signed_by_title", fieldnames)
        self.assertIn("signed_by_email", fieldnames)

    def test_service_agreement_addendum_web_form_fixture_file_exists_and_targets_addendum(self):
        web_forms = json.loads(WEB_FORM_FIXTURE_PATH.read_text(encoding="utf-8"))
        web_form = next(doc for doc in web_forms if doc["name"] == "service-agreement-addendum")

        self.assertEqual(web_form["doctype"], "Web Form")
        self.assertEqual(web_form["title"], "Service Agreement Addendum")
        self.assertEqual(web_form["route"], "service-agreement-addendum-form")
        self.assertEqual(web_form["doc_type"], "Service Agreement Addendum")
        self.assertEqual(web_form["published"], 0)
        self.assertEqual(web_form["login_required"], 1)
        self.assertEqual(web_form["allow_edit"], 1)
        self.assertEqual(web_form["allow_incomplete"], 1)
        self.assertIsNotNone(web_form["custom_css"])
        self.assertIn("LOCATION ADDENDUM", web_form["custom_css"])
        self.assertIn(".web-form-header h1", web_form["custom_css"])
        self.assertIn(".btn-primary.submit-btn", web_form["custom_css"])
        self.assertIn(".discard-btn,.web-form-actions .discard-btn,.web-form-footer .discard-btn{display:none !important;}", web_form["custom_css"])
        self.assertIn("[data-doctype='Web Form'] .page-content-wrapper .container .page_content", web_form["custom_css"])
        self.assertIn(".form-column{padding-left:0;padding-right:0;}", web_form["custom_css"])
        self.assertIn(".select-icon{top:50%;right:16px;transform:translateY(-50%);", web_form["custom_css"])
        self.assertIn(".control-input{background:transparent;border:0;padding:0;box-shadow:none;}", web_form["custom_css"])

        fieldnames = {row.get("fieldname") for row in web_form["web_form_fields"] if row.get("fieldname")}
        self.assertIn("addendum_name", fieldnames)
        self.assertIn("service_agreement", fieldnames)
        self.assertIn("customer", fieldnames)
        self.assertIn("quotation", fieldnames)
        self.assertIn("sales_order", fieldnames)
        self.assertIn("term_model", fieldnames)
        self.assertIn("fixed_term_months", fieldnames)
        self.assertIn("start_date", fieldnames)
        self.assertIn("end_date", fieldnames)
        self.assertIn("template", fieldnames)
        self.assertIn("template_version", fieldnames)
        self.assertIn("rendered_html_snapshot", fieldnames)
        self.assertIn("signed_by_name", fieldnames)
        self.assertIn("signed_by_title", fieldnames)
        self.assertIn("signed_by_email", fieldnames)

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

    def test_building_schema_fixture_files_exist(self):
        self.assertTrue(BUILDING_DOCTYPE_FIXTURE_PATH.exists())
        self.assertTrue(BUILDING_CUSTOM_FIELD_FIXTURE_PATH.exists())

    def test_building_schema_fixture_entries_are_exported_in_safe_order(self):
        building_doctype_fixture = next(
            row
            for row in app_hooks.fixtures
            if row["dt"] == "DocType" and row.get("prefix") == "00_building"
        )
        building_custom_field_fixture = next(
            row
            for row in app_hooks.fixtures
            if row["dt"] == "Custom Field" and row.get("prefix") == "01_building"
        )

        self.assertEqual(building_doctype_fixture["filters"], [["name", "in", ["Building"]]])
        self.assertEqual(building_custom_field_fixture["filters"], [["dt", "=", "Building"]])

    def test_building_schema_fixture_files_cover_live_portal_fields(self):
        building_doctypes = json.loads(BUILDING_DOCTYPE_FIXTURE_PATH.read_text(encoding="utf-8"))
        building_custom_fields = json.loads(BUILDING_CUSTOM_FIELD_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(len(building_doctypes), 1)
        self.assertEqual(building_doctypes[0]["name"], "Building")

        base_field_names = {row["fieldname"] for row in building_doctypes[0]["fields"]}
        custom_field_names = {row["fieldname"] for row in building_custom_fields}

        self.assertIn("building_name", base_field_names)
        self.assertIn("customer", base_field_names)
        self.assertIn("alarm_notes", base_field_names)
        self.assertIn("access_method", custom_field_names)
        self.assertIn("access_entry_details", custom_field_names)
        self.assertIn("supervisor_user", custom_field_names)
        self.assertIn("custom_service_agreement", custom_field_names)
        self.assertIn("custom_service_agreement_addendum", custom_field_names)

    def test_building_custom_docperm_is_reconciled_outside_fixtures(self):
        custom_docperms = json.loads(CUSTOM_DOCPERM_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertNotIn(("Building", "Accounts Manager"), {(row["parent"], row["role"]) for row in custom_docperms})
        self.assertIn("pikt_inc.migrate.ensure_building_custom_docperms", app_hooks.after_sync)
        self.assertIn("pikt_inc.migrate.ensure_building_custom_docperms", app_hooks.after_migrate)

    def test_quote_builder_pages_are_absent_from_fixture(self):
        builder_pages = json.loads(BUILDER_PAGE_FIXTURE_PATH.read_text(encoding="utf-8"))
        quote_routes = {
            "quote",
            "thank-you",
            "digital-walkthrough",
            "digital-walkthrough-received",
            "review-quote",
            "quote-accepted",
            "billing-setup-complete",
        }

        fixture_routes = {page["route"] for page in builder_pages}
        self.assertTrue(quote_routes.isdisjoint(fixture_routes))

    def test_contact_builder_page_is_absent_from_fixture(self):
        builder_pages = json.loads(BUILDER_PAGE_FIXTURE_PATH.read_text(encoding="utf-8"))
        fixture_routes = {page["route"] for page in builder_pages}

        self.assertNotIn("contact", fixture_routes)

    def test_builder_page_export_excludes_quote_routes(self):
        builder_fixture = next(row for row in app_hooks.fixtures if row["dt"] == "Builder Page")
        exported_routes = set(builder_fixture["filters"][0][2])
        quote_routes = {
            "quote",
            "thank-you",
            "digital-walkthrough",
            "digital-walkthrough-received",
            "review-quote",
            "quote-accepted",
            "billing-setup-complete",
        }

        self.assertTrue(quote_routes.isdisjoint(exported_routes))

    def test_builder_exports_exclude_contact_builder_artifacts(self):
        builder_page_fixture = next(row for row in app_hooks.fixtures if row["dt"] == "Builder Page")
        exported_routes = set(builder_page_fixture["filters"][0][2])
        self.assertNotIn("contact", exported_routes)

        builder_component_fixture = next(row for row in app_hooks.fixtures if row["dt"] == "Builder Component")
        exported_components = set(builder_component_fixture["filters"][0][2])
        self.assertNotIn("LP Contact Form", exported_components)
        self.assertNotIn("LP Contact Info Card", exported_components)

    def test_contact_page_template_uses_native_submission_flow(self):
        template = CONTACT_TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn("/api/method/pikt_inc.api.contact_request.submit_contact_request", template)
        self.assertNotIn("/contact-request", template)
        self.assertNotIn("<iframe", template)
        for field_name in (
            "first_name",
            "last_name",
            "email_id",
            "mobile_no",
            "company_name",
            "city",
            "request_type",
            "message",
        ):
            self.assertIn(f'name="{field_name}"', template)

    def test_quote_funnel_frontend_contracts(self):
        thank_you_template = QUOTE_THANK_YOU_TEMPLATE_PATH.read_text(encoding="utf-8")
        walkthrough_template = QUOTE_DIGITAL_WALKTHROUGH_TEMPLATE_PATH.read_text(encoding="utf-8")
        review_template = QUOTE_REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        accepted_script = QUOTE_ACCEPTED_ASSET_PATH.read_text(encoding="utf-8")
        complete_script = QUOTE_BILLING_COMPLETE_ASSET_PATH.read_text(encoding="utf-8")

        self.assertIn("validate_public_funnel_opportunity", thank_you_template)
        self.assertIn("let booted = false;", thank_you_template)
        self.assertIn("/digital-walkthrough", thank_you_template)
        self.assertIn("save_opportunity_walkthrough_upload", walkthrough_template)
        self.assertIn("validate_public_quote", review_template)
        self.assertIn("accept_public_quote", accepted_script)
        self.assertIn("load_public_quote_portal_state", accepted_script)
        self.assertIn("complete_public_service_agreement_signature", accepted_script)
        self.assertIn("complete_public_quote_billing_setup_v2", accepted_script)
        self.assertIn("complete_public_quote_access_setup_v2", accepted_script)
        self.assertIn("load_public_quote_portal_state", complete_script)

    def test_quote_cleanup_patch_is_registered(self):
        patches_text = PATCHES_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "pikt_inc.patches.post_model_sync.remove_legacy_quote_builder_pages",
            patches_text,
        )

    def test_contact_cleanup_patch_is_registered(self):
        patches_text = PATCHES_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "pikt_inc.patches.post_model_sync.remove_legacy_contact_builder_page",
            patches_text,
        )
        self.assertTrue(CONTACT_CLEANUP_PATCH_PATH.exists())

    def test_contact_fixture_copy_does_not_ship_placeholder_service_area_text(self):
        components = json.loads(BUILDER_COMPONENT_FIXTURE_PATH.read_text(encoding="utf-8"))
        service_area_component = next(row for row in components if row["component_name"] == "LP Service Area Section")
        block = service_area_component["block"]

        self.assertNotIn("What to swap in", block)
        self.assertNotIn("Downtown core", block)
        self.assertNotIn("North corridor", block)
