from __future__ import annotations

import frappe

from . import incidents, shared


_BUILDING_CACHE = {}
_SHIFT_TYPE_CACHE = {}
_TERMINAL_COMPLETION_STATES = {"Completed", "Completed With Exception", "Unfilled Closed", "Cancelled"}
_ASSIGNMENT_RESETTABLE_STATUSES = {"Called Out", "Reassignment In Progress", "Open", "Draft", "Likely No-show"}


def get_building_cached(building_name: str):
    building_name = shared.clean(building_name)
    if not building_name:
        return None
    if building_name not in _BUILDING_CACHE:
        _BUILDING_CACHE[building_name] = shared.get_building_fields(
            building_name,
            ["latitude", "longitude", "supervisor_user"],
        )
    return _BUILDING_CACHE[building_name]


def distance_miles(home_building: str, target_building: str):
    home = get_building_cached(home_building)
    target = get_building_cached(target_building)
    if not home or not target:
        return None
    if (
        home.get("latitude") is None
        or home.get("longitude") is None
        or target.get("latitude") is None
        or target.get("longitude") is None
    ):
        return None

    lat_miles = abs(shared.as_float(home.get("latitude")) - shared.as_float(target.get("latitude"))) * 69.0
    lon_miles = abs(shared.as_float(home.get("longitude")) - shared.as_float(target.get("longitude"))) * 54.6
    return (lat_miles * lat_miles + lon_miles * lon_miles) ** 0.5


def get_shift_type_window(shift_type: str, service_date):
    shift_type = shared.clean(shift_type)
    if not shift_type or not service_date:
        return (None, None)

    if shift_type not in _SHIFT_TYPE_CACHE:
        _SHIFT_TYPE_CACHE[shift_type] = frappe.db.get_value(
            "Shift Type",
            shift_type,
            ["start_time", "end_time"],
            as_dict=True,
        )

    row = _SHIFT_TYPE_CACHE.get(shift_type) or {}
    if not row.get("start_time") or not row.get("end_time"):
        return (None, None)

    service_date_str = str(service_date)
    start_dt = shared.to_datetime(f"{service_date_str} {row.get('start_time')}")
    end_dt = shared.to_datetime(f"{service_date_str} {row.get('end_time')}")
    if not start_dt or not end_dt:
        return (None, None)
    if end_dt <= start_dt:
        end_dt = shared.to_datetime(frappe.utils.add_to_date(end_dt, days=1, as_string=True))
    return (start_dt, end_dt)


def has_overlap(start_a, end_a, start_b, end_b) -> bool:
    if not start_a or not end_a or not start_b or not end_b:
        return True
    return start_a < end_b and start_b < end_a


def has_assignment_conflict(employee: str, service_date, target_start, target_end) -> bool:
    assignments = frappe.get_all(
        "Shift Assignment",
        filters={
            "employee": employee,
            "start_date": ["<=", service_date],
            "end_date": [">=", service_date],
            "status": "Active",
            "docstatus": ["<", 2],
        },
        fields=["name", "custom_site_shift_requirement", "shift_type"],
        limit=5000,
    )

    for assignment in assignments:
        other_start = None
        other_end = None

        linked_requirement = shared.clean(assignment.get("custom_site_shift_requirement"))
        if linked_requirement and frappe.db.exists("Site Shift Requirement", linked_requirement):
            linked = frappe.db.get_value(
                "Site Shift Requirement",
                linked_requirement,
                ["arrival_window_start", "arrival_window_end"],
                as_dict=True,
            ) or {}
            other_start = shared.to_datetime(linked.get("arrival_window_start"))
            other_end = shared.to_datetime(linked.get("arrival_window_end"))

        if not other_start or not other_end:
            other_start, other_end = get_shift_type_window(assignment.get("shift_type"), service_date)

        if has_overlap(target_start, target_end, other_start, other_end):
            return True

    return False


def priority_points(priority: str) -> int:
    return {
        "Low": 10,
        "Medium": 20,
        "High": 30,
        "Critical": 40,
    }.get(shared.clean(priority) or "Medium", 20)


