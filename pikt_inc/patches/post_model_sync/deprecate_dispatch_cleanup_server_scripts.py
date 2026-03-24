from __future__ import annotations

import frappe


SERVER_SCRIPT_NAMES = [
    "Dispatch Calendar Subject Sync",
    "Dispatch Data Integrity Migration",
    "Dispatch Orchestrator Hour Gate",
    "Mark Dispatch Routes Dirty On Building Change",
    "Initial Assignment Attempt For Generated Requirements",
    "Nightly Generate Site Shift Requirements",
]


def execute():
    for script_name in SERVER_SCRIPT_NAMES:
        if frappe.db.exists("Server Script", script_name):
            frappe.db.set_value("Server Script", script_name, "disabled", 1)
