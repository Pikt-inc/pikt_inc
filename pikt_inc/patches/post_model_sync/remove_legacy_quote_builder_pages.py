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
LEGACY_QUOTE_COMPONENT_NAMES = (
    "LP Quote Form",
    "LP Quote Result Section",
    "LP Walkthrough Received",
)


def execute():
    if not frappe.db.exists("DocType", "Builder Page"):
        return {"status": "missing-doctype", "removed": {"pages": [], "components": []}}

    page_names = frappe.get_all(
        "Builder Page",
        filters={"route": ["in", LEGACY_QUOTE_PAGE_ROUTES]},
        pluck="name",
    )
    component_names = []
    if frappe.db.exists("DocType", "Builder Component"):
        component_names = frappe.get_all(
            "Builder Component",
            filters={"component_name": ["in", LEGACY_QUOTE_COMPONENT_NAMES]},
            pluck="name",
        )

    removed = {"pages": [], "components": []}
    for name in page_names:
        frappe.delete_doc("Builder Page", name, ignore_permissions=True, force=True)
        removed["pages"].append(name)

    for name in component_names:
        frappe.delete_doc("Builder Component", name, ignore_permissions=True, force=True)
        removed["components"].append(name)

    if removed["pages"] or removed["components"]:
        frappe.clear_cache()
        return {"status": "removed", "removed": removed}

    return {"status": "noop", "removed": removed}
