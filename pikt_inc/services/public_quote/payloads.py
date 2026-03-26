from __future__ import annotations

from typing import Any

import frappe

from .constants import DEFAULT_COUNTRY, DEFAULT_CURRENCY
from .models import (
    AccessSetupResponse,
    BillingSetupResponse,
    ServiceAgreementSignatureResponse,
    ValidateQuotePayload,
)
from .queries import (
    get_active_master_agreement,
    get_active_template,
    get_addendum_row,
    get_address_row,
    get_building_row,
    get_contact_row,
    get_customer_row,
    get_lead_row,
    get_quote_row,
    get_sales_order_row,
    load_accept_items,
)
from .shared import clean

def render_template_html(html, replacements):
    output = html or ""
    for key, value in (replacements or {}).items():
        output = output.replace("{{%s}}" % clean(key), clean(value))
    return output

def get_term_label(term_model, fixed_term_months):
    if clean(term_model) == "Fixed" and clean(fixed_term_months):
        return "Fixed %s months" % clean(fixed_term_months)
    return "Month-to-month"

def build_context(row):
    customer_row = {}
    lead_name = ""
    quotation_to = clean((row or {}).get("quotation_to"))
    if quotation_to == "Lead":
        lead_name = clean((row or {}).get("party_name"))
    elif quotation_to == "Customer":
        customer_row = get_customer_row((row or {}).get("party_name"))
        lead_name = clean(customer_row.get("lead_name"))

    lead_row = get_lead_row(lead_name)
    return {
        "customer_row": customer_row,
        "lead_row": lead_row,
        "lead_name": lead_name,
    }

def apply_review_building_payload(payload, sales_order_row):
    building_row = get_building_row((sales_order_row or {}).get("custom_building"))
    if building_row:
        payload.update(
            {
                "building": clean(building_row.get("name")),
                "building_name": clean(building_row.get("building_name")) or clean(building_row.get("name")),
                "service_address_line_1": clean(building_row.get("address_line_1")),
                "service_address_line_2": clean(building_row.get("address_line_2")),
                "service_city": clean(building_row.get("city")),
                "service_state": clean(building_row.get("state")),
                "service_postal_code": clean(building_row.get("postal_code")),
                "access_method": clean(building_row.get("access_method")),
                "access_entrance": clean(building_row.get("access_entrance")),
                "access_entry_details": clean(building_row.get("access_entry_details")),
                "has_alarm_system": clean(building_row.get("has_alarm_system")) or "No",
                "alarm_instructions": clean(building_row.get("alarm_instructions")),
                "allowed_entry_time": clean(building_row.get("allowed_entry_time")),
                "primary_site_contact": clean(building_row.get("primary_site_contact")),
                "lockout_emergency_contact": clean(building_row.get("lockout_emergency_contact")),
                "key_fob_handoff_details": clean(building_row.get("key_fob_handoff_details")),
                "areas_to_avoid": clean(building_row.get("areas_to_avoid")),
                "closing_instructions": clean(building_row.get("closing_instructions")),
                "parking_elevator_notes": clean(building_row.get("parking_elevator_notes")),
                "first_service_notes": clean(building_row.get("first_service_notes")),
                "access_details_confirmed": int(building_row.get("access_details_confirmed") or 0),
                "access_details_completed_on": clean(building_row.get("access_details_completed_on")),
            }
        )
        return

    payload.update(
        {
            "access_method": clean((sales_order_row or {}).get("custom_access_method")),
            "access_entrance": clean((sales_order_row or {}).get("custom_access_entrance")),
            "access_entry_details": clean((sales_order_row or {}).get("custom_access_entry_details")),
            "has_alarm_system": clean((sales_order_row or {}).get("custom_has_alarm_system")) or "No",
            "alarm_instructions": clean((sales_order_row or {}).get("custom_alarm_instructions")),
            "allowed_entry_time": clean((sales_order_row or {}).get("custom_allowed_entry_time")),
            "primary_site_contact": clean((sales_order_row or {}).get("custom_primary_site_contact")),
            "lockout_emergency_contact": clean(
                (sales_order_row or {}).get("custom_lockout_emergency_contact")
            ),
            "key_fob_handoff_details": clean(
                (sales_order_row or {}).get("custom_key_fob_handoff_details")
            ),
            "areas_to_avoid": clean((sales_order_row or {}).get("custom_areas_to_avoid")),
            "closing_instructions": clean((sales_order_row or {}).get("custom_closing_instructions")),
            "parking_elevator_notes": clean(
                (sales_order_row or {}).get("custom_parking_elevator_notes")
            ),
            "first_service_notes": clean((sales_order_row or {}).get("custom_first_service_notes")),
            "access_details_confirmed": int(
                (sales_order_row or {}).get("custom_access_details_confirmed") or 0
            ),
            "access_details_completed_on": clean(
                (sales_order_row or {}).get("custom_access_details_completed_on")
            ),
        }
    )

