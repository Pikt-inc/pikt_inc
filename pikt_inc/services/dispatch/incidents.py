from __future__ import annotations

import frappe

from . import shared


def deactivate_assignments_for_ssr(ssr_name: str, keep_name: str | None = None):
    rows = frappe.get_all(
        "Shift Assignment",
        filters={
            "custom_site_shift_requirement": ssr_name,
            "status": "Active",
            "docstatus": ["<", 2],
        },
        fields=["name"],
        limit=5000,
    )
    for row in rows:
        if keep_name and shared.clean(row.get("name")) == shared.clean(keep_name):
            continue
        frappe.db.set_value("Shift Assignment", row.get("name"), "status", "Inactive")


def close_open_callouts_for_ssr(ssr_name: str):
    rows = frappe.get_all(
        "Call Out",
        filters={
            "site_shift_requirement": ssr_name,
            "replacement_status": ["in", ["Recorded", "Replacement Pending"]],
        },
        fields=["name"],
        limit=5000,
    )
    for row in rows:
        frappe.db.set_value("Call Out", row.get("name"), "replacement_status", "Closed")


def close_callout_if_open(call_out_name: str) -> bool:
    call_out_name = shared.clean(call_out_name)
    if not call_out_name or not frappe.db.exists("Call Out", call_out_name):
        return False

    replacement_status = shared.clean(frappe.db.get_value("Call Out", call_out_name, "replacement_status"))
    if replacement_status not in {"Recorded", "Replacement Pending"}:
        return False

    frappe.db.set_value("Call Out", call_out_name, "replacement_status", "Closed")
    return True


def expire_previous_recommendations(
    ssr_name: str,
    recommendation_types: list[str] | tuple[str, ...] | None = ("Initial Assignment",),
    exclude_name: str | None = None,
):
    filters = {
        "site_shift_requirement": ssr_name,
        "decision_status": ["in", ["Suggested", "Approved", "Auto Assigned", "Escalated"]],
    }
    if recommendation_types:
        filters["recommendation_type"] = ["in", list(recommendation_types)]
    if exclude_name:
        filters["name"] = ["!=", exclude_name]

    rows = frappe.get_all(
        "Dispatch Recommendation",
        filters=filters,
        fields=["name", "decision_status"],
        limit=5000,
    )
    for row in rows:
        if row.get("decision_status") != "Rejected":
            frappe.db.set_value("Dispatch Recommendation", row.get("name"), "decision_status", "Expired")


def create_or_update_escalation(ssr_name: str, building_name: str, reason: str, message: str, settings: dict, root_cause=None):
    open_rows = frappe.get_all(
        "Dispatch Escalation",
        filters={
            "site_shift_requirement": ssr_name,
            "status": ["in", ["Open", "Acknowledged"]],
        },
        fields=["name"],
        limit=1,
    )

    building_row = shared.get_building_fields(building_name, ["supervisor_user"]) or {}
    supervisor_user = shared.clean(building_row.get("supervisor_user"))
    escalation_role = shared.clean(settings.get("escalation_role")) or shared.DEFAULT_ESCALATION_ROLE

    values = {
        "escalation_reason": reason,
        "severity": "High",
        "notes": message,
        "root_cause": root_cause,
        "assigned_role": escalation_role,
        "supervisor_user": supervisor_user or None,
        "notified_at": shared.now(),
    }

    if open_rows:
        escalation_name = open_rows[0].get("name")
        frappe.db.set_value("Dispatch Escalation", escalation_name, values)
    else:
        escalation = frappe.get_doc(
            {
                "doctype": "Dispatch Escalation",
                "site_shift_requirement": ssr_name,
                "status": "Open",
                **values,
            }
        )
        escalation.insert(ignore_permissions=True)
        escalation_name = escalation.name

    recipients = set(shared.get_role_users(escalation_role))
    if supervisor_user and "@" in supervisor_user:
        recipients.add(supervisor_user)

    if recipients:
        try:
            frappe.sendmail(
                recipients=sorted(recipients),
                subject=f"Dispatch Escalation: {ssr_name}",
                message=message,
                reference_doctype="Dispatch Escalation",
                reference_name=escalation_name,
                sender=settings.get("sender_email") or shared.DEFAULT_SENDER_EMAIL,
                now=True,
            )
        except Exception as exc:
            frappe.log_error(str(exc), "Dispatch escalation email")

    return escalation_name


