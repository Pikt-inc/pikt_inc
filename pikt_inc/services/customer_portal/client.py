from __future__ import annotations

from .. import building_sop as building_sop_service
from ..contracts.common import clean_str
from .context import resolve_context
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
from .scoped_reads import (
    get_customer_building_history,
    get_customer_completed_job,
    get_customer_job_proof_target,
    get_customer_overview_read,
)


def get_client_overview(_request: ClientOverviewRequest) -> ClientOverviewResponse:
    principal = resolve_context()
    overview = get_customer_overview_read(principal.customer_name, limit=200)
    buildings = [map_building_summary(row) for row in overview.buildings]
    completed_sessions = [
        map_session_summary(row.session)
        for row in overview.completed_sessions
    ]
    return ClientOverviewResponse(buildings=buildings, completed_sessions=completed_sessions)


def get_client_building(request: ClientBuildingRequest) -> ClientBuildingResponse:
    principal = resolve_context()
    building_history = get_customer_building_history(principal.customer_name, request.building_id, limit=200)
    completed_sessions = [
        map_session_summary(row.session)
        for row in building_history.completed_sessions
    ]
    return ClientBuildingResponse(
        building=map_building_summary(building_history.building),
        completed_sessions=completed_sessions,
    )


def get_client_job(request: ClientJobRequest) -> ClientJobResponse:
    principal = resolve_context()
    job_detail = get_customer_completed_job(principal.customer_name, request.session_id)
    session_payload = map_session_summary(job_detail.session).model_copy(
        update={"items": [map_session_item(item, request.session_id) for item in job_detail.items]}
    )
    return ClientJobResponse(building=map_building_summary(job_detail.building), session=session_payload)


def download_client_job_proof(request: ClientJobProofRequest) -> FileDownload:
    principal = resolve_context()
    proof_target = get_customer_job_proof_target(principal.customer_name, request.session_id, request.item_key)
    file_name, content, content_type = building_sop_service.get_proof_file_content(proof_target.item.proof_image)
    return FileDownload(
        filename=clean_str(file_name),
        content=content,
        content_type=clean_str(content_type) or "application/octet-stream",
        as_attachment=False,
    )
