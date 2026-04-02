from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlencode

from ..contracts.common import clean_str
from .building_repo import BuildingRecord
from .checklist_repo import ChecklistSessionItemRecord, ChecklistSessionRecord
from .models import ClientBuildingSummary, ClientSessionItem, ClientSessionSummary, StepCategory


def public_temporal_string(value: date | datetime | None) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="seconds")
    return value.isoformat()


def normalize_step_category(value: str) -> StepCategory:
    category = clean_str(value)
    if category in {"access", "job_completion", "rearm_security"}:
        return category
    return "job_completion"


def build_proof_download_url(session_name: str, item_key: str) -> str:
    query = urlencode({"session": clean_str(session_name), "item_key": clean_str(item_key)})
    return f"/api/method/pikt_inc.api.customer_portal.download_customer_portal_client_job_proof?{query}"


def building_address(row: BuildingRecord) -> str | None:
    locality = ", ".join(part for part in (row.city, row.state) if part)
    if locality and row.postal_code:
        locality = f"{locality} {row.postal_code}"
    parts = [row.address_line_1, row.address_line_2, locality]
    address = ", ".join(part for part in parts if part)
    return address or None


def map_building_summary(row: BuildingRecord) -> ClientBuildingSummary:
    return ClientBuildingSummary(
        id=row.name,
        name=row.building_name or row.name,
        address=building_address(row),
        notes=row.site_notes or None,
        active=row.active,
        current_checklist_template_id=row.current_checklist_template or None,
        created_at=public_temporal_string(row.creation or row.modified),
        updated_at=public_temporal_string(row.modified or row.creation),
    )


def map_session_summary(row: ChecklistSessionRecord) -> ClientSessionSummary:
    status = row.status or "completed"
    if status not in {"in_progress", "completed"}:
        status = "completed"
    return ClientSessionSummary(
        id=row.name,
        building_id=row.building,
        checklist_template_id=row.checklist_template,
        service_date=public_temporal_string(row.service_date),
        started_at=public_temporal_string(row.started_at),
        completed_at=public_temporal_string(row.completed_at) or None,
        worker=row.worker or None,
        session_notes=row.session_notes or None,
        status=status,
        items=[],
    )


def map_session_item(row: ChecklistSessionItemRecord, session_name: str) -> ClientSessionItem:
    item_key = row.item_key or row.name
    return ClientSessionItem(
        id=row.name or item_key,
        job_session_id=clean_str(session_name) or None,
        item_key=item_key,
        category=normalize_step_category(row.category),
        step_order=row.sort_order or row.idx or 0,
        title=row.title_snapshot or "Untitled Step",
        description=row.description_snapshot or None,
        requires_image=row.requires_image,
        allow_notes=row.allow_notes if row.allow_notes is not None else True,
        is_required=row.is_required if row.is_required is not None else True,
        completed=row.completed,
        completed_at=public_temporal_string(row.completed_at) or None,
        proof_image=build_proof_download_url(session_name, item_key) if row.proof_image else None,
        note=row.note or None,
    )
