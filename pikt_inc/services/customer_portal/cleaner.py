from __future__ import annotations

from .. import building_sop as building_sop_service
from ..contracts.common import clean_str
from .account import require_checklist_work_access, require_portal_section
from .building.mappers import map_portal_building, map_portal_storage_location
from .building.repo import get_building, list_buildings, list_storage_locations
from .checklist.mappers import map_checklist_step, map_portal_session, map_portal_session_item
from .checklist.repo import get_active_session, get_session_items, get_template_items
from .checklist.service import (
    complete_session,
    ensure_active_session,
    require_session,
    require_session_item,
    update_session_item,
    upload_session_item_issue_image,
    upload_session_item_proof,
)
from .errors import CustomerPortalNotFoundError
from .models import ChecklistPortalBuildingDetail, ChecklistSessionItemMutation, PortalMediaContent, ProofFileContent


def _require_checklist_building(building_id: str):
    building = get_building(building_id)
    if not building:
        raise CustomerPortalNotFoundError("That building is not available in this checklist.")
    return building


def _load_session_with_items(session):
    items = sorted(get_session_items(session.name), key=lambda row: row.sort_order or row.idx or 0)
    return map_portal_session(session, items=items), items


def list_checklist_buildings(*, active_only: bool = True):
    require_portal_section("checklist")
    return [map_portal_building(row) for row in list_buildings(active_only=active_only)]


def get_checklist_building(building_id: str, service_date: str) -> ChecklistPortalBuildingDetail:
    require_portal_section("checklist")
    building = _require_checklist_building(clean_str(building_id))

    active_session = get_active_session(building.name, clean_str(service_date))
    active_session_payload = None
    if active_session:
        active_session_payload, _items = _load_session_with_items(active_session)

    steps = [
        map_checklist_step(
            row,
            building_id=building.name,
            checklist_template_id=building.current_checklist_template or None,
        )
        for row in get_template_items(building.current_checklist_template, active_only=True)
    ] if building.current_checklist_template else []

    return ChecklistPortalBuildingDetail(
        building=map_portal_building(building),
        checklist_template_id=building.current_checklist_template or None,
        steps=steps,
        active_session=active_session_payload,
        storage_locations=[
            map_portal_storage_location(row) for row in list_storage_locations(building.name)
        ],
    )


def ensure_checklist_session(building_id: str, service_date: str):
    require_portal_section("checklist")
    require_checklist_work_access()
    building = _require_checklist_building(clean_str(building_id))
    session = ensure_active_session(building.name, clean_str(service_date))
    payload, _items = _load_session_with_items(session)
    return payload


def update_checklist_session_item(
    session_id: str,
    item_key: str,
    *,
    completed: bool | None = None,
    issue_reported: bool | None = None,
    issue_reason: str | None = None,
    note: str | None = None,
    proof_image: str | None = None,
) -> ChecklistSessionItemMutation:
    require_portal_section("checklist")
    require_checklist_work_access()
    session = require_session(clean_str(session_id))
    updated_session, updated_item = update_session_item(
        session.name,
        clean_str(item_key),
        completed=completed,
        issue_reported=issue_reported,
        issue_reason=issue_reason,
        note=note,
        proof_image=proof_image,
    )
    session_payload, _items = _load_session_with_items(updated_session)
    return ChecklistSessionItemMutation(
        session=session_payload,
        item=map_portal_session_item(updated_item, updated_session.name),
    )


def complete_checklist_session(session_id: str):
    require_portal_section("checklist")
    require_checklist_work_access()
    session = complete_session(clean_str(session_id))
    payload, _items = _load_session_with_items(session)
    return payload


def upload_checklist_session_item_proof(session_id: str, item_key: str, uploaded=None) -> ChecklistSessionItemMutation:
    require_portal_section("checklist")
    require_checklist_work_access()
    updated_session, updated_item = upload_session_item_proof(clean_str(session_id), clean_str(item_key), uploaded=uploaded)
    session_payload, _items = _load_session_with_items(updated_session)
    return ChecklistSessionItemMutation(
        session=session_payload,
        item=map_portal_session_item(updated_item, updated_session.name),
    )


def upload_checklist_session_item_issue_image(session_id: str, item_key: str, uploaded=None) -> ChecklistSessionItemMutation:
    require_portal_section("checklist")
    require_checklist_work_access()
    updated_session, updated_item = upload_session_item_issue_image(
        clean_str(session_id),
        clean_str(item_key),
        uploaded=uploaded,
    )
    session_payload, _items = _load_session_with_items(updated_session)
    return ChecklistSessionItemMutation(
        session=session_payload,
        item=map_portal_session_item(updated_item, updated_session.name),
    )


def download_checklist_step_training_media(building_id: str, item_key: str) -> PortalMediaContent:
    require_portal_section("checklist")
    building = _require_checklist_building(clean_str(building_id))
    template_name = clean_str(building.current_checklist_template)
    if not template_name:
        raise CustomerPortalNotFoundError("No training media is attached to this checklist item.")

    normalized_item_key = clean_str(item_key)
    item = next(
        (
            row
            for row in get_template_items(template_name, active_only=True)
            if row.item_key == normalized_item_key or row.name == normalized_item_key
        ),
        None,
    )
    if not item or not item.training_media:
        raise CustomerPortalNotFoundError("No training media is attached to this checklist item.")

    file_name, content, content_type = building_sop_service.get_proof_file_content(item.training_media)
    return PortalMediaContent(
        filename=clean_str(file_name),
        content=content,
        content_type=clean_str(content_type) or "application/octet-stream",
        display_content_as="inline",
    )


def download_checklist_session_item_training_media(session_id: str, item_key: str) -> PortalMediaContent:
    require_portal_section("checklist")
    session = require_session(clean_str(session_id))
    _require_checklist_building(session.building)
    item = require_session_item(session.name, clean_str(item_key))
    if not item.training_media:
        raise CustomerPortalNotFoundError("No training media is attached to this checklist item.")

    file_name, content, content_type = building_sop_service.get_proof_file_content(item.training_media)
    return PortalMediaContent(
        filename=clean_str(file_name),
        content=content,
        content_type=clean_str(content_type) or "application/octet-stream",
        display_content_as="inline",
    )
