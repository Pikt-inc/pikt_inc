from __future__ import annotations

import json
from pathlib import Path
import unittest

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc import hooks as app_hooks


BUILDER_PAGE_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "builder_page.json"
BUILDING_DOCTYPE_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "00_building_doctype.json"
BUILDING_SOP_DOCTYPE_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "00_building_sop_doctype.json"
CONTACT_REQUEST_DOCTYPE_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1] / "fixtures" / "03_contact_request_doctype.json"
)
BUILDING_CUSTOM_FIELD_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "01_building_custom_field.json"
CUSTOM_FIELD_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "custom_field.json"
CUSTOM_DOCPERM_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "custom_docperm.json"
BUILDER_COMPONENT_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "builder_component.json"
WEB_FORM_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "web_form.json"
PORTAL_SETTINGS_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "portal_settings.json"
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
CONTACT_WEB_FORM_CLEANUP_PATCH_PATH = (
    Path(__file__).resolve().parents[1]
    / "patches"
    / "post_model_sync"
    / "remove_legacy_contact_request_web_form.py"
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

    def test_instant_quote_selects_have_explicit_cross_browser_styling(self):
        template = INSTANT_QUOTE_TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn(".quote-field select{", template)
        self.assertIn("-webkit-appearance:none;", template)
        self.assertIn("appearance:none;", template)
        self.assertIn("min-height:54px;", template)
        self.assertIn("padding-right:48px;", template)
        self.assertIn("background-image:", template)
        self.assertIn("background-size:6px 6px;", template)

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

    def test_site_shell_mobile_actions_have_specific_color_rules(self):
        site_shell = SITE_SHELL_MACROS_PATH.read_text(encoding="utf-8")

        self.assertIn('.site-shell-mobile-panel .site-shell-mobile-quote', site_shell)
        self.assertIn('.site-shell-mobile-panel .site-shell-mobile-login', site_shell)
        self.assertIn('color:#fff', site_shell)

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

    def test_portal_settings_fixture_is_exported(self):
        portal_settings_fixture = next(row for row in app_hooks.fixtures if row["dt"] == "Portal Settings")

        self.assertEqual(portal_settings_fixture, {"dt": "Portal Settings"})

    def test_portal_settings_fixture_file_enables_customer_transaction_menu_and_stages_agreement_links(self):
        portal_settings_docs = json.loads(PORTAL_SETTINGS_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(len(portal_settings_docs), 1)
        portal_settings = portal_settings_docs[0]
        self.assertEqual(portal_settings["doctype"], "Portal Settings")
        self.assertEqual(portal_settings["default_portal_home"], "/orders")
        self.assertEqual(portal_settings["hide_standard_menu"], 1)

        menu_by_title = {row["title"]: row for row in portal_settings["menu"]}
        self.assertEqual(menu_by_title["Quotations"]["enabled"], 0)
        self.assertEqual(menu_by_title["Orders"]["enabled"], 0)
        self.assertEqual(menu_by_title["Invoices"]["enabled"], 0)
        self.assertEqual(menu_by_title["Issues"]["enabled"], 0)
        self.assertEqual(menu_by_title["Projects"]["enabled"], 0)
        self.assertEqual(menu_by_title["Shipments"]["enabled"], 0)
        self.assertEqual(menu_by_title["Appointment Booking"]["enabled"], 0)

        custom_menu_by_title = {row["title"]: row for row in portal_settings["custom_menu"]}
        self.assertEqual(custom_menu_by_title["Quotations"]["enabled"], 1)
        self.assertEqual(custom_menu_by_title["Orders"]["enabled"], 1)
        self.assertEqual(custom_menu_by_title["Invoices"]["enabled"], 1)
        self.assertEqual(custom_menu_by_title["Issues"]["enabled"], 1)
        self.assertEqual(
            custom_menu_by_title["Master Service Agreement"]["route"],
            "/master-service-agreement-form",
        )
        self.assertEqual(
            custom_menu_by_title["Master Service Agreement"]["reference_doctype"],
            "Service Agreement",
        )
        self.assertEqual(custom_menu_by_title["Master Service Agreement"]["enabled"], 0)
        self.assertEqual(
            custom_menu_by_title["Business Agreements"]["route"],
            "/service-agreement-addendum-form",
        )
        self.assertEqual(
            custom_menu_by_title["Business Agreements"]["reference_doctype"],
            "Service Agreement Addendum",
        )
        self.assertEqual(custom_menu_by_title["Business Agreements"]["enabled"], 0)
        self.assertEqual(custom_menu_by_title["Buildings"]["route"], "/building-form")
        self.assertEqual(custom_menu_by_title["Buildings"]["reference_doctype"], "Building")
        self.assertEqual(custom_menu_by_title["Buildings"]["enabled"], 0)
        self.assertEqual(custom_menu_by_title["Checklist Items"]["route"], "/building-sop-form")
        self.assertEqual(custom_menu_by_title["Checklist Items"]["reference_doctype"], "Building SOP")
        self.assertEqual(custom_menu_by_title["Checklist Items"]["enabled"], 0)

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

    def test_web_form_fixture_file_contains_only_agreement_forms(self):
        web_forms = json.loads(WEB_FORM_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(
            {doc["name"] for doc in web_forms},
            {"master-service-agreement", "service-agreement-addendum"},
        )

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
        self.assertTrue(CONTACT_REQUEST_DOCTYPE_FIXTURE_PATH.exists())

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

        contact_request_fixture = next(
            row
            for row in app_hooks.fixtures
            if row["dt"] == "DocType" and row.get("prefix") == "03_contact_request"
        )
        self.assertEqual(contact_request_fixture["filters"], [["name", "in", ["Contact Request"]]])
    def test_building_schema_fixture_files_cover_live_portal_fields(self):
        building_doctypes = json.loads(BUILDING_DOCTYPE_FIXTURE_PATH.read_text(encoding="utf-8"))
        building_custom_fields = json.loads(BUILDING_CUSTOM_FIELD_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(len(building_doctypes), 1)
        self.assertEqual(building_doctypes[0]["name"], "Building")
        self.assertEqual(building_doctypes[0]["title_field"], "building_name")
        self.assertEqual(building_doctypes[0]["search_fields"], "building_name,customer,city,state,postal_code")
        self.assertEqual(building_doctypes[0]["show_title_field_in_link"], 1)

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

    def test_building_sop_fixture_supports_portal_titles_and_search(self):
        building_sop_doctypes = json.loads(BUILDING_SOP_DOCTYPE_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(len(building_sop_doctypes), 1)
        self.assertEqual(building_sop_doctypes[0]["name"], "Building SOP")
        self.assertEqual(building_sop_doctypes[0]["title_field"], "building")
        self.assertEqual(building_sop_doctypes[0]["search_fields"], "building,customer,version_number")
        self.assertEqual(building_sop_doctypes[0]["show_title_field_in_link"], 1)

    def test_contact_request_doctype_fixture_covers_public_contact_fields(self):
        doctypes = json.loads(CONTACT_REQUEST_DOCTYPE_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertEqual(len(doctypes), 1)
        self.assertEqual(doctypes[0]["name"], "Contact Request")
        self.assertEqual(doctypes[0]["autoname"], "format:CR-{YYYY}-{#####}")

        field_names = {row["fieldname"] for row in doctypes[0]["fields"] if row.get("fieldname")}
        for field_name in (
            "first_name",
            "last_name",
            "email_id",
            "mobile_no",
            "company_name",
            "city",
            "request_type",
            "message",
            "request_status",
        ):
            self.assertIn(field_name, field_names)
    def test_building_custom_docperm_is_reconciled_outside_fixtures(self):
        custom_docperms = json.loads(CUSTOM_DOCPERM_FIXTURE_PATH.read_text(encoding="utf-8"))

        self.assertNotIn(("Building", "Accounts Manager"), {(row["parent"], row["role"]) for row in custom_docperms})
        self.assertNotIn(("Building", "Customer Portal User"), {(row["parent"], row["role"]) for row in custom_docperms})
        self.assertNotIn(("Service Agreement", "Customer Portal User"), {(row["parent"], row["role"]) for row in custom_docperms})
        self.assertNotIn(("Service Agreement Addendum", "Customer Portal User"), {(row["parent"], row["role"]) for row in custom_docperms})
        self.assertIn("pikt_inc.migrate.ensure_building_custom_docperms", app_hooks.after_sync)
        self.assertIn("pikt_inc.migrate.ensure_building_custom_docperms", app_hooks.after_migrate)
        self.assertIn("pikt_inc.migrate.ensure_building_sop_custom_docperms", app_hooks.after_sync)
        self.assertIn("pikt_inc.migrate.ensure_service_agreement_custom_docperms", app_hooks.after_sync)
        self.assertIn("pikt_inc.migrate.ensure_service_agreement_addendum_custom_docperms", app_hooks.after_sync)
        self.assertIn("pikt_inc.migrate.ensure_customer_portal_doctype_metadata", app_hooks.after_sync)
        self.assertIn("pikt_inc.migrate.ensure_building_sop_custom_docperms", app_hooks.after_migrate)
        self.assertIn("pikt_inc.migrate.ensure_service_agreement_custom_docperms", app_hooks.after_migrate)
        self.assertIn("pikt_inc.migrate.ensure_service_agreement_addendum_custom_docperms", app_hooks.after_migrate)
        self.assertIn("pikt_inc.migrate.ensure_customer_portal_doctype_metadata", app_hooks.after_migrate)

    def test_customer_portal_permission_hooks_cover_portal_doctypes(self):
        self.assertEqual(
            app_hooks.permission_query_conditions["Building"],
            "pikt_inc.permissions.customer_portal.get_building_permission_query_conditions",
        )
        self.assertEqual(
            app_hooks.permission_query_conditions["Building SOP"],
            "pikt_inc.permissions.customer_portal.get_building_sop_permission_query_conditions",
        )
        self.assertEqual(
            app_hooks.permission_query_conditions["Service Agreement"],
            "pikt_inc.permissions.customer_portal.get_service_agreement_permission_query_conditions",
        )
        self.assertEqual(
            app_hooks.permission_query_conditions["Service Agreement Addendum"],
            "pikt_inc.permissions.customer_portal.get_service_agreement_addendum_permission_query_conditions",
        )
        self.assertEqual(
            app_hooks.has_permission["Building"],
            "pikt_inc.permissions.customer_portal.has_building_permission",
        )
        self.assertEqual(
            app_hooks.has_permission["Building SOP"],
            "pikt_inc.permissions.customer_portal.has_building_sop_permission",
        )
        self.assertEqual(
            app_hooks.has_permission["Service Agreement"],
            "pikt_inc.permissions.customer_portal.has_service_agreement_permission",
        )
        self.assertEqual(
            app_hooks.has_permission["Service Agreement Addendum"],
            "pikt_inc.permissions.customer_portal.has_service_agreement_addendum_permission",
        )

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
        self.assertNotIn("LP Quote Form", exported_components)
        self.assertNotIn("LP Quote Result Section", exported_components)
        self.assertNotIn("LP Walkthrough Received", exported_components)

    def test_contact_page_template_uses_custom_submission_flow(self):
        template = CONTACT_TEMPLATE_PATH.read_text(encoding="utf-8")

        self.assertIn('<form id="contact-request-form"', template)
        self.assertIn('/api/method/pikt_inc.api.contact_request.submit_contact_request', template)
        self.assertIn("request_type_options", template)
        self.assertIn("contact-request-success", template)
        self.assertNotIn('<iframe', template)
        self.assertNotIn('embedded=1', template)
        self.assertNotIn("pikt-contact-request-form", template)
        self.assertNotIn("event.source !== iframe.contentWindow", template)
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

    def test_contact_notification_fixture_targets_contact_request(self):
        notifications = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "notification.json").read_text(encoding="utf-8"))
        notification = next(doc for doc in notifications if doc["name"] == "New Contact Form Lead")

        self.assertEqual(notification["document_type"], "Contact Request")
        self.assertIn("{{ doc.message }}", notification["message"])
        self.assertIn("Contact Request: {{ doc.name }}", notification["message"])

    def test_quote_funnel_frontend_contracts(self):
        thank_you_template = QUOTE_THANK_YOU_TEMPLATE_PATH.read_text(encoding="utf-8")
        walkthrough_template = QUOTE_DIGITAL_WALKTHROUGH_TEMPLATE_PATH.read_text(encoding="utf-8")
        walkthrough_received_template = QUOTE_DIGITAL_WALKTHROUGH_RECEIVED_TEMPLATE_PATH.read_text(encoding="utf-8")
        review_template = QUOTE_REVIEW_TEMPLATE_PATH.read_text(encoding="utf-8")
        accepted_script = QUOTE_ACCEPTED_ASSET_PATH.read_text(encoding="utf-8")
        complete_script = QUOTE_BILLING_COMPLETE_ASSET_PATH.read_text(encoding="utf-8")

        self.assertIn("validate_public_funnel_opportunity", thank_you_template)
        self.assertIn("validation.reason", thank_you_template)
        self.assertIn("let booted = false;", thank_you_template)
        self.assertIn("/digital-walkthrough", thank_you_template)
        self.assertIn("save_opportunity_walkthrough_upload", walkthrough_template)
        self.assertIn("message.reason", walkthrough_received_template)
        self.assertIn("validate_public_quote", review_template)
        self.assertNotIn("window.location.replace('/quote-accepted", review_template)
        self.assertIn("Continue to Secure Quote Portal", review_template)
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

    def test_contact_web_form_cleanup_patch_is_registered(self):
        patches_text = PATCHES_PATH.read_text(encoding="utf-8")

        self.assertIn(
            "pikt_inc.patches.post_model_sync.remove_legacy_contact_request_web_form",
            patches_text,
        )
        self.assertTrue(CONTACT_WEB_FORM_CLEANUP_PATCH_PATH.exists())

    def test_contact_fixture_copy_does_not_ship_placeholder_service_area_text(self):
        components = json.loads(BUILDER_COMPONENT_FIXTURE_PATH.read_text(encoding="utf-8"))
        component_names = {row["component_name"] for row in components}
        service_area_component = next(row for row in components if row["component_name"] == "LP Service Area Section")
        block = service_area_component["block"]

        self.assertNotIn("LP Quote Form", component_names)
        self.assertNotIn("LP Quote Result Section", component_names)
        self.assertNotIn("LP Walkthrough Received", component_names)
        self.assertNotIn("What to swap in", block)
        self.assertNotIn("Downtown core", block)
        self.assertNotIn("North corridor", block)

    def test_marketing_copy_cleanup_replaces_internal_placeholder_text(self):
        components_text = BUILDER_COMPONENT_FIXTURE_PATH.read_text(encoding="utf-8")
        site_shell = SITE_SHELL_MACROS_PATH.read_text(encoding="utf-8")

        for phrase in (
            "Keep the quote form as the primary path",
            "Share why the business exists and how you work",
            "Use this section for a short founder note",
            "A good pattern is: why you started",
            "Suggested headline",
            "What to customize",
            "Swap these cards for founder bio",
            "Built for local SEO landing pages, quote capture, and commercial cleaning service inquiries.",
            "What\\u00e2\\u20ac\\u2122s included",
        ):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, components_text + site_shell)

        self.assertIn("PIKT serves recurring commercial cleaning accounts", site_shell)
