from __future__ import annotations

from typing import Any, Iterable

import frappe
from frappe.utils import now_datetime

from .customer_portal.queries import _get_portal_contact_links
from .public_quote.shared import make_unique_name, truthy


CUSTOMER_DESK_ROLE = "Customer Desk User"
CUSTOMER_PORTAL_ROLE = "Customer Portal User"
DESK_ROLE = "Desk User"
CUSTOMER_DESK_PROFILE = "Customer Desk"
CUSTOMER_WORKSPACE = "Customer Workspace"
CUSTOMER_DESK_APP = "erpnext"
CUSTOMER_DESK_HOME = "app/customer-workspace"
CUSTOMER_DESK_MODULE = "Pikt Inc"
CUSTOMER_DESK_ALLOWED_COMPANION_ROLES = {
    CUSTOMER_DESK_ROLE,
    CUSTOMER_PORTAL_ROLE,
    DESK_ROLE,
}
CUSTOMER_DESK_TITLE_FIELDS = {
    "Building": "building_name",
    "Service Agreement": "agreement_name",
    "Service Agreement Addendum": "addendum_name",
}
CUSTOMER_DESK_WORKSPACE_SHORTCUTS = (
    {
        "label": "Buildings",
        "link_to": "Building",
        "type": "DocType",
        "doc_view": "List",
        "color": "Blue",
    },
    {
        "label": "Agreements",
        "link_to": "Service Agreement",
        "type": "DocType",
        "doc_view": "List",
        "color": "Green",
    },
    {
        "label": "Addenda",
        "link_to": "Service Agreement Addendum",
        "type": "DocType",
        "doc_view": "List",
        "color": "Orange",
    },
)


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _get_role_name(row: Any) -> str:
    if isinstance(row, dict):
        return clean(row.get("role"))
    return clean(getattr(row, "role", None))


def _normalize_role_names(rows: Iterable[Any]) -> set[str]:
    return {_get_role_name(row) for row in (rows or []) if _get_role_name(row)}


def get_user_roles(user: str | None = None) -> set[str]:
    user = clean(user) or clean(getattr(getattr(frappe, "session", None), "user", None))
    if not user or user == "Guest":
        return set()
    try:
        roles = frappe.get_roles(user)
    except Exception:
        return set()
    return {clean(role) for role in roles or [] if clean(role)}


def is_customer_desk_user(user: str | None = None) -> bool:
    role_names = get_user_roles(user)
    return CUSTOMER_DESK_ROLE in role_names and not bool(role_names - CUSTOMER_DESK_ALLOWED_COMPANION_ROLES)


def resolve_customer_name(user: str | None = None) -> str:
    user = clean(user) or clean(getattr(getattr(frappe, "session", None), "user", None))
    if not user or user == "Guest":
        return ""

    rows = _get_portal_contact_links(user)
    customer_names = {clean(row.get("customer_name")) for row in rows if clean(row.get("customer_name"))}
    if len(customer_names) != 1:
        return ""
    return next(iter(customer_names))


def apply_customer_desk_module_profile(doc: Any) -> dict[str, Any]:
    role_names = _normalize_role_names(getattr(doc, "roles", None) or [])

    if CUSTOMER_DESK_ROLE in role_names and DESK_ROLE not in role_names:
        doc.append("roles", {"role": DESK_ROLE})
        role_names.add(DESK_ROLE)

    non_customer_roles = role_names - CUSTOMER_DESK_ALLOWED_COMPANION_ROLES
    workspace_exists = bool(frappe.db.exists("Workspace", CUSTOMER_WORKSPACE))

    if CUSTOMER_DESK_ROLE in role_names and not non_customer_roles:
        doc.module_profile = CUSTOMER_DESK_PROFILE
        if workspace_exists:
            doc.default_workspace = CUSTOMER_WORKSPACE
        elif clean(getattr(doc, "default_workspace", None)) == CUSTOMER_WORKSPACE:
            doc.default_workspace = None
        doc.default_app = CUSTOMER_DESK_APP
        return {
            "status": "customer_desk_profile_applied",
            "workspace_applied": int(workspace_exists),
        }

    if clean(getattr(doc, "module_profile", None)) == CUSTOMER_DESK_PROFILE:
        doc.module_profile = None
        if clean(getattr(doc, "default_workspace", None)) == CUSTOMER_WORKSPACE:
            doc.default_workspace = None
        if clean(getattr(doc, "default_app", None)) == CUSTOMER_DESK_APP:
            doc.default_app = None
        return {"status": "customer_desk_profile_cleared"}

    return {"status": "noop"}


def normalize_access_details_confirmation(
    confirmed_value: Any,
    existing_completed_on: Any = None,
    current_completed_on: Any = None,
) -> tuple[int, Any]:
    normalized_confirmed = 1 if truthy(confirmed_value) else 0
    completed_on = current_completed_on
    if normalized_confirmed and not (existing_completed_on or current_completed_on):
        completed_on = now_datetime()
    return normalized_confirmed, completed_on


def apply_building_access_confirmation(doc: Any) -> dict[str, Any]:
    existing_completed_on = None
    building_name = clean(getattr(doc, "name", None))
    if building_name:
        try:
            existing_completed_on = frappe.db.get_value("Building", building_name, "access_details_completed_on")
        except Exception:
            existing_completed_on = None

    normalized_confirmed, completed_on = normalize_access_details_confirmation(
        getattr(doc, "access_details_confirmed", None),
        existing_completed_on=existing_completed_on,
        current_completed_on=getattr(doc, "access_details_completed_on", None),
    )

    changed = False
    if getattr(doc, "access_details_confirmed", None) != normalized_confirmed:
        doc.access_details_confirmed = normalized_confirmed
        changed = True
    if completed_on and getattr(doc, "access_details_completed_on", None) != completed_on:
        doc.access_details_completed_on = completed_on
        changed = True

    return {
        "status": "updated" if changed else "noop",
        "access_details_confirmed": normalized_confirmed,
    }


def apply_customer_desk_building_defaults(doc: Any) -> dict[str, Any]:
    session_user = clean(getattr(getattr(frappe, "session", None), "user", None))
    if not is_customer_desk_user(session_user):
        return {"status": "noop"}

    customer_name = resolve_customer_name(session_user)
    if not customer_name:
        frappe.throw("This customer desk account is not linked to a customer.")

    current_customer = clean(getattr(doc, "customer", None))
    if current_customer and current_customer != customer_name:
        frappe.throw("That building is not available for this customer desk account.")

    changed = False
    if current_customer != customer_name:
        doc.customer = customer_name
        changed = True

    is_new = False
    if callable(getattr(doc, "is_new", None)):
        try:
            is_new = bool(doc.is_new())
        except Exception:
            is_new = False
    elif not clean(getattr(doc, "name", None)):
        is_new = True

    if is_new and getattr(doc, "active", None) in (None, ""):
        doc.active = 1
        changed = True

    building_name = clean(getattr(doc, "building_name", None))
    current_name = clean(getattr(doc, "name", None))
    if (not is_new) and current_name and building_name and building_name != current_name:
        doc.building_name = current_name
        changed = True
        building_name = current_name

    if is_new and building_name and frappe.db.exists("Building", building_name):
        unique_name = make_unique_name("Building", building_name)
        if unique_name != building_name:
            doc.building_name = unique_name
            try:
                doc.name = unique_name
            except Exception:
                pass
            changed = True

    return {
        "status": "updated" if changed else "noop",
        "customer": customer_name,
    }
