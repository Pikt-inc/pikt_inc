from __future__ import annotations

import frappe

from .. import building_sop as building_sop_service
from ..contracts.common import clean_str
from .account import repo as account_repo
from .account import get_account_summary, require_checklist_work_access, require_portal_section
from .building.mappers import compose_building_address, map_portal_building, map_portal_storage_location
from .building.repo import (
    get_building,
    get_building_context,
    list_assigned_building_names_for_employee,
    list_buildings,
    list_storage_locations,
)
from .checklist.mappers import map_checklist_step, map_portal_session, map_portal_session_item
from .checklist.repo import (
    create_session,
    get_active_session,
    get_active_session_for_requirement,
    get_session_items,
    get_template_items,
    list_sessions,
)
from .checklist.service import (
    complete_session,
    download_session_item_issue_image,
    download_session_item_proof,
    ensure_active_session,
    require_session,
    require_session_item,
    update_session_item,
    upload_session_item_issue_image,
    upload_session_item_proof,
)
from ..dispatch.routing import (
    build_structured_access_lines,
    build_structured_alarm_lines,
    build_structured_site_lines,
)
from .errors import CustomerPortalNotFoundError
from .models import (
    AssignedWorkDetail,
    AssignedWorkProgressSummary,
    AssignedWorkQueue,
    AssignedWorkSummary,
    ChecklistPortalBuildingDetail,
    ChecklistSessionItemMutation,
    PortalMediaContent,
    ProofFileContent,
)

REQUIREMENT_FIELDS = [
    "name",
    "building",
    "service_date",
    "shift_type",
    "arrival_window_start",
    "arrival_window_end",
    "status",
    "checked_in_at",
    "current_employee",
    "custom_dispatch_route",
    "shift_assignment",
    "completion_status",
    "service_notes_snapshot",
    "service_timezone",
    "slot_index",
    "creation",
    "modified",
]

ROUTE_STOP_FIELDS = [
    "parent",
    "site_shift_requirement",
    "stop_index",
    "arrival_window_start",
    "arrival_window_end",
]

TERMINAL_WORK_STATUSES = {"Completed", "Completed With Exception", "Unfilled Closed", "Cancelled"}


def _get_checklist_employee_name() -> str:
    session_user = clean_str(getattr(getattr(frappe, "session", None), "user", None))
    employee = account_repo.get_employee_for_user(session_user)
    return clean_str(employee.name if employee else "")


def _get_assigned_building_names(service_date) -> list[str]:
    employee_name = _get_checklist_employee_name()
    return list_assigned_building_names_for_employee(employee_name, service_date)


def _get_all_assigned_building_names() -> list[str]:
    employee_name = _get_checklist_employee_name()
    if not employee_name:
        return []

    rows = frappe.get_all(
        "Site Shift Requirement",
        filters={"current_employee": employee_name},
        fields=["building"],
        order_by="service_date asc, arrival_window_start asc, creation asc",
        limit=500,
    )

    seen: set[str] = set()
    building_names: list[str] = []
    for row in rows or []:
        building_name = clean_str((row or {}).get("building"))
        if building_name and building_name not in seen:
            seen.add(building_name)
            building_names.append(building_name)

    return building_names


def _list_assigned_requirement_rows(service_date: str | None = None) -> list[dict]:
    employee_name = _get_checklist_employee_name()
    if not employee_name:
        return []

    filters: dict[str, object] = {
        "current_employee": employee_name,
    }
    if clean_str(service_date):
        filters["service_date"] = [">=", clean_str(service_date)]

    return frappe.get_all(
        "Site Shift Requirement",
        filters=filters,
        fields=REQUIREMENT_FIELDS,
        order_by="service_date asc, arrival_window_start asc, creation asc",
        limit=200,
    ) or []


def _require_assigned_requirement(requirement_id: str) -> dict:
    requirement_id = clean_str(requirement_id)
    if not requirement_id:
        raise CustomerPortalNotFoundError("That assigned work item is not available in this checklist.")

    employee_name = _get_checklist_employee_name()
    row = frappe.db.get_value("Site Shift Requirement", requirement_id, REQUIREMENT_FIELDS, as_dict=True)
    if not row or clean_str(row.get("current_employee")) != employee_name:
        raise CustomerPortalNotFoundError("That assigned work item is not available in this checklist.")

    return row


def _require_session_access(session) -> None:
    requirement_name = clean_str(getattr(session, "site_shift_requirement", None))
    if requirement_name:
        _require_assigned_requirement(requirement_name)
        return

    raise CustomerPortalNotFoundError("That checklist session is not available in this portal.")


