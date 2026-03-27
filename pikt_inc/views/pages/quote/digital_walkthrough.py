from __future__ import annotations

from pikt_inc.views.quote import QuotePageView


class QuoteDigitalWalkthroughPageView(QuotePageView):
    """Concrete view for the digital walkthrough upload page."""

    sitemap = 0
    page_title = "Digital Walkthrough"
    meta_description = "Upload your completed digital walkthrough for commercial cleaning review."
