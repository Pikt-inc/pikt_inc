from __future__ import annotations

import frappe


LEGACY_CONTACT_PAGE_ROUTES = ("contact",)
LEGACY_CONTACT_COMPONENT_NAMES = (
    "LP Contact Form",
    "LP Contact Info Card",
)


def execute():
    if not frappe.db.exists("DocType", "Builder Page"):
        return {"status": "missing-doctype", "removed": []}

    page_names = frappe.get_all(
        "Builder Page",
        filters={"route": ["in", LEGACY_CONTACT_PAGE_ROUTES]},
        pluck="name",
    )
    component_names = []
    if frappe.db.exists("DocType", "Builder Component"):
        component_names = frappe.get_all(
            "Builder Component",
            filters={"component_name": ["in", LEGACY_CONTACT_COMPONENT_NAMES]},
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
