from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlencode

import frappe

from ..services.contracts.common import clean_str
from ..services.customer_portal.building.models import CustomerPortalBuilding
from ..services.customer_portal.checklist.models import CustomerPortalSession, CustomerPortalSessionItem
from ..services.customer_portal.models import CustomerBuildingHistory, CustomerJobDetail, CustomerOverview, ProofFileContent
from .customer_portal_contracts import (
    CustomerPortalClientBuildingPayload,
    CustomerPortalClientBuildingSummaryPayload,
    CustomerPortalClientJobPayload,
    CustomerPortalClientOverviewPayload,
    CustomerPortalClientSessionItemPayload,
    CustomerPortalClientSessionPayload,
)


def public_temporal_string(value: date | datetime | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return value.isoformat()


def build_proof_download_url(session_name: str, item_key: str) -> str:
    query = urlencode({"session": clean_str(session_name), "item_key": clean_str(item_key)})
    return f"/api/method/pikt_inc.api.customer_portal.download_customer_portal_client_job_proof?{query}"


def serialize_customer_portal_building(
    building: CustomerPortalBuilding,
) -> CustomerPortalClientBuildingSummaryPayload:
    return CustomerPortalClientBuildingSummaryPayload(
        id=building.id,
        name=building.name,
        address=building.address,
        notes=building.notes,
        active=building.active,
        current_checklist_template_id=building.current_checklist_template_id,
        created_at=public_temporal_string(building.created_at),
        updated_at=public_temporal_string(building.updated_at),
    )


def serialize_customer_portal_session_item(
    item: CustomerPortalSessionItem,
    session_id: str,
) -> CustomerPortalClientSessionItemPayload:
    return CustomerPortalClientSessionItemPayload(
        id=item.id,
        job_session_id=item.job_session_id,
        item_key=item.item_key,
        category=item.category,
        step_order=item.step_order,
        title=item.title,
        description=item.description,
        target_duration_seconds=item.target_duration_seconds,
        requires_image=item.requires_image,
        allow_notes=item.allow_notes,
        is_required=item.is_required,
        completed=item.completed,
        completed_at=public_temporal_string(item.completed_at) or None,
        proof_image=build_proof_download_url(session_id, item.item_key) if item.proof_image_path else None,
        note=item.note,
    )


def serialize_customer_portal_session(
    session: CustomerPortalSession,
) -> CustomerPortalClientSessionPayload:
    return CustomerPortalClientSessionPayload(
        id=session.id,
        building_id=session.building_id,
        checklist_template_id=session.checklist_template_id,
        service_date=public_temporal_string(session.service_date),
        started_at=public_temporal_string(session.started_at),
        completed_at=public_temporal_string(session.completed_at) or None,
        worker=session.worker,
        session_notes=session.session_notes,
        status=session.status,
        items=[serialize_customer_portal_session_item(item, session.id) for item in session.items],
    )


def serialize_customer_portal_overview(overview: CustomerOverview) -> CustomerPortalClientOverviewPayload:
    return CustomerPortalClientOverviewPayload(
        buildings=[serialize_customer_portal_building(building) for building in overview.buildings],
        completed_sessions=[serialize_customer_portal_session(session) for session in overview.completed_sessions],
    )


def serialize_customer_portal_building_history(history: CustomerBuildingHistory) -> CustomerPortalClientBuildingPayload:
    return CustomerPortalClientBuildingPayload(
        building=serialize_customer_portal_building(history.building),
        completed_sessions=[serialize_customer_portal_session(session) for session in history.completed_sessions],
    )


def serialize_customer_portal_job_detail(job_detail: CustomerJobDetail) -> CustomerPortalClientJobPayload:
    return CustomerPortalClientJobPayload(
        building=serialize_customer_portal_building(job_detail.building),
        session=serialize_customer_portal_session(job_detail.session),
    )


def apply_customer_portal_file_download(download: ProofFileContent) -> None:
    local = getattr(frappe, "local", None)
    if local is None:
        return

    response = getattr(local, "response", None)
    if response is None:
        local.response = {}
        response = local.response

    response["filename"] = clean_str(download.filename)
    response["filecontent"] = download.content
    response["type"] = "binary"
    response["content_type"] = clean_str(download.content_type) or "application/octet-stream"
