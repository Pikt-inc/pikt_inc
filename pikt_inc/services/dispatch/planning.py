from __future__ import annotations

import frappe

from . import incidents, shared, staffing


def parse_days(value) -> list[str]:
    return [token.strip() for token in str(value or "").split(",") if token.strip()]


def is_eligible_date(rule, target_date, parsed_days: list[str]) -> bool:
    weekday_map = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    weekday_code = weekday_map[target_date.weekday()]
    if parsed_days and weekday_code not in parsed_days:
        return False
    if rule.effective_from and str(target_date) < str(rule.effective_from):
        return False
    if rule.effective_to and str(target_date) > str(rule.effective_to):
        return False
    return True


def acquire_rule_lock(rule_name: str):
    lock_key = f"dispatch_reconcile_rule::{rule_name}"
    try:
        rows = frappe.db.sql("SELECT GET_LOCK(%s, 0) AS acquired", (lock_key,), as_dict=True)
        acquired = bool(rows and shared.as_int(rows[0].get("acquired"), 0) == 1)
    except Exception:
        acquired = True
    return {"acquired": acquired, "lock_key": lock_key}


def release_rule_lock(lock_key: str | None):
    if not lock_key:
        return
    try:
        frappe.db.sql("SELECT RELEASE_LOCK(%s)", (lock_key,))
    except Exception:
        pass


def score_existing_requirement_row(row: dict):
    score = 0
    if row.get("checked_in_at"):
        score += 1000
    if row.get("status") == "Completed":
        score += 900
    if row.get("shift_assignment"):
        score += 120
    if row.get("current_employee"):
        score += 80
    if row.get("status") in {"Assigned", "Checked In", "Reassignment In Progress", "Likely No-show"}:
        score += 40
    return (score, str(row.get("creation") or ""))


def is_frozen_requirement_row(row: dict, now_dt) -> bool:
    start_dt = shared.to_datetime(row.get("arrival_window_start"))
    return bool(start_dt and start_dt < now_dt)


def normalize_site_shift_requirement(doc):
    non_terminal_statuses = {
        "Draft",
        "Open",
        "Assigned",
        "Called Out",
        "Likely No-show",
        "Reassignment In Progress",
        "Checked In",
    }
    terminal_completion_states = {"Completed", "Completed With Exception", "Unfilled Closed", "Cancelled"}

    if doc.call_out_record and not frappe.db.exists("Call Out", doc.call_out_record):
        doc.call_out_record = None

    if not doc.slot_index or shared.as_int(doc.slot_index, 0) <= 0:
        doc.slot_index = 1

    doc.grace_period_minutes = max(
        1,
        shared.as_int(doc.grace_period_minutes, shared.DEFAULT_GRACE_MINUTES),
    )

    if doc.recurring_service_rule and doc.service_date and doc.slot_index:
        duplicate = frappe.get_all(
            "Site Shift Requirement",
            filters={
                "name": ["!=", doc.name],
                "recurring_service_rule": doc.recurring_service_rule,
                "service_date": doc.service_date,
                "slot_index": doc.slot_index,
            },
            fields=["name"],
            limit=1,
        )
        if duplicate:
            frappe.throw(
                f"Duplicate slot exists for this rule/date/slot: {duplicate[0].get('name')}. "
                "SSR identity must be unique by (Recurring Service Rule, Service Date, Slot Index)."
            )

    if doc.status in non_terminal_statuses:
        if doc.completion_status in terminal_completion_states:
            doc.completion_status = None
        doc.completed_at = None

    if doc.status in {"Completed", "Unfilled Closed"} and not doc.completed_at:
        doc.completed_at = shared.now()

    if doc.status != "Unfilled Closed":
        doc.superseded_at = None
        doc.superseded_reason = None

    if doc.status == "Open" and not doc.current_employee and doc.auto_assignment_status in {"Auto Assigned", "Expired"}:
        doc.auto_assignment_status = "Not Evaluated"

    cutoff_anchor = doc.arrival_window_start or doc.arrival_window_end
    if cutoff_anchor:
        try:
            doc.no_show_cutoff = str(
                frappe.utils.add_to_date(
                    cutoff_anchor,
                    minutes=shared.as_int(doc.grace_period_minutes, shared.DEFAULT_GRACE_MINUTES),
                    as_datetime=True,
                )
            )
        except Exception:
            doc.no_show_cutoff = None
    else:
        doc.no_show_cutoff = None

    doc.custom_calendar_subject = shared.make_calendar_subject(
        doc.building,
        doc.shift_type,
        doc.slot_index,
        doc.current_employee,
        doc.status,
        doc.service_timezone,
    )


