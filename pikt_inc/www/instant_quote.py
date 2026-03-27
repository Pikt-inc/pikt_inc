from __future__ import annotations

from pikt_inc.views.pages.quote.instant_quote import InstantQuotePageView


VIEW_CLASS = InstantQuotePageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the instant quote context through the quote entry page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated instant quote context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/quote`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated instant quote context.
    """
    return build_context(context)
