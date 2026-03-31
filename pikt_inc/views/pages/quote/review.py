from __future__ import annotations

from pikt_inc.views.quote import QuotePageView


class QuoteReviewPageView(QuotePageView):
    """Concrete view for the quote review compatibility page."""

    sitemap = 0
    page_title = "Review Your Quote"
    meta_description = "Review the status of your secure quote link before continuing into the setup portal."
