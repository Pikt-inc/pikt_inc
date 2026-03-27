from __future__ import annotations

from pikt_inc.views.pages.portal.agreements import PortalAgreementsPageView


VIEW_CLASS = PortalAgreementsPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the portal agreements context through the agreements page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated portal agreements context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/portal/agreements`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated portal agreements context.
    """
    return build_context(context)
