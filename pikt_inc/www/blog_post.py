from __future__ import annotations

from pikt_inc.views.pages.blog.post import BlogPostPageView


VIEW_CLASS = BlogPostPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the blog article context through the blog post page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated blog article context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/blog/<slug>`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated blog article context.
    """
    return build_context(context)