def has_open_callout_for_ssr(ssr_name: str) -> bool:
    rows = frappe.get_all(
        "Call Out",
        filters={
            "site_shift_requirement": ssr_name,
            "replacement_status": ["in", ["Recorded", "Replacement Pending"]],
        },
        fields=["name"],
        limit=1,
    )
    return bool(rows)


def has_open_escalation_for_ssr(ssr_name: str) -> bool:
    rows = frappe.get_all(
        "Dispatch Escalation",
        filters={
            "site_shift_requirement": ssr_name,
            "status": ["in", ["Open", "Acknowledged"]],
        },
        fields=["name"],
        limit=1,
    )
    return bool(rows)


def resolve_open_escalations(ssr_name: str) -> int:
    rows = frappe.get_all(
        "Dispatch Escalation",
        filters={
            "site_shift_requirement": ssr_name,
            "status": ["in", ["Open", "Acknowledged"]],
        },
        fields=["name"],
        limit=5000,
    )
    for row in rows:
        frappe.db.set_value(
            "Dispatch Escalation",
            row.get("name"),
            {
                "status": "Resolved",
                "resolved_at": shared.now(),
            },
        )
    return len(rows)


def sync_from_call_out(call_out_name: str | None = None, call_out_doc=None):
    call_out_name = shared.clean(call_out_name) or shared.clean(getattr(call_out_doc, "name", None))
    if not call_out_doc and not call_out_name:
        return {"status": "skipped", "reason": "missing_call_out"}

    call_out_doc = call_out_doc or frappe.get_doc("Call Out", call_out_name)
    requirement_name = shared.clean(getattr(call_out_doc, "site_shift_requirement", None))
    if not requirement_name:
        return {"status": "skipped", "reason": "missing_requirement", "call_out": call_out_doc.name}
    if not frappe.db.exists("Site Shift Requirement", requirement_name):
        return {
            "status": "skipped",
            "reason": "requirement_not_found",
            "call_out": call_out_doc.name,
            "site_shift_requirement": requirement_name,
        }

    ssr = frappe.get_doc("Site Shift Requirement", requirement_name)
    ssr.call_out_record = call_out_doc.name
    ssr.status = "Called Out"
    ssr.incident_type = "No-show" if shared.clean(getattr(call_out_doc, "incident_origin", None)) == "System No-show" else "Call-out"
    if not shared.clean(ssr.get("building")) and shared.clean(getattr(call_out_doc, "building", None)):
        ssr.building = call_out_doc.building
    ssr.completed_at = None
    if shared.clean(ssr.get("completion_status")) in {"Completed", "Completed With Exception", "Unfilled Closed"}:
        ssr.completion_status = None
    ssr.flags.ignore_permissions = True
    ssr.save(ignore_permissions=True)
    return {"status": "updated", "call_out": call_out_doc.name, "site_shift_requirement": requirement_name}


