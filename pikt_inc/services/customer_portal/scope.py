from __future__ import annotations

from dataclasses import dataclass

import frappe

from .. import public_quote as public_quote_service
from .queries import _find_customer_contact_by_email, _get_customer_row, _load_contact_row, _load_user_row
from .shared import _throw, clean


class PortalAccessError(Exception):
    pass


@dataclass(frozen=True)
class PortalScope:
    session_user: str
    customer_name: str
    customer_display: str
    portal_contact_name: str
    portal_contact_email: str
    portal_contact_phone: str
    portal_contact_designation: str
    portal_address_name: str
    billing_contact_name: str
    billing_contact_email: str
    billing_contact_phone: str
    billing_contact_designation: str
    billing_address_name: str
    tax_id: str


CUSTOMER_ROLE = "Customer"


def _is_guest_session() -> bool:
    return clean(getattr(getattr(frappe, "session", None), "user", None)) in {"", "Guest"}


def _resolve_portal_scope_or_error() -> PortalScope:
    session_user = clean(getattr(getattr(frappe, "session", None), "user", None))
    if not session_user or session_user == "Guest":
        raise PortalAccessError("Sign in to access your customer portal.")

    get_roles = getattr(frappe, "get_roles", None)
    role_values = get_roles(session_user) if callable(get_roles) else []
    roles = {clean(role) for role in role_values or [] if clean(role)}
    if CUSTOMER_ROLE not in roles:
        raise PortalAccessError("This account does not have customer portal access.")

    user_row = _load_user_row(session_user)
    customer_name = clean(user_row.get("custom_customer"))
    if not customer_name:
        raise PortalAccessError("This customer portal account is missing a linked customer.")

    customer_row = _get_customer_row(customer_name)
    if not customer_row:
        raise PortalAccessError("The linked customer record could not be loaded.")

    portal_contact_email = clean(user_row.get("email")) or session_user
    portal_contact_name = _find_customer_contact_by_email(customer_name, portal_contact_email)
    if not portal_contact_name:
        portal_contact_name = clean(customer_row.get("customer_primary_contact"))
    portal_contact_row = _load_contact_row(portal_contact_name)
    if clean(portal_contact_row.get("email_id")) and not portal_contact_email:
        portal_contact_email = clean(portal_contact_row.get("email_id"))

    portal_phone = (
        clean(portal_contact_row.get("phone"))
        or clean(portal_contact_row.get("mobile_no"))
    )

    billing_contact_name = clean(public_quote_service.find_contact_for_customer(customer_name, portal_contact_email))
    if not billing_contact_name:
        billing_contact_name = clean(customer_row.get("customer_primary_contact")) or portal_contact_name
    billing_contact_row = _load_contact_row(billing_contact_name)
    billing_contact_email = clean(billing_contact_row.get("email_id")) or portal_contact_email
    billing_phone = clean(billing_contact_row.get("phone")) or clean(billing_contact_row.get("mobile_no"))

    billing_address_name = clean(public_quote_service.find_address_for_customer(customer_name))
    return PortalScope(
        session_user=session_user,
        customer_name=customer_name,
        customer_display=clean(customer_row.get("customer_name")) or customer_name,
        portal_contact_name=portal_contact_name,
        portal_contact_email=portal_contact_email,
        portal_contact_phone=portal_phone,
        portal_contact_designation=clean(portal_contact_row.get("designation")),
        portal_address_name=clean(portal_contact_row.get("address")),
        billing_contact_name=billing_contact_name,
        billing_contact_email=billing_contact_email,
        billing_contact_phone=billing_phone,
        billing_contact_designation=clean(billing_contact_row.get("designation")),
        billing_address_name=billing_address_name or clean(customer_row.get("customer_primary_address")),
        tax_id=clean(customer_row.get("tax_id")),
    )


def _require_portal_scope() -> PortalScope:
    try:
        return _resolve_portal_scope_or_error()
    except PortalAccessError as exc:
        _throw(str(exc))
        raise
