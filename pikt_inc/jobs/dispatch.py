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