def generate_recommendations(call_out_name: str | None = None, call_out_doc=None):
    call_out_name = shared.clean(call_out_name) or shared.clean(getattr(call_out_doc, "name", None))
    if not call_out_doc and not call_out_name:
        return {"status": "skipped", "reason": "missing_call_out"}

    call_out_doc = call_out_doc or frappe.get_doc("Call Out", call_out_name)
    requirement_name = shared.clean(getattr(call_out_doc, "site_shift_requirement", None))
    call_out_date = getattr(call_out_doc, "call_out_date", None)
    if not requirement_name or not call_out_date:
        return {"status": "skipped", "reason": "missing_requirement_or_date", "call_out": call_out_doc.name}

    replacement_status = shared.clean(getattr(call_out_doc, "replacement_status", None) or "Recorded")
    if replacement_status not in {"Recorded", "Replacement Pending"}:
        return {"status": "skipped", "reason": "replacement_not_pending", "call_out": call_out_doc.name}

    if not frappe.db.exists("Site Shift Requirement", requirement_name):
        return {
            "status": "skipped",
            "reason": "requirement_not_found",
            "call_out": call_out_doc.name,
            "site_shift_requirement": requirement_name,
        }

    from . import staffing

    settings = shared.get_dispatch_settings()
    ssr = frappe.get_doc("Site Shift Requirement", requirement_name)
    recommendation_type = "No-show Recovery" if shared.clean(getattr(call_out_doc, "incident_origin", None)) == "System No-show" else "Redispatch"
    incident_type = "No-show" if recommendation_type == "No-show Recovery" else "Call-out"

    frappe.db.set_value(
        "Site Shift Requirement",
        ssr.name,
        {
            "call_out_record": call_out_doc.name,
            "status": "Reassignment In Progress",
            "incident_type": incident_type,
        },
    )

    expire_previous_recommendations(ssr.name, recommendation_types=None)
    candidates = staffing.build_candidates(
        ssr,
        settings,
        excluded_employees={shared.clean(getattr(call_out_doc, "employee", None))},
    )

    if not candidates:
        message = f"No valid replacement candidate found for requirement {ssr.name} on {ssr.service_date}."
        create_or_update_escalation(
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
                "status": "Reassignment In Progress",
                "auto_assignment_status": "Escalated",
                "exception_reason": message,
            },
        )
        frappe.db.set_value("Call Out", call_out_doc.name, "replacement_status", "Replacement Pending")
        return {"status": "escalated", "site_shift_requirement": ssr.name, "call_out": call_out_doc.name}

    top_candidate = candidates[0]
    try:
        if ssr.shift_assignment and frappe.db.exists("Shift Assignment", ssr.shift_assignment):
            deactivate_assignments_for_ssr(ssr.name)

        shift_assignment = staffing.ensure_active_shift_assignment_for_requirement(ssr, top_candidate["employee"])
        deactivate_assignments_for_ssr(ssr.name, keep_name=shift_assignment.name)
        staffing.create_recommendation_batch(
            ssr,
            candidates,
            recommendation_type=recommendation_type,
            decision_notes="Auto-generated by the dispatch service layer.",
            top_decision_status="Auto Assigned",
        )
        staffing.sync_from_shift_assignment(assignment_doc=shift_assignment)
        frappe.db.set_value(
            "Site Shift Requirement",
            ssr.name,
            {
                "status": "Assigned",
                "current_employee": top_candidate["employee"],
                "shift_assignment": shift_assignment.name,
                "auto_assignment_status": "Auto Assigned",
                "exception_reason": None,
            },
        )
        frappe.db.set_value("Call Out", call_out_doc.name, "replacement_status", "Replaced")
        resolve_open_escalations(ssr.name)
        return {
            "status": "assigned",
            "call_out": call_out_doc.name,
            "site_shift_requirement": ssr.name,
            "shift_assignment": shift_assignment.name,
        }
    except Exception as exc:
        message = f"Validation error while redispatching requirement {ssr.name}."
        create_or_update_escalation(
            ssr.name,
            ssr.building,
            "Validation Error",
            message,
            settings,
            str(exc),
        )
        frappe.db.set_value(
            "Site Shift Requirement",
            ssr.name,
            {
                "status": "Reassignment In Progress",
                "auto_assignment_status": "Escalated",
                "exception_reason": message,
            },
        )
        frappe.db.set_value("Call Out", call_out_doc.name, "replacement_status", "Replacement Pending")
        frappe.log_error(str(exc), "Generate Recommendations On Call Out")
        return {"status": "error", "call_out": call_out_doc.name, "site_shift_requirement": ssr.name}


