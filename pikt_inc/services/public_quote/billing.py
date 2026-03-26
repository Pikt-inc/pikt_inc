from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import now_datetime, nowdate

from .constants import DEFAULT_COMPANY, DEFAULT_COUNTRY, DEFAULT_CURRENCY, DEFAULT_PRICE_LIST, DEFAULT_WAREHOUSE
from .models import BillingSetupInput
from .payloads import build_billing_setup_response, get_existing_billing_setup_response
from .portal import ensure_quote_is_valid_for_portal_write
from .queries import get_addendum_row, get_customer_row, get_sales_order_row, find_address_for_customer, find_contact_for_customer
from .shared import (
    begin_savepoint,
    child_value,
    clean,
    doc_db_set_values,
    fail,
    get_date_safe,
    get_traceback_text,
    lock_document_row,
    release_savepoint,
    rollback_savepoint,
    split_name,
    valid_email,
)


def _find_billing_contact_match(customer_name, billing_email):
    billing_email = clean(billing_email).lower()
    if billing_email:
        matched_contact = find_contact_for_customer(customer_name, billing_email)
        if matched_contact:
            matched_email = clean(frappe.db.get_value("Contact", matched_contact, "email_id")).lower()
            if matched_email == billing_email:
                return matched_contact

    customer_row = get_customer_row(customer_name)
    if not isinstance(customer_row, dict):
        customer_row = {}

    primary_contact = clean(customer_row.get("customer_primary_contact"))
    if primary_contact:
        primary_email = clean(frappe.db.get_value("Contact", primary_contact, "email_id")).lower()
        if not billing_email or primary_email == billing_email:
            return primary_contact

    return ""

def dynamic_link_filters(parenttype, parent, link_doctype, link_name):
    return {
        "parenttype": clean(parenttype),
        "parent": clean(parent),
        "link_doctype": clean(link_doctype),
        "link_name": clean(link_name),
    }

def ensure_dynamic_link(parenttype, parent, link_doctype, link_name):
    filters = dynamic_link_filters(parenttype, parent, link_doctype, link_name)
    if not filters.get("parent") or not filters.get("link_name"):
        return
    if frappe.db.exists("Dynamic Link", filters):
        return
    try:
        frappe.get_doc(
            {
                "doctype": "Dynamic Link",
                **filters,
                "parentfield": "links",
            }
        ).insert(ignore_permissions=True)
    except Exception:
        if frappe.db.exists("Dynamic Link", filters):
            return
        raise

def ensure_signed_addendum(quote_name, sales_order_name):
    addendum_row = get_addendum_row(quote_name, sales_order_name)
    if not clean(addendum_row.get("name")):
        fail("Complete the service agreement before setting up billing.")
    status = clean(addendum_row.get("status"))
    if status in ("Cancelled", "Expired"):
        fail("This service agreement addendum is no longer active.")
    return addendum_row

def ensure_contact(customer_name, customer_display, billing_contact_name, billing_email):
    if customer_name and frappe.db.exists("Customer", customer_name):
        lock_document_row("Customer", customer_name)

    name_parts = split_name(billing_contact_name)
    contact_name = _find_billing_contact_match(customer_name, billing_email)
    if contact_name:
        doc_db_set_values(
            "Contact",
            contact_name,
            {
                "first_name": name_parts.get("first_name"),
                "last_name": name_parts.get("last_name"),
                "email_id": clean(billing_email).lower(),
                "company_name": customer_display,
                "status": "Open",
                "is_primary_contact": 1,
                "is_billing_contact": 1,
            },
        )
        ensure_dynamic_link("Contact", contact_name, "Customer", customer_name)
        return contact_name

    contact_doc = frappe.get_doc(
        {
            "doctype": "Contact",
            "first_name": name_parts.get("first_name"),
            "last_name": name_parts.get("last_name"),
            "email_id": clean(billing_email).lower(),
            "company_name": customer_display,
            "status": "Open",
            "is_primary_contact": 1,
            "is_billing_contact": 1,
            "email_ids": [{"email_id": clean(billing_email).lower(), "is_primary": 1}],
            "links": [{"link_doctype": "Customer", "link_name": customer_name}],
        }
    )
    try:
        contact_doc.insert(ignore_permissions=True)
    except Exception:
        contact_name = _find_billing_contact_match(customer_name, billing_email)
        if contact_name:
            doc_db_set_values(
                "Contact",
                contact_name,
                {
                    "first_name": name_parts.get("first_name"),
                    "last_name": name_parts.get("last_name"),
                    "email_id": clean(billing_email).lower(),
                    "company_name": customer_display,
                    "status": "Open",
                    "is_primary_contact": 1,
                    "is_billing_contact": 1,
                },
            )
            ensure_dynamic_link("Contact", contact_name, "Customer", customer_name)
            return contact_name
        raise
    return contact_doc.name

