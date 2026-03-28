from __future__ import annotations

from typing import Any

import frappe

from pikt_inc.services import customer_desk


_CUSTOMER_FIELD_BY_DOCTYPE = {
    "Building": "customer",
    "Service Agreement": "customer",
    "Service Agreement Addendum": "customer",
}


def _clean(value: Any) -> str:
    return customer_desk.clean(value)


def _sql_literal(value: Any) -> str:
    value = _clean(value)
    db = getattr(frappe, "db", None)
    if db and hasattr(db, "escape"):
        return str(db.escape(value))
    return "'" + value.replace("'", "''") + "'"


def _document_customer(doctype: str, doc: Any) -> str:
    if isinstance(doc, dict):
        return _clean(doc.get(_CUSTOMER_FIELD_BY_DOCTYPE[doctype]))

    fieldname = _CUSTOMER_FIELD_BY_DOCTYPE[doctype]
    value = _clean(getattr(doc, fieldname, None))
    if value:
        return value

    docname = _clean(getattr(doc, "name", None) or doc)
    if not docname or isinstance(doc, bool):
        return ""
    try:
        return _clean(frappe.db.get_value(doctype, docname, fieldname))
    except Exception:
        return ""


def _permission_query_conditions(doctype: str, user: str | None = None) -> str | None:
    if not customer_desk.is_customer_desk_user(user):
        return None

    customer_name = customer_desk.resolve_customer_name(user)
    if not customer_name:
        return "1=0"

    fieldname = _CUSTOMER_FIELD_BY_DOCTYPE[doctype]
    return f"`tab{doctype}`.`{fieldname}` = {_sql_literal(customer_name)}"


def _has_permission(
    doctype: str,
    doc: Any,
    user: str | None = None,
    permission_type: str | None = None,
    allow_write: bool = False,
) -> bool | None:
    if not customer_desk.is_customer_desk_user(user):
        return None

    customer_name = customer_desk.resolve_customer_name(user)
    if not customer_name:
        return False

    if permission_type == "create":
        return allow_write

    if permission_type in {"write", "submit", "cancel", "delete"} and not allow_write:
        return False

    document_customer = _document_customer(doctype, doc)
    return document_customer == customer_name


def get_building_permission_query_conditions(user: str | None = None) -> str | None:
    return _permission_query_conditions("Building", user)


def get_service_agreement_permission_query_conditions(user: str | None = None) -> str | None:
    return _permission_query_conditions("Service Agreement", user)


def get_service_agreement_addendum_permission_query_conditions(user: str | None = None) -> str | None:
    return _permission_query_conditions("Service Agreement Addendum", user)


def has_building_permission(doc: Any, user: str | None = None, permission_type: str | None = None) -> bool | None:
    return _has_permission("Building", doc, user=user, permission_type=permission_type, allow_write=True)


def has_service_agreement_permission(doc: Any, user: str | None = None, permission_type: str | None = None) -> bool | None:
    return _has_permission("Service Agreement", doc, user=user, permission_type=permission_type, allow_write=False)


def has_service_agreement_addendum_permission(
    doc: Any,
    user: str | None = None,
    permission_type: str | None = None,
) -> bool | None:
    return _has_permission("Service Agreement Addendum", doc, user=user, permission_type=permission_type, allow_write=False)