def approve_reassignment(recommendation_name: str | None = None, recommendation_doc=None):
    recommendation_name = shared.clean(recommendation_name) or shared.clean(getattr(recommendation_doc, "name", None))
    if not recommendation_doc and not recommendation_name:
        return {"status": "skipped", "reason": "missing_recommendation"}

    recommendation_doc = recommendation_doc or frappe.get_doc("Dispatch Recommendation", recommendation_name)
    if shared.clean(getattr(recommendation_doc, "decision_status", None)) != "Approved":
        return {"status": "skipped", "reason": "decision_not_approved", "recommendation": recommendation_doc.name}

    requirement_name = shared.clean(getattr(recommendation_doc, "site_shift_requirement", None))
    if not requirement_name:
        return {"status": "skipped", "reason": "missing_requirement", "recommendation": recommendation_doc.name}

    if not frappe.db.exists("Site Shift Requirement", requirement_name):
        return {
            "status": "skipped",
            "reason": "requirement_not_found",
            "recommendation": recommendation_doc.name,
            "site_shift_requirement": requirement_name,
        }

    ssr = frappe.get_doc("Site Shift Requirement", requirement_name)
    if shared.clean(ssr.get("auto_assignment_status")) != "Escalated":
        return {"status": "skipped", "reason": "requirement_not_escalated", "recommendation": recommendation_doc.name}

    candidate_employee = shared.clean(getattr(recommendation_doc, "candidate_employee", None))
    if not candidate_employee:
        frappe.throw("Candidate employee is required for approval")

    from . import staffing

    settings = shared.get_dispatch_settings()
    expire_previous_recommendations(ssr.name, recommendation_types=None, exclude_name=recommendation_doc.name)
    try:
        if staffing.has_assignment_conflict(
            candidate_employee,
            ssr.service_date,
            shared.to_datetime(ssr.get("arrival_window_start")),
            shared.to_datetime(ssr.get("arrival_window_end")),
            target_shift_type=ssr.get("shift_type"),
            ignore_requirement=ssr.name,
        ):
            validation_error = getattr(frappe, "ValidationError", Exception)
            raise validation_error(
                f"Candidate {candidate_employee} has a conflicting active shift assignment."
            )

        shift_assignment = staffing.ensure_active_shift_assignment_for_requirement(ssr, candidate_employee)
        deactivate_assignments_for_ssr(ssr.name, keep_name=shift_assignment.name)
        staffing.sync_from_shift_assignment(assignment_doc=shift_assignment)
        frappe.db.set_value(
            "Site Shift Requirement",
            ssr.name,
            {
                "status": "Assigned",
                "current_employee": candidate_employee,
                "shift_assignment": shift_assignment.name,
                "auto_assignment_status": "Auto Assigned",
                "exception_reason": None,
            },
        )
        if ssr.call_out_record and frappe.db.exists("Call Out", ssr.call_out_record):
            frappe.db.set_value("Call Out", ssr.call_out_record, "replacement_status", "Replaced")
        resolve_open_escalations(ssr.name)
        return {
            "status": "assigned",
            "recommendation": recommendation_doc.name,
            "site_shift_requirement": ssr.name,
            "shift_assignment": shift_assignment.name,
        }
    except Exception as exc:
        message = f"Approved recommendation {recommendation_doc.name} is no longer valid for requirement {ssr.name}."
        create_or_update_escalation(
            ssr.name,
            ssr.building,
            "Validation Error",
            message,
            settings,
            str(exc),
        )
        frappe.db.set_value(
            "Site Shift Requirement",
            ssr.name,
            {
                "status": "Reassignment In Progress",
                "auto_assignment_status": "Escalated",
                "exception_reason": message,
            },
        )
        frappe.db.set_value(
            "Dispatch Recommendation",
            recommendation_doc.name,
            {
                "decision_status": "Escalated",
                "decision_notes": str(exc),
            },
        )
        if ssr.call_out_record and frappe.db.exists("Call Out", ssr.call_out_record):
            frappe.db.set_value("Call Out", ssr.call_out_record, "replacement_status", "Replacement Pending")
        frappe.log_error(
            title="Approve Recommendation And Reassign",
            message=f"Recommendation {recommendation_doc.name}: {str(exc)}",
        )
        return {
            "status": "error",
            "recommendation": recommendation_doc.name,
            "site_shift_requirement": ssr.name,
        }


