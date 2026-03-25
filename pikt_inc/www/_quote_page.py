from __future__ import annotations


no_cache = 1
sitemap = 0


def build_context(context, *, title: str, description: str, noindex_meta: int = 1):
    context.no_cache = 1
    context.body_class = "no-web-page-sections"
    context.page_title = title
    context.meta_description = description
    context.description = description
    context.noindex_meta = 1 if noindex_meta else 0
    return context
