from __future__ import annotations

from typing import Any, Mapping

import frappe
from pydantic import ValidationError
from frappe.utils import add_to_date, now_datetime, nowdate

from pikt_inc.services.contracts.common import first_validation_message
from pikt_inc.services.contracts.public_intake import InstantQuoteRequestInput
from pikt_inc.services.contracts.public_intake import InstantQuoteResponse
from pikt_inc.services.contracts.public_intake import PublicFunnelValidationInput
from pikt_inc.services.contracts.public_intake import PublicQuoteRequestStateInput
from pikt_inc.services.contracts.public_intake import PublicQuoteRequestStateResponse
from . import tokens
from .constants import (
    DEFAULT_COMPANY,
    DEFAULT_COUNTRY,
    DEFAULT_CURRENCY,
    DEFAULT_EMPLOYEE_RANGE,
    DEFAULT_LANGUAGE,
    FUNNEL_TOKEN_EXPIRY_DAYS,
)
from .shared import clean, coerce_datetime, fail


PUBLIC_QUOTE_REQUEST_FIELDS = (
    "prospect_name",
    "phone",
    "contact_email",
    "prospect_company",
    "building_type",
    "building_size",
    "service_frequency",
    "service_interest",
    "bathroom_count_range",
)

LEGACY_OPPORTUNITY_LINK_MESSAGE = (
    "This estimate link format is no longer supported. Please return to the quote page and request a new secure link."
)


def validate_and_normalize_quote_request(form_dict: Mapping[str, Any] | None = None):
    try:
        return InstantQuoteRequestInput.model_validate(form_dict or frappe.form_dict)
    except ValidationError as exc:
        fail(first_validation_message(exc))


def split_prospect_name(prospect_name):
    name_parts = prospect_name.split()
    first_name = prospect_name
    last_name = ""
    if len(name_parts) > 0:
        first_name = name_parts[0]
    if len(name_parts) > 1:
        last_name = " ".join(name_parts[1:])
    return first_name, last_name


def get_public_quote_request_values(request_data: InstantQuoteRequestInput) -> dict[str, str]:
    return {
        "prospect_name": request_data.prospect_name,
        "phone": request_data.phone,
        "contact_email": request_data.contact_email,
        "prospect_company": request_data.prospect_company,
        "building_type": request_data.building_type,
        "building_size": str(request_data.building_size),
        "service_frequency": request_data.service_frequency,
        "service_interest": request_data.service_interest,
        "bathroom_count_range": request_data.bathroom_count_range.value,
    }


