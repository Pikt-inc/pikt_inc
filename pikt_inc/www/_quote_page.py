from __future__ import annotations

from pikt_inc.views.quote import QuotePageView


no_cache = 1
sitemap = 0


def build_context(context, *, title: str, description: str, noindex_meta: int = 1):
    """Build quote-page context through the shared quote view abstraction.

    :param context: The mutable Frappe page context object.
    :param title: The page title to apply.
    :param description: The page meta description to apply.
    :param noindex_meta: Whether the page should emit the noindex flag.
    :returns: The populated page context.
    """
    return QuotePageView(
        title=title,
        description=description,
        noindex_meta=noindex_meta,
    ).build_context(context)