def ensure_address(
    customer_name,
    customer_display,
    billing_address_line_1,
    billing_address_line_2,
    billing_city,
    billing_state,
    billing_postal_code,
    billing_country,
):
    if customer_name and frappe.db.exists("Customer", customer_name):
        lock_document_row("Customer", customer_name)

    address_name = find_address_for_customer(customer_name)
    address_values = {
        "address_title": customer_display,
        "address_type": "Billing",
        "address_line1": clean(billing_address_line_1),
        "address_line2": clean(billing_address_line_2),
        "city": clean(billing_city),
        "state": clean(billing_state),
        "pincode": clean(billing_postal_code),
        "country": clean(billing_country) or DEFAULT_COUNTRY,
        "is_primary_address": 1,
        "is_shipping_address": 0,
    }
    if address_name:
        doc_db_set_values("Address", address_name, address_values)
        ensure_dynamic_link("Address", address_name, "Customer", customer_name)
        return address_name

    address_doc = frappe.get_doc(
        {
            "doctype": "Address",
            "address_title": customer_display,
            "address_type": "Billing",
            "address_line1": clean(billing_address_line_1),
            "address_line2": clean(billing_address_line_2),
            "city": clean(billing_city),
            "state": clean(billing_state),
            "pincode": clean(billing_postal_code),
            "country": clean(billing_country) or DEFAULT_COUNTRY,
            "is_primary_address": 1,
            "is_shipping_address": 0,
            "links": [{"link_doctype": "Customer", "link_name": customer_name}],
        }
    )
    try:
        address_doc.insert(ignore_permissions=True)
    except Exception:
        address_name = find_address_for_customer(customer_name)
        if address_name:
            doc_db_set_values("Address", address_name, address_values)
            ensure_dynamic_link("Address", address_name, "Customer", customer_name)
            return address_name
        raise
    return address_doc.name

def sync_customer(customer_name, billing_email, contact_name, address_name, tax_id):
    customer_row = get_customer_row(customer_name)
    updates = {
        "customer_primary_contact": clean(contact_name),
        "customer_primary_address": clean(address_name),
    }
    if not clean(customer_row.get("email_id")):
        updates["email_id"] = clean(billing_email).lower()
    if clean(tax_id):
        updates["tax_id"] = clean(tax_id)
    doc_db_set_values("Customer", customer_name, updates)

def update_sales_order_billing(
    sales_order_name,
    contact_name,
    billing_email,
    address_name,
    po_number,
    billing_notes,
    invoice_name,
    service_agreement_name,
    addendum_name,
):
    updates = {
        "contact_person": clean(contact_name),
        "contact_email": clean(billing_email).lower(),
        "customer_address": clean(address_name),
        "po_no": clean(po_number),
        "custom_public_billing_notes": clean(billing_notes),
        "custom_billing_recipient_email": clean(billing_email).lower(),
        "custom_service_agreement": clean(service_agreement_name),
        "custom_service_agreement_addendum": clean(addendum_name),
    }
    if clean(invoice_name):
        updates["custom_initial_invoice"] = clean(invoice_name)
        updates["custom_billing_setup_completed_on"] = now_datetime()
    doc_db_set_values("Sales Order", sales_order_name, updates)

