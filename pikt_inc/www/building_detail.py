from __future__ import annotations

import frappe

from pikt_inc.services.customer_portal.website_records import build_portal_detail_context


no_cache = 1
sitemap = 0


def get_context(context):
    return build_portal_detail_context(context, "buildings", frappe.form_dict.get("slug"))
