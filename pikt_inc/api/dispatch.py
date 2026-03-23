from __future__ import annotations

import frappe

from pikt_inc.services.dispatch import planning, routing, shared


@frappe.whitelist()
def dispatch_reconcile_routes(site_shift_requirement=None, trigger_source="manual", **kwargs):
    return routing.reconcile_routes(
        site_shift_requirement=site_shift_requirement or kwargs.get("site_shift_requirement"),
        trigger_source=trigger_source or kwargs.get("trigger_source") or "manual",
    )


@frappe.whitelist()
def dispatch_reconcile_rule(rule=None, trigger_source="manual", run_assignment=1, **kwargs):
    rule_name = rule or kwargs.get("rule") or kwargs.get("rule_name")
    run_assignment_value = run_assignment if run_assignment is not None else kwargs.get("run_assignment", 1)
    return planning.reconcile_rule(
        rule_name=rule_name,
        trigger_source=trigger_source or kwargs.get("trigger_source") or "manual",
        run_assignment=shared.is_truthy(run_assignment_value),
    )


@frappe.whitelist()
def dispatch_sync_paused_buildings(**_kwargs):
    return planning.sync_paused_buildings()
