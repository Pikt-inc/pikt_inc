from __future__ import annotations

from .. import building_sop as building_sop_service
from ..contracts.common import clean_str
from .context import resolve_context
from .mappers import map_customer_building, map_customer_session, map_customer_session_item
from .models import (
    CustomerBuildingHistory,
    CustomerJobDetail,
    CustomerOverview,
    ProofFileContent,
)
from .scoped_reads import (
    get_customer_building_history,
    get_customer_completed_job,
    get_customer_job_proof_target,
    get_customer_overview_read,
)


def get_client_overview() -> CustomerOverview:
    principal = resolve_context()
    overview = get_customer_overview_read(principal.customer_name, limit=200)
    buildings = [map_customer_building(row) for row in overview.buildings]
    completed_sessions = [
        map_customer_session(row.session)
        for row in overview.completed_sessions
    ]
    return CustomerOverview(buildings=buildings, completed_sessions=completed_sessions)


def get_client_building(building_id: str) -> CustomerBuildingHistory:
    principal = resolve_context()
    building_history = get_customer_building_history(principal.customer_name, clean_str(building_id), limit=200)
    completed_sessions = [
        map_customer_session(row.session)
        for row in building_history.completed_sessions
    ]
    return CustomerBuildingHistory(
        building=map_customer_building(building_history.building),
        completed_sessions=completed_sessions,
    )


def get_client_job(session_id: str) -> CustomerJobDetail:
    principal = resolve_context()
    session_id = clean_str(session_id)
    job_detail = get_customer_completed_job(principal.customer_name, session_id)
    session_payload = map_customer_session(job_detail.session).model_copy(
        update={"items": [map_customer_session_item(item, session_id) for item in job_detail.items]}
    )
    return CustomerJobDetail(building=map_customer_building(job_detail.building), session=session_payload)


def download_client_job_proof(session_id: str, item_key: str) -> ProofFileContent:
    principal = resolve_context()
    proof_target = get_customer_job_proof_target(
        principal.customer_name,
        clean_str(session_id),
        clean_str(item_key),
    )
    file_name, content, content_type = building_sop_service.get_proof_file_content(proof_target.item.proof_image)
    return ProofFileContent(
        filename=clean_str(file_name),
        content=content,
        content_type=clean_str(content_type) or "application/octet-stream",
    )