def supersede_requirement(requirement_row: dict, reason: str, status: str = "Unfilled Closed"):
    incidents.deactivate_assignments_for_ssr(requirement_row.get("name"))
    incidents.close_open_callouts_for_ssr(requirement_row.get("name"))
    frappe.db.set_value(
        "Site Shift Requirement",
        requirement_row.get("name"),
        {
            "status": status,
            "auto_assignment_status": "Expired",
            "completion_status": "Unfilled Closed",
            "completed_at": shared.now(),
            "current_employee": None,
            "shift_assignment": None,
            "incident_type": "Unfilled",
            "exception_reason": reason,
            "superseded_at": shared.now(),
            "superseded_reason": reason,
            "reconciled_at": shared.now(),
            "custom_calendar_subject": shared.make_calendar_subject(
                requirement_row.get("building"),
                requirement_row.get("shift_type"),
                requirement_row.get("slot_index"),
                None,
                status,
                requirement_row.get("service_timezone"),
            ),
        },
    )


def build_desired_slots(rule, trigger_source: str, settings: dict) -> dict:
    desired = {}
    if not shared.as_int(rule.active, 0):
        return desired

    building_active = frappe.db.get_value("Building", rule.building, "active")
    if building_active is not None and not shared.as_int(building_active, 1):
        return desired

    timezone_value = shared.normalize_timezone(rule.service_timezone)
    local_today = shared.get_local_today(timezone_value)
    horizon_days = max(1, shared.as_int(rule.generation_horizon_days, 1))
    grace_minutes = max(1, shared.as_int(rule.default_grace_period_minutes, settings["default_grace_minutes"]))
    parsed_days = parse_days(rule.days_of_week)
    headcount = max(1, shared.as_int(rule.required_headcount, 1))
    estimated_hours = shared.as_float(rule.estimated_hours, 0)
    snapshot_hash = shared.get_rule_snapshot_hash(rule, timezone_value, grace_minutes)

    for offset in range(horizon_days + 1):
        target_date = frappe.utils.add_days(local_today, offset)
        if not is_eligible_date(rule, target_date, parsed_days):
            continue

        start_dt = shared.to_datetime(f"{target_date} {rule.start_time}")
        if not start_dt:
            continue
        arrival_start = str(start_dt)
        arrival_end = frappe.utils.add_to_date(start_dt, hours=estimated_hours, as_string=True)
        no_show_cutoff = frappe.utils.add_to_date(arrival_start, minutes=grace_minutes, as_string=True)

        for slot in range(1, headcount + 1):
            desired[(str(target_date), slot)] = {
                "building": rule.building,
                "service_date": target_date,
                "shift_type": rule.shift_type,
                "shift_location": rule.shift_location,
                "service_timezone": timezone_value,
                "arrival_window_start": arrival_start,
                "arrival_window_end": arrival_end,
                "estimated_hours": estimated_hours,
                "required_headcount": 1,
                "slot_index": slot,
                "must_fill": shared.as_int(rule.must_fill, 0),
                "priority": rule.priority or "Medium",
                "grace_period_minutes": grace_minutes,
                "no_show_cutoff": no_show_cutoff,
                "service_notes_snapshot": rule.service_notes_template,
                "incident_type": "None",
                "generation_source": "Recurring Rule",
                "auto_assignment_status": "Not Evaluated",
                "recurring_service_rule": rule.name,
                "rule_snapshot_hash": snapshot_hash,
                "trigger_source": trigger_source,
            }
    return desired


def log_reconcile_run(*_args, **_kwargs):
    return None


