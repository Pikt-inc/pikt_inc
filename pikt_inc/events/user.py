from __future__ import annotations

import frappe

from pikt_inc.services import walkthrough_review


CUSTOMER_ROLE = "Customer"


def _clean(value):
    return str(value or "").strip()


def _role_names(doc) -> set[str]:
    names: set[str] = set()
    for row in getattr(doc, "roles", None) or []:
        if isinstance(row, dict):
            role_name = _clean(row.get("role"))
        else:
            role_name = _clean(getattr(row, "role", None))
        if role_name:
            names.add(role_name)
    return names


def _validate_customer_scope_link(doc) -> None:
    roles = _role_names(doc)
    if CUSTOMER_ROLE not in roles:
        return
    if _clean(getattr(doc, "custom_customer", None)):
        return
    frappe.throw("Users with the Customer role must have a linked Customer.")


def before_save(doc, _method=None):
    walkthrough_review.apply_reviewer_module_profile(doc)
    _validate_customer_scope_link(doc)