def ensure_sales_order_submitted(sales_order_name):
    sales_order_name = clean(sales_order_name)
    if not sales_order_name:
        fail("We could not find the accepted sales order for this quotation.")
    sales_order_doc = frappe.get_doc("Sales Order", sales_order_name)
    if int(sales_order_doc.docstatus or 0) == 2:
        fail("The accepted sales order is no longer active.")
    if int(sales_order_doc.docstatus or 0) == 0:
        sales_order_doc.flags.ignore_permissions = True
        sales_order_doc.submit()
    return frappe.get_doc("Sales Order", sales_order_name)

def update_invoice_links(invoice_name, service_agreement_name, addendum_name, billing_email):
    doc_db_set_values(
        "Sales Invoice",
        invoice_name,
        {
            "custom_service_agreement": clean(service_agreement_name),
            "custom_service_agreement_addendum": clean(addendum_name),
            "contact_email": clean(billing_email).lower(),
            "update_billed_amount_in_sales_order": 1,
        },
    )

def create_invoice_from_sales_order(sales_order_doc, billing_email, addendum_row):
    invoice_items = []
    for item in sales_order_doc.items or []:
        invoice_items.append(
            {
                "item_code": clean(child_value(item, "item_code")),
                "qty": child_value(item, "qty") or 1,
                "rate": child_value(item, "rate") or 0,
                "warehouse": clean(child_value(item, "warehouse")),
                "uom": clean(child_value(item, "uom")),
                "stock_uom": clean(child_value(item, "stock_uom")),
                "conversion_factor": child_value(item, "conversion_factor") or 1,
                "description": child_value(item, "description") or "",
                "item_tax_template": clean(child_value(item, "item_tax_template")),
                "item_tax_rate": child_value(item, "item_tax_rate") or "",
                "sales_order": clean(sales_order_doc.name),
                "so_detail": clean(child_value(item, "name")),
            }
        )

    invoice_taxes = []
    for tax in sales_order_doc.taxes or []:
        invoice_taxes.append(
            {
                "charge_type": clean(child_value(tax, "charge_type")),
                "row_id": child_value(tax, "row_id"),
                "account_head": clean(child_value(tax, "account_head")),
                "description": clean(child_value(tax, "description")),
                "included_in_print_rate": child_value(tax, "included_in_print_rate") or 0,
                "included_in_paid_amount": child_value(tax, "included_in_paid_amount") or 0,
                "set_by_item_tax_template": child_value(tax, "set_by_item_tax_template") or 0,
                "is_tax_withholding_account": child_value(tax, "is_tax_withholding_account") or 0,
                "cost_center": clean(child_value(tax, "cost_center")),
                "project": clean(child_value(tax, "project")),
                "rate": child_value(tax, "rate") or 0,
                "account_currency": clean(child_value(tax, "account_currency")),
                "tax_amount": child_value(tax, "tax_amount") or 0,
                "tax_amount_after_discount_amount": child_value(
                    tax,
                    "tax_amount_after_discount_amount",
                )
                or 0,
                "total": child_value(tax, "total") or 0,
                "dont_recompute_tax": child_value(tax, "dont_recompute_tax") or 0,
            }
        )

    due_date = nowdate()
    if sales_order_doc.get("payment_schedule") and len(sales_order_doc.payment_schedule):
        due_date = sales_order_doc.payment_schedule[0].due_date or due_date

    invoice_doc = frappe.get_doc(
        {
            "doctype": "Sales Invoice",
            "company": clean(sales_order_doc.company),
            "naming_series": "ACC-SINV-.YYYY.-",
            "customer": clean(sales_order_doc.customer),
            "posting_date": nowdate(),
            "due_date": due_date,
            "currency": clean(sales_order_doc.currency) or DEFAULT_CURRENCY,
            "conversion_rate": sales_order_doc.conversion_rate or 1,
            "selling_price_list": clean(sales_order_doc.selling_price_list) or DEFAULT_PRICE_LIST,
            "price_list_currency": clean(sales_order_doc.price_list_currency)
            or clean(sales_order_doc.currency)
            or DEFAULT_CURRENCY,
            "plc_conversion_rate": sales_order_doc.plc_conversion_rate or 1,
            "taxes_and_charges": clean(sales_order_doc.taxes_and_charges),
            "customer_address": clean(sales_order_doc.customer_address),
            "contact_person": clean(sales_order_doc.contact_person),
            "contact_email": clean(billing_email).lower(),
            "payment_terms_template": clean(sales_order_doc.payment_terms_template),
            "po_no": clean(sales_order_doc.po_no),
            "tax_id": clean(frappe.db.get_value("Customer", sales_order_doc.customer, "tax_id")),
            "update_billed_amount_in_sales_order": 1,
            "custom_building": clean(sales_order_doc.custom_building),
            "custom_service_agreement": clean(addendum_row.get("service_agreement")),
            "custom_service_agreement_addendum": clean(addendum_row.get("name")),
            "items": invoice_items,
            "taxes": invoice_taxes,
        }
    )
    invoice_doc.flags.ignore_permissions = True
    invoice_doc.insert(ignore_permissions=True)
    invoice_doc.flags.ignore_permissions = True
    invoice_doc.submit()
    return invoice_doc

