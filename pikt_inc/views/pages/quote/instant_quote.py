from __future__ import annotations

from pikt_inc.views.quote import QuotePageView


class InstantQuotePageView(QuotePageView):
    """Concrete view for the public quote entry page."""

    sitemap = 0
    noindex_meta = None
    page_title = "Get a Quote"
