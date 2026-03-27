from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc.services.contracts.customer_portal import PortalMetaTags
from pikt_inc.services.contracts.customer_portal import PortalNavItem
from pikt_inc.views.base import BasePageView
from pikt_inc.views.pages.contact import ContactPageView
from pikt_inc.views.pages.portal.overview import PortalOverviewPageView
from pikt_inc.views.quote import QuotePageView
from pikt_inc.views.portal import PortalPageView


class ExamplePageView(BasePageView):
    noindex_meta = 0
    page_title = "Default title"
    meta_description = "Default description"

    def get_page_data(self):
        return {
            "page_title": "Override title",
            "meta_description": "Override description",
            "extra": "value",
            "http_status_code": 404,
        }


class TestPageViews(TestCase):
    def test_base_page_view_applies_defaults_and_payload(self):
        context = SimpleNamespace()

        result = ExamplePageView().build_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.no_cache, 1)
        self.assertEqual(context.body_class, "no-web-page-sections")
        self.assertEqual(context.noindex_meta, 0)
        self.assertEqual(context.page_title, "Override title")
        self.assertEqual(context.meta_description, "Override description")
        self.assertEqual(context.description, "Override description")
        self.assertEqual(context.http_status_code, 404)
        self.assertEqual(context.extra, "value")

    def test_quote_page_view_sets_static_shell_values(self):
        context = SimpleNamespace()

        result = QuotePageView(
            title="Get a Quote",
            description="Commercial cleaning quote page.",
            noindex_meta=1,
        ).build_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.page_title, "Get a Quote")
        self.assertEqual(context.meta_description, "Commercial cleaning quote page.")
        self.assertEqual(context.description, "Commercial cleaning quote page.")
        self.assertEqual(context.noindex_meta, 1)
        self.assertEqual(context.body_class, "no-web-page-sections")

    def test_portal_page_view_normalizes_nested_models(self):
        context = SimpleNamespace()

        result = PortalPageView(
            page_loader=lambda: {
                "portal_title": "Customer Portal",
                "portal_description": "Secure portal",
                "portal_nav": [
                    PortalNavItem(key="overview", label="Overview", url="/portal", is_active=True),
                    PortalNavItem(key="contact", label="Contact", url="/contact", is_active=False),
                ],
                "metatags": PortalMetaTags(
                    title="Account Overview | Customer Portal",
                    description="Secure portal",
                    canonical="https://example.test/portal",
                ),
            }
        ).build_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.page_title, "Account Overview | Customer Portal")
        self.assertEqual(context.meta_description, "Secure portal")
        self.assertEqual([item["key"] for item in context.primary_nav], ["overview"])
        self.assertEqual([item["key"] for item in context.utility_nav], ["contact"])

    def test_contact_page_view_builds_public_contact_context(self):
        context = SimpleNamespace()

        result = ContactPageView().build_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.page_title, "Contact Pikt")
        self.assertIn("walkthrough requests", context.meta_description)
        self.assertEqual(context.description, context.meta_description)
        self.assertIn("Walkthrough request", context.request_type_options)

    def test_portal_overview_page_view_uses_class_level_loader(self):
        context = SimpleNamespace()
        original_loader = PortalOverviewPageView.page_loader
        PortalOverviewPageView.page_loader = staticmethod(
            lambda: {
                "portal_title": "Customer Portal",
                "portal_description": "Secure portal",
                "portal_nav": [
                    {"key": "overview", "label": "Overview", "url": "/portal", "is_active": True},
                ],
                "metatags": {
                    "title": "Account Overview | Customer Portal",
                    "description": "Secure portal",
                },
                "customer_display": "Portal Customer LLC",
            }
        )
        try:
            result = PortalOverviewPageView().build_context(context)
        finally:
            PortalOverviewPageView.page_loader = original_loader

        self.assertIs(result, context)
        self.assertEqual(PortalOverviewPageView.sitemap, 0)
        self.assertEqual(context.customer_display, "Portal Customer LLC")
