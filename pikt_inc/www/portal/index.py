from __future__ import annotations

from pikt_inc.services import customer_portal
from pikt_inc.www._portal_page import build_context


no_cache = 1
sitemap = 0


def get_context(context):
    return build_context(context, page_loader=customer_portal.get_customer_portal_dashboard_data)
