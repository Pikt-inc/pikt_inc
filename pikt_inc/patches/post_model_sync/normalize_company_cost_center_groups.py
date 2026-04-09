from __future__ import annotations

import frappe


def _clean(value) -> str:
    return str(value or "").strip()


def _cost_center_row(name: str) -> dict | None:
    cost_center_name = _clean(name)
    if not cost_center_name:
        return None

    row = frappe.db.get_value(
        "Cost Center",
        cost_center_name,
        ["name", "company", "parent_cost_center", "is_group"],
        as_dict=True,
    )
    return dict(row) if row else None


def _group_cost_centers(company: str) -> list[dict]:
    company_name = _clean(company)
    if not company_name:
        return []

    return [
        dict(row)
        for row in frappe.get_all(
            "Cost Center",
            filters={"company": company_name, "is_group": 1},
            fields=["name", "parent_cost_center"],
            order_by="lft asc",
            limit_page_length=0,
        )
    ]


def resolve_group_cost_center(company: str, configured_cost_center: str | None) -> str:
    company_name = _clean(company)
    configured_name = _clean(configured_cost_center)

    if configured_name:
        configured_row = _cost_center_row(configured_name) or {}
        if _clean(configured_row.get("company")) == company_name:
            if int(configured_row.get("is_group") or 0) == 1:
                return configured_name

            parent_name = _clean(configured_row.get("parent_cost_center"))
            if parent_name:
                parent_row = _cost_center_row(parent_name) or {}
                if _clean(parent_row.get("company")) == company_name and int(parent_row.get("is_group") or 0) == 1:
                    return parent_name

    group_rows = _group_cost_centers(company_name)
    if not group_rows:
        return ""

    for row in group_rows:
        if not _clean(row.get("parent_cost_center")):
            return _clean(row.get("name"))

    return _clean(group_rows[0].get("name"))


def execute():
    if not frappe.db.exists("DocType", "Company") or not frappe.db.exists("DocType", "Cost Center"):
        return {"status": "missing-doctype", "updated": 0}

    rows = frappe.get_all(
        "Company",
        fields=["name", "cost_center"],
        limit_page_length=0,
    )

    updated = 0
    for row in rows:
        company_name = _clean((row or {}).get("name"))
        if not company_name:
            continue

        desired_cost_center = resolve_group_cost_center(company_name, (row or {}).get("cost_center"))
        if not desired_cost_center or desired_cost_center == _clean((row or {}).get("cost_center")):
            continue

        frappe.db.set_value(
            "Company",
            company_name,
            "cost_center",
            desired_cost_center,
            update_modified=False,
        )
        updated += 1

    if updated:
        frappe.clear_cache()

    return {"status": "updated" if updated else "noop", "updated": updated}
