from __future__ import annotations

import frappe


SERVER_SCRIPT_NAMES = [
    "Provision Employee Onboarding Request",
    "Sync Employee Onboarding Packet",
]


def execute():
    for script_name in SERVER_SCRIPT_NAMES:
        if frappe.db.exists("Server Script", script_name):
            frappe.db.set_value("Server Script", script_name, "disabled", 1)
