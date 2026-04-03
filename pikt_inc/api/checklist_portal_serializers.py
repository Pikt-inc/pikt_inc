from __future__ import annotations

from ..services.customer_portal.building.models import CustomerPortalBuilding
from ..services.customer_portal.checklist.models import ChecklistStep, CustomerPortalSession, CustomerPortalSessionItem
from ..services.customer_portal.models import ChecklistPortalBuildingDetail, ChecklistSessionItemMutation
from .checklist_portal_contracts import (
    ChecklistPortalBuildingDetailPayload,
    ChecklistPortalBuildingPayload,
    ChecklistPortalSessionItemMutationPayload,
    ChecklistPortalSessionItemPayload,
    ChecklistPortalSessionPayload,
    ChecklistPortalStepPayload,
)
from .customer_portal_serializers import public_temporal_string


def serialize_checklist_portal_building(building: CustomerPortalBuilding) -> ChecklistPortalBuildingPayload:
    return ChecklistPortalBuildingPayload(
        id=building.id,
        name=building.name,
        address=building.address,
        notes=building.notes,
        active=building.active,
        current_checklist_template_id=building.current_checklist_template_id,
        created_at=public_temporal_string(building.created_at),
        updated_at=public_temporal_string(building.updated_at),
    )


def serialize_checklist_portal_step(step: ChecklistStep) -> ChecklistPortalStepPayload:
    return ChecklistPortalStepPayload(
        id=step.id,
        building_id=step.building_id,
        checklist_template_id=step.checklist_template_id,
        category=step.category,
        step_order=step.step_order,
        title=step.title,
        description=step.description,
        target_duration_seconds=step.target_duration_seconds,
        requires_image=step.requires_image,
        allow_notes=step.allow_notes,
        is_required=step.is_required,
        active=step.active,
    )


def serialize_checklist_portal_session_item(item: CustomerPortalSessionItem) -> ChecklistPortalSessionItemPayload:
    return ChecklistPortalSessionItemPayload(
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
        proof_image=item.proof_image_path,
        note=item.note,
    )


def serialize_checklist_portal_session(session: CustomerPortalSession) -> ChecklistPortalSessionPayload:
    return ChecklistPortalSessionPayload(
        id=session.id,
        building_id=session.building_id,
        checklist_template_id=session.checklist_template_id,
        service_date=public_temporal_string(session.service_date),
        started_at=public_temporal_string(session.started_at),
        completed_at=public_temporal_string(session.completed_at) or None,
        worker=session.worker,
        session_notes=session.session_notes,
        status=session.status,
        items=[serialize_checklist_portal_session_item(item) for item in session.items],
    )


def serialize_checklist_portal_building_detail(
    detail: ChecklistPortalBuildingDetail,
) -> ChecklistPortalBuildingDetailPayload:
    return ChecklistPortalBuildingDetailPayload(
        building=serialize_checklist_portal_building(detail.building),
        checklist_template_id=detail.checklist_template_id,
        steps=[serialize_checklist_portal_step(step) for step in detail.steps],
        active_session=serialize_checklist_portal_session(detail.active_session) if detail.active_session else None,
    )


def serialize_checklist_portal_session_item_mutation(
    mutation: ChecklistSessionItemMutation,
) -> ChecklistPortalSessionItemMutationPayload:
    return ChecklistPortalSessionItemMutationPayload(
        session=serialize_checklist_portal_session(mutation.session),
        item=serialize_checklist_portal_session_item(mutation.item),
    )
