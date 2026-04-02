from __future__ import annotations

from .. import building_sop as building_sop_service
from ..contracts.common import clean_str
from .building_repo import BuildingRecord, get_building, get_customer_buildings
from .checklist_repo import ChecklistSessionRecord, get_customer_sessions, get_session, get_session_items
from .context import resolve_context
from .errors import CustomerPortalNotFoundError
from .mappers import map_building_summary, map_session_item, map_session_summary
from .models import (
    ClientBuildingRequest,
    ClientBuildingResponse,
    ClientJobProofRequest,
    ClientJobRequest,
    ClientJobResponse,
    ClientOverviewRequest,
    ClientOverviewResponse,
    FileDownload,
)


def _load_scoped_building_or_error(customer_name: str, building_name: str) -> BuildingRecord:
    building = get_building(building_name)
    if not building or building.customer != clean_str(customer_name):
        raise CustomerPortalNotFoundError("That building is not available in this portal account.")
    return building


def _load_scoped_completed_session_or_error(
    customer_name: str,
    session_name: str,
) -> tuple[ChecklistSessionRecord, BuildingRecord]:
    session = get_session(session_name)
    if not session:
        raise CustomerPortalNotFoundError("That job report is not available in this portal account.")

    building = get_building(session.building)
    if not building or building.customer != clean_str(customer_name) or session.status != "completed":
        raise CustomerPortalNotFoundError("That job report is not available in this portal account.")

    return session, building


def get_client_overview(_request: ClientOverviewRequest) -> ClientOverviewResponse:
    principal = resolve_context()
    buildings = [map_building_summary(row) for row in get_customer_buildings(principal.customer_name)]
    completed_sessions = [
        map_session_summary(row)
        for row in get_customer_sessions(principal.customer_name, status="completed", limit=200)
    ]
    return ClientOverviewResponse(buildings=buildings, completed_sessions=completed_sessions)


def get_client_building(request: ClientBuildingRequest) -> ClientBuildingResponse:
    principal = resolve_context()
    building = _load_scoped_building_or_error(principal.customer_name, request.building_id)
    completed_sessions = [
        map_session_summary(row)
        for row in get_customer_sessions(
            principal.customer_name,
            building_name=request.building_id,
            status="completed",
            limit=200,
        )
    ]
    return ClientBuildingResponse(building=map_building_summary(building), completed_sessions=completed_sessions)


def get_client_job(request: ClientJobRequest) -> ClientJobResponse:
    principal = resolve_context()
    session, building = _load_scoped_completed_session_or_error(principal.customer_name, request.session_id)
    items = sorted(get_session_items(request.session_id), key=lambda row: row.sort_order or row.idx or 0)
    session_payload = map_session_summary(session).model_copy(
        update={"items": [map_session_item(item, request.session_id) for item in items]}
    )
    return ClientJobResponse(building=map_building_summary(building), session=session_payload)


def download_client_job_proof(request: ClientJobProofRequest) -> FileDownload:
    principal = resolve_context()
    _load_scoped_completed_session_or_error(principal.customer_name, request.session_id)
    item = next(
        (
            row
            for row in get_session_items(request.session_id)
            if row.item_key == request.item_key or row.name == request.item_key
        ),
        None,
    )
    if not item:
        raise CustomerPortalNotFoundError("That checklist proof is not available in this portal account.")

    if not item.proof_image:
        raise CustomerPortalNotFoundError("No proof photo is attached to this checklist item.")

    file_name, content, content_type = building_sop_service.get_proof_file_content(item.proof_image)
    return FileDownload(
        filename=clean_str(file_name),
        content=content,
        content_type=clean_str(content_type) or "application/octet-stream",
        as_attachment=False,
    )
