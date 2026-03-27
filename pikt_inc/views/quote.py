from __future__ import annotations

from .public import PublicPageView


class QuotePageView(PublicPageView):
    """Static view for quote-funnel pages with shared metadata defaults."""

    noindex_meta = 1

    def __init__(self, *, title: str | None = None, description: str | None = None, noindex_meta: int | None = None):
        """Initialize a quote-funnel page view.

        :param title: Optional page title override for the rendered context.
        :param description: Optional meta description override for the rendered
            context.
        :param noindex_meta: Optional override for the noindex flag.
        """
        if title is not None:
            self.page_title = title
        if description is not None:
            self.meta_description = description
        if noindex_meta is not None:
            self.noindex_meta = 1 if noindex_meta else 0
