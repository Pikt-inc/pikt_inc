from __future__ import annotations

from typing import Any

import frappe

from pikt_inc.services import public_quote as public_quote_service


CONTACT_REQUEST_TYPE_OPTIONS = (
    "General service question",
    "Walkthrough request",
    "Custom scope or out-of-area request",
    "Current customer support",
    "Careers or partner inquiry",
)


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


def submit_contact_request(form_dict: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    payload = dict(form_dict or {})
    for key, value in kwargs.items():
        payload.setdefault(key, value)

    first_name = clean(payload.get("first_name"))
    last_name = clean(payload.get("last_name"))
    email_id = clean(payload.get("email_id")).lower()
    mobile_no = clean(payload.get("mobile_no"))
    company_name = clean(payload.get("company_name"))
    city = clean(payload.get("city"))
    request_type = clean(payload.get("request_type"))
    message = clean(payload.get("message"))

    if not first_name:
        _throw("Enter your first name.")
    if not last_name:
        _throw("Enter your last name.")
    if not public_quote_service.valid_email(email_id):
        _throw("Enter a valid email address.")
    if not company_name:
        _throw("Enter your company name.")
    if not city:
        _throw("Enter the city where the request is based.")
    if not request_type:
        _throw("Choose the request type that fits best.")
    if request_type not in CONTACT_REQUEST_TYPE_OPTIONS:
        _throw("Choose a valid request type.")
    if not message:
        _throw("Tell us a little more about the request.")

    fieldnames = _lead_fieldnames()
    full_name = " ".join(part for part in (first_name, last_name) if part).strip()
    lead_payload = {"doctype": "Lead"}

    def set_if_available(fieldname: str, value: Any):
        if fieldname in fieldnames and value not in (None, ""):
            lead_payload[fieldname] = value

    set_if_available("lead_name", company_name or full_name)
    set_if_available("first_name", first_name)
    set_if_available("last_name", last_name)
    set_if_available("email_id", email_id)
    set_if_available("mobile_no", mobile_no)
    set_if_available("company_name", company_name)
    set_if_available("city", city)
    set_if_available("request_type", request_type)
    set_if_available("service_interest", message)
    set_if_available("source", "Contact Form")

    lead_doc = frappe.get_doc(lead_payload)
    lead_doc.insert(ignore_permissions=True)

    return {
        "status": "submitted",
        "message": "Thanks for reaching out. We received your message and will get back to you shortly.",
        "lead": clean(getattr(lead_doc, "name", "")),
    }
