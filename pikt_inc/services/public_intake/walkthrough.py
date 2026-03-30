from __future__ import annotations

import frappe
from pydantic import ValidationError
from frappe.utils import now

from pikt_inc.services.contracts.common import first_validation_message
from pikt_inc.services.contracts.public_intake import WalkthroughUploadInput
from pikt_inc.services.contracts.public_intake import WalkthroughUploadResponse
from .constants import ALLOWED_WALKTHROUGH_EXTENSIONS, MAX_WALKTHROUGH_BYTES
from .shared import clean, fail
from . import intake


def save_opportunity_walkthrough_upload(request=None, token=None, uploaded=None):
    uploaded = uploaded or (
        frappe.request.files.get("walkthrough_upload")
        if getattr(frappe, "request", None) and getattr(frappe.request, "files", None)
        else None
    )
    try:
        payload = WalkthroughUploadInput.model_validate(
            {
                "request": request if request is not None else frappe.form_dict.get("request"),
                "token": token if token is not None else frappe.form_dict.get("token"),
                "uploaded": uploaded,
            }
        )
    except ValidationError as exc:
        fail(first_validation_message(exc))
    request_name = payload.request
    token = payload.token
    uploaded = payload.uploaded

    request_row = intake.require_valid_public_quote_request(request_name, token)
    opportunity = clean((request_row or {}).get("opportunity"))
    if not opportunity:
        fail("We could not reopen that estimate request. Please start a new quote request and try again.")

    file_name = clean(getattr(uploaded, "filename", "")) or "digital-walkthrough-upload"
    extension = ""
    if "." in file_name:
        extension = file_name.rsplit(".", 1)[1].lower().strip()

    if not extension or extension not in ALLOWED_WALKTHROUGH_EXTENSIONS:
        fail("We could not read that file. Please upload a standard image, video, or document under 100 MB.")

    content = uploaded.read()
    if not content:
        fail("Uploaded file was empty. Please choose the file again.")
    if len(content) > MAX_WALKTHROUGH_BYTES:
        fail("That file is larger than the 100 MB upload limit. Please choose a smaller file.")

    existing_files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Opportunity",
            "attached_to_name": opportunity,
            "attached_to_field": "digital_walkthrough_file",
        },
        fields=["name", "file_url"],
    )

    try:
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": file_name,
                "is_private": 1,
                "attached_to_doctype": "Opportunity",
                "attached_to_name": opportunity,
                "attached_to_field": "digital_walkthrough_file",
                "content": content,
            }
        )
        file_doc.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Save Opportunity Walkthrough Upload")
        fail("We could not read that file. Please upload a standard image, video, or document under 100 MB.")

    try:
        doc = frappe.get_doc("Opportunity", opportunity)
        doc.digital_walkthrough_file = file_doc.file_url
        doc.digital_walkthrough_status = "Submitted"
        doc.digital_walkthrough_received_on = now()
        doc.latest_digital_walkthrough = ""
        doc.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Save Opportunity Walkthrough Upload - Opportunity Update")
        fail("We could not attach the walkthrough to your estimate. Please try again.")

    for existing in existing_files:
        if existing.get("name") and existing.get("name") != file_doc.name:
            try:
                old_file = frappe.get_doc("File", existing.get("name"))
                old_file.delete(ignore_permissions=True)
            except Exception:
                frappe.log_error(frappe.get_traceback(), "Cleanup Replaced Walkthrough File")

    return WalkthroughUploadResponse(
        request=clean((request_row or {}).get("name")) or request_name,
        digital_walkthrough_file=doc.digital_walkthrough_file,
        digital_walkthrough_status=doc.digital_walkthrough_status,
        digital_walkthrough_received_on=clean(doc.digital_walkthrough_received_on),
    ).model_dump(mode="python")
