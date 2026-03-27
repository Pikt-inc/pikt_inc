from __future__ import annotations

from pikt_inc.services import customer_portal
from pikt_inc.views.portal import PortalPageView


class PortalOverviewPageView(PortalPageView):
    """Concrete portal overview page view."""

    sitemap = 0
    page_loader = staticmethod(customer_portal.get_customer_portal_dashboard_data)
