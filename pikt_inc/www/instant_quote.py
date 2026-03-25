from __future__ import annotations


no_cache = 1
sitemap = 0


def get_context(context):
    context.no_cache = 1
    context.body_class = "no-web-page-sections"
    context.page_title = "Get a Quote"
    return context
