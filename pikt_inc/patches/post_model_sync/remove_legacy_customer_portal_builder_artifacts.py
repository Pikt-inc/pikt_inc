from __future__ import annotations

import frappe


LEGACY_PORTAL_PAGE_ROUTES = (
    "portal",
    "portal/agreements",
    "portal/billing",
    "portal/locations",
)

LEGACY_PORTAL_COMPONENT_NAMES = (
    "Portal Shell Header",
    "Portal Summary Stat Card",
    "Portal Record List Card",
    "Portal Invoice Row Card",
    "Portal Agreement Preview Card",
    "Portal Location Edit Card",
    "Portal Empty State Block",
)


def execute():
    if not frappe.db.exists("DocType", "Builder Page"):
        return {"status": "missing-doctype", "removed_pages": [], "removed_components": []}

    page_names = frappe.get_all(
        "Builder Page",
        filters={"route": ["in", LEGACY_PORTAL_PAGE_ROUTES]},
        pluck="name",
    )
    removed_pages = []
    for name in page_names:
        frappe.delete_doc("Builder Page", name, ignore_permissions=True, force=True)
        removed_pages.append(name)

    removed_components = []
    if frappe.db.exists("DocType", "Builder Component"):
        component_names = frappe.get_all(
            "Builder Component",
            filters={"component_name": ["in", LEGACY_PORTAL_COMPONENT_NAMES]},
            pluck="name",
        )
        for name in component_names:
            frappe.delete_doc("Builder Component", name, ignore_permissions=True, force=True)
            removed_components.append(name)

    if removed_pages or removed_components:
        frappe.clear_cache()
        return {
            "status": "removed",
            "removed_pages": removed_pages,
            "removed_components": removed_components,
        }

    return {"status": "noop", "removed_pages": [], "removed_components": []}