def _get_route_stop_index_map(requirement_rows: list[dict]) -> dict[str, int]:
    route_names = sorted(
        {clean_str(row.get("custom_dispatch_route")) for row in requirement_rows if clean_str(row.get("custom_dispatch_route"))}
    )
    if not route_names:
        return {}

    rows = frappe.get_all(
        "Dispatch Route Stop",
        filters={
            "parent": ["in", route_names],
            "parenttype": "Dispatch Route",
        },
        fields=ROUTE_STOP_FIELDS,
        order_by="parent asc, stop_index asc, creation asc",
        limit=500,
    )

    stop_index_map: dict[str, int] = {}
    for row in rows or []:
        requirement_name = clean_str((row or {}).get("site_shift_requirement"))
        if not requirement_name or requirement_name in stop_index_map:
            continue
        stop_index_map[requirement_name] = int(row.get("stop_index") or 0)

    return stop_index_map


def _select_sessions_by_requirement(requirement_names: list[str]) -> dict[str, object]:
    sessions = list_sessions(requirement_names=requirement_names, limit=max(50, len(requirement_names) * 5))
    selected: dict[str, object] = {}
    for session in sessions:
        requirement_name = clean_str(getattr(session, "site_shift_requirement", None))
        if not requirement_name:
            continue
        existing = selected.get(requirement_name)
        if existing is None:
            selected[requirement_name] = session
            continue
        if getattr(existing, "status", None) != "in_progress" and getattr(session, "status", None) == "in_progress":
            selected[requirement_name] = session
    return selected


def _build_progress_summary(session, items: list, template_steps_total: int) -> AssignedWorkProgressSummary:
    if not session:
        return AssignedWorkProgressSummary(total_steps=template_steps_total, resolved_steps=0)

    total_steps = len(items)
    resolved_steps = len([row for row in items if row.completed or row.issue_reported])
    return AssignedWorkProgressSummary(total_steps=total_steps, resolved_steps=resolved_steps)


def _derive_work_status(requirement_row: dict, session, items: list) -> str:
    requirement_status = clean_str(requirement_row.get("status")) or "Assigned"
    completion_status = clean_str(requirement_row.get("completion_status"))

    if completion_status in TERMINAL_WORK_STATUSES:
        return completion_status

    if session and clean_str(getattr(session, "status", None)) == "completed":
        has_issue = any(row.issue_reported for row in items)
        return "Completed With Exception" if has_issue else "Completed"

    if session and clean_str(getattr(session, "status", None)) == "in_progress":
        return "In Progress"

    return requirement_status or "Assigned"


def _requires_clock_in(account_summary, requirement_row: dict, session, status: str) -> bool:
    if status in TERMINAL_WORK_STATUSES or status == "In Progress":
        return False
    if session and clean_str(getattr(session, "status", None)) == "in_progress":
        return False
    if not getattr(account_summary, "can_clock", False):
        return False

    service_date = str(requirement_row.get("service_date") or "")
    today = frappe.utils.today()
    clock_state = getattr(account_summary, "clock_state", None)
    return service_date == today and getattr(clock_state, "status", None) != "clocked_in"


def _sort_work_cards(cards: list[AssignedWorkSummary]) -> list[AssignedWorkSummary]:
    def sort_key(card: AssignedWorkSummary):
        return (
            str(card.service_date or ""),
            card.route_stop_index if card.route_stop_index not in (None, 0) else 9999,
            str(card.arrival_window_start or card.arrival_window_end or ""),
            card.building_name,
        )

    return sorted(cards, key=sort_key)


def _pick_current_shift(today_cards: list[AssignedWorkSummary]) -> AssignedWorkSummary | None:
    for preferred_status in ("In Progress", "Checked In"):
        for card in today_cards:
            if card.status == preferred_status:
                return card
    for card in today_cards:
        if card.status not in TERMINAL_WORK_STATUSES:
            return card
    return today_cards[0] if today_cards else None


