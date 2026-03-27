from __future__ import annotations

from pikt_inc.views.pages.blog.sitemap import BlogSitemapPageView

base_template_path = "www/blog-sitemap.xml"
VIEW_CLASS = BlogSitemapPageView
no_cache = VIEW_CLASS.no_cache
sitemap = VIEW_CLASS.sitemap


def build_context(context):
    """Build the blog sitemap context through the sitemap page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated blog sitemap context.
    """
    return VIEW_CLASS().build_context(context)


def get_context(context):
    """Build the context for the ``/blog-sitemap.xml`` route.

    :param context: The mutable Frappe page context object.
    :returns: The populated blog sitemap context.
    """
    return build_context(context)
