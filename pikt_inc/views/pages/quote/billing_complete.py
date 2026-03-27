from __future__ import annotations

from pikt_inc.views.quote import QuotePageView


class QuoteBillingCompletePageView(QuotePageView):
    """Concrete view for the billing-complete confirmation page."""

    sitemap = 0
    page_title = "Setup Complete"
    meta_description = "Your quote, invoice setup, and service-site access details are complete."
