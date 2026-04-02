from __future__ import annotations

from types import SimpleNamespace
from unittest import TestCase

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

from pikt_inc.services.contracts.customer_portal import PortalMetaTags
from pikt_inc.services.contracts.customer_portal import PortalNavItem
from pikt_inc.views.base import BasePageView
from pikt_inc.views.pages.blog.home import BlogHomePageView
from pikt_inc.views.pages.blog.post import BlogPostPageView
from pikt_inc.views.pages.blog.rss import BlogRssPageView
from pikt_inc.views.pages.blog.sitemap import BlogSitemapPageView
from pikt_inc.views.pages.contact import ContactPageView
from pikt_inc.views.pages.quote.billing_complete import QuoteBillingCompletePageView
from pikt_inc.views.pages.quote.digital_walkthrough import QuoteDigitalWalkthroughPageView
from pikt_inc.views.pages.quote.digital_walkthrough_received import QuoteDigitalWalkthroughReceivedPageView
from pikt_inc.views.pages.quote.instant_quote import InstantQuotePageView
from pikt_inc.views.pages.quote.quote_accepted import QuoteAcceptedPortalPageView
from pikt_inc.views.pages.quote.review import QuoteReviewPageView
from pikt_inc.views.pages.quote.thank_you import QuoteThankYouPageView
from pikt_inc.views.blog import BlogPageView
from pikt_inc.views.blog import FeedPageView
from pikt_inc.views.quote import QuotePageView


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
            (QuoteReviewPageView, "Review Your Quote", "Review the status of your secure quote link before continuing into the setup portal."),
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

    def test_contact_page_view_builds_public_contact_context(self):
        context = SimpleNamespace()

        result = ContactPageView().build_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.page_title, "Contact Pikt")
        self.assertIn("walkthrough requests", context.meta_description)
        self.assertEqual(context.description, context.meta_description)
        self.assertIn("Walkthrough request", context.request_type_options)

    def test_blog_page_view_reads_nested_metatags_and_dynamic_noindex(self):
        context = SimpleNamespace()

        result = BlogPageView(
            page_loader=lambda: {
                "page_title": "Fallback title",
                "metatags": {
                    "title": "Commercial Cleaning Blog",
                    "description": "Facility insights for recurring cleaning teams.",
                },
                "noindex_meta": 1,
            }
        ).build_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.page_title, "Commercial Cleaning Blog")
        self.assertEqual(context.meta_description, "Facility insights for recurring cleaning teams.")
        self.assertEqual(context.noindex_meta, 1)

    def test_blog_page_view_sets_404_for_not_found_payloads(self):
        context = SimpleNamespace()

        result = BlogPageView(
            page_loader=lambda: {
                "page_title": "Article Not Found",
                "not_found": 1,
            }
        ).build_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.http_status_code, 404)

    def test_feed_page_view_omits_body_class(self):
        context = SimpleNamespace()

        result = FeedPageView(page_loader=lambda: {"posts": []}).build_context(context)

        self.assertIs(result, context)
        self.assertFalse(hasattr(context, "body_class"))
        self.assertEqual(context.no_cache, 1)

    def test_concrete_blog_page_views_use_class_level_loaders(self):
        expectations = [
            (
                BlogHomePageView,
                {
                    "page_title": "Commercial Cleaning Blog",
                    "metatags": {
                        "title": "Commercial Cleaning Blog",
                        "description": "Commercial cleaning insights.",
                    },
                    "posts": [],
                    "noindex_meta": 0,
                },
                "Commercial Cleaning Blog",
            ),
            (
                BlogPostPageView,
                {
                    "page_title": "Lobby Cleaning Checklist",
                    "metatags": {
                        "title": "Lobby Cleaning Checklist",
                        "description": "A faster lobby checklist for shared spaces.",
                    },
                    "post": {"slug": "keep-a-lobby-presentation-ready"},
                    "noindex_meta": 0,
                },
                "Lobby Cleaning Checklist",
            ),
        ]

        for view_class, payload, title in expectations:
            with self.subTest(view_class=view_class.__name__):
                context = SimpleNamespace()
                original_loader = view_class.page_loader
                view_class.page_loader = staticmethod(lambda payload=payload: payload)
                try:
                    result = view_class().build_context(context)
                finally:
                    view_class.page_loader = original_loader

                self.assertIs(result, context)
                self.assertEqual(view_class.sitemap, 0)
                self.assertEqual(context.page_title, title)

    def test_concrete_blog_feed_views_use_class_level_loaders(self):
        expectations = [
            (BlogRssPageView, {"posts": [{"title": "RSS post"}]}, "posts"),
            (BlogSitemapPageView, {"links": [{"loc": "https://example.test/blog/post"}]}, "links"),
        ]

        for view_class, payload, key in expectations:
            with self.subTest(view_class=view_class.__name__):
                context = SimpleNamespace()
                original_loader = view_class.page_loader
                view_class.page_loader = staticmethod(lambda payload=payload: payload)
                try:
                    result = view_class().build_context(context)
                finally:
                    view_class.page_loader = original_loader

                self.assertIs(result, context)
                self.assertEqual(view_class.sitemap, 0)
                self.assertEqual(getattr(context, key), payload[key])
