from __future__ import annotations

from typing import Any, Mapping

import frappe
from pydantic import ValidationError

from pikt_inc.services.contracts.common import first_validation_message
from pikt_inc.services.contracts.contact_request import CONTACT_REQUEST_TYPE_OPTIONS
from pikt_inc.services.contracts.contact_request import ContactRequestInput
from pikt_inc.services.contracts.contact_request import ContactRequestSubmitted


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _throw(message: str):
    frappe.throw(message)


def validate_contact_request(form_dict: Mapping[str, Any] | None = None):
    try:
        return ContactRequestInput.model_validate(form_dict or frappe.form_dict)
    except ValidationError as exc:
        _throw(first_validation_message(exc))


def get_contact_request_values(request_data: ContactRequestInput) -> dict[str, str]:
    return {
        "first_name": request_data.first_name,
        "last_name": request_data.last_name,
        "email_id": request_data.email_id,
        "mobile_no": request_data.mobile_no,
        "company_name": request_data.company_name,
        "city": request_data.city,
        "request_type": request_data.request_type.value,
        "message": request_data.message,
    }


def get_contact_request_public_payload(source: Mapping[str, Any] | Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    getter = getattr(source, "get", None)
    for fieldname in (
        "first_name",
        "last_name",
        "email_id",
        "mobile_no",
        "company_name",
        "city",
        "request_type",
        "message",
    ):
        if callable(getter):
            payload[fieldname] = getter(fieldname)
        else:
            payload[fieldname] = getattr(source, fieldname, None)
    return payload


def prepare_contact_request(doc):
    request_data = validate_contact_request(form_dict=get_contact_request_public_payload(doc))
    values = get_contact_request_values(request_data)
    for fieldname, value in values.items():
        setattr(doc, fieldname, value)
    if not clean(doc.get("request_status")):
        doc.request_status = "New"
    return doc


def create_contact_request(form_dict: Mapping[str, Any] | None = None, **kwargs: Any):
    payload = dict(form_dict or {})
    for key, value in kwargs.items():
        payload.setdefault(key, value)

    request_data = validate_contact_request(form_dict=payload)
    try:
        doc = frappe.get_doc(
            {
                "doctype": "Contact Request",
                **get_contact_request_values(request_data),
                "request_status": "New",
            }
        )
        doc.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Contact Request")
        _throw("We could not submit the request. Please try again.")
    return doc


def submit_contact_request(form_dict: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
    request_doc = create_contact_request(form_dict=form_dict, **kwargs)
    return ContactRequestSubmitted(
        status="submitted",
        message="Thanks for reaching out. We received your message and will get back to you shortly.",
        request=clean(getattr(request_doc, "name", "")),
    ).model_dump(mode="python")