def build_candidates(ssr, settings: dict) -> list[dict]:
    target_start = shared.to_datetime(ssr.get("arrival_window_start"))
    target_end = shared.to_datetime(ssr.get("arrival_window_end"))

    availability_rows = frappe.get_all(
        "Employee Availability",
        filters={
            "availability_date": ssr.get("service_date"),
            "available": 1,
            "availability_status": ["in", ["Available", "Tentative"]],
        },
        fields=["employee", "max_hours", "home_base_building", "availability_status"],
        limit=5000,
    )
    availability_map = {row.get("employee"): row for row in availability_rows if row.get("employee")}

    employees = frappe.get_all("Employee", filters={"status": "Active"}, fields=["name", "company"], limit=5000)

    max_overtime_hours = shared.as_float(settings.get("max_overtime_hours"), shared.DEFAULT_MAX_OVERTIME_HOURS)
    max_distance_miles = shared.as_float(settings.get("max_distance_miles"), shared.DEFAULT_MAX_DISTANCE_MILES)
    estimated_hours = shared.as_float(ssr.get("estimated_hours"), 0)

    candidates = []
    for employee in employees:
        employee_name = employee.get("name")
        if not employee_name:
            continue

        if has_assignment_conflict(employee_name, ssr.get("service_date"), target_start, target_end):
            continue

        explicit_availability = employee_name in availability_map
        availability = availability_map.get(employee_name) or {}

        availability_score = 15
        home_base_building = None
        max_hours = 6.0

        if explicit_availability:
            availability_score = 40 if (availability.get("availability_status") or "Available") == "Available" else 30
            home_base_building = availability.get("home_base_building")
            if availability.get("max_hours") is not None:
                max_hours = shared.as_float(availability.get("max_hours"), 6.0)

        overtime_hours = max(0.0, estimated_hours - max_hours)
        if overtime_hours > max_overtime_hours:
            continue

        familiarity_score = 5
        if home_base_building:
            familiarity_score = 20 if home_base_building == ssr.get("building") else 8

        distance = distance_miles(home_base_building, ssr.get("building")) if home_base_building else None
        distance_cap = max_distance_miles if explicit_availability else round(max_distance_miles * 0.8, 2)
        if distance is not None and distance > distance_cap:
            continue

        distance_penalty = shared.as_int((distance or 0) / 5, 0)
        overtime_penalty = shared.as_int(round(overtime_hours * 10), 0)
        if not explicit_availability:
            overtime_penalty += 8

        total_score = (
            priority_points(ssr.get("priority"))
            + availability_score
            + familiarity_score
            + 15
            - distance_penalty
            - overtime_penalty
        )

        candidates.append(
            {
                "employee": employee_name,
                "total_score": total_score,
                "availability_score": availability_score,
                "familiarity_score": familiarity_score,
                "priority_score": priority_points(ssr.get("priority")),
                "overtime_penalty": overtime_penalty,
                "distance_miles": distance,
                "drive_time_minutes": None if distance is None else round(shared.as_float(distance) * 2.2, 1),
            }
        )

    candidates.sort(key=lambda row: row["total_score"], reverse=True)
    return candidates


