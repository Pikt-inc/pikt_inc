from __future__ import annotations

from pikt_inc.views.pages.portal.locations import PortalLocationsPageView


VIEW_CLASS = PortalLocationsPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the portal locations context through the locations page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated portal locations context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/portal/locations`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated portal locations context.
    """
    return build_context(context)
