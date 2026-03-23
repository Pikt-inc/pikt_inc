from __future__ import annotations

import frappe


SERVER_SCRIPT_NAMES = (
    "Complete Public Service Agreement Signature",
    "Complete Public Quote Billing Setup V2",
    "Complete Public Quote Access Setup V2",
    "Complete Public Quote Billing Setup",
    "Complete Public Quote Access Setup",
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