def auto_assign_requirement(ssr_name: str, settings: dict | None = None) -> str:
    settings = settings or shared.get_dispatch_settings()
    ssr = frappe.get_doc("Site Shift Requirement", ssr_name)

    if ssr.status != "Open" or ssr.checked_in_at:
        return "skipped"

    incidents.expire_previous_recommendations(ssr.name)
    candidates = build_candidates(ssr, settings)

    if not candidates:
        message = f"No valid initial assignment candidate found for requirement {ssr.name} on {ssr.service_date}."
        incidents.create_or_update_escalation(
            ssr.name,
            ssr.building,
            "No Valid Candidate",
            message,
            settings,
            None,
        )
        frappe.db.set_value(
            "Site Shift Requirement",
            ssr.name,
            {
                "auto_assignment_status": "Escalated",
                "exception_reason": message,
                "reconciled_at": shared.now(),
            },
        )
        return "escalated"

    top_candidate = candidates[0]
    try:
        company = frappe.db.get_value("Employee", top_candidate["employee"], "company")
        shift_assignment = frappe.get_doc(
            {
                "doctype": "Shift Assignment",
                "employee": top_candidate["employee"],
                "company": company,
                "shift_type": ssr.shift_type,
                "shift_location": ssr.shift_location,
                "start_date": ssr.service_date,
                "end_date": ssr.service_date,
                "custom_site_shift_requirement": ssr.name,
            }
        )
        shift_assignment.insert(ignore_permissions=True)
        if shift_assignment.docstatus == 0:
            shift_assignment.flags.ignore_permissions = True
            shift_assignment.submit()

        for index, candidate in enumerate(candidates[:5], start=1):
            confidence = "High" if candidate["total_score"] >= 85 else ("Medium" if candidate["total_score"] >= 65 else "Low")
            decision_status = "Auto Assigned" if index == 1 else "Suggested"
            recommendation = frappe.get_doc(
                {
                    "doctype": "Dispatch Recommendation",
                    "site_shift_requirement": ssr.name,
                    "candidate_employee": candidate["employee"],
                    "rank": index,
                    "total_score": candidate["total_score"],
                    "drive_time_minutes": candidate["drive_time_minutes"],
                    "distance_miles": candidate["distance_miles"],
                    "familiarity_score": candidate["familiarity_score"],
                    "availability_score": candidate["availability_score"],
                    "overtime_penalty": candidate["overtime_penalty"],
                    "priority_score": candidate["priority_score"],
                    "decision_status": decision_status,
                    "decision_notes": "Auto-generated by the dispatch service layer.",
                    "recommendation_type": "Initial Assignment",
                    "confidence_level": confidence,
                    "auto_assign_eligible": 1 if index == 1 else 0,
                }
            )
            recommendation.insert(ignore_permissions=True)

        frappe.db.set_value(
            "Site Shift Requirement",
            ssr.name,
            {
                "status": "Assigned",
                "current_employee": top_candidate["employee"],
                "auto_assignment_status": "Auto Assigned",
                "exception_reason": None,
                "reconciled_at": shared.now(),
                "custom_calendar_subject": shared.make_calendar_subject(
                    ssr.building,
                    ssr.shift_type,
                    ssr.slot_index,
                    top_candidate["employee"],
                    "Assigned",
                    ssr.service_timezone,
                ),
            },
        )

        incidents.resolve_open_escalations(ssr.name)
        return "assigned"
    except Exception as exc:
        incidents.create_or_update_escalation(
            ssr.name,
            ssr.building,
            "Validation Error",
            f"Automatic initial assignment failed for {ssr.name}.",
            settings,
            str(exc),
        )
        frappe.log_error(str(exc), f"Dispatch auto assign {ssr_name}")
        return "error"


def sync_from_shift_assignment(assignment_name: str | None = None, assignment_doc=None):
    assignment_name = shared.clean(assignment_name) or shared.clean(getattr(assignment_doc, "name", None))
    if not assignment_doc and not assignment_name:
        return {"status": "skipped", "reason": "missing_assignment"}

    assignment_doc = assignment_doc or frappe.get_doc("Shift Assignment", assignment_name)
    requirement_name = shared.clean(getattr(assignment_doc, "custom_site_shift_requirement", None))
    if not requirement_name:
        return {"status": "skipped", "reason": "missing_requirement", "assignment": assignment_doc.name}

    if getattr(assignment_doc, "docstatus", 0) >= 2 or shared.clean(getattr(assignment_doc, "status", None)) != "Active":
        return {"status": "skipped", "reason": "inactive_assignment", "assignment": assignment_doc.name}

    if not frappe.db.exists("Site Shift Requirement", requirement_name):
        return {
            "status": "skipped",
            "reason": "requirement_not_found",
            "assignment": assignment_doc.name,
            "site_shift_requirement": requirement_name,
        }

    ssr = frappe.get_doc("Site Shift Requirement", requirement_name)
    safe_to_update = any(
        [
            not shared.clean(ssr.get("shift_assignment")),
            shared.clean(ssr.get("shift_assignment")) == assignment_doc.name,
            shared.clean(ssr.get("status")) in _ASSIGNMENT_RESETTABLE_STATUSES,
            shared.clean(ssr.get("auto_assignment_status")) == "Escalated",
        ]
    )
    if not safe_to_update:
        return {
            "status": "skipped",
            "reason": "unsafe_requirement_state",
            "assignment": assignment_doc.name,
            "site_shift_requirement": requirement_name,
        }

    ssr.shift_assignment = assignment_doc.name
    ssr.current_employee = assignment_doc.employee
    if shared.clean(ssr.get("status")) in _ASSIGNMENT_RESETTABLE_STATUSES:
        ssr.status = "Assigned"
    if not shared.clean(ssr.get("shift_location")) and shared.clean(getattr(assignment_doc, "shift_location", None)):
        ssr.shift_location = assignment_doc.shift_location
    if not shared.clean(ssr.get("shift_type")) and shared.clean(getattr(assignment_doc, "shift_type", None)):
        ssr.shift_type = assignment_doc.shift_type

    ssr.auto_assignment_status = "Auto Assigned"
    if shared.clean(ssr.get("status")) != "Completed":
        if shared.clean(ssr.get("completion_status")) in _TERMINAL_COMPLETION_STATES:
            ssr.completion_status = None
        ssr.completed_at = None

    ssr.flags.ignore_permissions = True
    ssr.save(ignore_permissions=True)
    return {
        "status": "updated",
        "assignment": assignment_doc.name,
        "site_shift_requirement": requirement_name,
    }


