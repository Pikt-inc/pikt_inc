from __future__ import annotations

from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode

from .. import building_sop as building_sop_service
from ..contracts.common import clean_str, truthy
from .building_repo import BuildingRecord, get_building, get_customer_buildings
from .checklist_repo import ChecklistSessionItemRecord, ChecklistSessionRecord, get_customer_sessions, get_session, get_session_items
from .context import resolve_context
from .errors import CustomerPortalNotFoundError
from .models import (
    ClientBuildingRequest,
    ClientBuildingResponse,
    ClientBuildingSummary,
    ClientJobProofRequest,
    ClientJobRequest,
    ClientJobResponse,
    ClientOverviewRequest,
    ClientOverviewResponse,
    ClientSessionItem,
    ClientSessionSummary,
    FileDownload,
    StepCategory,
)


def _temporal_string(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _normalize_step_category(value: Any) -> StepCategory:
    category = clean_str(value)
    if category in {"access", "job_completion", "rearm_security"}:
        return category
    return "job_completion"


def _proof_download_url(session_name: str, item_key: str) -> str:
    query = urlencode({"session": clean_str(session_name), "item_key": clean_str(item_key)})
    return f"/api/method/pikt_inc.api.customer_portal.download_customer_portal_client_job_proof?{query}"


def _building_address(row: BuildingRecord) -> str | None:
    locality = ", ".join(part for part in (clean_str(row.city), clean_str(row.state)) if part)
    if locality and clean_str(row.postal_code):
        locality = f"{locality} {clean_str(row.postal_code)}"
    parts = [clean_str(row.address_line_1), clean_str(row.address_line_2), locality]
    address = ", ".join(part for part in parts if part)
    return address or None


def _shape_building(row: BuildingRecord) -> ClientBuildingSummary:
    return ClientBuildingSummary(
        id=clean_str(row.name),
        name=clean_str(row.building_name) or clean_str(row.name),
        address=_building_address(row),
        notes=clean_str(row.site_notes) or None,
        active=truthy(row.active),
        current_checklist_template_id=clean_str(row.current_checklist_template) or None,
        created_at=_temporal_string(row.creation or row.modified),
        updated_at=_temporal_string(row.modified or row.creation),
    )


def _shape_session_summary(row: ChecklistSessionRecord) -> ClientSessionSummary:
    status = clean_str(row.status) or "completed"
    if status not in {"in_progress", "completed"}:
        status = "completed"
    return ClientSessionSummary(
        id=clean_str(row.name),
        building_id=clean_str(row.building),
        checklist_template_id=clean_str(row.checklist_template),
        service_date=_temporal_string(row.service_date),
        started_at=_temporal_string(row.started_at),
        completed_at=_temporal_string(row.completed_at) or None,
        worker=clean_str(row.worker) or None,
        session_notes=clean_str(row.session_notes) or None,
        status=status,
        items=[],
    )


def _shape_session_item(row: ChecklistSessionItemRecord, session_name: str) -> ClientSessionItem:
    item_key = clean_str(row.item_key) or clean_str(row.name)
    proof_image = clean_str(row.proof_image)
    return ClientSessionItem(
        id=clean_str(row.name) or item_key,
        job_session_id=clean_str(session_name) or None,
        item_key=item_key,
        category=_normalize_step_category(row.category),
        step_order=int(row.sort_order or row.idx or 0),
        title=clean_str(row.title_snapshot) or "Untitled Step",
        description=clean_str(row.description_snapshot) or None,
        requires_image=truthy(row.requires_image),
        allow_notes=truthy(row.allow_notes) if row.allow_notes is not None else True,
        is_required=truthy(row.is_required) if row.is_required is not None else True,
        completed=truthy(row.completed),
        completed_at=_temporal_string(row.completed_at) or None,
        proof_image=_proof_download_url(session_name, item_key) if proof_image else None,
        note=clean_str(row.note) or None,
    )


def _load_scoped_building_or_error(customer_name: str, building_name: str) -> BuildingRecord:
    building = get_building(building_name)
    if not building or clean_str(building.customer) != clean_str(customer_name):
        raise CustomerPortalNotFoundError("That building is not available in this portal account.")
    return building


def _load_scoped_completed_session_or_error(customer_name: str, session_name: str) -> tuple[ChecklistSessionRecord, BuildingRecord]:
    session = get_session(session_name)
    if not session:
        raise CustomerPortalNotFoundError("That job report is not available in this portal account.")

    building = get_building(session.building)
    if not building or clean_str(building.customer) != clean_str(customer_name) or clean_str(session.status) != "completed":
        raise CustomerPortalNotFoundError("That job report is not available in this portal account.")
    return session, building


def get_client_overview(_request: ClientOverviewRequest) -> ClientOverviewResponse:
    context = resolve_context()
    buildings = [_shape_building(row) for row in get_customer_buildings(context.customer_name)]
    completed_sessions = [
        _shape_session_summary(row)
        for row in get_customer_sessions(context.customer_name, status="completed", limit=200)
    ]
    return ClientOverviewResponse(buildings=buildings, completed_sessions=completed_sessions)


def get_client_building(request: ClientBuildingRequest) -> ClientBuildingResponse:
    context = resolve_context()
    building = _load_scoped_building_or_error(context.customer_name, request.building_id)
    completed_sessions = [
        _shape_session_summary(row)
        for row in get_customer_sessions(
            context.customer_name,
            building_name=request.building_id,
            status="completed",
            limit=200,
        )
    ]
    return ClientBuildingResponse(building=_shape_building(building), completed_sessions=completed_sessions)


def get_client_job(request: ClientJobRequest) -> ClientJobResponse:
    context = resolve_context()
    session, building = _load_scoped_completed_session_or_error(context.customer_name, request.session_id)
    items = sorted(get_session_items(request.session_id), key=lambda row: int(row.sort_order or row.idx or 0))
    session_payload = _shape_session_summary(session).model_copy(
        update={"items": [_shape_session_item(item, request.session_id) for item in items]}
    )
    return ClientJobResponse(building=_shape_building(building), session=session_payload)


def download_client_job_proof(request: ClientJobProofRequest) -> FileDownload:
    context = resolve_context()
    _load_scoped_completed_session_or_error(context.customer_name, request.session_id)
    item = next(
        (
            row
            for row in get_session_items(request.session_id)
            if clean_str(row.item_key) == request.item_key or clean_str(row.name) == request.item_key
        ),
        None,
    )
    if not item:
        raise CustomerPortalNotFoundError("That checklist proof is not available in this portal account.")

    file_url = clean_str(item.proof_image)
    if not file_url:
        raise CustomerPortalNotFoundError("No proof photo is attached to this checklist item.")

    file_name, content, content_type = building_sop_service.get_proof_file_content(file_url)
    return FileDownload(
        filename=clean_str(file_name),
        content=content,
        content_type=clean_str(content_type) or "application/octet-stream",
        as_attachment=False,
    )
