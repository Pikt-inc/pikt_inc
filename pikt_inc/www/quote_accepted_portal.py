from __future__ import annotations

from pikt_inc.views.pages.quote.quote_accepted import QuoteAcceptedPortalPageView


VIEW_CLASS = QuoteAcceptedPortalPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the accepted quote portal context through the accepted page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated accepted quote portal context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/quote-accepted`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated accepted quote portal context.
    """
    return build_context(context)