def apply_employee_checkin(checkin_name: str | None = None, checkin_doc=None):
    checkin_name = shared.clean(checkin_name) or shared.clean(getattr(checkin_doc, "name", None))
    if not checkin_doc and not checkin_name:
        return {"status": "skipped", "reason": "missing_checkin"}

    checkin_doc = checkin_doc or frappe.get_doc("Employee Checkin", checkin_name)
    employee = shared.clean(getattr(checkin_doc, "employee", None))
    checkin_time = shared.to_datetime(getattr(checkin_doc, "time", None))
    if not employee or not checkin_time:
        return {"status": "skipped", "reason": "missing_employee_or_time", "checkin": checkin_doc.name}

    log_type = shared.clean(getattr(checkin_doc, "log_type", None))
    if log_type and log_type != "IN":
        return {"status": "skipped", "reason": "non_in_log_type", "checkin": checkin_doc.name}

    service_date = str(checkin_time.date())
    candidate_rows = frappe.get_all(
        "Site Shift Requirement",
        filters={
            "current_employee": employee,
            "service_date": service_date,
            "status": ["in", ["Assigned", "Likely No-show", "Reassignment In Progress"]],
            "checked_in_at": ["is", "not set"],
        },
        fields=["name", "arrival_window_start", "arrival_window_end", "call_out_record"],
        limit=5000,
        order_by="arrival_window_start asc",
    )

    matched_row = None
    matched_delta = None
    for row in candidate_rows:
        start_dt = shared.to_datetime(row.get("arrival_window_start"))
        end_dt = shared.to_datetime(row.get("arrival_window_end"))
        if not start_dt or not end_dt:
            continue
        if not (start_dt <= checkin_time <= end_dt):
            continue

        delta = abs((checkin_time - start_dt).total_seconds())
        if matched_row is None or delta < matched_delta:
            matched_row = row
            matched_delta = delta

    if not matched_row:
        return {
            "status": "skipped",
            "reason": "no_matching_requirement",
            "checkin": checkin_doc.name,
            "employee": employee,
        }

    frappe.db.set_value(
        "Site Shift Requirement",
        matched_row.get("name"),
        {
            "checked_in_at": getattr(checkin_doc, "time", None),
            "status": "Checked In",
        },
    )

    incidents.close_callout_if_open(matched_row.get("call_out_record"))
    incidents.resolve_open_escalations(matched_row.get("name"))
    return {
        "status": "updated",
        "checkin": checkin_doc.name,
        "site_shift_requirement": matched_row.get("name"),
    }


