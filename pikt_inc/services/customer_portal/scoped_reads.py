from __future__ import annotations

from ..contracts.common import clean_str
from .building_repo import BuildingRecord, get_building, get_customer_buildings
from .checklist_repo import ChecklistSessionRecord, get_session, get_session_items, list_sessions
from .errors import CustomerPortalNotFoundError
from .read_models import (
    ScopedBuildingHistoryRead,
    ScopedCompletedSessionRead,
    ScopedJobDetailRead,
    ScopedJobProofRead,
    ScopedOverviewRead,
)


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


def list_customer_completed_sessions(customer_name: str, *, limit: int = 200) -> list[ScopedCompletedSessionRead]:
    buildings = get_customer_buildings(customer_name)
    if not buildings:
        return []
    sessions = list_sessions(
        building_names=[building.name for building in buildings],
        status="completed",
        limit=limit,
    )
    return [ScopedCompletedSessionRead(session=session) for session in sessions]


def get_customer_overview_read(customer_name: str, *, limit: int = 200) -> ScopedOverviewRead:
    buildings = get_customer_buildings(customer_name)
    if not buildings:
        return ScopedOverviewRead(buildings=[], completed_sessions=[])
    completed_sessions = list_sessions(
        building_names=[building.name for building in buildings],
        status="completed",
        limit=limit,
    )
    return ScopedOverviewRead(
        buildings=buildings,
        completed_sessions=[ScopedCompletedSessionRead(session=session) for session in completed_sessions],
    )


def get_customer_building_history(
    customer_name: str,
    building_id: str,
    *,
    limit: int = 200,
) -> ScopedBuildingHistoryRead:
    building = _require_scoped_building(customer_name, building_id)
    sessions = list_sessions(building_names=[building.name], status="completed", limit=limit)
    return ScopedBuildingHistoryRead(
        building=building,
        completed_sessions=[ScopedCompletedSessionRead(session=session) for session in sessions],
    )


def get_customer_completed_job(customer_name: str, session_id: str) -> ScopedJobDetailRead:
    session, building = _require_scoped_completed_session(customer_name, session_id)
    items = sorted(get_session_items(session.name), key=lambda row: row.sort_order or row.idx or 0)
    return ScopedJobDetailRead(building=building, session=session, items=items)


def get_customer_job_proof_target(customer_name: str, session_id: str, item_key: str) -> ScopedJobProofRead:
    session, _building = _require_scoped_completed_session(customer_name, session_id)
    item_key = clean_str(item_key)
    item = next(
        (
            row
            for row in get_session_items(session.name)
            if row.item_key == item_key or row.name == item_key
        ),
        None,
    )
    if not item:
        raise CustomerPortalNotFoundError("That checklist proof is not available in this portal account.")

    if not item.proof_image:
        raise CustomerPortalNotFoundError("No proof photo is attached to this checklist item.")

    return ScopedJobProofRead(session=session, item=item)
