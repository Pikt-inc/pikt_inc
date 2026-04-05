from __future__ import annotations

import frappe


WEEKDAY_ORDER = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
WEEKDAY_SET = set(WEEKDAY_ORDER)


def derive_unavailable_service_days(raw_service_days: str | None) -> list[str]:
    if not raw_service_days:
        return []

    selected_days = []
    seen_days = set()

    for value in raw_service_days.split(","):
        normalized = value.strip().lower()
        if normalized in WEEKDAY_SET and normalized not in seen_days:
            selected_days.append(normalized)
            seen_days.add(normalized)

    if not selected_days:
        return []

    selected_day_set = set(selected_days)
    return [day for day in WEEKDAY_ORDER if day not in selected_day_set]


def execute():
    if not frappe.db.exists("DocType", "Building"):
        return {"status": "missing-doctype", "updated": 0}

    meta = frappe.get_meta("Building")
    fieldnames = {field.fieldname for field in meta.fields}

    if "unavailable_service_days" not in fieldnames:
        return {"status": "missing-field", "updated": 0}

    if "service_days" not in fieldnames:
        return {"status": "missing-legacy-field", "updated": 0}

    rows = frappe.get_all(
        "Building",
        fields=["name", "service_days", "unavailable_service_days"],
        limit_page_length=0,
    )

    updated = 0
    for row in rows:
        if row.get("unavailable_service_days") not in (None, ""):
            continue

        unavailable_days = derive_unavailable_service_days(row.get("service_days"))
        if not unavailable_days:
            continue

        frappe.db.set_value(
            "Building",
            row["name"],
            "unavailable_service_days",
            ",".join(unavailable_days),
            update_modified=False,
        )
        updated += 1

    if updated:
        frappe.clear_cache()

    return {"status": "updated" if updated else "noop", "updated": updated}
