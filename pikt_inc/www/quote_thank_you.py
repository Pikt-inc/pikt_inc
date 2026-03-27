from __future__ import annotations

from pikt_inc.views.pages.quote.thank_you import QuoteThankYouPageView


VIEW_CLASS = QuoteThankYouPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the quote thank-you context through the thank-you page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated quote thank-you context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/thank-you`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated quote thank-you context.
    """
    return build_context(context)
