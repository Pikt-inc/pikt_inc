from __future__ import annotations

import frappe

from ..contracts.common import clean_str
from .customer_repo import get_customer, get_user
from .errors import CustomerPortalAccessError
from .models import CustomerPortalPrincipal


CUSTOMER_ROLE = "Customer"


def _get_roles(session_user: str) -> set[str]:
    get_roles = getattr(frappe, "get_roles", None)
    if not callable(get_roles):
        return set()
    return {clean_str(role) for role in (get_roles(session_user) or []) if clean_str(role)}


def resolve_context() -> CustomerPortalPrincipal:
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

    return CustomerPortalPrincipal(
        session_user=session_user,
        customer_name=customer_name,
        customer_display=clean_str(customer_record.customer_name) or customer_name,
    )