def build_validate_payload(state, message="", row=None, items=None):
    payload = {
        "state": state,
        "message": message,
    }
    if not row:
        return payload

    context = build_context(row)
    customer_row = context.get("customer_row") or {}
    lead_row = context.get("lead_row") or {}
    lead_name = clean(context.get("lead_name"))
    company_name = (
        clean(row.get("customer_name"))
        or clean(customer_row.get("customer_name"))
        or clean(lead_row.get("company_name"))
        or clean(row.get("party_name"))
    )
    contact_name = ("%s %s" % (clean(lead_row.get("first_name")), clean(lead_row.get("last_name")))).strip()
    if not contact_name:
        contact_name = company_name

    sales_order_row = get_sales_order_row(row.get("custom_accepted_sales_order"))
    payload.update(
        {
            "quote": clean(row.get("name")),
            "lead": lead_name,
            "company_name": company_name,
            "contact_name": contact_name,
            "contact_email": clean(row.get("contact_email"))
            or clean(customer_row.get("email_id"))
            or clean(lead_row.get("email_id")),
            "currency": clean(row.get("currency")) or DEFAULT_CURRENCY,
            "grand_total": row.get("grand_total") or 0,
            "rounded_total": row.get("rounded_total") or row.get("grand_total") or 0,
            "transaction_date": row.get("transaction_date"),
            "valid_till": row.get("valid_till"),
            "terms": row.get("terms") or "",
            "sales_order": clean(row.get("custom_accepted_sales_order")),
            "initial_invoice": clean(sales_order_row.get("custom_initial_invoice")),
            "billing_setup_completed_on": clean(sales_order_row.get("custom_billing_setup_completed_on")),
            "billing_recipient_email": clean(sales_order_row.get("custom_billing_recipient_email")),
            "building": clean(sales_order_row.get("custom_building")),
            "building_name": "",
            "service_address_line_1": "",
            "service_address_line_2": "",
            "service_city": "",
            "service_state": "",
            "service_postal_code": "",
            "access_method": "",
            "access_entrance": "",
            "access_entry_details": "",
            "has_alarm_system": "No",
            "alarm_instructions": "",
            "allowed_entry_time": "",
            "primary_site_contact": "",
            "lockout_emergency_contact": "",
            "key_fob_handoff_details": "",
            "areas_to_avoid": "",
            "closing_instructions": "",
            "parking_elevator_notes": "",
            "first_service_notes": "",
            "access_details_confirmed": 0,
            "access_details_completed_on": "",
            "items": items or [],
        }
    )
    apply_review_building_payload(payload, sales_order_row)
    return ValidateQuotePayload.model_validate(payload).model_dump()

