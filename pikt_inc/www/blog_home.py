from __future__ import annotations

from pikt_inc.views.pages.blog.home import BlogHomePageView


VIEW_CLASS = BlogHomePageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the blog index context through the blog home page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated blog index context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/blog`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated blog index context.
    """
    return build_context(context)
