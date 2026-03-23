from __future__ import annotations

import frappe


SERVER_SCRIPT_NAMES = (
    "Validate Public Quotation",
    "Accept Public Quotation",
    "Load Public Quote Portal State",
    "Prepare Public Quotation Acceptance",
    "Mark Opportunity Reviewed On Quotation",
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