def build_accept_portal_payload(sales_order_name):
    payload = {
        "billing_setup_completed_on": "",
        "initial_invoice": "",
        "billing_recipient_email": "",
        "billing_contact_name": "",
        "billing_email": "",
        "billing_address_line_1": "",
        "billing_address_line_2": "",
        "billing_city": "",
        "billing_state": "",
        "billing_postal_code": "",
        "billing_country": DEFAULT_COUNTRY,
        "po_number": "",
        "tax_id": "",
        "billing_notes": "",
        "building": "",
        "building_name": "",
        "service_address_line_1": "",
        "service_address_line_2": "",
        "service_city": "",
        "service_state": "",
        "service_postal_code": "",
        "access_method": "",
        "access_entrance": "",
        "access_entry_details": "",
        "has_alarm_system": "No",
        "alarm_instructions": "",
        "allowed_entry_time": "",
        "primary_site_contact": "",
        "lockout_emergency_contact": "",
        "key_fob_handoff_details": "",
        "areas_to_avoid": "",
        "closing_instructions": "",
        "parking_elevator_notes": "",
        "first_service_notes": "",
        "access_details_confirmed": 0,
        "access_details_completed_on": "",
    }

    sales_order_row = get_sales_order_row(sales_order_name)
    if not sales_order_row:
        return payload

    customer_row = get_customer_row(sales_order_row.get("customer"))
    contact_name = clean(sales_order_row.get("contact_person")) or clean(
        customer_row.get("customer_primary_contact")
    )
    address_name = clean(sales_order_row.get("customer_address")) or clean(
        customer_row.get("customer_primary_address")
    )
    contact_row = get_contact_row(contact_name)
    address_row = get_address_row(address_name)
    building_row = get_building_row(sales_order_row.get("custom_building"))

    payload.update(
        {
            "billing_setup_completed_on": clean(sales_order_row.get("custom_billing_setup_completed_on")),
            "initial_invoice": clean(sales_order_row.get("custom_initial_invoice")),
            "billing_recipient_email": clean(sales_order_row.get("custom_billing_recipient_email")),
            "billing_contact_name": clean(contact_row.get("full_name")),
            "billing_email": clean(sales_order_row.get("custom_billing_recipient_email"))
            or clean(sales_order_row.get("contact_email"))
            or clean(contact_row.get("email_id"))
            or clean(customer_row.get("email_id")),
            "billing_address_line_1": clean(address_row.get("address_line1")),
            "billing_address_line_2": clean(address_row.get("address_line2")),
            "billing_city": clean(address_row.get("city")),
            "billing_state": clean(address_row.get("state")),
            "billing_postal_code": clean(address_row.get("pincode")),
            "billing_country": clean(address_row.get("country")) or DEFAULT_COUNTRY,
            "po_number": clean(sales_order_row.get("po_no")),
            "tax_id": clean(customer_row.get("tax_id")),
            "billing_notes": clean(sales_order_row.get("custom_public_billing_notes")),
        }
    )

    if building_row:
        payload.update(
            {
                "building": clean(building_row.get("name")),
                "building_name": clean(building_row.get("building_name")) or clean(building_row.get("name")),
                "service_address_line_1": clean(building_row.get("address_line_1")),
                "service_address_line_2": clean(building_row.get("address_line_2")),
                "service_city": clean(building_row.get("city")),
                "service_state": clean(building_row.get("state")),
                "service_postal_code": clean(building_row.get("postal_code")),
                "access_method": clean(building_row.get("access_method")),
                "access_entrance": clean(building_row.get("access_entrance")),
                "access_entry_details": clean(building_row.get("access_entry_details")),
                "has_alarm_system": clean(building_row.get("has_alarm_system")) or "No",
                "alarm_instructions": clean(building_row.get("alarm_instructions")),
                "allowed_entry_time": clean(building_row.get("allowed_entry_time")),
                "primary_site_contact": clean(building_row.get("primary_site_contact")),
                "lockout_emergency_contact": clean(building_row.get("lockout_emergency_contact")),
                "key_fob_handoff_details": clean(building_row.get("key_fob_handoff_details")),
                "areas_to_avoid": clean(building_row.get("areas_to_avoid")),
                "closing_instructions": clean(building_row.get("closing_instructions")),
                "parking_elevator_notes": clean(building_row.get("parking_elevator_notes")),
                "first_service_notes": clean(building_row.get("first_service_notes")),
                "access_details_confirmed": int(building_row.get("access_details_confirmed") or 0),
                "access_details_completed_on": clean(building_row.get("access_details_completed_on")),
            }
        )
        return payload

    if int(sales_order_row.get("custom_access_details_confirmed") or 0) != 1 and not clean(
        sales_order_row.get("custom_access_details_completed_on")
    ):
        return payload

    payload.update(
        {
            "access_method": clean(sales_order_row.get("custom_access_method")),
            "access_entrance": clean(sales_order_row.get("custom_access_entrance")),
            "access_entry_details": clean(sales_order_row.get("custom_access_entry_details")),
            "has_alarm_system": clean(sales_order_row.get("custom_has_alarm_system")) or "No",
            "alarm_instructions": clean(sales_order_row.get("custom_alarm_instructions")),
            "allowed_entry_time": clean(sales_order_row.get("custom_allowed_entry_time")),
            "primary_site_contact": clean(sales_order_row.get("custom_primary_site_contact")),
            "lockout_emergency_contact": clean(
                sales_order_row.get("custom_lockout_emergency_contact")
            ),
            "key_fob_handoff_details": clean(sales_order_row.get("custom_key_fob_handoff_details")),
            "areas_to_avoid": clean(sales_order_row.get("custom_areas_to_avoid")),
            "closing_instructions": clean(sales_order_row.get("custom_closing_instructions")),
            "parking_elevator_notes": clean(sales_order_row.get("custom_parking_elevator_notes")),
            "first_service_notes": clean(sales_order_row.get("custom_first_service_notes")),
            "access_details_confirmed": int(
                sales_order_row.get("custom_access_details_confirmed") or 0
            ),
            "access_details_completed_on": clean(sales_order_row.get("custom_access_details_completed_on")),
        }
    )
    return payload