def _build_assigned_work_summary(
    requirement_row: dict,
    *,
    building_row_cache: dict[str, object],
    route_stop_index_map: dict[str, int],
    session_map: dict[str, object],
    session_items_map: dict[str, list],
    template_count_cache: dict[str, int],
    account_summary,
) -> AssignedWorkSummary:
    building_name = clean_str(requirement_row.get("building"))
    building = building_row_cache.get(building_name)
    session = session_map.get(clean_str(requirement_row.get("name")))
    items = session_items_map.get(getattr(session, "name", ""), [])

    template_steps_total = 0
    if building and clean_str(getattr(building, "current_checklist_template", "")):
        template_name = clean_str(getattr(building, "current_checklist_template", ""))
        if template_name not in template_count_cache:
            template_count_cache[template_name] = len(get_template_items(template_name, active_only=True))
        template_steps_total = template_count_cache[template_name]

    progress_summary = _build_progress_summary(session, items, template_steps_total)
    status = _derive_work_status(requirement_row, session, items)
    requires_clock_in = _requires_clock_in(account_summary, requirement_row, session, status)

    return AssignedWorkSummary(
        requirement_id=clean_str(requirement_row.get("name")),
        building_id=building_name,
        building_name=(getattr(building, "building_name", None) or getattr(building, "name", None) or building_name),
        short_address=compose_building_address(building) if building else None,
        service_date=requirement_row.get("service_date"),
        shift_type=clean_str(requirement_row.get("shift_type")) or None,
        arrival_window_start=requirement_row.get("arrival_window_start"),
        arrival_window_end=requirement_row.get("arrival_window_end"),
        status=status,
        checked_in_at=requirement_row.get("checked_in_at"),
        checklist_session_id=getattr(session, "name", None) or None,
        progress_summary=progress_summary,
        requires_clock_in=requires_clock_in,
        route_stop_index=route_stop_index_map.get(clean_str(requirement_row.get("name"))),
    )


def _require_checklist_building(building_id: str, service_date=None):
    building = get_building(building_id)
    if not building:
        raise CustomerPortalNotFoundError("That building is not available in this checklist.")

    if service_date not in (None, ""):
        assigned_building_names = _get_assigned_building_names(service_date)
        if building.name not in assigned_building_names:
            raise CustomerPortalNotFoundError("That building is not available in this checklist.")

    return building


def _load_session_with_items(session):
    items = sorted(get_session_items(session.name), key=lambda row: row.sort_order or row.idx or 0)
    return map_portal_session(session, items=items), items


def get_assigned_work_queue(*, service_date: str | None = None) -> AssignedWorkQueue:
    require_portal_section("checklist")
    target_date = clean_str(service_date) or frappe.utils.today()
    requirement_rows = _list_assigned_requirement_rows(target_date)
    if not requirement_rows:
        return AssignedWorkQueue()

    building_names = sorted({clean_str(row.get("building")) for row in requirement_rows if clean_str(row.get("building"))})
    building_row_cache = {
        row.name: row
        for row in list_buildings(active_only=None, building_names=building_names)
    }
    route_stop_index_map = _get_route_stop_index_map(requirement_rows)
    session_map = _select_sessions_by_requirement([clean_str(row.get("name")) for row in requirement_rows])
    session_items_map = {
        session.name: get_session_items(session.name)
        for session in session_map.values()
    }
    template_count_cache: dict[str, int] = {}
    account_summary = get_account_summary()

    cards = _sort_work_cards(
        [
            _build_assigned_work_summary(
                row,
                building_row_cache=building_row_cache,
                route_stop_index_map=route_stop_index_map,
                session_map=session_map,
                session_items_map=session_items_map,
                template_count_cache=template_count_cache,
                account_summary=account_summary,
            )
            for row in requirement_rows
        ]
    )

    today_cards = [card for card in cards if str(card.service_date or "") == target_date]
    upcoming_cards = [card for card in cards if str(card.service_date or "") > target_date]
    current_shift = _pick_current_shift(today_cards)
    assigned_work = [card for card in today_cards if current_shift is None or card.requirement_id != current_shift.requirement_id]

    return AssignedWorkQueue(
        current_shift=current_shift,
        assigned_work=assigned_work,
        upcoming_assigned_work=upcoming_cards,
    )


