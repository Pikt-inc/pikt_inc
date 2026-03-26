from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import add_to_date, nowdate

from .constants import DEFAULT_COMPANY, DEFAULT_COUNTRY, DEFAULT_CURRENCY, DEFAULT_PRICE_LIST, DEFAULT_WAREHOUSE
from .payloads import build_accept_payload, get_existing_accept_response
from .portal import get_public_quote_access_result
from .queries import get_lead_row, get_quote_row, get_customer_row, load_accept_items, load_quote_taxes, find_customer_for_quote
from .shared import (
    begin_savepoint, clean, doc_db_set_values, fail, get_date_safe, get_traceback_text, lock_document_row,
    make_accept_token, release_savepoint, rollback_savepoint, truncate_name
)

def prepare_public_quotation_acceptance(doc):
    quotation_target = clean(doc.quotation_to)
    if quotation_target not in ("Lead", "Customer"):
        fail("This quotation flow only supports quotations issued to a Lead or Customer.")

    party_name = clean(doc.party_name)
    if not party_name:
        fail("A linked Lead or Customer is required before submitting this quotation.")

    if quotation_target == "Lead" and not frappe.db.exists("Lead", party_name):
        fail("The linked Lead could not be found.")
    if quotation_target == "Customer" and not frappe.db.exists("Customer", party_name):
        fail("The linked Customer could not be found.")

    contact_email = clean(doc.contact_email).lower()
    if not contact_email:
        fail("Contact email is required before submitting this quotation.")
    if ("@" not in contact_email) or ("." not in contact_email.split("@")[-1]):
        fail("Enter a valid contact email before submitting this quotation.")

    doc.contact_email = contact_email
    doc.custom_accepted_sales_order = ""

    effective_date = get_date_safe(doc.valid_till)
    if not effective_date:
        base_date = get_date_safe(doc.transaction_date) or get_date_safe(nowdate())
        effective_date = get_date_safe(add_to_date(base_date, days=30))

    doc.custom_accept_token = make_accept_token(doc.name)
    doc.custom_accept_token_expires_on = add_to_date(
        effective_date,
        days=1,
        seconds=-1,
        as_datetime=True,
    )

def mark_opportunity_reviewed_on_quotation(doc):
    opportunity_name = clean(doc.opportunity)
    if not opportunity_name:
        return

    opp = frappe.get_doc("Opportunity", opportunity_name)
    changed = False

    if clean(opp.status) != "Quotation":
        opp.status = "Quotation"
        changed = True

    if (opp.digital_walkthrough_file or opp.latest_digital_walkthrough) and clean(
        opp.digital_walkthrough_status
    ) != "Reviewed":
        opp.digital_walkthrough_status = "Reviewed"
        changed = True

    if changed:
        opp.save(ignore_permissions=True)

    submission_name = clean(opp.latest_digital_walkthrough)
    if submission_name and frappe.db.exists("Digital Walkthrough Submission", submission_name):
        submission = frappe.get_doc("Digital Walkthrough Submission", submission_name)
        if clean(submission.status) != "Reviewed":
            submission.status = "Reviewed"
            submission.save(ignore_permissions=True)
        return

    linked = frappe.get_all(
        "Digital Walkthrough Submission",
        filters={"opportunity": opp.name},
        fields=["name", "status"],
        order_by="modified desc",
        limit=1,
    )
    if not linked:
        return

    submission = frappe.get_doc("Digital Walkthrough Submission", linked[0].get("name"))
    if clean(submission.status) != "Reviewed":
        submission.status = "Reviewed"
        submission.save(ignore_permissions=True)

def ensure_customer(quote_row, lead_row):
    lead_name = clean((quote_row or {}).get("party_name"))
    contact_email = clean((quote_row or {}).get("contact_email")) or clean((lead_row or {}).get("email_id"))
    if lead_name and frappe.db.exists("Lead", lead_name):
        lock_document_row("Lead", lead_name)

    customer = find_customer_for_quote(lead_name, contact_email)

    if customer:
        updates = {}
        current_customer = get_customer_row(customer)
        if not clean(current_customer.get("lead_name")) and lead_name:
            updates["lead_name"] = lead_name
        if not clean(current_customer.get("email_id")) and contact_email:
            updates["email_id"] = contact_email
        if updates:
            frappe.db.set_value("Customer", customer, updates, update_modified=False)
        return customer

    company_name = clean((lead_row or {}).get("company_name")) or clean((quote_row or {}).get("customer_name")) or lead_name
    first_name = clean((lead_row or {}).get("first_name"))
    last_name = clean((lead_row or {}).get("last_name"))
    customer_type = "Company" if clean((lead_row or {}).get("company_name")) else "Individual"

    customer_doc = frappe.get_doc(
        {
            "doctype": "Customer",
            "customer_name": company_name,
            "customer_type": customer_type,
            "lead_name": lead_name,
            "email_id": contact_email,
            "mobile_no": clean((lead_row or {}).get("phone")),
            "first_name": first_name,
            "last_name": last_name,
            "opportunity_name": clean((quote_row or {}).get("opportunity")),
        }
    )
    try:
        customer_doc.insert(ignore_permissions=True)
    except Exception:
        customer = find_customer_for_quote(lead_name, contact_email)
        if customer:
            updates = {}
            current_customer = get_customer_row(customer)
            if not clean(current_customer.get("lead_name")) and lead_name:
                updates["lead_name"] = lead_name
            if not clean(current_customer.get("email_id")) and contact_email:
                updates["email_id"] = contact_email
            if updates:
                frappe.db.set_value("Customer", customer, updates, update_modified=False)
            return customer
        raise
    return customer_doc.name