def build_accept_payload(state, message="", row=None, items=None, sales_order_name=""):
    accepted_sales_order = clean(sales_order_name) or clean((row or {}).get("custom_accepted_sales_order"))
    payload = {
        "state": state,
        "message": message,
        "sales_order": accepted_sales_order,
    }
    if not row:
        return payload

    context = build_context(row)
    customer_row = context.get("customer_row") or {}
    lead_row = context.get("lead_row") or {}
    lead_name = clean(context.get("lead_name"))
    company_name = (
        clean(row.get("customer_name"))
        or clean(customer_row.get("customer_name"))
        or clean(lead_row.get("company_name"))
        or clean(row.get("party_name"))
    )
    contact_name = ("%s %s" % (clean(lead_row.get("first_name")), clean(lead_row.get("last_name")))).strip()
    if not contact_name:
        contact_name = company_name

    payload.update(
        {
            "quote": clean(row.get("name")),
            "lead": lead_name,
            "company_name": company_name,
            "contact_name": contact_name,
            "contact_email": clean(row.get("contact_email"))
            or clean(customer_row.get("email_id"))
            or clean(lead_row.get("email_id")),
            "currency": clean(row.get("currency")) or DEFAULT_CURRENCY,
            "grand_total": row.get("grand_total") or 0,
            "rounded_total": row.get("rounded_total") or row.get("grand_total") or 0,
            "transaction_date": row.get("transaction_date"),
            "valid_till": row.get("valid_till"),
            "terms": row.get("terms") or "",
            "items": items or [],
        }
    )
    payload.update(build_accept_portal_payload(accepted_sales_order))
    return payload

def get_existing_accept_response(
    quote_name,
    row=None,
    message="This quotation has already been accepted.",
    sales_order_name="",
):
    from .acceptance import mark_opportunity_converted

    quote_name = clean(quote_name) or clean((row or {}).get("name"))
    row = row or get_quote_row(quote_name)
    sales_order_name = clean(sales_order_name) or clean((row or {}).get("custom_accepted_sales_order"))
    if sales_order_name and frappe.db.exists("Sales Order", sales_order_name):
        mark_opportunity_converted((row or {}).get("opportunity"))
        return build_accept_payload(
            "accepted",
            message,
            row=row,
            items=load_accept_items(quote_name),
            sales_order_name=sales_order_name,
        )
    return None

