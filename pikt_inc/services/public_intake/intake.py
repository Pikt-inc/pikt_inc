from __future__ import annotations

from typing import Any, Mapping

import frappe
from pydantic import ValidationError
from frappe.utils import add_to_date, now, now_datetime, nowdate

from pikt_inc.services.contracts.common import first_validation_message
from pikt_inc.services.contracts.public_intake import InstantQuoteRequestInput
from pikt_inc.services.contracts.public_intake import InstantQuoteResponse
from .constants import (
    DEFAULT_COMPANY,
    DEFAULT_COUNTRY,
    DEFAULT_CURRENCY,
    DEFAULT_EMPLOYEE_RANGE,
    DEFAULT_LANGUAGE,
    DEDUPE_WINDOW_MINUTES,
    FUNNEL_TOKEN_EXPIRY_DAYS,
)
from .shared import clean, fail
from . import tokens


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


def upsert_lead_for_quote_request(request_data):
    first_name, last_name = split_prospect_name(request_data.prospect_name)
    lead_rows = frappe.get_all(
        "Lead",
        filters={
            "email_id": request_data.contact_email,
            "company_name": request_data.prospect_company,
            "disabled": 0,
        },
        fields=["name"],
        order_by="creation asc",
        limit=1,
    )

    if lead_rows:
        lead = frappe.get_doc("Lead", lead_rows[0].get("name"))
        lead_changed = 0
        if not clean(lead.get("first_name")) and first_name:
            lead.first_name = first_name
            lead_changed = 1
        if not clean(lead.get("last_name")) and last_name:
            lead.last_name = last_name
            lead_changed = 1
        if not clean(lead.get("email_id")) and request_data.contact_email:
            lead.email_id = request_data.contact_email
            lead_changed = 1
        if not clean(lead.get("phone")) and request_data.phone:
            lead.phone = request_data.phone
            lead_changed = 1
        if not clean(lead.get("company_name")) and request_data.prospect_company:
            lead.company_name = request_data.prospect_company
            lead_changed = 1
        if not clean(lead.get("company")):
            lead.company = DEFAULT_COMPANY
            lead_changed = 1
        if not clean(lead.get("country")):
            lead.country = DEFAULT_COUNTRY
            lead_changed = 1
        if not clean(lead.get("no_of_employees")):
            lead.no_of_employees = DEFAULT_EMPLOYEE_RANGE
            lead_changed = 1
        if clean(lead.get("status")) != "Opportunity":
            lead.status = "Opportunity"
            lead_changed = 1
        if lead_changed:
            lead.save(ignore_permissions=True)
        return lead

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


def build_quote_request_response(row, token, duplicate):
    opportunity_name = row.get("name")
    return InstantQuoteResponse(
        name=opportunity_name,
        opp=opportunity_name,
        low=float(row.get("custom_estimate_low") or 0),
        high=float(row.get("custom_estimate_high") or 0),
        risk=row.get("risk_level") or "",
        currency=row.get("currency") or DEFAULT_CURRENCY,
        final_price=float(row.get("opportunity_amount") or 0),
        token=token,
        duplicate=duplicate,
    ).model_dump(mode="python")


def create_instant_quote_opportunity(form_dict: Mapping[str, Any] | None = None):
    request_data = validate_and_normalize_quote_request(form_dict=form_dict)
    recent_cutoff = add_to_date(now(), minutes=-DEDUPE_WINDOW_MINUTES)
    existing_rows = frappe.get_all(
        "Opportunity",
        filters=[
            ["Opportunity", "creation", ">=", recent_cutoff],
            ["Opportunity", "contact_email", "=", request_data.contact_email],
            ["Opportunity", "prospect_name", "=", request_data.prospect_name],
            ["Opportunity", "prospect_company", "=", request_data.prospect_company],
            ["Opportunity", "building_type", "=", request_data.building_type],
            ["Opportunity", "building_size", "=", str(request_data.building_size)],
            ["Opportunity", "service_frequency", "=", request_data.service_frequency],
            ["Opportunity", "service_interest", "=", request_data.service_interest],
            ["Opportunity", "bathroom_count_range", "=", request_data.bathroom_count_range.value],
        ],
        fields=[
            "name",
            "custom_estimate_low",
            "custom_estimate_high",
            "risk_level",
            "currency",
            "opportunity_amount",
            "public_funnel_token",
            "public_funnel_token_expires_on",
        ],
        order_by="creation desc",
        limit=1,
    )

    if existing_rows:
        row = existing_rows[0]
        token = tokens.ensure_public_token(
            row.get("name"),
            row.get("public_funnel_token"),
            row.get("public_funnel_token_expires_on"),
        )
        return build_quote_request_response(row, token, duplicate=1)

    try:
        lead = upsert_lead_for_quote_request(request_data)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Instant Quote Opportunity - Lead Upsert")
        fail("We could not create your estimate right now. Please try again.")

    try:
        token = tokens.make_public_token()
        expires_on = add_to_date(now_datetime(), days=FUNNEL_TOKEN_EXPIRY_DAYS, as_datetime=True)
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
                "public_funnel_token": token,
                "public_funnel_token_expires_on": expires_on,
            }
        )
        opportunity.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Instant Quote Opportunity - Opportunity Insert")
        fail("We could not create your estimate right now. Please try again.")

    return build_quote_request_response(opportunity, token, duplicate=0)
