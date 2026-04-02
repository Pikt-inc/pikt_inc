from __future__ import annotations

from typing import Any

from .. import building_sop as building_sop_service
from .queries import (
    _get_buildings,
    _get_checklist_session_item_rows,
    _get_checklist_session_rows,
    _load_building_row,
    _load_checklist_session_row,
)
from .scope import _require_portal_scope
from .shared import _job_checklist_proof_download_url, _set_file_response, _throw, clean, truthy


def _normalize_step_category(value: Any) -> str:
    category = clean(value)
    if category in {"access", "job_completion", "rearm_security"}:
        return category
    return "job_completion"


def _building_address(row: dict[str, Any]) -> str | None:
    parts = [
        clean(row.get("address_line_1")),
        clean(row.get("address_line_2")),
        ", ".join(part for part in (clean(row.get("city")), clean(row.get("state"))) if part),
    ]
    postal_code = clean(row.get("postal_code"))
    if parts[-1] and postal_code:
        parts[-1] = f"{parts[-1]} {postal_code}"
    address = ", ".join(part for part in parts if part)
    return address or None


def _shape_building(row: dict[str, Any]) -> dict[str, Any]:
    created_at = row.get("creation") or row.get("modified")
    updated_at = row.get("modified") or row.get("creation")
    return {
        "id": clean(row.get("name")),
        "name": clean(row.get("building_name")) or clean(row.get("name")),
        "address": _building_address(row),
        "notes": clean(row.get("site_notes")) or None,
        "active": truthy(row.get("active")),
        "current_checklist_template_id": clean(row.get("current_checklist_template")) or None,
        "created_at": created_at,
        "updated_at": updated_at,
    }


def _shape_checklist_session_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": clean(row.get("name")),
        "building_id": clean(row.get("building")),
        "checklist_template_id": clean(row.get("checklist_template")),
        "service_date": row.get("service_date"),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at") or None,
        "worker": clean(row.get("worker")) or None,
        "session_notes": clean(row.get("session_notes")) or None,
        "status": clean(row.get("status")) or "completed",
        "items": [],
    }


def _shape_checklist_session_item(row: dict[str, Any], session_name: str) -> dict[str, Any]:
    item_key = clean(row.get("item_key")) or clean(row.get("name"))
    proof_image = clean(row.get("proof_image"))
    return {
        "id": clean(row.get("name")) or item_key,
        "job_session_id": clean(session_name) or None,
        "item_key": item_key,
        "category": _normalize_step_category(row.get("category")),
        "step_order": int(row.get("sort_order") or row.get("idx") or 0),
        "title": clean(row.get("title_snapshot")) or "Untitled Step",
        "description": clean(row.get("description_snapshot")) or None,
        "requires_image": truthy(row.get("requires_image")),
        "allow_notes": truthy(row.get("allow_notes")) if row.get("allow_notes") is not None else True,
        "is_required": truthy(row.get("is_required")) if row.get("is_required") is not None else True,
        "completed": truthy(row.get("completed")),
        "completed_at": row.get("completed_at") or None,
        "proof_image": _job_checklist_proof_download_url(session_name, item_key) if proof_image else None,
        "note": clean(row.get("note")) or None,
    }


def _load_scoped_building_or_error(customer_name: str, building_name: str) -> dict[str, Any]:
    building_row = _load_building_row(building_name)
    if not building_row or clean(building_row.get("customer")) != clean(customer_name):
        _throw("That building is not available in this portal account.")
    return building_row


def _load_scoped_completed_session_or_error(customer_name: str, session_name: str) -> tuple[dict[str, Any], dict[str, Any]]:
    session_row = _load_checklist_session_row(session_name)
    if not session_row:
        _throw("That job report is not available in this portal account.")

    building_row = _load_building_row(clean(session_row.get("building")))
    if (
        not building_row
        or clean(building_row.get("customer")) != clean(customer_name)
        or clean(session_row.get("status")) != "completed"
    ):
        _throw("That job report is not available in this portal account.")

    return session_row, building_row


def get_customer_portal_client_overview(**_kwargs):
    scope = _require_portal_scope()
    building_rows = _get_buildings(scope.customer_name)
    session_rows = _get_checklist_session_rows(scope.customer_name, status="completed", limit=200)
    return {
        "buildings": [_shape_building(row) for row in building_rows],
        "completed_sessions": [_shape_checklist_session_summary(row) for row in session_rows],
    }


def get_customer_portal_client_building(building: str | None = None, **kwargs):
    scope = _require_portal_scope()
    building_name = clean(building or kwargs.get("building") or kwargs.get("building_id"))
    if not building_name:
        _throw("Building is required.")

    building_row = _load_scoped_building_or_error(scope.customer_name, building_name)
    session_rows = _get_checklist_session_rows(
        scope.customer_name,
        building_name=building_name,
        status="completed",
        limit=200,
    )
    return {
        "building": _shape_building(building_row),
        "completed_sessions": [_shape_checklist_session_summary(row) for row in session_rows],
    }


def get_customer_portal_client_job(session: str | None = None, **kwargs):
    scope = _require_portal_scope()
    session_name = clean(session or kwargs.get("session") or kwargs.get("session_id"))
    if not session_name:
        _throw("Job session is required.")

    session_row, building_row = _load_scoped_completed_session_or_error(scope.customer_name, session_name)
    item_rows = sorted(
        _get_checklist_session_item_rows(session_name),
        key=lambda row: int(row.get("sort_order") or row.get("idx") or 0),
    )
    session_payload = _shape_checklist_session_summary(session_row)
    session_payload["items"] = [_shape_checklist_session_item(row, session_name) for row in item_rows]
    return {
        "building": _shape_building(building_row),
        "session": session_payload,
    }


def download_customer_portal_client_job_proof(session: str | None = None, item_key: str | None = None, **kwargs):
    scope = _require_portal_scope()
    session_name = clean(session or kwargs.get("session") or kwargs.get("session_id"))
    selected_item_key = clean(item_key or kwargs.get("item_key"))
    if not session_name or not selected_item_key:
        _throw("A completed job proof is required.")

    _load_scoped_completed_session_or_error(scope.customer_name, session_name)
    item_rows = _get_checklist_session_item_rows(session_name)
    item_row = next(
        (
            row
            for row in item_rows
            if clean(row.get("item_key")) == selected_item_key or clean(row.get("name")) == selected_item_key
        ),
        None,
    )
    if not item_row:
        _throw("That checklist proof is not available in this portal account.")

    file_url = clean(item_row.get("proof_image"))
    if not file_url:
        _throw("No proof photo is attached to this checklist item.")

    file_name, content, content_type = building_sop_service.get_proof_file_content(file_url)
    _set_file_response(file_name, content, content_type, as_attachment=False)
    return None