def resolve_customer_name(row, sales_order_row):
    customer_name = clean((sales_order_row or {}).get("customer"))
    if customer_name:
        return customer_name
    if clean((row or {}).get("quotation_to")) == "Customer":
        return clean((row or {}).get("party_name"))
    return ""

def build_agreement_payload(row, sales_order_row):
    quote_name = clean((row or {}).get("name"))
    sales_order_name = clean((sales_order_row or {}).get("name"))
    customer_name = resolve_customer_name(row, sales_order_row)
    customer_row = get_customer_row(customer_name)
    customer_display = (
        clean(customer_row.get("customer_name"))
        or clean((sales_order_row or {}).get("customer_name"))
        or clean((row or {}).get("customer_name"))
        or customer_name
    )
    active_master = get_active_master_agreement(customer_name)
    addendum_row = get_addendum_row(quote_name, sales_order_name)

    template_row = {}
    agreement_mode = ""
    if clean(addendum_row.get("name")):
        agreement_mode = "signed"
    elif clean(active_master.get("name")):
        agreement_mode = "addendum"
        template_row = get_active_template("Addendum")
    else:
        agreement_mode = "master"
        template_row = get_active_template("Master")

    term_model = clean(addendum_row.get("term_model"))
    fixed_term_months = clean(addendum_row.get("fixed_term_months"))
    start_date = clean(addendum_row.get("start_date"))
    end_date = clean(addendum_row.get("end_date"))
    term_label = get_term_label(term_model, fixed_term_months)
    replacements = {
        "customer_name": customer_display,
        "quote_name": quote_name,
        "sales_order_name": sales_order_name,
        "start_date": start_date,
        "term_label": term_label,
    }
    template_html = render_template_html(template_row.get("body_html"), replacements)

    agreement_step_complete = 1 if clean(addendum_row.get("name")) else 0
    billing_step_complete = 1 if (
        clean(addendum_row.get("billing_completed_on"))
        or clean((sales_order_row or {}).get("custom_billing_setup_completed_on"))
    ) else 0
    access_step_complete = 1 if (
        clean(addendum_row.get("access_completed_on"))
        or clean((sales_order_row or {}).get("custom_access_details_completed_on"))
    ) else 0

    return {
        "service_agreement": clean(active_master.get("name")) or clean(addendum_row.get("service_agreement")),
        "service_agreement_status": clean(active_master.get("status")) or "Pending Signature",
        "service_agreement_addendum": clean(addendum_row.get("name")),
        "service_agreement_addendum_status": clean(addendum_row.get("status")),
        "has_active_service_agreement": 1 if clean(active_master.get("name")) else 0,
        "agreement_mode": agreement_mode,
        "agreement_step_complete": agreement_step_complete,
        "billing_step_complete": billing_step_complete,
        "access_step_complete": access_step_complete,
        "agreement_template_name": clean(template_row.get("name")),
        "agreement_template_version": clean(template_row.get("version")),
        "agreement_template_type": clean(template_row.get("template_type")),
        "agreement_summary_title": clean(template_row.get("summary_title")),
        "agreement_summary_text": clean(template_row.get("summary_text")),
        "agreement_template_html": template_html,
        "agreement_rendered_html_snapshot": clean(addendum_row.get("rendered_html_snapshot")),
        "agreement_term_model": term_model,
        "agreement_fixed_term_months": fixed_term_months,
        "agreement_start_date": start_date,
        "agreement_end_date": end_date,
        "agreement_term_label": term_label,
        "agreement_signed_by_name": clean(addendum_row.get("signed_by_name")),
        "agreement_signed_by_email": clean(addendum_row.get("signed_by_email")),
        "agreement_signed_on": clean(addendum_row.get("signed_on")),
    }

