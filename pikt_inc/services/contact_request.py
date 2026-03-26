from __future__ import annotations

from typing import Any

import frappe
from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from pikt_inc.services import public_quote as public_quote_service


CONTACT_REQUEST_TYPE_OPTIONS = (
    "General service question",
    "Walkthrough request",
    "Custom scope or out-of-area request",
    "Current customer support",
    "Careers or partner inquiry",
)

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


def _first_validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid request payload."
    return clean(errors[0].get("msg")) or "Invalid request payload."


class ContactRequestInput(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, validate_default=True)

    first_name: str = ""
    last_name: str = ""
    email_id: str = ""
    mobile_no: str = ""
    company_name: str = ""
    city: str = ""
    request_type: str = ""
    message: str = ""

    @field_validator(
        "first_name",
        "last_name",
        "email_id",
        "mobile_no",
        "company_name",
        "city",
        "request_type",
        "message",
        mode="before",
    )
    @classmethod
    def clean_strings(cls, value: Any) -> str:
        return clean(value)

    @field_validator("first_name")
    @classmethod
    def validate_first_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Enter your first name.")
        return value

    @field_validator("last_name")
    @classmethod
    def validate_last_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Enter your last name.")
        return value

    @field_validator("email_id")
    @classmethod
    def validate_email(cls, value: str) -> str:
        lowered = clean(value).lower()
        if not public_quote_service.valid_email(lowered):
            raise ValueError("Enter a valid email address.")
        return lowered

    @field_validator("company_name")
    @classmethod
    def validate_company_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Enter your company name.")
        return value

    @field_validator("city")
    @classmethod
    def validate_city(cls, value: str) -> str:
        if not value:
            raise ValueError("Enter the city where the request is based.")
        return value

    @field_validator("request_type")
    @classmethod
    def validate_request_type(cls, value: str) -> str:
        if not value:
            raise ValueError("Choose the request type that fits best.")
        if value not in CONTACT_REQUEST_TYPE_OPTIONS:
            raise ValueError("Choose a valid request type.")
        return value

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if not value:
            raise ValueError("Tell us a little more about the request.")
        return value


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
        _throw(_first_validation_message(exc))

    fieldnames = _lead_fieldnames()
    lead_request_type = _map_request_type_for_lead(contact_request.request_type, _lead_request_type_options())
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
        _service_interest_message(contact_request.request_type, lead_request_type, contact_request.message),
    )
    set_if_available("source", "Contact Form")

    lead_doc = frappe.get_doc(lead_payload)
    lead_doc.insert(ignore_permissions=True)

    return {
        "status": "submitted",
        "message": "Thanks for reaching out. We received your message and will get back to you shortly.",
        "lead": clean(getattr(lead_doc, "name", "")),
    }
