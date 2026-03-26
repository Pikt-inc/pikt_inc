from __future__ import annotations

from typing import Any

import frappe
from pydantic import ValidationError

from pikt_inc.services.contracts.common import first_validation_message
from pikt_inc.services.contracts.contact_request import ContactRequestInput
from pikt_inc.services.contracts.contact_request import ContactRequestSubmitted
from pikt_inc.services.contracts.contact_request import CONTACT_REQUEST_TYPE_OPTIONS
from pikt_inc.services import public_quote as public_quote_service

DEFAULT_LEAD_REQUEST_TYPE_OPTIONS = (
    "",
    "Product Enquiry",
    "Request for Information",
    "Suggestions",
    "Other",
)

CONTACT_REQUEST_TYPE_TO_LEAD_VALUE = {
    "General service question": "Request for Information",
    "Walkthrough request": "Product Enquiry",
    "Custom scope or out-of-area request": "Product Enquiry",
    "Current customer support": "Other",
    "Careers or partner inquiry": "Other",
}


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _throw(message: str):
    frappe.throw(message)


def _lead_fieldnames() -> set[str]:
    get_meta = getattr(frappe, "get_meta", None)
    if callable(get_meta):
        try:
            meta = get_meta("Lead")
            fields = getattr(meta, "fields", []) or []
            return {clean(getattr(df, "fieldname", "")) for df in fields if clean(getattr(df, "fieldname", ""))}
        except Exception:
            pass

    return {
        "lead_name",
        "first_name",
        "last_name",
        "email_id",
        "mobile_no",
        "company_name",
        "city",
        "request_type",
        "service_interest",
        "source",
    }


def _lead_request_type_options() -> set[str]:
    get_meta = getattr(frappe, "get_meta", None)
    if callable(get_meta):
        try:
            meta = get_meta("Lead")
            fields = getattr(meta, "fields", []) or []
            for df in fields:
                if clean(getattr(df, "fieldname", "")) != "request_type":
                    continue
                options = {
                    clean(option)
                    for option in str(getattr(df, "options", "") or "").splitlines()
                }
                options.add("")
                cleaned = {option for option in options if option or option == ""}
                if cleaned:
                    return cleaned
        except Exception:
            pass

    return set(DEFAULT_LEAD_REQUEST_TYPE_OPTIONS)


def _map_request_type_for_lead(request_type: str, allowed_options: set[str]) -> str:
    request_type = clean(request_type)
    preferred = clean(CONTACT_REQUEST_TYPE_TO_LEAD_VALUE.get(request_type, request_type))
    candidates = (
        preferred,
        request_type,
        "Request for Information",
        "Product Enquiry",
        "Other",
    )
    for candidate in candidates:
        if clean(candidate) in allowed_options:
            return clean(candidate)
    return preferred or request_type


def _service_interest_message(request_type: str, lead_request_type: str, message: str) -> str:
    request_type = clean(request_type)
    lead_request_type = clean(lead_request_type)
    message = clean(message)
    if not request_type or not message or request_type == lead_request_type:
        return message
    return f"Requested contact type: {request_type}\n\n{message}"


def submit_contact_request(form_dict: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    payload = dict(form_dict or {})
    for key, value in kwargs.items():
        payload.setdefault(key, value)

    try:
        contact_request = ContactRequestInput.model_validate(payload)
    except ValidationError as exc:
        _throw(first_validation_message(exc))

    if not public_quote_service.valid_email(contact_request.email_id):
        _throw("Enter a valid email address.")

    fieldnames = _lead_fieldnames()
    request_type = str(contact_request.request_type.value)
    lead_request_type = _map_request_type_for_lead(request_type, _lead_request_type_options())
    full_name = " ".join(part for part in (contact_request.first_name, contact_request.last_name) if part).strip()
    lead_payload = {"doctype": "Lead"}

    def set_if_available(fieldname: str, value: Any):
        if fieldname in fieldnames and value not in (None, ""):
            lead_payload[fieldname] = value

    set_if_available("lead_name", contact_request.company_name or full_name)
    set_if_available("first_name", contact_request.first_name)
    set_if_available("last_name", contact_request.last_name)
    set_if_available("email_id", contact_request.email_id)
    set_if_available("mobile_no", contact_request.mobile_no)
    set_if_available("company_name", contact_request.company_name)
    set_if_available("city", contact_request.city)
    set_if_available("request_type", lead_request_type)
    set_if_available(
        "service_interest",
        _service_interest_message(request_type, lead_request_type, contact_request.message),
    )
    set_if_available("source", "Contact Form")

    lead_doc = frappe.get_doc(lead_payload)
    lead_doc.insert(ignore_permissions=True)
    return ContactRequestSubmitted(
        status="submitted",
        message="Thanks for reaching out. We received your message and will get back to you shortly.",
        lead=clean(getattr(lead_doc, "name", "")),
    ).model_dump(mode="python")
