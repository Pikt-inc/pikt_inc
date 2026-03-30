from __future__ import annotations

import frappe


LEGACY_CONTACT_REQUEST_WEB_FORM = "contact-request-form"


def execute():
    if not frappe.db.exists("DocType", "Web Form"):
        return {"status": "missing-doctype", "removed": []}

    if not frappe.db.exists("Web Form", LEGACY_CONTACT_REQUEST_WEB_FORM):
        return {"status": "noop", "removed": []}

    frappe.delete_doc("Web Form", LEGACY_CONTACT_REQUEST_WEB_FORM, ignore_permissions=True, force=True)
    frappe.clear_cache()
    return {"status": "removed", "removed": [LEGACY_CONTACT_REQUEST_WEB_FORM]}
