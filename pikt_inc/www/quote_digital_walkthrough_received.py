from __future__ import annotations

from pikt_inc.views.pages.quote.digital_walkthrough_received import QuoteDigitalWalkthroughReceivedPageView


VIEW_CLASS = QuoteDigitalWalkthroughReceivedPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the walkthrough confirmation context through the received page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated walkthrough confirmation context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/digital-walkthrough-received`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated walkthrough confirmation context.
    """
    return build_context(context)
