from __future__ import annotations

import frappe


ROLE_NAME = "Customer Portal User"
ROLE_HOME = "portal"


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def execute():
    existing = frappe.db.exists("Role", ROLE_NAME)
    if existing:
        role_doc = frappe.get_doc("Role", ROLE_NAME)
    else:
        role_doc = frappe.get_doc(
            {
                "doctype": "Role",
                "role_name": ROLE_NAME,
                "desk_access": 0,
                "home_page": ROLE_HOME,
            }
        )
        role_doc.insert(ignore_permissions=True)
        return {"status": "created", "role": role_doc.name}

    changed = False
    if int(getattr(role_doc, "desk_access", 0) or 0) != 0:
        role_doc.desk_access = 0
        changed = True
    if clean(getattr(role_doc, "home_page", None)) != ROLE_HOME:
        role_doc.home_page = ROLE_HOME
        changed = True
    if changed:
        role_doc.save(ignore_permissions=True)
        return {"status": "updated", "role": role_doc.name}
    return {"status": "noop", "role": role_doc.name}
