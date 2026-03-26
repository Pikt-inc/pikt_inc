from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import getdate, now_datetime

from .models import AgreementSignatureInput
from .payloads import (
    build_service_agreement_signature_response,
    get_existing_service_agreement_signature_response,
    get_term_label,
    render_template_html,
)
from .portal import ensure_quote_is_valid_for_portal_write
from .queries import get_active_master_agreement, get_active_template, get_addendum_row, get_customer_row, get_sales_order_row
from .shared import (
    begin_savepoint,
    calculate_end_date,
    clean,
    doc_db_set_values,
    fail,
    get_request_ip,
    get_traceback_text,
    get_user_agent,
    lock_document_row,
    make_unique_name,
    release_savepoint,
    rollback_savepoint,
    valid_email,
)

def link_quote_agreement_records(master_name, addendum_name, quote_row, sales_order_row):
    master_name = clean(master_name)
    addendum_name = clean(addendum_name)
    quote_name = clean((quote_row or {}).get("name"))
    sales_order_name = clean((sales_order_row or {}).get("name"))
    opportunity_name = clean((quote_row or {}).get("opportunity"))

    if opportunity_name and frappe.db.exists("Opportunity", opportunity_name):
        doc_db_set_values(
            "Opportunity",
            opportunity_name,
            {"custom_service_agreement": master_name},
        )
    if quote_name and frappe.db.exists("Quotation", quote_name):
        doc_db_set_values(
            "Quotation",
            quote_name,
            {
                "custom_service_agreement": master_name,
                "custom_service_agreement_addendum": addendum_name,
            },
        )
    if sales_order_name and frappe.db.exists("Sales Order", sales_order_name):
        doc_db_set_values(
            "Sales Order",
            sales_order_name,
            {
                "custom_service_agreement": master_name,
                "custom_service_agreement_addendum": addendum_name,
            },
        )

