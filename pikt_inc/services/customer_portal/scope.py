from __future__ import annotations

from dataclasses import dataclass

import frappe

from .. import public_quote as public_quote_service
from .queries import _get_customer_row, _get_portal_contact_links, _load_contact_row
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


def _is_guest_session() -> bool:
    return clean(getattr(getattr(frappe, "session", None), "user", None)) in {"", "Guest"}


def _resolve_portal_scope_or_error() -> PortalScope:
    session_user = clean(getattr(getattr(frappe, "session", None), "user", None))
    if not session_user or session_user == "Guest":
        raise PortalAccessError("Sign in to access your customer portal.")

    rows = _get_portal_contact_links(session_user)
    if not rows:
        raise PortalAccessError("This portal account is not linked to a customer contact yet.")

    customer_names = {clean(row.get("customer_name")) for row in rows if clean(row.get("customer_name"))}
    if not customer_names:
        raise PortalAccessError("This portal account is missing a customer link.")
    if len(customer_names) != 1:
        raise PortalAccessError("This portal account is linked to multiple customers. Contact support.")

    customer_name = next(iter(customer_names))
    customer_row = _get_customer_row(customer_name)
    if not customer_row:
        raise PortalAccessError("The linked customer record could not be loaded.")

    portal_row = dict(rows[0])
    portal_contact_name = clean(portal_row.get("contact_name"))
    portal_contact_email = clean(portal_row.get("email_id")) or session_user
    portal_phone = clean(portal_row.get("phone")) or clean(portal_row.get("mobile_no"))

    billing_contact_name = clean(public_quote_service.find_contact_for_customer(customer_name, portal_contact_email))
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
        portal_contact_designation=clean(portal_row.get("designation")),
        portal_address_name=clean(portal_row.get("address_name")),
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
