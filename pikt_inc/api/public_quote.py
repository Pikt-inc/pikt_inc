from __future__ import annotations

import frappe

from pikt_inc.services import public_quote as public_quote_service


@frappe.whitelist(allow_guest=True)
def validate_public_quote(quote=None, token=None, **kwargs):
    return public_quote_service.validate_public_quote(
        quote=quote or kwargs.get("quote"),
        token=token or kwargs.get("token"),
    )


@frappe.whitelist(allow_guest=True)
def accept_public_quote(quote=None, token=None, **kwargs):
    return public_quote_service.accept_public_quote(
        quote=quote or kwargs.get("quote"),
        token=token or kwargs.get("token"),
    )


@frappe.whitelist(allow_guest=True)
def load_public_quote_portal_state(quote=None, token=None, **kwargs):
    return public_quote_service.load_public_quote_portal_state(
        quote=quote or kwargs.get("quote"),
        token=token or kwargs.get("token"),
    )
