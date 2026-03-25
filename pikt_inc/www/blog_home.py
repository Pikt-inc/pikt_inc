from __future__ import annotations

import frappe

from pikt_inc.services import blog


no_cache = 1
sitemap = 0


def get_context(context):
    context.no_cache = 1
    context.body_class = "no-web-page-sections"
    return blog.get_blog_index_data(
        page=frappe.form_dict.get("page"),
        category=frappe.form_dict.get("category"),
    )
