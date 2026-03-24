from __future__ import annotations

import frappe


SERVER_SCRIPT_NAMES = [
    "Sync Digital Walkthrough Submission To Opportunity",
    "Apply Digital Walkthrough Reviewer Module Profile",
]


def execute():
    for script_name in SERVER_SCRIPT_NAMES:
        if frappe.db.exists("Server Script", script_name):
            frappe.db.set_value("Server Script", script_name, "disabled", 1)
