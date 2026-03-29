from __future__ import annotations

from pikt_inc.views.pages.portal.billing_info import PortalBillingInfoPageView


VIEW_CLASS = PortalBillingInfoPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the portal billing-info context through the billing-info page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated portal billing-info context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/portal/billing-info`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated portal billing-info context.
    """
    return build_context(context)
