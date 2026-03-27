from __future__ import annotations

from pikt_inc.services import customer_portal
from pikt_inc.views.portal import PortalPageView


class PortalLocationsPageView(PortalPageView):
    """Concrete portal locations page view."""

    sitemap = 0
    page_loader = staticmethod(customer_portal.get_customer_portal_locations_data)