def build_sales_order(quote_row, quote_items, quote_taxes, customer):
    delivery_date = (quote_row or {}).get("valid_till") or nowdate()
    customer_row = get_customer_row(customer)
    contact_person = clean(customer_row.get("customer_primary_contact"))
    customer_address = clean(customer_row.get("customer_primary_address"))
    contact_email = clean(customer_row.get("email_id")) or clean((quote_row or {}).get("contact_email"))

    order_items = []
    for item in quote_items or []:
        order_items.append(
            {
                "item_code": clean(item.get("item_code")),
                "qty": item.get("qty") or 1,
                "rate": item.get("rate") or 0,
                "warehouse": clean(item.get("warehouse")) or DEFAULT_WAREHOUSE,
                "delivery_date": delivery_date,
                "uom": clean(item.get("uom")),
                "stock_uom": clean(item.get("stock_uom")),
                "conversion_factor": item.get("conversion_factor") or 1,
                "description": item.get("description") or "",
                "item_tax_template": clean(item.get("item_tax_template")),
                "item_tax_rate": item.get("item_tax_rate") or "",
                "prevdoc_docname": clean((quote_row or {}).get("name")),
                "quotation_item": clean(item.get("name")),
            }
        )

    order_taxes = []
    for tax in quote_taxes or []:
        order_taxes.append(
            {
                "charge_type": clean(tax.get("charge_type")),
                "row_id": tax.get("row_id"),
                "account_head": clean(tax.get("account_head")),
                "description": clean(tax.get("description")),
                "included_in_print_rate": tax.get("included_in_print_rate") or 0,
                "included_in_paid_amount": tax.get("included_in_paid_amount") or 0,
                "set_by_item_tax_template": tax.get("set_by_item_tax_template") or 0,
                "is_tax_withholding_account": tax.get("is_tax_withholding_account") or 0,
                "cost_center": clean(tax.get("cost_center")),
                "project": clean(tax.get("project")),
                "rate": tax.get("rate") or 0,
                "account_currency": clean(tax.get("account_currency")),
                "tax_amount": tax.get("tax_amount") or 0,
                "tax_amount_after_discount_amount": tax.get("tax_amount_after_discount_amount") or 0,
                "total": tax.get("total") or 0,
                "dont_recompute_tax": tax.get("dont_recompute_tax") or 0,
            }
        )

    sales_order = frappe.get_doc(
        {
            "doctype": "Sales Order",
            "company": clean((quote_row or {}).get("company")) or DEFAULT_COMPANY,
            "naming_series": "SAL-ORD-.YYYY.-",
            "customer": customer,
            "order_type": clean((quote_row or {}).get("order_type")) or "Sales",
            "transaction_date": nowdate(),
            "delivery_date": delivery_date,
            "currency": clean((quote_row or {}).get("currency")) or DEFAULT_CURRENCY,
            "conversion_rate": (quote_row or {}).get("conversion_rate") or 1,
            "selling_price_list": clean((quote_row or {}).get("selling_price_list")) or DEFAULT_PRICE_LIST,
            "price_list_currency": clean((quote_row or {}).get("price_list_currency"))
            or clean((quote_row or {}).get("currency"))
            or DEFAULT_CURRENCY,
            "plc_conversion_rate": (quote_row or {}).get("plc_conversion_rate") or 1,
            "taxes_and_charges": clean((quote_row or {}).get("taxes_and_charges")),
            "tc_name": "",
            "terms": (quote_row or {}).get("terms") or "",
            "contact_person": contact_person,
            "contact_email": contact_email,
            "customer_address": customer_address,
            "custom_building": clean((quote_row or {}).get("custom_building")),
            "custom_access_method": "",
            "custom_access_entrance": "",
            "custom_access_entry_details": "",
            "custom_has_alarm_system": "No",
            "custom_alarm_instructions": "",
            "custom_allowed_entry_time": "",
            "custom_primary_site_contact": "",
            "custom_lockout_emergency_contact": "",
            "custom_key_fob_handoff_details": "",
            "custom_areas_to_avoid": "",
            "custom_closing_instructions": "",
            "custom_parking_elevator_notes": "",
            "custom_first_service_notes": "",
            "custom_access_details_confirmed": 0,
            "custom_access_details_completed_on": None,
            "items": order_items,
            "taxes": order_taxes,
        }
    )
    sales_order.insert(ignore_permissions=True)
    if int(sales_order.docstatus or 0) == 0:
        sales_order.submit()
    return sales_order

