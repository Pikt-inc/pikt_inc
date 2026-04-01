from __future__ import annotations

from pikt_inc.services.customer_portal.website_records import build_portal_list_context


no_cache = 1
sitemap = 0


def get_context(context):
    return build_portal_list_context(context, "agreements")