def reconcile_rule(rule_name: str | None, trigger_source: str = "manual", run_assignment=True):
    started_at = shared.now()
    finished_at = started_at
    notes = ""
    created_count = 0
    updated_count = 0
    superseded_count = 0
    escalated_count = 0
    skipped_frozen_count = 0
    redispatch_count = 0
    assigned_count = 0
    error_count = 0
    skipped_locked = 0

    rule_name = shared.clean(rule_name)
    if not rule_name:
        return {
            "rule": "",
            "trigger_source": trigger_source,
            "started_at": started_at,
            "finished_at": finished_at,
            "created": 0,
            "updated": 0,
            "superseded": 0,
            "escalated": 0,
            "skipped_frozen": 0,
            "redispatch": 0,
            "assigned": 0,
            "error_count": 0,
            "skipped_locked": 0,
            "notes": "Missing rule_name.",
        }

    lock = acquire_rule_lock(rule_name)
    if not lock["acquired"]:
        return {
            "rule": rule_name,
            "trigger_source": trigger_source,
            "started_at": started_at,
            "finished_at": shared.now(),
            "created": 0,
            "updated": 0,
            "superseded": 0,
            "escalated": 0,
            "skipped_frozen": 0,
            "redispatch": 0,
            "assigned": 0,
            "error_count": 0,
            "skipped_locked": 1,
            "notes": "Skipped because another reconcile holds the lock.",
        }

    try:
        settings = shared.get_dispatch_settings()
        run_assignment = bool(run_assignment)
        now_dt = shared.now_datetime()
        rule = frappe.get_doc("Recurring Service Rule", rule_name)
        local_today = shared.get_local_today(shared.normalize_timezone(rule.service_timezone))

        desired = build_desired_slots(rule, trigger_source, settings)
        existing_rows = frappe.get_all(
            "Site Shift Requirement",
            filters={
                "recurring_service_rule": rule.name,
                "service_date": [">=", local_today],
            },
            fields=[
                "name",
                "creation",
                "building",
                "service_date",
                "shift_type",
                "shift_location",
                "service_timezone",
                "arrival_window_start",
                "arrival_window_end",
                "estimated_hours",
                "required_headcount",
                "slot_index",
                "must_fill",
                "priority",
                "status",
                "current_employee",
                "shift_assignment",
                "checked_in_at",
                "grace_period_minutes",
                "no_show_cutoff",
                "service_notes_snapshot",
                "call_out_record",
                "incident_type",
                "auto_assignment_status",
                "completion_status",
                "completed_at",
                "superseded_at",
                "superseded_reason",
                "rule_snapshot_hash",
            ],
            limit=5000,
            order_by="service_date asc, slot_index asc, creation asc",
        )

        grouped = {}
        for row in existing_rows:
            key = (str(row.get("service_date")), shared.as_int(row.get("slot_index"), 1))
            grouped.setdefault(key, []).append(row)

        canonical_by_key = {}
        for key, rows in grouped.items():
            ordered = sorted(rows, key=score_existing_requirement_row, reverse=True)
            canonical_by_key[key] = ordered[0]
            for duplicate in ordered[1:]:
                if is_frozen_requirement_row(duplicate, now_dt):
                    skipped_frozen_count += 1
                    continue
                try:
                    supersede_requirement(
                        duplicate,
                        "Superseded by rule reconciliation: duplicate slot key resolved",
                    )
                    superseded_count += 1
                except Exception as exc:
                    escalated_count += 1
                    error_count += 1
                    incidents.create_or_update_escalation(
                        duplicate.get("name"),
                        duplicate.get("building"),
                        "Reconcile Conflict",
                        f"Duplicate SSR key reconciliation failed for {duplicate.get('name')}.",
                        settings,
                        str(exc),
                    )

        for key, payload in desired.items():
            existing = canonical_by_key.get(key)
            if not existing:
                try:
                    ssr = frappe.get_doc(
                        {
                            "doctype": "Site Shift Requirement",
                            "building": payload["building"],
                            "service_date": payload["service_date"],
                            "shift_type": payload["shift_type"],
                            "shift_location": payload["shift_location"],
                            "service_timezone": payload["service_timezone"],
                            "arrival_window_start": payload["arrival_window_start"],
                            "arrival_window_end": payload["arrival_window_end"],
                            "estimated_hours": payload["estimated_hours"],
                            "required_headcount": payload["required_headcount"],
                            "slot_index": payload["slot_index"],
                            "must_fill": payload["must_fill"],
                            "priority": payload["priority"],
                            "status": "Open",
                            "grace_period_minutes": payload["grace_period_minutes"],
                            "no_show_cutoff": payload["no_show_cutoff"],
                            "service_notes_snapshot": payload["service_notes_snapshot"],
                            "incident_type": "None",
                            "generation_source": "Recurring Rule",
                            "auto_assignment_status": "Not Evaluated",
                            "completion_status": None,
                            "completed_at": None,
                            "exception_reason": None,
                            "custom_calendar_subject": shared.make_calendar_subject(
                                payload["building"],
                                payload["shift_type"],
                                payload["slot_index"],
                                None,
                                "Open",
                                payload["service_timezone"],
                            ),
                            "recurring_service_rule": payload["recurring_service_rule"],
                            "reconciled_at": shared.now(),
                            "rule_snapshot_hash": payload["rule_snapshot_hash"],
                            "superseded_at": None,
                            "superseded_reason": None,
                        }
                    )
                    ssr.insert(ignore_permissions=True)
                    created_count += 1
                except Exception as exc:
                    escalated_count += 1
                    error_count += 1
                    frappe.log_error(str(exc), f"Dispatch reconcile create failure {rule.name} {key}")
                continue

            if is_frozen_requirement_row(existing, now_dt):
                skipped_frozen_count += 1
                continue

            update_map = {}
            material_change = False
            material_fields = {
                "building",
                "shift_type",
                "shift_location",
                "service_timezone",
                "arrival_window_start",
                "arrival_window_end",
                "estimated_hours",
                "grace_period_minutes",
                "no_show_cutoff",
            }
            compare_fields = [
                "building",
                "shift_type",
                "shift_location",
                "service_timezone",
                "arrival_window_start",
                "arrival_window_end",
                "estimated_hours",
                "required_headcount",
                "slot_index",
                "must_fill",
                "priority",
                "grace_period_minutes",
                "no_show_cutoff",
                "service_notes_snapshot",
            ]

            for fieldname in compare_fields:
                old_value = existing.get(fieldname)
                new_value = payload.get(fieldname)
                if str(old_value or "") != str(new_value or ""):
                    update_map[fieldname] = new_value
                    if fieldname in material_fields:
                        material_change = True

            if (
                existing.get("status") == "Unfilled Closed"
                and shared.clean(existing.get("superseded_reason")).startswith("Superseded by rule reconciliation")
            ):
                update_map.update(
                    {
                        "status": "Open",
                        "completion_status": None,
                        "completed_at": None,
                        "incident_type": "None",
                        "current_employee": None,
                        "shift_assignment": None,
                        "exception_reason": None,
                        "auto_assignment_status": "Not Evaluated",
                    }
                )

            status_for_subject = update_map.get("status", existing.get("status") or "Open")
            employee_for_subject = update_map.get("current_employee", existing.get("current_employee"))
            update_map["custom_calendar_subject"] = shared.make_calendar_subject(
                payload["building"],
                payload["shift_type"],
                payload["slot_index"],
                employee_for_subject,
                status_for_subject,
                payload["service_timezone"],
            )
            update_map["reconciled_at"] = shared.now()
            update_map["rule_snapshot_hash"] = payload["rule_snapshot_hash"]
            update_map["superseded_at"] = None
            update_map["superseded_reason"] = None

            if update_map:
                frappe.db.set_value("Site Shift Requirement", existing.get("name"), update_map)
                updated_count += 1

            if material_change and (existing.get("current_employee") or existing.get("shift_assignment")):
                try:
                    fresh = frappe.get_doc("Site Shift Requirement", existing.get("name"))
                    if incidents.ensure_redispatch_callout(fresh, trigger_source):
                        redispatch_count += 1
                except Exception as exc:
                    escalated_count += 1
                    error_count += 1
                    incidents.create_or_update_escalation(
                        existing.get("name"),
                        payload["building"],
                        "Reconcile Conflict",
                        f"Assigned future slot changed but redispatch trigger failed for {existing.get('name')}.",
                        settings,
                        str(exc),
                    )

        for key, existing in canonical_by_key.items():
            if key in desired:
                continue
            if is_frozen_requirement_row(existing, now_dt):
                skipped_frozen_count += 1
                continue

            if (
                existing.get("status") == "Unfilled Closed"
                and shared.clean(existing.get("superseded_reason")).startswith("Superseded by rule reconciliation")
                and not existing.get("current_employee")
                and not existing.get("shift_assignment")
            ):
                continue

            try:
                supersede_requirement(
                    existing,
                    "Superseded by rule reconciliation: slot no longer implied by recurring rule",
                )
                superseded_count += 1
            except Exception as exc:
                escalated_count += 1
                error_count += 1
                incidents.create_or_update_escalation(
                    existing.get("name"),
                    existing.get("building"),
                    "Reconcile Conflict",
                    f"Failed to supersede no-longer-valid slot {existing.get('name')}.",
                    settings,
                    str(exc),
                )

        if run_assignment:
            assign_rows = frappe.get_all(
                "Site Shift Requirement",
                filters={
                    "recurring_service_rule": rule.name,
                    "service_date": [">=", local_today],
                    "status": "Open",
                    "auto_assignment_status": ["in", ["Not Evaluated", "Suggested", "Escalated"]],
                    "checked_in_at": ["is", "not set"],
                },
                fields=["name"],
                limit=2000,
            )
            for row in assign_rows:
                result = staffing.auto_assign_requirement(row.get("name"), settings=settings)
                if result == "assigned":
                    assigned_count += 1
                elif result in {"error", "escalated"}:
                    error_count += 1
    except Exception as exc:
        error_count += 1
        escalated_count += 1
        notes = str(exc)
        frappe.log_error(str(exc), f"Dispatch reconcile fatal {rule_name}")
    finally:
        release_rule_lock(lock["lock_key"])
        finished_at = shared.now()

    log_reconcile_run(
        rule_name,
        trigger_source,
        started_at,
        finished_at,
        created_count,
        updated_count,
        superseded_count,
        escalated_count,
        skipped_frozen_count,
        redispatch_count,
        error_count,
        notes,
    )
    return {
        "rule": rule_name,
        "trigger_source": trigger_source,
        "started_at": started_at,
        "finished_at": finished_at,
        "created": created_count,
        "updated": updated_count,
        "superseded": superseded_count,
        "escalated": escalated_count,
        "skipped_frozen": skipped_frozen_count,
        "redispatch": redispatch_count,
        "assigned": assigned_count,
        "error_count": error_count,
        "skipped_locked": skipped_locked,
        "notes": notes,
    }


