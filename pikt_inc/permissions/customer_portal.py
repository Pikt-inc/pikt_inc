from __future__ import annotations

from typing import Any

import frappe

from pikt_inc.services.customer_portal.constants import PORTAL_ROLE
from pikt_inc.services.customer_portal.queries import _get_portal_contact_links
from pikt_inc.services.customer_portal.shared import clean


def _resolve_user(user: str | None = None) -> str:
	return clean(user) or clean(getattr(getattr(frappe, "session", None), "user", None))


def _get_roles(user: str) -> set[str]:
	get_roles = getattr(frappe, "get_roles", None)
	if not callable(get_roles):
		return set()

	try:
		roles = get_roles(user) if user else get_roles()
	except TypeError:
		roles = get_roles(user)
	return {clean(role) for role in (roles or []) if clean(role)}


def _is_portal_user(user: str) -> bool:
	return bool(user) and PORTAL_ROLE in _get_roles(user)


def _resolve_customer_name(user: str) -> str:
	customer_names = {
		clean(row.get("customer_name"))
		for row in _get_portal_contact_links(user)
		if clean(row.get("customer_name"))
	}
	if len(customer_names) != 1:
		return ""
	return next(iter(customer_names))


def _escape_sql_literal(value: str) -> str:
	escape = getattr(getattr(frappe, "db", None), "escape", None)
	if callable(escape):
		return escape(value)
	return "'" + value.replace("\\", "\\\\").replace("'", "''") + "'"


def _extract_customer_name(doctype_name: str, doc: Any) -> str:
	if doc is None:
		return ""

	if isinstance(doc, dict):
		customer_name = clean(doc.get("customer"))
		record_name = clean(doc.get("name"))
	else:
		customer_name = clean(getattr(doc, "customer", None))
		record_name = clean(getattr(doc, "name", None))

	if customer_name or not record_name:
		return customer_name

	return clean(frappe.db.get_value(doctype_name, record_name, "customer"))


def _get_permission_query_conditions(doctype_name: str, user: str | None = None) -> str | None:
	session_user = _resolve_user(user)
	if not _is_portal_user(session_user):
		return None

	customer_name = _resolve_customer_name(session_user)
	if not customer_name:
		return "1=0"

	return f"`tab{doctype_name}`.`customer` = {_escape_sql_literal(customer_name)}"


def _has_permission(
	doctype_name: str,
	doc: Any = None,
	user: str | None = None,
	permission_type: str | None = None,
) -> bool | None:
	session_user = _resolve_user(user)
	if not _is_portal_user(session_user):
		return None

	if clean(permission_type).lower() == "create":
		return False

	customer_name = _resolve_customer_name(session_user)
	if not customer_name:
		return False

	if doc is None:
		return None

	return _extract_customer_name(doctype_name, doc) == customer_name


def get_building_permission_query_conditions(user: str | None = None) -> str | None:
	return _get_permission_query_conditions("Building", user)


def has_building_permission(doc: Any = None, user: str | None = None, permission_type: str | None = None) -> bool | None:
	return _has_permission("Building", doc, user, permission_type)


def get_building_sop_permission_query_conditions(user: str | None = None) -> str | None:
	return _get_permission_query_conditions("Building SOP", user)


def has_building_sop_permission(
	doc: Any = None,
	user: str | None = None,
	permission_type: str | None = None,
) -> bool | None:
	return _has_permission("Building SOP", doc, user, permission_type)


def get_service_agreement_permission_query_conditions(user: str | None = None) -> str | None:
	return _get_permission_query_conditions("Service Agreement", user)


def has_service_agreement_permission(
	doc: Any = None,
	user: str | None = None,
	permission_type: str | None = None,
) -> bool | None:
	return _has_permission("Service Agreement", doc, user, permission_type)


def get_service_agreement_addendum_permission_query_conditions(user: str | None = None) -> str | None:
	return _get_permission_query_conditions("Service Agreement Addendum", user)


def has_service_agreement_addendum_permission(
	doc: Any = None,
	user: str | None = None,
	permission_type: str | None = None,
) -> bool | None:
	return _has_permission("Service Agreement Addendum", doc, user, permission_type)
