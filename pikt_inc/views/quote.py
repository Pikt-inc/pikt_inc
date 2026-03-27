from __future__ import annotations

from .public import PublicPageView


class QuotePageView(PublicPageView):
    """Static view for quote-funnel pages with shared metadata defaults."""

    def __init__(self, *, title: str, description: str, noindex_meta: int = 1):
        """Initialize a quote-funnel page view.

        :param title: The page title to expose in the rendered context.
        :param description: The meta description to expose in the rendered
            context.
        :param noindex_meta: Whether the page should emit the noindex flag.
        """
        self.page_title = title
        self.meta_description = description
        self.noindex_meta = 1 if noindex_meta else 0
