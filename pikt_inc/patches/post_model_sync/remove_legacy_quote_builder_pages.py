from __future__ import annotations

import frappe


LEGACY_QUOTE_PAGE_ROUTES = (
    "quote",
    "thank-you",
    "digital-walkthrough",
    "digital-walkthrough-received",
    "review-quote",
    "quote-accepted",
    "billing-setup-complete",
)


def execute():
    if not frappe.db.exists("DocType", "Builder Page"):
        return {"status": "missing-doctype", "removed": []}

    page_names = frappe.get_all(
        "Builder Page",
        filters={"route": ["in", LEGACY_QUOTE_PAGE_ROUTES]},
        pluck="name",
    )
    removed = []
    for name in page_names:
        frappe.delete_doc("Builder Page", name, ignore_permissions=True, force=True)
        removed.append(name)

    if removed:
        frappe.clear_cache()
        return {"status": "removed", "removed": removed}

    return {"status": "noop", "removed": removed}