def sync_paused_buildings():
    now_dt = shared.now_datetime()
    today = shared.today()
    buildings = frappe.get_all("Building", filters={"active": 0}, fields=["name"], limit=5000)

    processed = 0
    for building in buildings:
        rows = frappe.get_all(
            "Site Shift Requirement",
            filters={
                "building": building.get("name"),
                "service_date": [">=", today],
                "status": ["!=", "Unfilled Closed"],
            },
            fields=[
                "name",
                "building",
                "shift_type",
                "slot_index",
                "service_timezone",
                "arrival_window_start",
            ],
            limit=5000,
        )

        for row in rows:
            start_dt = shared.to_datetime(row.get("arrival_window_start"))
            if start_dt and start_dt < now_dt:
                continue

            supersede_requirement(row, "Superseded by building pause: building marked inactive")
            processed += 1

    return {"status": "ok", "processed": processed}


def handle_recurring_service_rule_after_save(doc):
    if not doc or not doc.name:
        return
    try:
        reconcile_rule(doc.name, trigger_source="after_save", run_assignment=True)
        sync_paused_buildings()
    except Exception as exc:
        frappe.log_error(str(exc), "Recurring Service Rule Immediate Generate")


def handle_building_after_save(doc):
    if not doc or not doc.name:
        return
    try:
        active_flag = shared.as_int(doc.active, 0)
        if active_flag == 0:
            sync_paused_buildings()
            return

        rules = frappe.get_all(
            "Recurring Service Rule",
            filters={"building": doc.name, "active": 1},
            fields=["name"],
            limit=500,
        )
        for rule in rules:
            try:
                reconcile_rule(rule.get("name"), trigger_source="building_reactivated", run_assignment=True)
            except Exception as exc:
                frappe.log_error(str(exc), f"Building reactivation reconcile {rule.get('name')}")
        sync_paused_buildings()
    except Exception as exc:
        frappe.log_error(str(exc), "Building Pause Sync Site Shift Requirements")
