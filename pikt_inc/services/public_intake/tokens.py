from __future__ import annotations

import frappe
from pydantic import ValidationError
from frappe.utils import add_to_date, now_datetime

from pikt_inc.services.contracts.common import first_validation_message
from pikt_inc.services.contracts.public_intake import PublicFunnelValidationInput
from .constants import FUNNEL_TOKEN_EXPIRY_DAYS
from .shared import clean, coerce_datetime, fail


def make_public_token():
    rows = frappe.db.sql(
        "select concat(replace(uuid(), '-', ''), replace(uuid(), '-', '')) as token",
        as_dict=True,
    )
    token = ""
    if rows:
        token = clean(rows[0].get("token"))
    if not token:
        fail("We could not create your estimate right now. Please try again.")
    return token


def ensure_public_token(docname, current_token, current_expiry):
    token = clean(current_token)
    expiry_dt = coerce_datetime(current_expiry)
    current_dt = now_datetime()

    if token and expiry_dt and current_dt < expiry_dt:
        return token

    token = make_public_token()
    expiry_dt = add_to_date(current_dt, days=FUNNEL_TOKEN_EXPIRY_DAYS, as_datetime=True)
    frappe.db.set_value("Opportunity", docname, "public_funnel_token", token, update_modified=False)
    frappe.db.set_value(
        "Opportunity",
        docname,
        "public_funnel_token_expires_on",
        expiry_dt,
        update_modified=False,
    )
    return token


def get_public_funnel_validation_message(opportunity, token, row):
    opportunity = clean(opportunity)
    token = clean(token)

    if not opportunity:
        return {
            "valid": 0,
            "message": (
                "This link is missing the estimate reference. Please return to the estimate page and try again."
            ),
        }

    if not token:
        return {
            "valid": 0,
            "message": (
                "This link is missing its secure access token. Please return to the estimate page and try again."
            ),
        }

    if not row:
        return {
            "valid": 0,
            "message": "We could not find that estimate. Please return to the estimate page and try again.",
        }

    stored_token = clean(row.get("public_funnel_token"))
    expires_dt = coerce_datetime(row.get("public_funnel_token_expires_on"))

    if (not stored_token) or (stored_token != token):
        return {
            "valid": 0,
            "message": (
                "This estimate link is no longer valid. Please return to the estimate page and try again."
            ),
        }

    if (not expires_dt) or (now_datetime() >= expires_dt):
        return {
            "valid": 0,
            "message": "This estimate link has expired. Please return to the estimate page to continue.",
        }

    return {"valid": 1, "opportunity": opportunity}


def validate_public_funnel_opportunity(opportunity=None, token=None):
    try:
        payload = PublicFunnelValidationInput.model_validate(
            {
                "opportunity": opportunity if opportunity is not None else frappe.form_dict.get("opportunity"),
                "token": token if token is not None else frappe.form_dict.get("token"),
            }
        )
    except ValidationError as exc:
        fail(first_validation_message(exc))
    opportunity = payload.opportunity
    token = payload.token
    row = None
    if opportunity:
        row = frappe.db.get_value(
            "Opportunity",
            opportunity,
            ["name", "public_funnel_token", "public_funnel_token_expires_on"],
            as_dict=True,
        )
    return get_public_funnel_validation_message(opportunity, token, row)


def require_valid_public_funnel_opportunity(opportunity, token):
    try:
        payload = PublicFunnelValidationInput.model_validate({"opportunity": opportunity, "token": token})
    except ValidationError as exc:
        fail(first_validation_message(exc))
    opportunity = payload.opportunity
    token = payload.token
    row = frappe.db.get_value(
        "Opportunity",
        opportunity,
        ["name", "public_funnel_token", "public_funnel_token_expires_on"],
        as_dict=True,
    )
    validation = get_public_funnel_validation_message(opportunity, token, row)
    if not validation.get("valid"):
        fail(validation.get("message"))
    return row
