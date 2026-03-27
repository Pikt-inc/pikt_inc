from __future__ import annotations

from pikt_inc.views.pages.portal.billing import PortalBillingPageView


VIEW_CLASS = PortalBillingPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the portal billing context through the billing page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated portal billing context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/portal/billing`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated portal billing context.
    """
    return build_context(context)
