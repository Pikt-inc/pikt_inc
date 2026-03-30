from __future__ import annotations

import frappe

from pikt_inc.api._request_payload import collect_request_payload
from pikt_inc.services import public_intake as public_intake_service


@frappe.whitelist(allow_guest=True)
def create_instant_quote_opportunity(**kwargs):
    return public_intake_service.create_instant_quote_opportunity(form_dict=collect_request_payload(kwargs))


@frappe.whitelist(allow_guest=True)
def validate_public_funnel_opportunity(opportunity=None, token=None, **kwargs):
    payload = collect_request_payload({"opportunity": opportunity, "token": token, **kwargs})
    return public_intake_service.validate_public_funnel_opportunity(
        opportunity=payload.get("opportunity"),
        token=payload.get("token"),
    )


@frappe.whitelist(allow_guest=True)
def save_opportunity_walkthrough_upload(opportunity=None, token=None, **kwargs):
    payload = collect_request_payload({"opportunity": opportunity, "token": token, **kwargs})
    uploaded = None
    if getattr(frappe, "request", None) and getattr(frappe.request, "files", None):
        uploaded = frappe.request.files.get("walkthrough_upload")

    return public_intake_service.save_opportunity_walkthrough_upload(
        opportunity=payload.get("opportunity"),
        token=payload.get("token"),
        uploaded=uploaded,
    )
