from __future__ import annotations

import frappe

from pikt_inc.services import blog


no_cache = 1
sitemap = 0


def get_context(context):
    context.no_cache = 1
    context.body_class = "no-web-page-sections"
    data = blog.get_blog_post_data(
        slug=frappe.form_dict.get("slug"),
        preview=frappe.form_dict.get("preview"),
    )
    if data.get("not_found"):
        context.http_status_code = 404
    return data
