from __future__ import annotations

from pikt_inc.views.pages.quote.review import QuoteReviewPageView


VIEW_CLASS = QuoteReviewPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the quote review context through the review page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated quote review context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/review-quote`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated quote review context.
    """
    return build_context(context)
