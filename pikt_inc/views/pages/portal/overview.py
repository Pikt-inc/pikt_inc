from __future__ import annotations

from pikt_inc.services import customer_portal
from pikt_inc.views.portal import PortalPageView


class PortalOverviewPageView(PortalPageView):
    """Concrete portal overview page view."""

    sitemap = 0
    retired_redirect_to = "/orders"
    page_loader = staticmethod(customer_portal.get_customer_portal_dashboard_data)
