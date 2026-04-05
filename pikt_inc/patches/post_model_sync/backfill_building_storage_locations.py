from __future__ import annotations

import frappe


BUILDING_DOCTYPE = "Building"
STORAGE_LOCATION_DOCTYPE = "Storage Location"
DEFAULT_LOCATION_NAME = "Primary Storage"


def build_legacy_storage_location_values(building_name: str, directions: str) -> dict[str, object]:
    return {
        "doctype": STORAGE_LOCATION_DOCTYPE,
        "building": building_name,
        "location_name": DEFAULT_LOCATION_NAME,
        "location_type": "other",
        "directions": directions,
        "notes": None,
        "active": 1,
        "is_primary": 1,
    }


def execute():
    if not frappe.db.exists("DocType", BUILDING_DOCTYPE):
        return {"status": "missing-building-doctype", "created": 0}

    if not frappe.db.exists("DocType", STORAGE_LOCATION_DOCTYPE):
        return {"status": "missing-storage-location-doctype", "created": 0}

    meta = frappe.get_meta(BUILDING_DOCTYPE)
    fieldnames = {field.fieldname for field in meta.fields}
    if "key_storage_location" not in fieldnames:
        return {"status": "missing-legacy-field", "created": 0}

    rows = frappe.get_all(
        BUILDING_DOCTYPE,
        fields=["name", "key_storage_location"],
        limit_page_length=0,
    )

    created = 0
    for row in rows or []:
        building_name = str((row or {}).get("name") or "").strip()
        directions = str((row or {}).get("key_storage_location") or "").strip()
        if not building_name or not directions:
            continue

        existing = frappe.get_all(
            STORAGE_LOCATION_DOCTYPE,
            filters={"building": building_name},
            fields=["name"],
            limit_page_length=1,
        )
        if existing:
            continue

        frappe.get_doc(
            build_legacy_storage_location_values(
                building_name=building_name,
                directions=directions,
            )
        ).insert(ignore_permissions=True)
        created += 1

    if created:
        frappe.clear_cache()

    return {"status": "created" if created else "noop", "created": created}
