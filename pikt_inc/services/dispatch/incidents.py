from __future__ import annotations

import frappe

from . import shared


def deactivate_assignments_for_ssr(ssr_name: str):
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


def expire_previous_recommendations(ssr_name: str):
    rows = frappe.get_all(
        "Dispatch Recommendation",
        filters={
            "site_shift_requirement": ssr_name,
            "recommendation_type": "Initial Assignment",
            "decision_status": ["in", ["Suggested", "Approved", "Auto Assigned", "Escalated"]],
        },
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
