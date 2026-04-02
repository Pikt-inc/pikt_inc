from __future__ import annotations

import frappe

from .. import public_quote as public_quote_service
from ..contracts.common import clean_str
from .customer_repo import find_customer_contact_by_email, get_contact, get_customer, get_user
from .errors import CustomerPortalAccessError
from .models import CustomerPortalContext


CUSTOMER_ROLE = "Customer"


def _get_roles(session_user: str) -> set[str]:
    get_roles = getattr(frappe, "get_roles", None)
    if not callable(get_roles):
        return set()
    return {clean_str(role) for role in (get_roles(session_user) or []) if clean_str(role)}


def resolve_context() -> CustomerPortalContext:
    session_user = clean_str(getattr(getattr(frappe, "session", None), "user", None))
    if not session_user or session_user == "Guest":
        raise CustomerPortalAccessError("Sign in to access your customer portal.")

    if CUSTOMER_ROLE not in _get_roles(session_user):
        raise CustomerPortalAccessError("This account does not have customer portal access.")

    user_record = get_user(session_user)
    customer_name = clean_str(getattr(user_record, "custom_customer", ""))
    if not customer_name:
        raise CustomerPortalAccessError("This customer portal account is missing a linked customer.")

    customer_record = get_customer(customer_name)
    if not customer_record:
        raise CustomerPortalAccessError("The linked customer record could not be loaded.")

    portal_contact_email = clean_str(user_record.email if user_record else "") or session_user
    portal_contact_name = find_customer_contact_by_email(customer_name, portal_contact_email)
    if not portal_contact_name:
        portal_contact_name = customer_record.customer_primary_contact
    portal_contact = get_contact(portal_contact_name)
    if portal_contact and portal_contact.email_id and not portal_contact_email:
        portal_contact_email = clean_str(portal_contact.email_id)

    billing_contact_name = clean_str(public_quote_service.find_contact_for_customer(customer_name, portal_contact_email))
    if not billing_contact_name:
        billing_contact_name = customer_record.customer_primary_contact or portal_contact_name
    billing_contact = get_contact(billing_contact_name)

    billing_address_name = clean_str(public_quote_service.find_address_for_customer(customer_name))
    if not billing_address_name:
        billing_address_name = customer_record.customer_primary_address

    return CustomerPortalContext(
        session_user=session_user,
        customer_name=customer_name,
        customer_display=clean_str(customer_record.customer_name) or customer_name,
        portal_contact_name=clean_str(portal_contact_name),
        portal_contact_email=portal_contact_email,
        portal_contact_phone=clean_str(getattr(portal_contact, "phone", "")) or clean_str(getattr(portal_contact, "mobile_no", "")),
        portal_contact_designation=clean_str(getattr(portal_contact, "designation", "")),
        portal_address_name=clean_str(getattr(portal_contact, "address", "")),
        billing_contact_name=clean_str(billing_contact_name),
        billing_contact_email=clean_str(getattr(billing_contact, "email_id", "")) or portal_contact_email,
        billing_contact_phone=clean_str(getattr(billing_contact, "phone", "")) or clean_str(getattr(billing_contact, "mobile_no", "")),
        billing_contact_designation=clean_str(getattr(billing_contact, "designation", "")),
        billing_address_name=billing_address_name,
        tax_id=clean_str(customer_record.tax_id),
    )
