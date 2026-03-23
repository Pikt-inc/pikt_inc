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


@frappe.whitelist(allow_guest=True)
def complete_public_service_agreement_signature(quote=None, token=None, **kwargs):
    payload = dict(kwargs)
    if quote is not None:
        payload["quote"] = quote
    if token is not None:
        payload["token"] = token
    return public_quote_service.complete_public_service_agreement_signature(**payload)


@frappe.whitelist(allow_guest=True)
def complete_public_quote_billing_setup_v2(quote=None, token=None, **kwargs):
    payload = dict(kwargs)
    if quote is not None:
        payload["quote"] = quote
    if token is not None:
        payload["token"] = token
    return public_quote_service.complete_public_quote_billing_setup_v2(**payload)


@frappe.whitelist(allow_guest=True)
def complete_public_quote_access_setup_v2(quote=None, token=None, **kwargs):
    payload = dict(kwargs)
    if quote is not None:
        payload["quote"] = quote
    if token is not None:
        payload["token"] = token
    return public_quote_service.complete_public_quote_access_setup_v2(**payload)