def build_load_portal_state_payload(row):
    context = build_context(row)
    customer_row = context.get("customer_row") or {}
    lead_row = context.get("lead_row") or {}
    lead_name = clean(context.get("lead_name"))
    company_name = (
        clean(row.get("customer_name"))
        or clean(customer_row.get("customer_name"))
        or clean(lead_row.get("company_name"))
        or clean(row.get("party_name"))
    )
    contact_name = ("%s %s" % (clean(lead_row.get("first_name")), clean(lead_row.get("last_name")))).strip()
    if not contact_name:
        contact_name = company_name

    sales_order_row = get_sales_order_row(row.get("custom_accepted_sales_order"))
    sales_order_customer = get_customer_row(sales_order_row.get("customer"))
    building_row = get_building_row(sales_order_row.get("custom_building"))
    contact_row = get_contact_row(
        clean(sales_order_row.get("contact_person")) or clean(sales_order_customer.get("customer_primary_contact"))
    )
    address_row = get_address_row(
        clean(sales_order_row.get("customer_address"))
        or clean(sales_order_customer.get("customer_primary_address"))
    )

    payload = {
        "quote": clean(row.get("name")),
        "lead": lead_name,
        "company_name": company_name,
        "contact_name": contact_name,
        "contact_email": clean(row.get("contact_email"))
        or clean(customer_row.get("email_id"))
        or clean(lead_row.get("email_id")),
        "currency": clean(row.get("currency")) or DEFAULT_CURRENCY,
        "grand_total": row.get("grand_total") or 0,
        "rounded_total": row.get("rounded_total") or row.get("grand_total") or 0,
        "transaction_date": row.get("transaction_date"),
        "valid_till": row.get("valid_till"),
        "terms": row.get("terms") or "",
        "sales_order": clean(row.get("custom_accepted_sales_order")),
        "initial_invoice": clean(sales_order_row.get("custom_initial_invoice")),
        "billing_setup_completed_on": clean(sales_order_row.get("custom_billing_setup_completed_on")),
        "billing_recipient_email": clean(sales_order_row.get("custom_billing_recipient_email")),
        "billing_contact_name": clean(contact_row.get("full_name")),
        "billing_email": clean(sales_order_row.get("custom_billing_recipient_email"))
        or clean(sales_order_row.get("contact_email"))
        or clean(contact_row.get("email_id")),
        "billing_address_line_1": clean(address_row.get("address_line1")),
        "billing_address_line_2": clean(address_row.get("address_line2")),
        "billing_city": clean(address_row.get("city")),
        "billing_state": clean(address_row.get("state")),
        "billing_postal_code": clean(address_row.get("pincode")),
        "billing_country": clean(address_row.get("country")) or DEFAULT_COUNTRY,
        "po_number": clean(sales_order_row.get("po_no")),
        "tax_id": clean(sales_order_customer.get("tax_id")),
        "billing_notes": clean(sales_order_row.get("custom_public_billing_notes")),
        "building": clean(building_row.get("name")) or clean(sales_order_row.get("custom_building")),
        "building_name": clean(building_row.get("building_name")) or clean(building_row.get("name")),
        "service_address_line_1": clean(building_row.get("address_line_1")),
        "service_address_line_2": clean(building_row.get("address_line_2")),
        "service_city": clean(building_row.get("city")),
        "service_state": clean(building_row.get("state")),
        "service_postal_code": clean(building_row.get("postal_code")),
        "access_method": clean(building_row.get("access_method"))
        or clean(sales_order_row.get("custom_access_method")),
        "access_entrance": clean(building_row.get("access_entrance"))
        or clean(sales_order_row.get("custom_access_entrance")),
        "access_entry_details": clean(building_row.get("access_entry_details"))
        or clean(sales_order_row.get("custom_access_entry_details")),
        "has_alarm_system": clean(building_row.get("has_alarm_system"))
        or clean(sales_order_row.get("custom_has_alarm_system"))
        or "No",
        "alarm_instructions": clean(building_row.get("alarm_instructions"))
        or clean(sales_order_row.get("custom_alarm_instructions")),
        "allowed_entry_time": clean(building_row.get("allowed_entry_time"))
        or clean(sales_order_row.get("custom_allowed_entry_time")),
        "primary_site_contact": clean(building_row.get("primary_site_contact"))
        or clean(sales_order_row.get("custom_primary_site_contact")),
        "lockout_emergency_contact": clean(building_row.get("lockout_emergency_contact"))
        or clean(sales_order_row.get("custom_lockout_emergency_contact")),
        "key_fob_handoff_details": clean(building_row.get("key_fob_handoff_details"))
        or clean(sales_order_row.get("custom_key_fob_handoff_details")),
        "areas_to_avoid": clean(building_row.get("areas_to_avoid"))
        or clean(sales_order_row.get("custom_areas_to_avoid")),
        "closing_instructions": clean(building_row.get("closing_instructions"))
        or clean(sales_order_row.get("custom_closing_instructions")),
        "parking_elevator_notes": clean(building_row.get("parking_elevator_notes"))
        or clean(sales_order_row.get("custom_parking_elevator_notes")),
        "first_service_notes": clean(building_row.get("first_service_notes"))
        or clean(sales_order_row.get("custom_first_service_notes")),
        "access_details_confirmed": int(
            building_row.get("access_details_confirmed")
            or sales_order_row.get("custom_access_details_confirmed")
            or 0
        ),
        "access_details_completed_on": clean(building_row.get("access_details_completed_on"))
        or clean(sales_order_row.get("custom_access_details_completed_on")),
    }

    if not clean(building_row.get("name")) and int(
        sales_order_row.get("custom_access_details_confirmed") or 0
    ) != 1 and not clean(sales_order_row.get("custom_access_details_completed_on")):
        payload.update(
            {
                "service_address_line_1": "",
                "service_address_line_2": "",
                "service_city": "",
                "service_state": "",
                "service_postal_code": "",
                "access_method": "",
                "access_entrance": "",
                "access_entry_details": "",
                "has_alarm_system": "No",
                "alarm_instructions": "",
                "allowed_entry_time": "",
                "primary_site_contact": "",
                "lockout_emergency_contact": "",
                "key_fob_handoff_details": "",
                "areas_to_avoid": "",
                "closing_instructions": "",
                "parking_elevator_notes": "",
                "first_service_notes": "",
                "access_details_confirmed": 0,
                "access_details_completed_on": "",
            }
        )

    payload.update(build_agreement_payload(row, sales_order_row))
    return payload