def send_invoice_email(invoice_doc, billing_email):
    billing_email = clean(billing_email).lower()
    if not valid_email(billing_email):
        fail("Enter a valid billing email address.")

    subject = "Your Invoice from Pikt, inc. - %s" % clean(invoice_doc.name)
    message = (
        "<p>Hello,</p>"
        "<p>Your quote has been accepted and your billing setup is complete.</p>"
        "<p>Your first invoice is attached here for reference: <strong>%s</strong>.</p>"
        "<p>If you need anything adjusted, reply to this email and our team will help.</p>"
    ) % clean(invoice_doc.name)

    attachments = []
    try:
        attachments = [frappe.attach_print("Sales Invoice", invoice_doc.name, print_letterhead=True)]
    except Exception:
        attachments = []

    frappe.sendmail(
        recipients=[billing_email],
        subject=subject,
        message=message,
        reference_doctype="Sales Invoice",
        reference_name=invoice_doc.name,
        attachments=attachments,
    )

def ensure_auto_repeat(invoice_name, billing_email, addendum_row):
    invoice_name = clean(invoice_name)
    billing_email = clean(billing_email).lower()
    start_date = clean(addendum_row.get("start_date")) or nowdate()
    end_date_value = get_date_safe(addendum_row.get("end_date"))
    end_date = str(end_date_value) if end_date_value else None
    auto_repeat_name = clean(
        frappe.db.get_value(
            "Auto Repeat",
            {"reference_doctype": "Sales Invoice", "reference_document": invoice_name},
            "name",
        )
    )
    values = {
        "frequency": "Monthly",
        "start_date": start_date,
        "disabled": 0,
        "submit_on_creation": 1,
        "notify_by_email": 1,
        "recipients": billing_email,
        "end_date": end_date,
    }
    if auto_repeat_name:
        doc_db_set_values("Auto Repeat", auto_repeat_name, values)
        doc_db_set_values("Sales Invoice", invoice_name, {"auto_repeat": auto_repeat_name})
        return auto_repeat_name

    auto_repeat_doc = frappe.new_doc("Auto Repeat")
    auto_repeat_doc.reference_doctype = "Sales Invoice"
    auto_repeat_doc.reference_document = invoice_name
    auto_repeat_doc.frequency = "Monthly"
    auto_repeat_doc.start_date = start_date
    auto_repeat_doc.disabled = 0
    auto_repeat_doc.submit_on_creation = 1
    auto_repeat_doc.notify_by_email = 1
    auto_repeat_doc.recipients = billing_email
    auto_repeat_doc.end_date = end_date
    auto_repeat_doc.flags.ignore_permissions = True
    auto_repeat_doc.insert(ignore_permissions=True)
    doc_db_set_values("Sales Invoice", invoice_name, {"auto_repeat": auto_repeat_doc.name})
    return auto_repeat_doc.name

