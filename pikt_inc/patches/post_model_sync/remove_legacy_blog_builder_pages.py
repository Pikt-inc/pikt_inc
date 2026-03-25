from __future__ import annotations

import frappe


LEGACY_BLOG_PAGE_NAMES = (
    "page-blog-index",
    "page-blog-detail",
)


def execute():
    if not frappe.db.exists("DocType", "Builder Page"):
        return {"status": "missing-doctype", "removed": []}

    removed = []
    for name in LEGACY_BLOG_PAGE_NAMES:
        if frappe.db.exists("Builder Page", name):
            frappe.delete_doc("Builder Page", name, ignore_permissions=True, force=True)
            removed.append(name)

    if removed:
        frappe.clear_cache()
        return {"status": "removed", "removed": removed}

    return {"status": "noop", "removed": removed}
