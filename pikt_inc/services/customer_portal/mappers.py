from __future__ import annotations

from ..contracts.common import clean_str
from .building_repo import BuildingRecord
from .checklist_repo import ChecklistSessionItemRecord, ChecklistSessionRecord
from .models import CustomerPortalBuilding, CustomerPortalSession, CustomerPortalSessionItem, StepCategory


def normalize_step_category(value: str) -> StepCategory:
    category = clean_str(value)
    if category in {"access", "job_completion", "rearm_security"}:
        return category
    return "job_completion"


def building_address(row: BuildingRecord) -> str | None:
    locality = ", ".join(part for part in (row.city, row.state) if part)
    if locality and row.postal_code:
        locality = f"{locality} {row.postal_code}"
    parts = [row.address_line_1, row.address_line_2, locality]
    address = ", ".join(part for part in parts if part)
    return address or None


def map_customer_building(row: BuildingRecord) -> CustomerPortalBuilding:
    return CustomerPortalBuilding(
        id=row.name,
        name=row.building_name or row.name,
        address=building_address(row),
        notes=row.site_notes or None,
        active=row.active,
        current_checklist_template_id=row.current_checklist_template or None,
        created_at=row.creation or row.modified,
        updated_at=row.modified or row.creation,
    )


def map_customer_session(row: ChecklistSessionRecord) -> CustomerPortalSession:
    status = row.status or "completed"
    if status not in {"in_progress", "completed"}:
        status = "completed"
    return CustomerPortalSession(
        id=row.name,
        building_id=row.building,
        checklist_template_id=row.checklist_template,
        service_date=row.service_date,
        started_at=row.started_at,
        completed_at=row.completed_at,
        worker=row.worker or None,
        session_notes=row.session_notes or None,
        status=status,
        items=[],
    )


def map_customer_session_item(row: ChecklistSessionItemRecord, session_name: str) -> CustomerPortalSessionItem:
    item_key = row.item_key or row.name
    return CustomerPortalSessionItem(
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
        completed_at=row.completed_at,
        proof_image_path=row.proof_image or None,
        note=row.note or None,
    )