def get_quote_request_public_payload(source: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    getter = getattr(source, "get", None)
    for fieldname in PUBLIC_QUOTE_REQUEST_FIELDS:
        if callable(getter):
            payload[fieldname] = getter(fieldname)
        else:
            payload[fieldname] = getattr(source, fieldname, None)
    return payload


def normalize_instant_quote_request_doc(doc):
    request_data = validate_and_normalize_quote_request(form_dict=get_quote_request_public_payload(doc))
    values = get_public_quote_request_values(request_data)
    for fieldname, value in values.items():
        setattr(doc, fieldname, value)
    if not clean(doc.get("currency")):
        doc.currency = DEFAULT_CURRENCY
    return request_data


def create_lead_for_quote_request(request_data: InstantQuoteRequestInput):
    first_name, last_name = split_prospect_name(request_data.prospect_name)
    lead = frappe.get_doc({"doctype": "Lead"})
    lead.naming_series = lead.get("naming_series") or "CRM-LEAD-.YYYY.-"
    lead.first_name = first_name
    lead.last_name = last_name
    lead.email_id = request_data.contact_email
    lead.phone = request_data.phone
    lead.company_name = request_data.prospect_company
    lead.company = DEFAULT_COMPANY
    lead.country = DEFAULT_COUNTRY
    lead.status = "Opportunity"
    lead.no_of_employees = DEFAULT_EMPLOYEE_RANGE
    lead.insert(ignore_permissions=True)
    return lead


def create_opportunity_for_quote_request(
    lead,
    request_data: InstantQuoteRequestInput,
):
    opportunity = frappe.get_doc(
        {
            "doctype": "Opportunity",
            "naming_series": "CRM-OPP-.YYYY.-",
            "opportunity_from": "Lead",
            "party_name": lead.name,
            "status": "Open",
            "opportunity_type": "Sales",
            "sales_stage": "Prospecting",
            "company": DEFAULT_COMPANY,
            "transaction_date": nowdate(),
            "currency": DEFAULT_CURRENCY,
            "conversion_rate": 1,
            "title": request_data.prospect_name,
            "customer_name": request_data.prospect_name,
            "prospect_name": request_data.prospect_name,
            "prospect_company": request_data.prospect_company,
            "building_type": request_data.building_type,
            "building_size": str(request_data.building_size),
            "bathroom_count_range": request_data.bathroom_count_range.value,
            "service_frequency": request_data.service_frequency,
            "service_interest": request_data.service_interest,
            "contact_email": request_data.contact_email,
            "phone": request_data.phone,
            "country": DEFAULT_COUNTRY,
            "language": DEFAULT_LANGUAGE,
            "no_of_employees": DEFAULT_EMPLOYEE_RANGE,
            "digital_walkthrough_status": "Not Requested",
        }
    )
    opportunity.insert(ignore_permissions=True)
    return opportunity


def build_quote_request_response(row, token, duplicate, request_name=""):
    opportunity_name = clean(row.get("name"))
    return InstantQuoteResponse(
        request=clean(request_name),
        name=opportunity_name,
        opp=opportunity_name,
        low=float(row.get("custom_estimate_low") or row.get("estimate_low") or 0),
        high=float(row.get("custom_estimate_high") or row.get("estimate_high") or 0),
        risk=clean(row.get("risk_level")),
        currency=clean(row.get("currency")) or DEFAULT_CURRENCY,
        final_price=float(row.get("opportunity_amount") or row.get("final_price") or 0),
        token=clean(token),
        duplicate=duplicate,
    ).model_dump(mode="python")


def get_public_quote_request_validation_message(request_name, token, row):
    request_name = clean(request_name)
    token = clean(token)

    if not request_name:
        return {
            "valid": 0,
            "message": "This link is missing the quote request reference. Please return to the quote page and try again.",
        }

    if not token:
        return {
            "valid": 0,
            "message": "This link is missing its secure access token. Please return to the quote page and try again.",
        }

    if not row:
        return {
            "valid": 0,
            "message": "We could not find that estimate. Please return to the quote page and try again.",
        }

    stored_token = clean(row.get("public_funnel_token"))
    expires_dt = coerce_datetime(row.get("public_funnel_token_expires_on"))

    if (not stored_token) or (stored_token != token):
        return {
            "valid": 0,
            "message": "This estimate link is no longer valid. Please return to the quote page and try again.",
        }

    if (not expires_dt) or (now_datetime() >= expires_dt):
        return {
            "valid": 0,
            "message": "This estimate link has expired. Please return to the quote page to continue.",
        }

    return {"valid": 1, "request": request_name}


def get_public_quote_request_row(request_name):
    request_name = clean(request_name)
    if not request_name:
        return None
    return frappe.db.get_value(
        "Instant Quote Request",
        request_name,
        [
            "name",
            "opportunity",
            "public_funnel_token",
            "public_funnel_token_expires_on",
            "estimate_low",
            "estimate_high",
            "currency",
            "final_price",
            "risk_level",
        ],
        as_dict=True,
    )


def require_valid_public_quote_request(request=None, token=None):
    try:
        payload = PublicQuoteRequestStateInput.model_validate(
            {
                "request": request if request is not None else frappe.form_dict.get("request"),
                "token": token if token is not None else frappe.form_dict.get("token"),
            }
        )
    except ValidationError as exc:
        fail(first_validation_message(exc))

    request_row = get_public_quote_request_row(payload.request)
    validation = get_public_quote_request_validation_message(payload.request, payload.token, request_row)
    if not validation.get("valid"):
        fail(validation.get("message"))

    return request_row


def build_public_quote_request_state_response(request_row, token):
    return PublicQuoteRequestStateResponse(
        valid=1,
        request=clean(request_row.get("name")),
        low=float(request_row.get("estimate_low") or 0),
        high=float(request_row.get("estimate_high") or 0),
        risk=clean(request_row.get("risk_level")),
        currency=clean(request_row.get("currency")) or DEFAULT_CURRENCY,
        final_price=float(request_row.get("final_price") or 0),
        token=clean(token),
    ).model_dump(mode="python")


def prepare_instant_quote_request(doc):
    request_data = normalize_instant_quote_request_doc(doc)
    token = tokens.make_public_token()
    expires_on = add_to_date(now_datetime(), days=FUNNEL_TOKEN_EXPIRY_DAYS, as_datetime=True)

    try:
        lead = create_lead_for_quote_request(request_data)
        opportunity = create_opportunity_for_quote_request(lead, request_data)
    except Exception:
        if hasattr(frappe.db, "rollback"):
            frappe.db.rollback()
        frappe.log_error(frappe.get_traceback(), "Instant Quote Request Processing")
        fail("We could not create your estimate right now. Please try again.")

    values = {
        "lead": clean(lead.name),
        "opportunity": clean(opportunity.name),
        "public_funnel_token": clean(token),
        "public_funnel_token_expires_on": expires_on,
        "estimate_low": opportunity.get("custom_estimate_low") or 0,
        "estimate_high": opportunity.get("custom_estimate_high") or 0,
        "currency": clean(opportunity.get("currency")) or DEFAULT_CURRENCY,
        "final_price": opportunity.get("opportunity_amount") or 0,
        "risk_level": clean(opportunity.get("risk_level")),
    }
    for fieldname, value in values.items():
        setattr(doc, fieldname, value)
    return doc


def process_instant_quote_request(doc):
    return prepare_instant_quote_request(doc)


def create_instant_quote_request(form_dict: Mapping[str, Any] | None = None):
    request_data = validate_and_normalize_quote_request(form_dict=form_dict)
    payload = {
        "doctype": "Instant Quote Request",
        **get_public_quote_request_values(request_data),
        "currency": DEFAULT_CURRENCY,
    }
    try:
        doc = frappe.get_doc(payload)
        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Instant Quote Request")
        fail("We could not create your estimate right now. Please try again.")
    return doc


def create_instant_quote_opportunity(form_dict: Mapping[str, Any] | None = None):
    request_doc = create_instant_quote_request(form_dict=form_dict)
    opportunity_row = {
        "name": request_doc.get("opportunity"),
        "custom_estimate_low": request_doc.get("estimate_low"),
        "custom_estimate_high": request_doc.get("estimate_high"),
        "risk_level": request_doc.get("risk_level"),
        "currency": request_doc.get("currency"),
        "opportunity_amount": request_doc.get("final_price"),
    }
    return build_quote_request_response(
        opportunity_row,
        request_doc.get("public_funnel_token"),
        duplicate=0,
        request_name=request_doc.get("name"),
    )


def load_public_quote_request_state(request=None, token=None):
    request_name = request if request is not None else frappe.form_dict.get("request")
    access_token = token if token is not None else frappe.form_dict.get("token")
    request_row = get_public_quote_request_row(request_name)
    validation = get_public_quote_request_validation_message(request_name, access_token, request_row)
    if not validation.get("valid"):
        return validation

    if not clean((request_row or {}).get("opportunity")):
        return {
            "valid": 0,
            "message": "We could not reopen that estimate request. Please start a new quote request and try again.",
        }

    return build_public_quote_request_state_response(request_row, access_token)


def validate_public_funnel_opportunity(opportunity=None, token=None):
    try:
        PublicFunnelValidationInput.model_validate(
            {
                "opportunity": opportunity if opportunity is not None else frappe.form_dict.get("opportunity"),
                "token": token if token is not None else frappe.form_dict.get("token"),
            }
        )
    except ValidationError as exc:
        fail(first_validation_message(exc))

    return {
        "valid": 0,
        "message": LEGACY_OPPORTUNITY_LINK_MESSAGE,
    }
