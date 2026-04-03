from __future__ import annotations

import re
from typing import Any

import frappe


BUILDING_DOCTYPE = "Building"
CHECKLIST_TEMPLATE_DOCTYPE = "Checklist Template"
CHECKLIST_TEMPLATE_ITEM_DOCTYPE = "Checklist Template Item"
CHECKLIST_SESSION_DOCTYPE = "Checklist Session"
CHECKLIST_SESSION_ITEM_DOCTYPE = "Checklist Session Item"

BUILDING_CURRENT_TEMPLATE_FIELD = "current_checklist_template"

TEMPLATE_STATUS_DRAFT = "Draft"
TEMPLATE_STATUS_ACTIVE = "Active"
TEMPLATE_STATUS_ARCHIVED = "Archived"

SESSION_STATUS_IN_PROGRESS = "in_progress"
SESSION_STATUS_COMPLETED = "completed"


def clean(value: Any) -> str:
    return str(value or "").strip()


def truthy(value: Any) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "on"}


def _normalize_target_duration_seconds(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        normalized = int(value)
    except (TypeError, ValueError):
        frappe.throw("Checklist item target duration must be a non-negative whole number of seconds.")
    if normalized < 0:
        frappe.throw("Checklist item target duration must be a non-negative whole number of seconds.")
    return normalized or None


def _now_datetime():
    try:
        return frappe.utils.now_datetime()
    except Exception:
        return frappe.utils.get_datetime(frappe.utils.now())


def _field_value(doc, fieldname: str, default=None):
    if hasattr(doc, "get"):
        try:
            return doc.get(fieldname, default)
        except Exception:
            pass
    return getattr(doc, fieldname, default)


def _set_field_value(doc, fieldname: str, value) -> None:
    if isinstance(doc, dict):
        doc[fieldname] = value
        return
    setattr(doc, fieldname, value)


def _row_value(row: Any, fieldname: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(fieldname, default)
    if hasattr(row, "get"):
        try:
            value = row.get(fieldname)
        except Exception:
            value = default
        if value is not None:
            return value
    return getattr(row, fieldname, default)


def _set_row_value(row: Any, fieldname: str, value) -> None:
    if isinstance(row, dict):
        row[fieldname] = value
        return
    setattr(row, fieldname, value)


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", clean(value).lower()).strip("_")
    return normalized[:140]


def _load_building_row(building_name: str) -> dict[str, Any]:
    return frappe.db.get_value(
        BUILDING_DOCTYPE,
        clean(building_name),
        ["name", BUILDING_CURRENT_TEMPLATE_FIELD],
        as_dict=True,
    ) or {}


def _load_template_row(template_name: str) -> dict[str, Any]:
    return frappe.db.get_value(
        CHECKLIST_TEMPLATE_DOCTYPE,
        clean(template_name),
        ["name", "building", "status", "template_name", "version_number"],
        as_dict=True,
    ) or {}


def _load_template_item_rows(template_name: str, *, active_only: bool = True) -> list[dict[str, Any]]:
    filters = {
        "parent": clean(template_name),
        "parenttype": CHECKLIST_TEMPLATE_DOCTYPE,
        "parentfield": "items",
    }
    if active_only:
        filters["active"] = 1
    rows = frappe.get_all(
        CHECKLIST_TEMPLATE_ITEM_DOCTYPE,
        filters=filters,
        fields=[
            "name",
            "idx",
            "item_key",
            "category",
            "sort_order",
            "title",
            "description",
            "target_duration_seconds",
            "requires_image",
            "allow_notes",
            "is_required",
            "active",
        ],
        order_by="sort_order asc, idx asc",
        limit=500,
    )
    return list(rows or [])


def _next_template_version(building_name: str) -> int:
    rows = frappe.get_all(
        CHECKLIST_TEMPLATE_DOCTYPE,
        filters={"building": clean(building_name)},
        fields=["version_number"],
        order_by="version_number desc, creation desc",
        limit=1,
    )
    if not rows:
        return 1
    try:
        return int(rows[0].get("version_number") or 0) + 1
    except Exception:
        return 1


def normalize_template_items(items: list[Any] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(items or [], start=1):
        item_key = clean(_row_value(raw, "item_key") or _row_value(raw, "item_id"))
        category = clean(_row_value(raw, "category"))
        title = clean(_row_value(raw, "title") or _row_value(raw, "item_title"))
        description = clean(_row_value(raw, "description") or _row_value(raw, "item_description"))

        if not any([item_key, category, title, description]):
            continue
        if not title:
            frappe.throw(f"Checklist Template Item {index} requires a title.")
        if not category:
            frappe.throw(f"{title} requires a category.")

        normalized.append(
            {
                "item_key": item_key or _slugify(title) or f"item_{index}",
                "category": category,
                "sort_order": int(_row_value(raw, "sort_order") or index),
                "title": title,
                "description": description,
                "target_duration_seconds": _normalize_target_duration_seconds(
                    _row_value(raw, "target_duration_seconds")
                ),
                "requires_image": 1 if truthy(_row_value(raw, "requires_image") or _row_value(raw, "requires_photo_proof")) else 0,
                "allow_notes": 0 if _row_value(raw, "allow_notes") in (0, "0", False) else 1,
                "is_required": 0 if _row_value(raw, "is_required") in (0, "0", False) else 1,
                "active": 0 if _row_value(raw, "active") in (0, "0", False) else 1,
            }
        )
    return normalized


def prepare_checklist_template(doc) -> None:
    building_name = clean(_field_value(doc, "building"))
    if not building_name:
        frappe.throw("Building is required.")

    if not clean(_field_value(doc, "status")):
        _set_field_value(doc, "status", TEMPLATE_STATUS_DRAFT)

    if not _field_value(doc, "version_number"):
        _set_field_value(doc, "version_number", _next_template_version(building_name))

    if clean(_field_value(doc, "status")) == TEMPLATE_STATUS_ACTIVE and not _field_value(doc, "published_at"):
        _set_field_value(doc, "published_at", _now_datetime())

    normalized_items = normalize_template_items(list(_field_value(doc, "items", []) or []))
    doc.set("items", [])
    for row in normalized_items:
        doc.append("items", row)


def sync_active_checklist_template(doc) -> None:
    building_name = clean(_field_value(doc, "building"))
    template_name = clean(_field_value(doc, "name"))
    status = clean(_field_value(doc, "status"))
    if not building_name or not template_name:
        return

    if status == TEMPLATE_STATUS_ACTIVE:
        active_rows = frappe.get_all(
            CHECKLIST_TEMPLATE_DOCTYPE,
            filters={"building": building_name, "status": TEMPLATE_STATUS_ACTIVE},
            fields=["name"],
            order_by="creation asc",
            limit=500,
        )
        for row in active_rows or []:
            other_name = clean(row.get("name"))
            if other_name and other_name != template_name:
                frappe.db.set_value(CHECKLIST_TEMPLATE_DOCTYPE, other_name, "status", TEMPLATE_STATUS_ARCHIVED)
        frappe.db.set_value(BUILDING_DOCTYPE, building_name, BUILDING_CURRENT_TEMPLATE_FIELD, template_name)
        return

    building_row = _load_building_row(building_name)
    if clean(building_row.get(BUILDING_CURRENT_TEMPLATE_FIELD)) != template_name:
        return

    replacement_rows = frappe.get_all(
        CHECKLIST_TEMPLATE_DOCTYPE,
        filters={"building": building_name, "status": TEMPLATE_STATUS_ACTIVE},
        fields=["name"],
        order_by="published_at desc, modified desc",
        limit=1,
    )
    replacement_name = clean(replacement_rows[0].get("name")) if replacement_rows else ""
    frappe.db.set_value(BUILDING_DOCTYPE, building_name, BUILDING_CURRENT_TEMPLATE_FIELD, replacement_name or None)


def _active_session_exists(building_name: str, service_date, current_name: str = "") -> str:
    rows = frappe.get_all(
        CHECKLIST_SESSION_DOCTYPE,
        filters={
            "building": clean(building_name),
            "service_date": service_date,
            "status": SESSION_STATUS_IN_PROGRESS,
        },
        fields=["name"],
        order_by="started_at desc, creation desc",
        limit=20,
    )
    for row in rows or []:
        name = clean(row.get("name"))
        if name and name != clean(current_name):
            return name
    return ""


def _resolve_session_template(doc) -> dict[str, Any]:
    building_name = clean(_field_value(doc, "building"))
    if not building_name:
        frappe.throw("Building is required.")

    building_row = _load_building_row(building_name)
    current_template = clean(building_row.get(BUILDING_CURRENT_TEMPLATE_FIELD))
    template_name = clean(_field_value(doc, "checklist_template"))
    if not template_name:
        template_name = current_template
        _set_field_value(doc, "checklist_template", template_name)

    if not template_name:
        frappe.throw("Building requires an active Checklist Template before a Checklist Session can be created.")

    if current_template and template_name != current_template:
        frappe.throw("Checklist Session must use the building's current active Checklist Template.")

    template_row = _load_template_row(template_name)
    if not template_row:
        frappe.throw("Checklist Template is required.")
    if clean(template_row.get("building")) != building_name:
        frappe.throw("Checklist Template must belong to the selected Building.")
    if clean(template_row.get("status")) != TEMPLATE_STATUS_ACTIVE:
        frappe.throw("Checklist Template must be Active before a Checklist Session can be created.")
    return template_row


def _build_session_items_from_template(template_name: str) -> list[dict[str, Any]]:
    session_rows: list[dict[str, Any]] = []
    for row in _load_template_item_rows(template_name, active_only=True):
        session_rows.append(
            {
                "doctype": CHECKLIST_SESSION_ITEM_DOCTYPE,
                "item_key": clean(row.get("item_key")),
                "category": clean(row.get("category")),
                "sort_order": int(row.get("sort_order") or row.get("idx") or 0),
                "title_snapshot": clean(row.get("title")),
                "description_snapshot": clean(row.get("description")),
                "target_duration_seconds": _normalize_target_duration_seconds(
                    row.get("target_duration_seconds")
                ),
                "requires_image": 1 if truthy(row.get("requires_image")) else 0,
                "allow_notes": 0 if row.get("allow_notes") in (0, "0", False) else 1,
                "is_required": 0 if row.get("is_required") in (0, "0", False) else 1,
                "completed": 0,
                "completed_at": None,
                "note": "",
                "proof_image": "",
            }
        )
    return session_rows


def prepare_checklist_session_for_insert(doc) -> None:
    building_name = clean(_field_value(doc, "building"))
    service_date = _field_value(doc, "service_date")
    if not building_name:
        frappe.throw("Building is required.")
    if not service_date:
        frappe.throw("Service Date is required.")
    if not clean(_field_value(doc, "status")):
        _set_field_value(doc, "status", SESSION_STATUS_IN_PROGRESS)

    session_status = clean(_field_value(doc, "status")) or SESSION_STATUS_IN_PROGRESS
    if session_status == SESSION_STATUS_IN_PROGRESS and _active_session_exists(
        building_name,
        service_date,
        clean(_field_value(doc, "name")),
    ):
        frappe.throw("Only one in-progress Checklist Session is allowed per building and service date.")

    _resolve_session_template(doc)

    if not _field_value(doc, "started_at"):
        _set_field_value(doc, "started_at", _now_datetime())

    existing_items = list(_field_value(doc, "items", []) or [])
    if existing_items:
        return

    doc.set("items", [])
    for row in _build_session_items_from_template(clean(_field_value(doc, "checklist_template"))):
        doc.append("items", row)


def validate_checklist_session(doc) -> None:
    building_name = clean(_field_value(doc, "building"))
    service_date = _field_value(doc, "service_date")
    current_name = clean(_field_value(doc, "name"))
    if not building_name:
        frappe.throw("Building is required.")
    if not service_date:
        frappe.throw("Service Date is required.")

    session_status = clean(_field_value(doc, "status")) or SESSION_STATUS_IN_PROGRESS
    if session_status == SESSION_STATUS_IN_PROGRESS and _active_session_exists(
        building_name,
        service_date,
        current_name,
    ):
        frappe.throw("Only one in-progress Checklist Session is allowed per building and service date.")

    _resolve_session_template(doc)

    if not _field_value(doc, "started_at"):
        _set_field_value(doc, "started_at", _now_datetime())

    required_incomplete: list[str] = []
    found_incomplete = False
    ordered_rows = sorted(
        list(_field_value(doc, "items", []) or []),
        key=lambda row: int(_row_value(row, "sort_order") or _row_value(row, "idx") or 0),
    )
    for row in ordered_rows:
        title = clean(_row_value(row, "title_snapshot") or _row_value(row, "title")) or "Checklist item"
        completed = truthy(_row_value(row, "completed"))
        requires_image = truthy(_row_value(row, "requires_image"))
        is_required = _row_value(row, "is_required") not in (0, "0", False)
        proof_image = clean(_row_value(row, "proof_image"))

        if completed and not _row_value(row, "completed_at"):
            _set_row_value(row, "completed_at", _now_datetime())
        if not completed:
            _set_row_value(row, "completed_at", None)
            found_incomplete = True
        if completed and requires_image and not proof_image:
            frappe.throw(f"{title} requires a proof image before completion.")
        if completed and found_incomplete:
            frappe.throw(f"{title} cannot be completed before the previous checklist item.")
        if session_status == SESSION_STATUS_COMPLETED and is_required and not completed:
            required_incomplete.append(title)

    if session_status == SESSION_STATUS_COMPLETED and required_incomplete:
        frappe.throw(f"{required_incomplete[0]} must be completed before the session can be completed.")

    if session_status == SESSION_STATUS_COMPLETED:
        if not _field_value(doc, "completed_at"):
            _set_field_value(doc, "completed_at", _now_datetime())
        return

    _set_field_value(doc, "completed_at", None)