def update_addendum_after_billing(addendum_name, invoice_name):
    addendum_doc = frappe.get_doc("Service Agreement Addendum", addendum_name)
    next_status = clean(addendum_doc.status)
    if next_status == "Pending Billing":
        next_status = "Pending Site Access"
    doc_db_set_values(
        "Service Agreement Addendum",
        addendum_name,
        {
            "initial_invoice": clean(invoice_name),
            "billing_completed_on": now_datetime(),
            "status": next_status,
        },
    )
    return next_status

def complete_public_quote_billing_setup_v2(quote=None, token=None, **kwargs):
    payload = BillingSetupInput.from_request(quote=quote, token=token, **kwargs)
    quote_name = payload.quote
    token = payload.token
    billing_contact_name = payload.billing_contact_name
    billing_email = payload.billing_email
    billing_address_line_1 = payload.billing_address_line_1
    billing_address_line_2 = payload.billing_address_line_2
    billing_city = payload.billing_city
    billing_state = payload.billing_state
    billing_postal_code = payload.billing_postal_code
    billing_country = payload.billing_country or DEFAULT_COUNTRY
    po_number = clean(kwargs.get("po_number") or frappe.form_dict.get("po_number"))
    tax_id = payload.tax_id
    billing_notes = clean(kwargs.get("billing_notes") or frappe.form_dict.get("billing_notes"))

    if not quote_name:
        fail("Missing quotation reference. Please return to your quote email and try again.")
    if not token:
        fail("Missing secure access token. Please return to your quote email and try again.")
    if not billing_contact_name:
        fail("Billing contact name is required.")
    if not valid_email(billing_email):
        fail("Enter a valid billing email address.")
    if not billing_address_line_1:
        fail("Billing address line 1 is required.")
    if not billing_city:
        fail("Billing city is required.")
    if not billing_state:
        fail("Billing state is required.")
    if not billing_postal_code:
        fail("Billing postal code is required.")
    if not billing_country:
        fail("Billing country is required.")

    quote_row = ensure_quote_is_valid_for_portal_write(
        quote_name,
        token,
        "This quotation has been cancelled and can no longer be billed.",
        "This quotation is not ready for public billing yet.",
    )
    sales_order_name = clean(quote_row.get("custom_accepted_sales_order"))
    if not sales_order_name or not frappe.db.exists("Sales Order", sales_order_name):
        fail("We could not prepare billing for this quote. Please reload the page or contact our team.")

    addendum_row = ensure_signed_addendum(quote_name, sales_order_name)
    service_agreement_name = clean(addendum_row.get("service_agreement"))
    sales_order_row = get_sales_order_row(sales_order_name)
    customer_name = clean(sales_order_row.get("customer"))
    if not customer_name or not frappe.db.exists("Customer", customer_name):
        fail("We could not resolve the customer for this quote. Please contact our team.")

    customer_row = get_customer_row(customer_name)
    customer_display = clean(customer_row.get("customer_name")) or customer_name
    existing_response = get_existing_billing_setup_response(
        quote_name,
        sales_order_name,
        addendum_row=addendum_row,
        sales_order_row=sales_order_row,
    )
    if existing_response:
        return existing_response
    savepoint_name = begin_savepoint("quote_billing_setup")

    try:
        lock_document_row("Sales Order", sales_order_name)
        sales_order_row = get_sales_order_row(sales_order_name)
        addendum_row = ensure_signed_addendum(quote_name, sales_order_name)
        service_agreement_name = clean(addendum_row.get("service_agreement")) or clean(
            sales_order_row.get("custom_service_agreement")
        )
        existing_response = get_existing_billing_setup_response(
            quote_name,
            sales_order_name,
            addendum_row=addendum_row,
            sales_order_row=sales_order_row,
        )
        if existing_response:
            release_savepoint(savepoint_name)
            return existing_response

        contact_name = ensure_contact(
            customer_name,
            customer_display,
            billing_contact_name,
            billing_email,
        )
        address_name = ensure_address(
            customer_name,
            customer_display,
            billing_address_line_1,
            billing_address_line_2,
            billing_city,
            billing_state,
            billing_postal_code,
            billing_country,
        )
        sync_customer(customer_name, billing_email, contact_name, address_name, tax_id)
        update_sales_order_billing(
            sales_order_name,
            contact_name,
            billing_email,
            address_name,
            po_number,
            billing_notes,
            "",
            service_agreement_name,
            clean(addendum_row.get("name")),
        )
        sales_order_doc = ensure_sales_order_submitted(sales_order_name)
        existing_invoice = clean(
            frappe.db.get_value("Sales Order", sales_order_name, "custom_initial_invoice")
        ) or clean(addendum_row.get("initial_invoice"))

        if existing_invoice and frappe.db.exists("Sales Invoice", existing_invoice):
            update_invoice_links(
                existing_invoice,
                service_agreement_name,
                clean(addendum_row.get("name")),
                billing_email,
            )
            auto_repeat_name = ensure_auto_repeat(existing_invoice, billing_email, addendum_row)
            addendum_status = update_addendum_after_billing(clean(addendum_row.get("name")), existing_invoice)
            update_sales_order_billing(
                sales_order_name,
                contact_name,
                billing_email,
                address_name,
                po_number,
                billing_notes,
                existing_invoice,
                service_agreement_name,
                clean(addendum_row.get("name")),
            )
            release_savepoint(savepoint_name)
            return build_billing_setup_response(
                quote_name,
                sales_order_name,
                existing_invoice,
                auto_repeat_name,
                service_agreement_name,
                clean(addendum_row.get("name")),
                addendum_status,
            )

        invoice_doc = create_invoice_from_sales_order(sales_order_doc, billing_email, addendum_row)
        update_invoice_links(
            invoice_doc.name,
            service_agreement_name,
            clean(addendum_row.get("name")),
            billing_email,
        )
        auto_repeat_name = ensure_auto_repeat(invoice_doc.name, billing_email, addendum_row)
        addendum_status = update_addendum_after_billing(clean(addendum_row.get("name")), invoice_doc.name)
        update_sales_order_billing(
            sales_order_name,
            contact_name,
            billing_email,
            address_name,
            po_number,
            billing_notes,
            invoice_doc.name,
            service_agreement_name,
            clean(addendum_row.get("name")),
        )
        release_savepoint(savepoint_name)
        try:
            send_invoice_email(invoice_doc, billing_email)
        except Exception:
            frappe.log_error(get_traceback_text(), "Public Quote Billing Invoice Email")
        return build_billing_setup_response(
            quote_name,
            sales_order_name,
            invoice_doc.name,
            auto_repeat_name,
            service_agreement_name,
            clean(addendum_row.get("name")),
            addendum_status,
        )
    except Exception:
        rollback_savepoint(savepoint_name)
        existing_response = get_existing_billing_setup_response(quote_name, sales_order_name)
        if existing_response:
            return existing_response
        frappe.log_error(get_traceback_text(), "Complete Public Quote Billing Setup V2")
        fail("We could not complete billing setup right now. Please reply to your quote email and our team will help.")

__all__ = [
    "dynamic_link_filters",
    "ensure_dynamic_link",
    "ensure_signed_addendum",
    "ensure_contact",
    "ensure_address",
    "sync_customer",
    "update_sales_order_billing",
    "ensure_sales_order_submitted",
    "update_invoice_links",
    "create_invoice_from_sales_order",
    "send_invoice_email",
    "ensure_auto_repeat",
    "update_addendum_after_billing",
    "complete_public_quote_billing_setup_v2",
]
