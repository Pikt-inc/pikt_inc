from __future__ import annotations

from pikt_inc.views.pages.quote.billing_complete import QuoteBillingCompletePageView


VIEW_CLASS = QuoteBillingCompletePageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the billing-complete context through the setup-complete page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated billing-complete context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/billing-setup-complete`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated billing-complete context.
    """
    return build_context(context)
