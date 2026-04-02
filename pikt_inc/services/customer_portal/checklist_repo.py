from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime

import frappe
from pydantic import field_validator

from ..contracts.common import ResponseModel, clean_str, truthy


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
    service_date: date | None = None
    checklist_template: str = ""
    status: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    worker: str = ""
    session_notes: str = ""
    creation: datetime | None = None
    modified: datetime | None = None

    @field_validator("name", "building", "checklist_template", "status", "worker", "session_notes", mode="before")
    @classmethod
    def clean_strings(cls, value: object) -> str:
        return clean_str(value)

    @field_validator("service_date", "started_at", "completed_at", "creation", "modified", mode="before")
    @classmethod
    def empty_temporal_to_none(cls, value: object):
        if value in (None, ""):
            return None
        return value


class ChecklistSessionItemRecord(ResponseModel):
    name: str = ""
    idx: int = 0
    item_key: str = ""
    category: str = ""
    sort_order: int = 0
    title_snapshot: str = ""
    description_snapshot: str = ""
    requires_image: bool = False
    allow_notes: bool | None = None
    is_required: bool | None = None
    completed: bool = False
    completed_at: datetime | None = None
    note: str = ""
    proof_image: str = ""

    @field_validator(
        "name",
        "item_key",
        "category",
        "title_snapshot",
        "description_snapshot",
        "note",
        "proof_image",
        mode="before",
    )
    @classmethod
    def clean_item_strings(cls, value: object) -> str:
        return clean_str(value)

    @field_validator("idx", "sort_order", mode="before")
    @classmethod
    def normalize_ints(cls, value: object) -> int:
        return int(value or 0)

    @field_validator("requires_image", "completed", mode="before")
    @classmethod
    def normalize_required_flags(cls, value: object) -> bool:
        if value in (None, ""):
            return False
        if isinstance(value, bool):
            return value
        return truthy(value)

    @field_validator("allow_notes", "is_required", mode="before")
    @classmethod
    def normalize_optional_flags(cls, value: object):
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return value
        return truthy(value)

    @field_validator("completed_at", mode="before")
    @classmethod
    def empty_completed_at_to_none(cls, value: object):
        if value in (None, ""):
            return None
        return value


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

    rows = frappe.get_all(
        "Checklist Session",
        filters=filters or None,
        fields=CHECKLIST_SESSION_FIELDS,
        order_by="completed_at desc, started_at desc, creation desc",
        limit=limit,
    )
    return [ChecklistSessionRecord.model_validate(row) for row in rows or []]


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
