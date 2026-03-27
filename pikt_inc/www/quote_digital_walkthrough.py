from __future__ import annotations

from pikt_inc.views.pages.quote.digital_walkthrough import QuoteDigitalWalkthroughPageView


VIEW_CLASS = QuoteDigitalWalkthroughPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the digital walkthrough context through the walkthrough page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated digital walkthrough context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/digital-walkthrough`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated digital walkthrough context.
    """
    return build_context(context)
