from __future__ import annotations

from ..contracts.common import clean_str
from .building.mappers import map_portal_building
from .building.repo import BuildingRecord, get_building, list_customer_buildings
from .checklist.mappers import map_portal_session, map_portal_session_item
from .checklist.repo import ChecklistSessionItemRecord, ChecklistSessionRecord, get_session, get_session_items, list_sessions
from .errors import CustomerPortalNotFoundError
from .models import CustomerBuildingHistory, CustomerJobDetail, CustomerOverview


def _require_scoped_building(customer_name: str, building_name: str) -> BuildingRecord:
    building = get_building(building_name)
    if not building or building.customer != clean_str(customer_name):
        raise CustomerPortalNotFoundError("That building is not available in this portal account.")
    return building


def _require_scoped_completed_session(customer_name: str, session_name: str) -> tuple[ChecklistSessionRecord, BuildingRecord]:
    session = get_session(session_name)
    if not session:
        raise CustomerPortalNotFoundError("That job report is not available in this portal account.")

    building = get_building(session.building)
    if not building or building.customer != clean_str(customer_name) or session.status != "completed":
        raise CustomerPortalNotFoundError("That job report is not available in this portal account.")

    return session, building


def get_customer_overview(customer_name: str, *, limit: int = 200) -> CustomerOverview:
    buildings = list_customer_buildings(customer_name)
    if not buildings:
        return CustomerOverview(buildings=[], completed_sessions=[])

    completed_sessions = list_sessions(
        building_names=[building.name for building in buildings],
        status="completed",
        limit=limit,
    )
    return CustomerOverview(
        buildings=[map_portal_building(building) for building in buildings],
        completed_sessions=[map_portal_session(session) for session in completed_sessions],
    )


def get_customer_building_history(customer_name: str, building_id: str, *, limit: int = 200) -> CustomerBuildingHistory:
    building = _require_scoped_building(customer_name, building_id)
    sessions = list_sessions(building_names=[building.name], status="completed", limit=limit)
    return CustomerBuildingHistory(
        building=map_portal_building(building),
        completed_sessions=[map_portal_session(session) for session in sessions],
    )


def get_customer_completed_job(customer_name: str, session_id: str) -> CustomerJobDetail:
    session, building = _require_scoped_completed_session(customer_name, session_id)
    items = sorted(get_session_items(session.name), key=lambda row: row.sort_order or row.idx or 0)
    return CustomerJobDetail(
        building=map_portal_building(building),
        session=map_portal_session(session, items=items),
    )


def get_customer_job_proof_item(customer_name: str, session_id: str, item_key: str) -> ChecklistSessionItemRecord:
    session, _building = _require_scoped_completed_session(customer_name, session_id)
    normalized_item_key = clean_str(item_key)
    item = next(
        (
            row
            for row in get_session_items(session.name)
            if row.item_key == normalized_item_key or row.name == normalized_item_key
        ),
        None,
    )
    if not item:
        raise CustomerPortalNotFoundError("That checklist proof is not available in this portal account.")
    if not item.proof_image:
        raise CustomerPortalNotFoundError("No proof photo is attached to this checklist item.")
    return item