def mark_opportunity_converted(opportunity_name):
    opportunity_name = clean(opportunity_name)
    if opportunity_name and frappe.db.exists("Opportunity", opportunity_name):
        frappe.db.set_value(
            "Opportunity",
            opportunity_name,
            {"status": "Converted"},
            update_modified=False,
        )

def accept_public_quote(quote=None, token=None):
    result = get_public_quote_access_result(quote_name=quote, token=token)
    state = clean(result.get("state"))
    row = result.get("row")

    if state == "accepted":
        mark_opportunity_converted((row or {}).get("opportunity"))
        items = load_accept_items(clean((row or {}).get("name")))
        return build_accept_payload(
            state,
            result.get("message", ""),
            row=row,
            items=items,
            sales_order_name=result.get("sales_order"),
        )

    if state != "ready":
        return build_accept_payload(state, result.get("message", ""))

    quote_name = clean((row or {}).get("name"))
    savepoint_name = begin_savepoint("accept_quote")

    try:
        lock_document_row("Quotation", quote_name)
        locked_row = get_quote_row(quote_name)
        existing_response = get_existing_accept_response(quote_name, row=locked_row)
        if existing_response:
            release_savepoint(savepoint_name)
            return existing_response
        if not row:
            row = locked_row

        quote_items = load_accept_items(quote_name)
        quote_taxes = load_quote_taxes(quote_name)
        current_target = clean((row or {}).get("quotation_to"))
        if current_target == "Lead":
            lead_row = get_lead_row((row or {}).get("party_name"))
            customer = ensure_customer(row, lead_row)
            customer_display = clean(frappe.db.get_value("Customer", customer, "customer_name")) or customer
            frappe.db.set_value(
                "Quotation",
                quote_name,
                {
                    "quotation_to": "Customer",
                    "party_name": customer,
                    "customer_name": customer_display,
                },
                update_modified=False,
            )
            row = dict(row or {})
            row.update(
                {
                    "quotation_to": "Customer",
                    "party_name": customer,
                    "customer_name": customer_display,
                }
            )
            quote_items = load_accept_items(quote_name)
            quote_taxes = load_quote_taxes(quote_name)
        else:
            customer = clean((row or {}).get("party_name"))
            if not frappe.db.exists("Customer", customer):
                return build_accept_payload(
                    "invalid",
                    "This quotation is not available through the public review flow.",
                )

        refreshed_sales_order = clean(frappe.db.get_value("Quotation", quote_name, "custom_accepted_sales_order"))
        if refreshed_sales_order and frappe.db.exists("Sales Order", refreshed_sales_order):
            row = get_quote_row(quote_name)
            quote_items = load_accept_items(quote_name)
            mark_opportunity_converted((row or {}).get("opportunity"))
            return build_accept_payload(
                "accepted",
                "This quotation has already been accepted.",
                row=row,
                items=quote_items,
                sales_order_name=refreshed_sales_order,
            )

        sales_order = build_sales_order(row, quote_items, quote_taxes, customer)
        frappe.db.set_value(
            "Quotation",
            quote_name,
            {"custom_accepted_sales_order": sales_order.name},
            update_modified=False,
        )
        mark_opportunity_converted((row or {}).get("opportunity"))

        row = get_quote_row(quote_name)
        quote_items = load_accept_items(quote_name)
        release_savepoint(savepoint_name)
        return build_accept_payload(
            "accepted",
            "Your quotation has been accepted.",
            row=row,
            items=quote_items,
            sales_order_name=sales_order.name,
        )
    except Exception:
        rollback_savepoint(savepoint_name)
        fallback_response = get_existing_accept_response(quote_name)
        if fallback_response:
            return fallback_response
        frappe.log_error(get_traceback_text(), "Accept Public Quotation")
        return build_accept_payload(
            "invalid",
            "We could not accept this quotation right now. Please contact our team for help.",
        )

__all__ = [
    "prepare_public_quotation_acceptance",
    "mark_opportunity_reviewed_on_quotation",
    "ensure_customer",
    "build_sales_order",
    "mark_opportunity_converted",
    "accept_public_quote",
]
