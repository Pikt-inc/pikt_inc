from __future__ import annotations

from pikt_inc.views.pages.blog.rss import BlogRssPageView

base_template_path = "www/blog-rss.xml"
VIEW_CLASS = BlogRssPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the RSS feed context through the blog RSS page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated RSS feed context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/blog/rss.xml`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated RSS feed context.
    """
    return build_context(context)
