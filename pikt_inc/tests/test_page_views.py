from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc.services.contracts.customer_portal import PortalMetaTags
from pikt_inc.services.contracts.customer_portal import PortalNavItem
from pikt_inc.views.base import BasePageView
from pikt_inc.views.pages.contact import ContactPageView
from pikt_inc.views.pages.portal.agreements import PortalAgreementsPageView
from pikt_inc.views.pages.portal.billing import PortalBillingPageView
from pikt_inc.views.pages.portal.locations import PortalLocationsPageView
from pikt_inc.views.pages.portal.overview import PortalOverviewPageView
from pikt_inc.views.pages.quote.billing_complete import QuoteBillingCompletePageView
from pikt_inc.views.pages.quote.digital_walkthrough import QuoteDigitalWalkthroughPageView
from pikt_inc.views.pages.quote.digital_walkthrough_received import QuoteDigitalWalkthroughReceivedPageView
from pikt_inc.views.pages.quote.instant_quote import InstantQuotePageView
from pikt_inc.views.pages.quote.quote_accepted import QuoteAcceptedPortalPageView
from pikt_inc.views.pages.quote.review import QuoteReviewPageView
from pikt_inc.views.pages.quote.thank_you import QuoteThankYouPageView
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

    def test_quote_page_view_supports_class_level_metadata(self):
        context = SimpleNamespace()

        result = QuoteThankYouPageView().build_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.page_title, "Instant Estimate")
        self.assertEqual(
            context.meta_description,
            "Instant estimate and next steps for your commercial cleaning request.",
        )
        self.assertEqual(context.noindex_meta, 1)

    def test_concrete_quote_page_views_expose_expected_titles(self):
        expectations = [
            (InstantQuotePageView, "Get a Quote", ""),
            (QuoteDigitalWalkthroughPageView, "Digital Walkthrough", "Upload your completed digital walkthrough for commercial cleaning review."),
            (QuoteDigitalWalkthroughReceivedPageView, "Digital Walkthrough Received", "Confirmation that your digital walkthrough has been received."),
            (QuoteReviewPageView, "Preparing Your Billing Setup", "Compatibility redirect for previously sent public quote links."),
            (QuoteAcceptedPortalPageView, "Quote Accepted", "Accept your quote, set up billing, and confirm your service site access in one secure portal."),
            (QuoteBillingCompletePageView, "Setup Complete", "Your quote, invoice setup, and service-site access details are complete."),
        ]

        for view_class, title, description in expectations:
            with self.subTest(view_class=view_class.__name__):
                context = SimpleNamespace()
                result = view_class().build_context(context)
                self.assertIs(result, context)
                self.assertEqual(view_class.sitemap, 0)
                self.assertEqual(context.page_title, title)
                self.assertEqual(context.meta_description, description)

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

    def test_portal_billing_page_view_uses_class_level_loader(self):
        context = SimpleNamespace()
        original_loader = PortalBillingPageView.page_loader
        PortalBillingPageView.page_loader = staticmethod(
            lambda: {
                "portal_title": "Customer Portal",
                "portal_description": "Secure portal",
                "portal_nav": [
                    {"key": "billing", "label": "Billing", "url": "/portal/billing", "is_active": True},
                    {"key": "logout", "label": "Log out", "url": "/logout", "is_active": False},
                ],
                "metatags": {
                    "title": "Billing | Customer Portal",
                    "description": "Secure billing portal",
                },
                "tax_id": "12-3456789",
            }
        )
        try:
            result = PortalBillingPageView().build_context(context)
        finally:
            PortalBillingPageView.page_loader = original_loader

        self.assertIs(result, context)
        self.assertEqual(PortalBillingPageView.sitemap, 0)
        self.assertEqual(context.tax_id, "12-3456789")
        self.assertEqual([item["key"] for item in context.primary_nav], ["billing"])
        self.assertEqual([item["key"] for item in context.utility_nav], ["logout"])

    def test_portal_agreements_page_view_uses_class_level_loader(self):
        context = SimpleNamespace()
        original_loader = PortalAgreementsPageView.page_loader
        PortalAgreementsPageView.page_loader = staticmethod(
            lambda: {
                "portal_title": "Customer Portal",
                "portal_description": "Secure portal",
                "portal_nav": [
                    {"key": "agreements", "label": "Agreements", "url": "/portal/agreements", "is_active": True},
                ],
                "metatags": {
                    "title": "Agreements | Customer Portal",
                    "description": "Secure agreements portal",
                },
                "addenda": [{"name": "ADD-1"}],
            }
        )
        try:
            result = PortalAgreementsPageView().build_context(context)
        finally:
            PortalAgreementsPageView.page_loader = original_loader

        self.assertIs(result, context)
        self.assertEqual(PortalAgreementsPageView.sitemap, 0)
        self.assertEqual(context.addenda, [{"name": "ADD-1"}])
        self.assertEqual([item["key"] for item in context.primary_nav], ["agreements"])

    def test_portal_locations_page_view_uses_class_level_loader(self):
        context = SimpleNamespace()
        original_loader = PortalLocationsPageView.page_loader
        PortalLocationsPageView.page_loader = staticmethod(
            lambda: {
                "portal_title": "Customer Portal",
                "portal_description": "Secure portal",
                "portal_nav": [
                    {"key": "locations", "label": "Locations", "url": "/portal/locations", "is_active": True},
                ],
                "metatags": {
                    "title": "Locations | Customer Portal",
                    "description": "Secure locations portal",
                },
                "buildings": [{"name": "BUILD-1"}],
            }
        )
        try:
            result = PortalLocationsPageView().build_context(context)
        finally:
            PortalLocationsPageView.page_loader = original_loader

        self.assertIs(result, context)
        self.assertEqual(PortalLocationsPageView.sitemap, 0)
        self.assertEqual(context.buildings, [{"name": "BUILD-1"}])
        self.assertEqual([item["key"] for item in context.primary_nav], ["locations"])