def build_load_portal_state_response(state, message="", row=None):
    payload = {
        "state": state,
        "message": message,
    }
    if row:
        payload.update(build_load_portal_state_payload(row))
    return payload

def build_service_agreement_signature_response(
    service_agreement_name,
    addendum_name,
    addendum_status,
    start_date,
    end_date,
    term_model,
    fixed_term_months,
):
    return ServiceAgreementSignatureResponse(
        status="ok",
        service_agreement=clean(service_agreement_name),
        addendum=clean(addendum_name),
        addendum_status=clean(addendum_status),
        start_date=clean(start_date),
        end_date=clean(end_date),
        term_model=clean(term_model),
        fixed_term_months=clean(fixed_term_months),
    ).model_dump()

def get_existing_service_agreement_signature_response(
    quote_name,
    sales_order_name,
    quote_row=None,
    sales_order_row=None,
):
    from .agreements import link_quote_agreement_records

    existing_addendum = get_addendum_row(quote_name, sales_order_name)
    if not clean(existing_addendum.get("name")):
        return None
    quote_row = quote_row or get_quote_row(quote_name)
    sales_order_row = sales_order_row or get_sales_order_row(sales_order_name)
    link_quote_agreement_records(
        clean(existing_addendum.get("service_agreement")),
        clean(existing_addendum.get("name")),
        quote_row,
        sales_order_row,
    )
    return build_service_agreement_signature_response(
        clean(existing_addendum.get("service_agreement")),
        clean(existing_addendum.get("name")),
        clean(existing_addendum.get("status")),
        clean(existing_addendum.get("start_date")),
        clean(existing_addendum.get("end_date")),
        clean(existing_addendum.get("term_model")),
        clean(existing_addendum.get("fixed_term_months")),
    )