def complete_public_service_agreement_signature(quote=None, token=None, **kwargs):
    payload = AgreementSignatureInput.from_request(quote=quote, token=token, **kwargs)
    quote_name = payload.quote
    token = payload.token
    signer_name = payload.signer_name
    signer_title = payload.signer_title
    signer_email = payload.signer_email
    assent_confirmed = payload.assent_confirmed
    term_model = payload.term_model
    fixed_term_months = payload.fixed_term_months
    start_date = payload.start_date

    if not quote_name:
        fail("Missing quotation reference. Please return to your quote email and try again.")
    if not token:
        fail("Missing secure access token. Please return to your quote email and try again.")
    if not signer_name:
        fail("Signer name is required.")
    if not signer_title:
        fail("Signer title is required.")
    if not valid_email(signer_email):
        fail("Enter a valid signer email address.")
    if term_model not in ("Month-to-month", "Fixed"):
        fail("Select a term for this agreement.")
    if term_model == "Fixed" and fixed_term_months not in ("3", "6", "12"):
        fail("Select a fixed term length of 3, 6, or 12 months.")
    if not start_date:
        fail("Agreement start date is required.")
    try:
        getdate(start_date)
    except Exception:
        fail("Enter a valid agreement start date.")
    if not assent_confirmed:
        fail("Please confirm that you agree to the service agreement terms.")

    quote_row = ensure_quote_is_valid_for_portal_write(
        quote_name,
        token,
        "This quotation has been cancelled and can no longer be updated.",
        "This quotation is not ready for service agreement setup.",
    )
    sales_order_name = clean(quote_row.get("custom_accepted_sales_order"))
    if not sales_order_name or not frappe.db.exists("Sales Order", sales_order_name):
        fail("We could not prepare the agreement for this quote. Please reload the page or contact our team.")

    sales_order_row = get_sales_order_row(sales_order_name)
    customer_name = clean(sales_order_row.get("customer"))
    if not customer_name or not frappe.db.exists("Customer", customer_name):
        fail("We could not resolve the customer for this agreement. Please contact our team.")

    customer_row = get_customer_row(customer_name)
    customer_display = (
        clean(customer_row.get("customer_name"))
        or clean(sales_order_row.get("customer_name"))
        or customer_name
    )

    existing_response = get_existing_service_agreement_signature_response(
        quote_name,
        sales_order_name,
        quote_row=quote_row,
        sales_order_row=sales_order_row,
    )
    if existing_response:
        return existing_response

    active_master = get_active_master_agreement(customer_name)
    master_name = clean(active_master.get("name"))
    master_template = get_active_template("Master")
    addendum_template = get_active_template("Addendum")
    if not clean(master_template.get("name")):
        fail("No active master service agreement template is available yet.")
    if not clean(addendum_template.get("name")):
        fail("No active service agreement addendum template is available yet.")

    signer_ip = get_request_ip()
    signer_user_agent = get_user_agent()
    signed_on = now_datetime()
    end_date = calculate_end_date(start_date, term_model, fixed_term_months)
    replacements = {
        "customer_name": customer_display,
        "quote_name": quote_name,
        "sales_order_name": sales_order_name,
        "start_date": start_date,
        "term_label": get_term_label(term_model, fixed_term_months),
    }
    savepoint_name = begin_savepoint("service_agreement_signature")

    try:
        lock_document_row("Sales Order", sales_order_name)
        sales_order_row = get_sales_order_row(sales_order_name)
        existing_response = get_existing_service_agreement_signature_response(
            quote_name,
            sales_order_name,
            quote_row=quote_row,
            sales_order_row=sales_order_row,
        )
        if existing_response:
            release_savepoint(savepoint_name)
            return existing_response

        if not master_name:
            master_doc = frappe.get_doc(
                {
                    "doctype": "Service Agreement",
                    "agreement_name": make_unique_name(
                        "Service Agreement",
                        customer_display + " - Master Agreement",
                    ),
                    "customer": customer_name,
                    "status": "Active",
                    "template": clean(master_template.get("name")),
                    "template_version": clean(master_template.get("version")),
                    "rendered_html_snapshot": render_template_html(
                        master_template.get("body_html"),
                        replacements,
                    ),
                    "signed_by_name": signer_name,
                    "signed_by_title": signer_title,
                    "signed_by_email": signer_email,
                    "signed_on": signed_on,
                    "signer_ip": signer_ip,
                    "signer_user_agent": signer_user_agent,
                }
            )
            master_doc.flags.ignore_permissions = True
            master_doc.insert(ignore_permissions=True)
            master_name = master_doc.name

        addendum_doc = frappe.get_doc(
            {
                "doctype": "Service Agreement Addendum",
                "addendum_name": make_unique_name(
                    "Service Agreement Addendum",
                    customer_display + " - " + quote_name + " Addendum",
                ),
                "service_agreement": master_name,
                "customer": customer_name,
                "quotation": quote_name,
                "sales_order": sales_order_name,
                "status": "Pending Billing",
                "term_model": term_model,
                "fixed_term_months": fixed_term_months if term_model == "Fixed" else "",
                "start_date": start_date,
                "end_date": end_date,
                "template": clean(addendum_template.get("name")),
                "template_version": clean(addendum_template.get("version")),
                "rendered_html_snapshot": render_template_html(
                    addendum_template.get("body_html"),
                    replacements,
                ),
                "signed_by_name": signer_name,
                "signed_by_title": signer_title,
                "signed_by_email": signer_email,
                "signed_on": signed_on,
                "signer_ip": signer_ip,
                "signer_user_agent": signer_user_agent,
            }
        )
        addendum_doc.flags.ignore_permissions = True
        addendum_doc.insert(ignore_permissions=True)

        link_quote_agreement_records(master_name, addendum_doc.name, quote_row, sales_order_row)
        release_savepoint(savepoint_name)
        return build_service_agreement_signature_response(
            master_name,
            addendum_doc.name,
            "Pending Billing",
            start_date,
            end_date,
            term_model,
            fixed_term_months if term_model == "Fixed" else "",
        )
    except Exception:
        rollback_savepoint(savepoint_name)
        existing_response = get_existing_service_agreement_signature_response(
            quote_name,
            sales_order_name,
            quote_row=quote_row,
            sales_order_row=sales_order_row,
        )
        if existing_response:
            return existing_response
        frappe.log_error(get_traceback_text(), "Complete Public Service Agreement Signature")
        fail("We could not save the service agreement right now. Please try again or contact our team.")

__all__ = [
    "link_quote_agreement_records",
    "complete_public_service_agreement_signature",
]
