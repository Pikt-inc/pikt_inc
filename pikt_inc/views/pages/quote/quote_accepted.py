from __future__ import annotations

from pikt_inc.views.quote import QuotePageView


class QuoteAcceptedPortalPageView(QuotePageView):
    """Concrete view for the accepted quote portal page."""

    sitemap = 0
    page_title = "Quote Accepted"
    meta_description = "Accept your quote, set up billing, and confirm your service site access in one secure portal."
