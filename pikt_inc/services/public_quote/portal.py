from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import now_datetime, nowdate

from .payloads import build_load_portal_state_response, build_validate_payload
from .queries import get_quote_row, load_review_items
from .shared import clean, fail, get_date_safe, get_datetime_safe

def get_public_quote_access_result(quote_name=None, token=None):
    quote_name = clean(quote_name if quote_name is not None else frappe.form_dict.get("quote"))
    token = clean(token if token is not None else frappe.form_dict.get("token"))

    if not quote_name:
        return {
            "state": "invalid",
            "message": "Missing quotation reference. Please return to your quote email and try again.",
        }

    if not token:
        return {
            "state": "invalid",
            "message": "Missing secure access token. Please return to your quote email and try again.",
        }

    row = get_quote_row(quote_name)
    if not row:
        return {
            "state": "invalid",
            "message": "We could not find that quotation. Please return to your quote email and try again.",
        }

    if clean(row.get("custom_accept_token")) != token:
        return {
            "state": "invalid",
            "message": "This quotation link is no longer valid. Please return to your quote email and try again.",
            "row": row,
        }

    if int(row.get("docstatus") or 0) == 2 or clean(row.get("status")) == "Cancelled":
        return {
            "state": "cancelled",
            "message": "This quotation has been cancelled and can no longer be accepted.",
            "row": row,
        }

    expires_dt = get_datetime_safe(row.get("custom_accept_token_expires_on"))
    if (not expires_dt) or (now_datetime() >= expires_dt):
        return {
            "state": "expired",
            "message": "This quotation link has expired. Please contact our team if you still need service.",
            "row": row,
        }

    valid_till = get_date_safe(row.get("valid_till"))
    if valid_till and nowdate() > str(valid_till):
        return {
            "state": "expired",
            "message": "This quotation is past its valid-through date. Please contact our team to refresh it.",
            "row": row,
        }

    if int(row.get("docstatus") or 0) != 1:
        return {
            "state": "invalid",
            "message": "This quotation is not ready for public review yet.",
            "row": row,
        }

    accepted_sales_order = clean(row.get("custom_accepted_sales_order"))
    if accepted_sales_order and frappe.db.exists("Sales Order", accepted_sales_order):
        return {
            "state": "accepted",
            "message": "This quotation has already been accepted.",
            "row": row,
            "sales_order": accepted_sales_order,
        }

    if clean(row.get("quotation_to")) not in ("Lead", "Customer") or not clean(row.get("party_name")):
        return {
            "state": "invalid",
            "message": "This quotation is not available through the public review flow.",
            "row": row,
        }

    return {
        "state": "ready",
        "message": "",
        "row": row,
        "sales_order": "",
    }

def validate_public_quote(quote=None, token=None):
    result = get_public_quote_access_result(quote_name=quote, token=token)
    if result.get("state") in ("ready", "accepted"):
        items = load_review_items(clean((result.get("row") or {}).get("name")))
        return build_validate_payload(
            result.get("state"),
            result.get("message", ""),
            row=result.get("row"),
            items=items,
        )
    return build_validate_payload(result.get("state"), result.get("message", ""))

def load_public_quote_portal_state(quote=None, token=None):
    result = get_public_quote_access_result(quote_name=quote, token=token)
    if result.get("state") in ("ready", "accepted"):
        return build_load_portal_state_response(
            result.get("state"),
            result.get("message", ""),
            row=result.get("row"),
        )
    return build_load_portal_state_response(result.get("state"), result.get("message", ""))

def ensure_quote_is_valid_for_portal_write(quote_name, token, cancelled_message, not_ready_message):
    quote_row = get_quote_row(quote_name)
    if not quote_row:
        fail("We could not find that quotation. Please return to your quote email and try again.")
    if clean(quote_row.get("custom_accept_token")) != clean(token):
        fail("This quotation link is no longer valid. Please return to your quote email and try again.")
    if int(quote_row.get("docstatus") or 0) == 2 or clean(quote_row.get("status")) == "Cancelled":
        fail(cancelled_message)

    expires_dt = get_datetime_safe(quote_row.get("custom_accept_token_expires_on"))
    if (not expires_dt) or (now_datetime() >= expires_dt):
        fail("This quotation link has expired. Please contact our team if you still need service.")

    valid_till = get_date_safe(quote_row.get("valid_till"))
    if valid_till and nowdate() > str(valid_till):
        fail("This quotation is past its valid-through date. Please contact our team to refresh it.")

    if int(quote_row.get("docstatus") or 0) != 1:
        fail(not_ready_message)

    return quote_row

__all__ = [
    "get_public_quote_access_result",
    "validate_public_quote",
    "load_public_quote_portal_state",
    "ensure_quote_is_valid_for_portal_write",
]
