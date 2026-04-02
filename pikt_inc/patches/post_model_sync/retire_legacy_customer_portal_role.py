from __future__ import annotations

import frappe


LEGACY_ROLE_NAME = "Customer Portal User"
CUSTOMER_ROLE_NAME = "Customer"


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def execute():
    legacy_rows = frappe.get_all(
        "Has Role",
        filters={"role": LEGACY_ROLE_NAME},
        fields=["name", "parent"],
        limit=5000,
    )

    migrated: list[str] = []
    removed: list[str] = []
    invalid: list[str] = []

    for row in legacy_rows:
        row_name = clean(row.get("name"))
        user_name = clean(row.get("parent"))
        if not row_name or not user_name or user_name == "Guest":
            continue

        customer_name = clean(frappe.db.get_value("User", user_name, "custom_customer"))
        has_customer_role = bool(frappe.db.exists("Has Role", {"parent": user_name, "role": CUSTOMER_ROLE_NAME}))

        if customer_name and not has_customer_role:
            frappe.db.set_value("Has Role", row_name, "role", CUSTOMER_ROLE_NAME, update_modified=False)
            migrated.append(user_name)
            continue

        frappe.delete_doc("Has Role", row_name, ignore_permissions=True, force=True)
        if customer_name:
            removed.append(user_name)
        else:
            invalid.append(user_name)

    role_removed = False
    if frappe.db.exists("Role", LEGACY_ROLE_NAME):
        frappe.delete_doc("Role", LEGACY_ROLE_NAME, ignore_permissions=True, force=True)
        role_removed = True

    if migrated or removed or invalid or role_removed:
        frappe.clear_cache()
        return {
            "status": "updated",
            "migrated_users": migrated,
            "removed_duplicate_assignments": removed,
            "removed_invalid_assignments": invalid,
            "role_removed": role_removed,
        }

    return {
        "status": "noop",
        "migrated_users": [],
        "removed_duplicate_assignments": [],
        "removed_invalid_assignments": [],
        "role_removed": False,
    }