def finalize_completed_requirements(now_dt=None):
    now_dt = shared.to_datetime(now_dt) or shared.now_datetime()
    rows = frappe.get_all(
        "Site Shift Requirement",
        filters={
            "status": ["in", ["Checked In", "Assigned"]],
            "checked_in_at": ["is", "set"],
        },
        fields=[
            "name",
            "building",
            "shift_type",
            "slot_index",
            "current_employee",
            "service_timezone",
            "arrival_window_end",
        ],
        limit=5000,
    )

    completed = 0
    for row in rows:
        arrival_window_end = shared.to_datetime(row.get("arrival_window_end"))
        if not arrival_window_end or now_dt < arrival_window_end:
            continue
        if incidents.has_open_escalation_for_ssr(row.get("name")) or incidents.has_open_callout_for_ssr(row.get("name")):
            continue

        frappe.db.set_value(
            "Site Shift Requirement",
            row.get("name"),
            {
                "status": "Completed",
                "completion_status": "Completed",
                "completed_at": shared.now(),
                "exception_reason": None,
                "custom_calendar_subject": shared.make_calendar_subject(
                    row.get("building"),
                    row.get("shift_type"),
                    row.get("slot_index"),
                    row.get("current_employee"),
                    "Completed",
                    row.get("service_timezone"),
                ),
            },
        )
        completed += 1

    return completed


def close_unfilled_requirements(now_dt=None, settings: dict | None = None):
    now_dt = shared.to_datetime(now_dt) or shared.now_datetime()
    settings = settings or shared.get_dispatch_settings()
    rows = frappe.get_all(
        "Site Shift Requirement",
        filters={
            "status": ["in", ["Open", "Called Out", "Reassignment In Progress", "Likely No-show", "Assigned"]],
            "checked_in_at": ["is", "not set"],
        },
        fields=[
            "name",
            "building",
            "shift_type",
            "slot_index",
            "current_employee",
            "service_timezone",
            "arrival_window_end",
        ],
        limit=5000,
    )

    closed = 0
    delay_minutes = max(1, shared.as_int(settings.get("unfilled_close_delay_minutes"), 120))
    for row in rows:
        arrival_window_end = shared.to_datetime(row.get("arrival_window_end"))
        if not arrival_window_end:
            continue

        close_after = shared.to_datetime(
            frappe.utils.add_to_date(arrival_window_end, minutes=delay_minutes, as_string=True)
        )
        if not close_after or now_dt < close_after:
            continue

        message = f"Requirement {row.get('name')} closed unfilled after policy window without check-in."
        incidents.create_or_update_escalation(
            row.get("name"),
            row.get("building"),
            "Manual Override Required",
            message,
            settings,
            None,
        )
        frappe.db.set_value(
            "Site Shift Requirement",
            row.get("name"),
            {
                "status": "Unfilled Closed",
                "completion_status": "Unfilled Closed",
                "completed_at": shared.now(),
                "auto_assignment_status": "Escalated",
                "exception_reason": message,
                "incident_type": "Unfilled",
                "custom_calendar_subject": shared.make_calendar_subject(
                    row.get("building"),
                    row.get("shift_type"),
                    row.get("slot_index"),
                    row.get("current_employee"),
                    "Unfilled Closed",
                    row.get("service_timezone"),
                ),
            },
        )
        closed += 1

    return closed


def finalize_dispatch_completion(now_value=None, settings: dict | None = None):
    now_dt = shared.to_datetime(now_value) or shared.now_datetime()
    settings = settings or shared.get_dispatch_settings()
    completed = finalize_completed_requirements(now_dt=now_dt)
    unfilled_closed = close_unfilled_requirements(now_dt=now_dt, settings=settings)
    return {
        "completed": completed,
        "unfilled_closed": unfilled_closed,
        "now": str(now_dt),
    }


def handle_shift_assignment_after_save(doc):
    if not doc or not getattr(doc, "name", None):
        return
    try:
        sync_from_shift_assignment(assignment_doc=doc)
    except Exception as exc:
        frappe.log_error(str(exc), "Shift Assignment -> Site Shift Requirement sync")


def handle_employee_checkin_after_insert(doc):
    if not doc or not getattr(doc, "name", None):
        return
    try:
        apply_employee_checkin(checkin_doc=doc)
    except Exception as exc:
        frappe.log_error(str(exc), "Employee Checkin Updates Site Shift Requirement")
