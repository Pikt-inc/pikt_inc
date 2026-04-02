from __future__ import annotations

from typing import Any

import frappe

from ..contracts.common import ResponseModel, clean_str
from .building_repo import get_building, get_customer_buildings


CHECKLIST_SESSION_FIELDS = [
    "name",
    "building",
    "service_date",
    "checklist_template",
    "status",
    "started_at",
    "completed_at",
    "worker",
    "session_notes",
    "creation",
    "modified",
]

CHECKLIST_SESSION_ITEM_FIELDS = [
    "name",
    "idx",
    "item_key",
    "category",
    "sort_order",
    "title_snapshot",
    "description_snapshot",
    "requires_image",
    "allow_notes",
    "is_required",
    "completed",
    "completed_at",
    "note",
    "proof_image",
]


class ChecklistSessionRecord(ResponseModel):
    name: str = ""
    building: str = ""
    service_date: Any = None
    checklist_template: str = ""
    status: str = ""
    started_at: Any = None
    completed_at: Any = None
    worker: str = ""
    session_notes: str = ""
    creation: Any = None
    modified: Any = None


class ChecklistSessionItemRecord(ResponseModel):
    name: str = ""
    idx: int = 0
    item_key: str = ""
    category: str = ""
    sort_order: int = 0
    title_snapshot: str = ""
    description_snapshot: str = ""
    requires_image: Any = None
    allow_notes: Any = None
    is_required: Any = None
    completed: Any = None
    completed_at: Any = None
    note: str = ""
    proof_image: str = ""


def _session_sort_value(row: ChecklistSessionRecord) -> str:
    return str(
        row.completed_at
        or row.started_at
        or row.service_date
        or row.modified
        or row.creation
        or ""
    )


def get_session(session_name: str) -> ChecklistSessionRecord | None:
    session_name = clean_str(session_name)
    if not session_name:
        return None
    row = frappe.db.get_value("Checklist Session", session_name, CHECKLIST_SESSION_FIELDS, as_dict=True)
    if not row:
        return None
    return ChecklistSessionRecord.model_validate(row)


def get_customer_sessions(
    customer_name: str,
    *,
    building_name: str = "",
    status: str = "",
    limit: int = 200,
) -> list[ChecklistSessionRecord]:
    customer_name = clean_str(customer_name)
    building_name = clean_str(building_name)
    limit = max(1, int(limit or 200))

    if building_name:
        building = get_building(building_name)
        building_names = [building.name] if building and building.customer == customer_name else []
    else:
        building_names = [building.name for building in get_customer_buildings(customer_name)]

    if not building_names:
        return []

    rows: list[ChecklistSessionRecord] = []
    for current_building in building_names:
        filters: dict[str, object] = {"building": current_building}
        if clean_str(status):
            filters["status"] = clean_str(status)
        session_rows = frappe.get_all(
            "Checklist Session",
            filters=filters,
            fields=CHECKLIST_SESSION_FIELDS,
            order_by="completed_at desc, started_at desc, creation desc",
            limit=limit,
        )
        rows.extend(ChecklistSessionRecord.model_validate(row) for row in session_rows or [])

    rows.sort(key=_session_sort_value, reverse=True)
    return rows[:limit]


def get_session_items(session_name: str) -> list[ChecklistSessionItemRecord]:
    session_name = clean_str(session_name)
    if not session_name:
        return []
    rows = frappe.get_all(
        "Checklist Session Item",
        filters={"parent": session_name, "parenttype": "Checklist Session", "parentfield": "items"},
        fields=CHECKLIST_SESSION_ITEM_FIELDS,
        order_by="idx asc",
        limit=500,
    )
    return [ChecklistSessionItemRecord.model_validate(row) for row in rows or []]
