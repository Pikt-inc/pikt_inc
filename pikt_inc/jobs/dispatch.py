from __future__ import annotations

import frappe

from pikt_inc.services.dispatch import incidents, planning, routing, shared, staffing


def nightly_dispatch_orchestrator():
    results = []
    rules = frappe.get_all(
        "Recurring Service Rule",
        filters={"active": 1},
        fields=["name"],
        order_by="modified asc",
        limit=5000,
    )

    for rule in rules:
        try:
            results.append(
                planning.reconcile_rule(
                    rule_name=rule.get("name"),
                    trigger_source="daily",
                    run_assignment=True,
                )
            )
        except Exception as exc:
            frappe.log_error(str(exc), f"Nightly Dispatch Orchestrator rule {rule.get('name')}")

    try:
        planning.sync_paused_buildings()
    except Exception as exc:
        frappe.log_error(str(exc), "Nightly Dispatch Orchestrator paused buildings")

    try:
        if frappe.db.exists("DocType", "Dispatch Automation Settings"):
            frappe.db.set_single_value(
                "Dispatch Automation Settings",
                "last_orchestrator_run_on",
                shared.now(),
            )
    except Exception:
        pass

    return {"rules": len(rules), "results": results}


def should_run_dispatch_orchestrator(now_value=None):
    try:
        settings = frappe.get_doc("Dispatch Automation Settings", "Dispatch Automation Settings")
    except Exception:
        return False

    now_dt = shared.to_datetime(now_value) or shared.now_datetime()
    if not now_dt:
        return False

    today = str(now_dt.date())
    last_run = getattr(settings, "last_orchestrator_run_on", None)
    if last_run:
        try:
            last_run_date = str(frappe.utils.getdate(last_run))
        except Exception:
            last_run_date = str(last_run)[:10]
        if last_run_date == today:
            return False

    hour = 6
    minute = 15
    raw = shared.clean(getattr(settings, "orchestrator_hour", None)) or "06:15"
    try:
        parts = raw.split(":")
        if len(parts) >= 2:
            hour = int(parts[0])
            minute = int(parts[1])
    except Exception:
        hour = 6
        minute = 15

    scheduled_dt = shared.to_datetime(f"{today} {hour:02d}:{minute:02d}:00")
    return bool(scheduled_dt and now_dt >= scheduled_dt)


def dispatch_orchestrator_hour_gate(now_value=None):
    current_now = now_value or shared.now()
    if not should_run_dispatch_orchestrator(now_value=current_now):
        return {"status": "skipped", "now": current_now}
    try:
        return {"status": "ran", "now": current_now, "result": nightly_dispatch_orchestrator()}
    except Exception as exc:
        frappe.log_error(str(exc), "Dispatch Orchestrator Hour Gate")
        return {"status": "error", "now": current_now, "error": str(exc)}


def dispatch_route_email_orchestrator():
    reconcile_result = routing.reconcile_routes(trigger_source="route_email_scheduler")
    email_result = routing.send_due_route_emails(now_value=shared.now())
    return {
        "reconcile": reconcile_result,
        "email": email_result,
    }


def monitor_no_show_site_shift_requirements():
    return incidents.monitor_no_shows(now_value=shared.now())


def dispatch_completion_finalizer():
    return staffing.finalize_dispatch_completion(now_value=shared.now())


def dispatch_calendar_subject_sync():
    return planning.sync_calendar_subjects()
