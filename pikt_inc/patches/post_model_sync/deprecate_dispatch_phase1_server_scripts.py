from __future__ import annotations

import frappe


SERVER_SCRIPT_NAMES = (
    "Dispatch SSR Reconcile Rule API",
    "Dispatch Sync Paused Buildings API",
    "Recurring Service Rule Immediate Generate",
    "Nightly Dispatch Orchestrator",
    "Normalize Site Shift Requirement Integrity",
    "Building Pause Sync Site Shift Requirements",
    "Dispatch Reconcile Routes API",
    "Sync Dispatch Route From Site Shift Requirement",
    "Normalize Dispatch Route",
    "Dispatch Route Email Orchestrator",
)


def execute():
    if not frappe.db.exists("DocType", "Server Script"):
        return

    scripts = frappe.get_all(
        "Server Script",
        filters={"name": ["in", list(SERVER_SCRIPT_NAMES)]},
        fields=["name", "disabled"],
        limit=len(SERVER_SCRIPT_NAMES),
    )

    for script in scripts:
        if not script.get("disabled"):
            frappe.db.set_value(
                "Server Script",
                script.get("name"),
                "disabled",
                1,
                update_modified=False,
            )

    frappe.clear_cache()
