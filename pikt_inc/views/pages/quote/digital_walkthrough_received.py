from __future__ import annotations

from pikt_inc.views.quote import QuotePageView


class QuoteDigitalWalkthroughReceivedPageView(QuotePageView):
    """Concrete view for the digital walkthrough confirmation page."""

    sitemap = 0
    page_title = "Digital Walkthrough Received"
    meta_description = "Confirmation that your digital walkthrough has been received."
