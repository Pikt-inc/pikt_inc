from __future__ import annotations

import frappe

from pikt_inc.services import public_intake as public_intake_service


@frappe.whitelist(allow_guest=True)
def create_instant_quote_opportunity(**kwargs):
    return public_intake_service.create_instant_quote_opportunity(form_dict=kwargs or frappe.form_dict)


@frappe.whitelist(allow_guest=True)
def validate_public_funnel_opportunity(opportunity=None, token=None, **kwargs):
    return public_intake_service.validate_public_funnel_opportunity(
        opportunity=opportunity or kwargs.get("opportunity"),
        token=token or kwargs.get("token"),
    )


@frappe.whitelist(allow_guest=True)
def save_opportunity_walkthrough_upload(opportunity=None, token=None, **kwargs):
    uploaded = None
    if getattr(frappe, "request", None) and getattr(frappe.request, "files", None):
        uploaded = frappe.request.files.get("walkthrough_upload")

    return public_intake_service.save_opportunity_walkthrough_upload(
        opportunity=opportunity or kwargs.get("opportunity"),
        token=token or kwargs.get("token"),
        uploaded=uploaded,
    )
