from __future__ import annotations

from pikt_inc.views.pages.portal.overview import PortalOverviewPageView


VIEW_CLASS = PortalOverviewPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the portal overview context through the overview page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated portal overview context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/portal`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated portal overview context.
    """
    return build_context(context)
