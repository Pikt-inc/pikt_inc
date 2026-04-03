from __future__ import annotations

from .. import building_sop as building_sop_service
from ..contracts.common import clean_str
from .account import resolve_customer_principal
from .models import CustomerBuildingHistory, CustomerJobDetail, CustomerOverview, ProofFileContent
from .scoped_reads import (
    get_customer_building_history,
    get_customer_completed_job,
    get_customer_job_proof_item,
    get_customer_overview,
)


def get_client_overview() -> CustomerOverview:
    principal = resolve_customer_principal()
    return get_customer_overview(principal.customer_name, limit=200)


def get_client_building(building_id: str) -> CustomerBuildingHistory:
    principal = resolve_customer_principal()
    return get_customer_building_history(principal.customer_name, clean_str(building_id), limit=200)


def get_client_job(session_id: str) -> CustomerJobDetail:
    principal = resolve_customer_principal()
    return get_customer_completed_job(principal.customer_name, clean_str(session_id))


def download_client_job_proof(session_id: str, item_key: str) -> ProofFileContent:
    principal = resolve_customer_principal()
    item = get_customer_job_proof_item(principal.customer_name, clean_str(session_id), clean_str(item_key))
    file_name, content, content_type = building_sop_service.get_proof_file_content(item.proof_image)
    return ProofFileContent(
        filename=clean_str(file_name),
        content=content,
        content_type=clean_str(content_type) or "application/octet-stream",
    )