def build_billing_setup_response(
    quote_name,
    sales_order_name,
    invoice_name,
    auto_repeat_name,
    service_agreement_name,
    addendum_name,
    addendum_status,
):
    return BillingSetupResponse(
        status="ok",
        quote=clean(quote_name),
        sales_order=clean(sales_order_name),
        invoice=clean(invoice_name),
        auto_repeat=clean(auto_repeat_name),
        service_agreement=clean(service_agreement_name),
        addendum=clean(addendum_name),
        addendum_status=clean(addendum_status),
    ).model_dump()

def get_existing_billing_setup_response(quote_name, sales_order_name, addendum_row=None, sales_order_row=None):
    sales_order_name = clean(sales_order_name)
    sales_order_row = sales_order_row or get_sales_order_row(sales_order_name)
    addendum_row = addendum_row or get_addendum_row(quote_name, sales_order_name)
    invoice_name = clean(sales_order_row.get("custom_initial_invoice")) or clean(addendum_row.get("initial_invoice"))
    billing_completed_on = clean(addendum_row.get("billing_completed_on")) or clean(
        sales_order_row.get("custom_billing_setup_completed_on")
    )
    if not invoice_name or not billing_completed_on or not frappe.db.exists("Sales Invoice", invoice_name):
        return None
    return build_billing_setup_response(
        quote_name,
        sales_order_name,
        invoice_name,
        clean(frappe.db.get_value("Sales Invoice", invoice_name, "auto_repeat")),
        clean(addendum_row.get("service_agreement")) or clean(sales_order_row.get("custom_service_agreement")),
        clean(addendum_row.get("name")) or clean(sales_order_row.get("custom_service_agreement_addendum")),
        clean(addendum_row.get("status")) or "Pending Site Access",
    )

def build_access_setup_response(
    quote_name,
    sales_order_name,
    invoice_name,
    building_name,
    service_agreement_name,
    addendum_name,
    addendum_status,
    access_completed_on,
):
    return AccessSetupResponse(
        status="ok",
        quote=clean(quote_name),
        sales_order=clean(sales_order_name),
        invoice=clean(invoice_name),
        building=clean(building_name),
        service_agreement=clean(service_agreement_name),
        addendum=clean(addendum_name),
        addendum_status=clean(addendum_status),
        access_completed_on=str(access_completed_on),
    ).model_dump()

def get_existing_access_setup_response(quote_name, sales_order_name, addendum_row=None, sales_order_row=None):
    sales_order_name = clean(sales_order_name)
    sales_order_row = sales_order_row or get_sales_order_row(sales_order_name)
    addendum_row = addendum_row or get_addendum_row(quote_name, sales_order_name)
    building_name = clean(sales_order_row.get("custom_building")) or clean(addendum_row.get("building"))
    access_completed_on = clean(addendum_row.get("access_completed_on")) or clean(
        sales_order_row.get("custom_access_details_completed_on")
    )
    if not access_completed_on and building_name and frappe.db.exists("Building", building_name):
        access_completed_on = clean(get_building_row(building_name).get("access_details_completed_on"))
    if not building_name or not access_completed_on:
        return None
    return build_access_setup_response(
        quote_name,
        sales_order_name,
        clean(sales_order_row.get("custom_initial_invoice")) or clean(addendum_row.get("initial_invoice")),
        building_name,
        clean(addendum_row.get("service_agreement")) or clean(sales_order_row.get("custom_service_agreement")),
        clean(addendum_row.get("name")) or clean(sales_order_row.get("custom_service_agreement_addendum")),
        clean(addendum_row.get("status")) or "Active",
        access_completed_on,
    )

__all__ = [
    "render_template_html",
    "get_term_label",
    "build_context",
    "apply_review_building_payload",
    "build_validate_payload",
    "build_accept_portal_payload",
    "build_accept_payload",
    "get_existing_accept_response",
    "resolve_customer_name",
    "build_agreement_payload",
    "build_load_portal_state_payload",
    "build_load_portal_state_response",
    "build_service_agreement_signature_response",
    "get_existing_service_agreement_signature_response",
    "build_billing_setup_response",
    "get_existing_billing_setup_response",
    "build_access_setup_response",
    "get_existing_access_setup_response",
]
