from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlencode

import frappe

from ..services.contracts.common import clean_str
from ..services.customer_portal.building.models import CustomerPortalBuilding, CustomerPortalStorageLocation
from ..services.customer_portal.checklist.models import ChecklistStep, CustomerPortalSession, CustomerPortalSessionItem
from ..services.customer_portal.models import ChecklistPortalBuildingDetail, ChecklistSessionItemMutation
from .checklist_portal_contracts import (
    ChecklistPortalBuildingDetailPayload,
    ChecklistPortalBuildingPayload,
    ChecklistPortalSessionItemMutationPayload,
    ChecklistPortalSessionItemPayload,
    ChecklistPortalSessionPayload,
    ChecklistPortalStorageLocationPayload,
    ChecklistPortalStepPayload,
)
from .customer_portal_serializers import public_temporal_string


def checklist_server_now_string() -> str | None:
    utils = getattr(frappe, "utils", None)
    if utils is None or not hasattr(utils, "now_datetime"):
        return None

    value = utils.now_datetime()
    if isinstance(value, (date, datetime)):
        return public_temporal_string(value) or None

    text = clean_str(value)
    return text or None


def build_checklist_step_training_media_download_url(building_id: str, item_key: str) -> str:
    query = urlencode({"building": clean_str(building_id), "item_key": clean_str(item_key)})
    return f"/api/method/pikt_inc.api.checklist_portal.download_checklist_portal_step_training_media?{query}"


def build_checklist_session_item_training_media_download_url(session_id: str, item_key: str) -> str:
    query = urlencode({"session": clean_str(session_id), "item_key": clean_str(item_key)})
    return f"/api/method/pikt_inc.api.checklist_portal.download_checklist_portal_session_item_training_media?{query}"


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


def serialize_checklist_portal_storage_location(
    location: CustomerPortalStorageLocation,
) -> ChecklistPortalStorageLocationPayload:
    return ChecklistPortalStorageLocationPayload(
        id=location.id,
        building_id=location.building_id,
        name=location.name,
        location_type=location.location_type,
        directions=location.directions,
        notes=location.notes,
        active=location.active,
        is_primary=location.is_primary,
        created_at=public_temporal_string(location.created_at),
        updated_at=public_temporal_string(location.updated_at),
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
        training_media=build_checklist_step_training_media_download_url(step.building_id, step.id) if step.training_media_path else None,
        training_media_kind=step.training_media_kind,
        requires_image=step.requires_image,
        allow_notes=step.allow_notes,
        is_required=step.is_required,
        active=step.active,
    )


def serialize_checklist_portal_session_item(
    item: CustomerPortalSessionItem,
    session_id: str,
) -> ChecklistPortalSessionItemPayload:
    return ChecklistPortalSessionItemPayload(
        id=item.id,
        job_session_id=item.job_session_id,
        item_key=item.item_key,
        category=item.category,
        step_order=item.step_order,
        title=item.title,
        description=item.description,
        target_duration_seconds=item.target_duration_seconds,
        training_media=build_checklist_session_item_training_media_download_url(session_id, item.item_key) if item.training_media_path else None,
        training_media_kind=item.training_media_kind,
        requires_image=item.requires_image,
        allow_notes=item.allow_notes,
        is_required=item.is_required,
        completed=item.completed,
        completed_at=public_temporal_string(item.completed_at) or None,
        issue_reported=item.issue_reported,
        issue_reason=item.issue_reason,
        issue_reported_at=public_temporal_string(item.issue_reported_at) or None,
        issue_image=item.issue_image_path,
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
        server_now=checklist_server_now_string(),
        worker=session.worker,
        session_notes=session.session_notes,
        status=session.status,
        items=[serialize_checklist_portal_session_item(item, session.id) for item in session.items],
    )


def serialize_checklist_portal_building_detail(
    detail: ChecklistPortalBuildingDetail,
) -> ChecklistPortalBuildingDetailPayload:
    return ChecklistPortalBuildingDetailPayload(
        building=serialize_checklist_portal_building(detail.building),
        checklist_template_id=detail.checklist_template_id,
        steps=[serialize_checklist_portal_step(step) for step in detail.steps],
        active_session=serialize_checklist_portal_session(detail.active_session) if detail.active_session else None,
        storage_locations=[
            serialize_checklist_portal_storage_location(location)
            for location in detail.storage_locations
        ],
    )


def serialize_checklist_portal_session_item_mutation(
    mutation: ChecklistSessionItemMutation,
) -> ChecklistPortalSessionItemMutationPayload:
    return ChecklistPortalSessionItemMutationPayload(
        session=serialize_checklist_portal_session(mutation.session),
        item=serialize_checklist_portal_session_item(mutation.item, mutation.session.id),
    )