def get_assigned_work_detail(requirement_id: str) -> AssignedWorkDetail:
    require_portal_section("checklist")
    requirement_row = _require_assigned_requirement(requirement_id)
    building_name = clean_str(requirement_row.get("building"))
    building = _require_checklist_building(building_name, requirement_row.get("service_date"))
    building_context = get_building_context(building_name) or {}

    session = get_active_session_for_requirement(clean_str(requirement_row.get("name")))
    if not session:
        sessions = list_sessions(requirement_names=[clean_str(requirement_row.get("name"))], limit=10)
        session = sessions[0] if sessions else None

    session_payload = None
    if session:
        session_payload, _items = _load_session_with_items(session)

    steps = [
        map_checklist_step(
            row,
            building_id=building.name,
            checklist_template_id=building.current_checklist_template or None,
        )
        for row in get_template_items(building.current_checklist_template, active_only=True)
    ] if building.current_checklist_template else []

    summary = _build_assigned_work_summary(
        requirement_row,
        building_row_cache={building.name: building},
        route_stop_index_map=_get_route_stop_index_map([requirement_row]),
        session_map={clean_str(requirement_row.get("name")): session} if session else {},
        session_items_map={session.name: get_session_items(session.name)} if session else {},
        template_count_cache={},
        account_summary=get_account_summary(),
    )

    return AssignedWorkDetail(
        work=summary,
        building=map_portal_building(building),
        checklist_template_id=building.current_checklist_template or None,
        steps=steps,
        active_session=session_payload,
        storage_locations=[
            map_portal_storage_location(row) for row in list_storage_locations(building.name)
        ],
        access_summary=build_structured_access_lines(building_context),
        alarm_summary=build_structured_alarm_lines(building_context),
        site_summary=build_structured_site_lines(building_context),
        service_notes=clean_str(requirement_row.get("service_notes_snapshot")) or None,
    )


def ensure_assigned_work_session(requirement_id: str):
    require_portal_section("checklist")
    require_checklist_work_access()
    requirement_row = _require_assigned_requirement(requirement_id)

    session = get_active_session_for_requirement(clean_str(requirement_row.get("name")))
    if not session:
        session = create_session(
            clean_str(requirement_row.get("building")),
            requirement_row.get("service_date"),
            requirement_name=clean_str(requirement_row.get("name")),
            worker=_get_checklist_employee_name(),
        )

    payload, _items = _load_session_with_items(session)
    return payload


def list_checklist_buildings(*, active_only: bool = True):
    require_portal_section("checklist")
    assigned_building_names = _get_assigned_building_names(frappe.utils.today())
    return [
        map_portal_building(row)
        for row in list_buildings(
            active_only=active_only,
            building_names=assigned_building_names,
        )
    ]


def get_checklist_building(building_id: str, service_date: str) -> ChecklistPortalBuildingDetail:
    require_portal_section("checklist")
    normalized_service_date = clean_str(service_date)
    building = _require_checklist_building(clean_str(building_id), normalized_service_date)

    active_session = get_active_session(building.name, normalized_service_date)
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
    normalized_service_date = clean_str(service_date)
    building = _require_checklist_building(clean_str(building_id), normalized_service_date)
    session = ensure_active_session(building.name, normalized_service_date)
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
    _require_session_access(session)
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
    current_session = require_session(clean_str(session_id))
    _require_session_access(current_session)
    session = complete_session(current_session.name)
    payload, _items = _load_session_with_items(session)
    return payload


def upload_checklist_session_item_proof(session_id: str, item_key: str, uploaded=None) -> ChecklistSessionItemMutation:
    require_portal_section("checklist")
    require_checklist_work_access()
    session = require_session(clean_str(session_id))
    _require_session_access(session)
    updated_session, updated_item = upload_session_item_proof(session.name, clean_str(item_key), uploaded=uploaded)
    session_payload, _items = _load_session_with_items(updated_session)
    return ChecklistSessionItemMutation(
        session=session_payload,
        item=map_portal_session_item(updated_item, updated_session.name),
    )


def upload_checklist_session_item_issue_image(session_id: str, item_key: str, uploaded=None) -> ChecklistSessionItemMutation:
    require_portal_section("checklist")
    require_checklist_work_access()
    session = require_session(clean_str(session_id))
    _require_session_access(session)
    updated_session, updated_item = upload_session_item_issue_image(
        session.name,
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
    if building.name not in _get_all_assigned_building_names():
        raise CustomerPortalNotFoundError("No training media is attached to this checklist item.")
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


def download_checklist_assigned_step_training_media(requirement_id: str, item_key: str) -> PortalMediaContent:
    require_portal_section("checklist")
    requirement_row = _require_assigned_requirement(requirement_id)
    building = _require_checklist_building(
        clean_str(requirement_row.get("building")),
        requirement_row.get("service_date"),
    )
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
    _require_session_access(session)
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


def download_checklist_session_item_proof_file(session_id: str, item_key: str) -> PortalMediaContent:
    require_portal_section("checklist")
    session = require_session(clean_str(session_id))
    _require_session_access(session)
    return download_session_item_proof(session.name, clean_str(item_key))


def download_checklist_session_item_issue_image_file(session_id: str, item_key: str) -> PortalMediaContent:
    require_portal_section("checklist")
    session = require_session(clean_str(session_id))
    _require_session_access(session)
    return download_session_item_issue_image(session.name, clean_str(item_key))
