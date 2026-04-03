from __future__ import annotations

from ...contracts.common import clean_str
from .models import (
    ChecklistSessionItemRecord,
    ChecklistSessionRecord,
    ChecklistStep,
    ChecklistTemplateItemRecord,
    CustomerPortalSession,
    CustomerPortalSessionItem,
    StepCategory,
)


def normalize_step_category(value: str) -> StepCategory:
    category = clean_str(value)
    if category in {"access", "job_completion", "rearm_security"}:
        return category
    return "job_completion"


def map_portal_session(
    row: ChecklistSessionRecord,
    items: list[ChecklistSessionItemRecord] | None = None,
) -> CustomerPortalSession:
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
        items=[map_portal_session_item(item, row.name) for item in (items or [])],
    )


def map_portal_session_item(row: ChecklistSessionItemRecord, session_name: str) -> CustomerPortalSessionItem:
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


def map_checklist_step(
    row: ChecklistTemplateItemRecord,
    *,
    building_id: str,
    checklist_template_id: str | None,
) -> ChecklistStep:
    item_id = row.item_key or row.name
    return ChecklistStep(
        id=item_id,
        building_id=clean_str(building_id),
        checklist_template_id=clean_str(checklist_template_id) or None,
        category=normalize_step_category(row.category),
        step_order=row.sort_order or row.idx or 0,
        title=row.title or "Untitled Step",
        description=row.description or None,
        requires_image=row.requires_image,
        allow_notes=row.allow_notes,
        is_required=row.is_required,
        active=row.active,
    )
