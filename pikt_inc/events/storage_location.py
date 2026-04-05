from __future__ import annotations

import frappe


def _clean(value) -> str:
    return str(value or "").strip()


def _truthy(value) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    return _clean(value).lower() in {"1", "true", "yes", "on"}


def before_save(doc, _method=None):
    if _truthy(getattr(doc, "is_primary", None)) and not _truthy(getattr(doc, "active", None)):
        frappe.throw("Primary storage location must be active.")

    building_name = _clean(getattr(doc, "building", None))
    if not building_name or not _truthy(getattr(doc, "is_primary", None)):
        return

    current_name = _clean(getattr(doc, "name", None))
    rows = frappe.get_all(
        "Storage Location",
        filters={"building": building_name, "is_primary": 1},
        fields=["name"],
        limit_page_length=0,
    )

    for row in rows or []:
        row_name = _clean((row or {}).get("name"))
        if not row_name or row_name == current_name:
            continue

        frappe.db.set_value(
            "Storage Location",
            row_name,
            "is_primary",
            0,
            update_modified=False,
        )
