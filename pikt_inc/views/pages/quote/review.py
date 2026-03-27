from __future__ import annotations

from pikt_inc.views.quote import QuotePageView


class QuoteReviewPageView(QuotePageView):
    """Concrete view for the quote review compatibility page."""

    sitemap = 0
    page_title = "Preparing Your Billing Setup"
    meta_description = "Compatibility redirect for previously sent public quote links."
