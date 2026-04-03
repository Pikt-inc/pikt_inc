from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import frappe

from ...contracts.common import clean_str
from .models import ChecklistSessionItemRecord, ChecklistSessionRecord, ChecklistTemplateItemRecord


CHECKLIST_TEMPLATE_ITEM_FIELDS = [
    "name",
    "idx",
    "item_key",
    "category",
    "sort_order",
    "title",
    "description",
    "requires_image",
    "allow_notes",
    "is_required",
    "active",
]

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


def _session_payload(doc: Any) -> dict[str, Any]:
    return {field: doc.get(field) if hasattr(doc, "get") else getattr(doc, field, None) for field in CHECKLIST_SESSION_FIELDS}


def _session_item_payload(row: Any) -> dict[str, Any]:
    return {
        field: row.get(field) if hasattr(row, "get") else getattr(row, field, None)
        for field in CHECKLIST_SESSION_ITEM_FIELDS
    }


def get_template_items(template_name: str, *, active_only: bool = True) -> list[ChecklistTemplateItemRecord]:
    template_name = clean_str(template_name)
    if not template_name:
        return []
    filters = {
        "parent": template_name,
        "parenttype": "Checklist Template",
        "parentfield": "items",
    }
    if active_only:
        filters["active"] = 1
    rows = frappe.get_all(
        "Checklist Template Item",
        filters=filters,
        fields=CHECKLIST_TEMPLATE_ITEM_FIELDS,
        order_by="sort_order asc, idx asc",
        limit=500,
    )
    return [ChecklistTemplateItemRecord.model_validate(row) for row in rows or []]


def get_session(session_name: str) -> ChecklistSessionRecord | None:
    session_name = clean_str(session_name)
    if not session_name:
        return None
    row = frappe.db.get_value("Checklist Session", session_name, CHECKLIST_SESSION_FIELDS, as_dict=True)
    if not row:
        return None
    return ChecklistSessionRecord.model_validate(row)


def list_sessions(
    *,
    building_names: Sequence[str] | None = None,
    session_name: str = "",
    status: str = "",
    service_date=None,
    limit: int = 200,
) -> list[ChecklistSessionRecord]:
    filters: list[list[object]] = []
    session_name = clean_str(session_name)
    limit = max(1, int(limit or 200))

    if session_name:
        filters.append(["name", "=", session_name])

    if building_names is not None:
        scoped_building_names = [clean_str(name) for name in building_names if clean_str(name)]
        if not scoped_building_names:
            return []
        filters.append(["building", "in", scoped_building_names])

    status = clean_str(status)
    if status:
        filters.append(["status", "=", status])

    if service_date not in (None, ""):
        filters.append(["service_date", "=", service_date])

    rows = frappe.get_all(
        "Checklist Session",
        filters=filters or None,
        fields=CHECKLIST_SESSION_FIELDS,
        order_by="completed_at desc, started_at desc, creation desc",
        limit=limit,
    )
    return [ChecklistSessionRecord.model_validate(row) for row in rows or []]


def get_active_session(building_name: str, service_date) -> ChecklistSessionRecord | None:
    sessions = list_sessions(
        building_names=[clean_str(building_name)],
        service_date=service_date,
        status="in_progress",
        limit=1,
    )
    return sessions[0] if sessions else None


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


def create_session(building_name: str, service_date) -> ChecklistSessionRecord:
    doc = frappe.get_doc(
        {
            "doctype": "Checklist Session",
            "building": clean_str(building_name),
            "service_date": service_date,
        }
    )
    doc.insert(ignore_permissions=True)
    return ChecklistSessionRecord.model_validate(_session_payload(doc))


def update_session_item(
    session_name: str,
    item_key: str,
    *,
    completed: bool | None = None,
    note: str | None = None,
    proof_image: str | None = None,
) -> tuple[ChecklistSessionRecord, ChecklistSessionItemRecord] | None:
    session_name = clean_str(session_name)
    item_key = clean_str(item_key)
    if not session_name or not item_key:
        return None

    doc = frappe.get_doc("Checklist Session", session_name)
    target = None
    for row in list(getattr(doc, "items", None) or []):
        row_item_key = clean_str(getattr(row, "item_key", None) or (row.get("item_key") if hasattr(row, "get") else None))
        row_name = clean_str(getattr(row, "name", None) or (row.get("name") if hasattr(row, "get") else None))
        if row_item_key == item_key or row_name == item_key:
            target = row
            break

    if target is None:
        return None

    if completed is not None:
        target.completed = 1 if completed else 0
        if not completed:
            target.completed_at = None

    if note is not None:
        target.note = clean_str(note)

    if proof_image is not None:
        target.proof_image = clean_str(proof_image)

    doc.save(ignore_permissions=True)

    refreshed = get_session(doc.name)
    if refreshed is None:
        return None
    refreshed_items = get_session_items(doc.name)
    refreshed_item = next(
        (row for row in refreshed_items if row.item_key == item_key or row.name == item_key),
        None,
    )
    if refreshed_item is None:
        return None

    return refreshed, refreshed_item


def complete_session(session_name: str) -> ChecklistSessionRecord | None:
    session_name = clean_str(session_name)
    if not session_name:
        return None
    doc = frappe.get_doc("Checklist Session", session_name)
    doc.status = "completed"
    doc.save(ignore_permissions=True)
    return ChecklistSessionRecord.model_validate(_session_payload(doc))
