from __future__ import annotations

from pikt_inc.views.quote import QuotePageView


class QuoteThankYouPageView(QuotePageView):
    """Concrete view for the quote thank-you page."""

    sitemap = 0
    page_title = "Instant Estimate"
    meta_description = "Instant estimate and next steps for your commercial cleaning request."
