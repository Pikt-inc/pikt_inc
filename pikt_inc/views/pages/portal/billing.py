from __future__ import annotations

from pikt_inc.services import customer_portal
from pikt_inc.views.portal import PortalPageView


class PortalBillingPageView(PortalPageView):
    """Concrete portal billing page view."""

    sitemap = 0
    retired_redirect_to = "/orders"
    page_loader = staticmethod(customer_portal.get_customer_portal_billing_data)