def monitor_no_shows(now_value=None):
    current_timestamp = str(now_value or shared.now())
    current_dt = shared.to_datetime(current_timestamp) or shared.now_datetime()
    today = str(current_dt.date())
    processed = 0

    requirements = frappe.get_all(
        "Site Shift Requirement",
        filters={
            "service_date": ["<=", today],
            "status": "Assigned",
            "checked_in_at": ["is", "not set"],
            "current_employee": ["is", "set"],
        },
        fields=[
            "name",
            "current_employee",
            "call_out_record",
            "service_date",
            "building",
            "arrival_window_start",
            "arrival_window_end",
            "grace_period_minutes",
            "no_show_cutoff",
        ],
        limit=5000,
    )

    for row in requirements:
        anchor_value = row.get("arrival_window_start") or row.get("arrival_window_end")
        anchor_dt = shared.to_datetime(anchor_value)
        if not anchor_dt:
            continue

        grace_minutes = max(1, shared.as_int(row.get("grace_period_minutes"), 15))
        cutoff_dt = shared.to_datetime(row.get("no_show_cutoff"))
        if not cutoff_dt or cutoff_dt <= anchor_dt:
            cutoff_value = frappe.utils.add_to_date(anchor_value, minutes=grace_minutes, as_string=True)
            cutoff_dt = shared.to_datetime(cutoff_value)
            if cutoff_dt:
                frappe.db.set_value("Site Shift Requirement", row.get("name"), "no_show_cutoff", str(cutoff_dt))
        if not cutoff_dt or cutoff_dt > current_dt:
            continue

        ssr = frappe.get_doc("Site Shift Requirement", row.get("name"))
        if shared.clean(ssr.status) != "Assigned" or ssr.checked_in_at or not shared.clean(ssr.current_employee):
            continue

        ssr.status = "Likely No-show"
        ssr.incident_type = "No-show"
        ssr.flags.ignore_permissions = True
        ssr.save(ignore_permissions=True)

        existing_callout = frappe.get_all(
            "Call Out",
            filters={
                "site_shift_requirement": row.get("name"),
                "call_out_date": row.get("service_date"),
            },
            fields=["name"],
            limit=1,
        )

        if existing_callout:
            call_out_doc = frappe.get_doc("Call Out", existing_callout[0].get("name"))
            call_out_doc.incident_origin = "System No-show"
            call_out_doc.replacement_status = "Replacement Pending"
            if not getattr(call_out_doc, "reported_at", None):
                call_out_doc.reported_at = current_timestamp
            if not shared.clean(getattr(call_out_doc, "building", None)) and row.get("building"):
                call_out_doc.building = row.get("building")
            if not shared.clean(getattr(call_out_doc, "employee", None)) and row.get("current_employee"):
                call_out_doc.employee = row.get("current_employee")
            call_out_doc.notes = "System-generated likely no-show event after no valid check-in by cutoff."
            call_out_doc.flags.ignore_permissions = True
            call_out_doc.save(ignore_permissions=True)
        else:
            call_out_doc = frappe.get_doc(
                {
                    "doctype": "Call Out",
                    "employee": row.get("current_employee"),
                    "call_out_date": row.get("service_date"),
                    "reported_at": current_timestamp,
                    "building": row.get("building"),
                    "site_shift_requirement": row.get("name"),
                    "reason_category": "Unknown",
                    "replacement_status": "Replacement Pending",
                    "incident_origin": "System No-show",
                    "notes": "System-generated likely no-show event after no valid check-in by cutoff.",
                }
            )
            call_out_doc.insert(ignore_permissions=True)
        processed += 1

    return {"processed": processed, "now": current_timestamp}


def handle_call_out_after_save(doc):
    if not doc or not getattr(doc, "name", None):
        return
    try:
        sync_from_call_out(call_out_doc=doc)
        generate_recommendations(call_out_doc=doc)
    except Exception as exc:
        frappe.log_error(str(exc), "Call Out -> Site Shift Requirement sync")


def handle_dispatch_recommendation_after_save(doc):
    if not doc or not getattr(doc, "name", None):
        return
    try:
        approve_reassignment(recommendation_doc=doc)
    except Exception as exc:
        frappe.log_error(
            title="Approve Recommendation And Reassign",
            message=f"Recommendation {getattr(doc, 'name', '')}: {str(exc)}",
        )


def ensure_redispatch_callout(ssr_doc, trigger_source: str):
    if not ssr_doc or not ssr_doc.get("name"):
        return False

    existing = frappe.get_all(
        "Call Out",
        filters={
            "site_shift_requirement": ssr_doc.name,
            "replacement_status": ["in", ["Recorded", "Replacement Pending"]],
        },
        fields=["name"],
        limit=1,
    )

    notes = (
        "Future assigned requirement changed during reconciliation and needs redispatch. "
        f"trigger_source={shared.clean(trigger_source) or 'system'}"
    )

    if existing:
        call_out_name = existing[0].get("name")
        frappe.db.set_value(
            "Call Out",
            call_out_name,
            {
                "employee": ssr_doc.get("current_employee"),
                "building": ssr_doc.get("building"),
                "shift_assignment": ssr_doc.get("shift_assignment"),
                "replacement_status": "Replacement Pending",
                "incident_origin": "Supervisor Entered",
                "notes": notes,
            },
        )
    else:
        call_out = frappe.get_doc(
            {
                "doctype": "Call Out",
                "employee": ssr_doc.get("current_employee"),
                "call_out_date": ssr_doc.get("service_date"),
                "reported_at": shared.now(),
                "building": ssr_doc.get("building"),
                "site_shift_requirement": ssr_doc.name,
                "shift_assignment": ssr_doc.get("shift_assignment"),
                "reason_category": "Other",
                "replacement_status": "Replacement Pending",
                "notes": notes,
                "incident_origin": "Supervisor Entered",
            }
        )
        call_out.insert(ignore_permissions=True)
        call_out_name = call_out.name

    frappe.db.set_value(
        "Site Shift Requirement",
        ssr_doc.name,
        {
            "status": "Reassignment In Progress",
            "call_out_record": call_out_name,
            "incident_type": "Call-out",
            "auto_assignment_status": "Escalated",
            "exception_reason": notes,
            "reconciled_at": shared.now(),
        },
    )
    return True
