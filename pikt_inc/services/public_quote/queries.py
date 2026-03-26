from __future__ import annotations

from typing import Any

import frappe

from .rows import (
    AddendumRow,
    AddressRow,
    BuildingRow,
    ContactRow,
    CustomerRow,
    LeadRow,
    SalesOrderRow,
    ServiceAgreementRow,
    ServiceAgreementTemplateRow,
    QuotationRow,
)
from .shared import clean, normalize

def get_quote_row(quote_name):
    quote_name = clean(quote_name)
    if not quote_name:
        return {}
    return (
        frappe.db.get_value(
            "Quotation",
            quote_name,
            [
                "name",
                "quotation_to",
                "party_name",
                "contact_email",
                "customer_name",
                "currency",
                "conversion_rate",
                "selling_price_list",
                "price_list_currency",
                "plc_conversion_rate",
                "taxes_and_charges",
                "grand_total",
                "rounded_total",
                "transaction_date",
                "valid_till",
                "terms",
                "company",
                "order_type",
                "docstatus",
                "status",
                "custom_accept_token",
                "custom_accept_token_expires_on",
                "custom_accepted_sales_order",
                "opportunity",
                "custom_building",
                "custom_service_agreement",
                "custom_service_agreement_addendum",
            ],
            as_dict=True,
        )
        or {}
    )

def get_customer_row(customer_name):
    customer_name = clean(customer_name)
    if not customer_name:
        return {}
    return (
        frappe.db.get_value(
            "Customer",
            customer_name,
            [
                "name",
                "customer_name",
                "lead_name",
                "email_id",
                "mobile_no",
                "customer_primary_contact",
                "customer_primary_address",
                "tax_id",
            ],
            as_dict=True,
        )
        or {}
    )

def get_lead_row(lead_name):
    lead_name = clean(lead_name)
    if not lead_name:
        return {}
    return (
        frappe.db.get_value(
            "Lead",
            lead_name,
            ["first_name", "last_name", "company_name", "email_id", "phone"],
            as_dict=True,
        )
        or {}
    )

def get_contact_row(contact_name):
    contact_name = clean(contact_name)
    if not contact_name:
        return {}
    return (
        frappe.db.get_value(
            "Contact",
            contact_name,
            ["name", "full_name", "first_name", "last_name", "email_id"],
            as_dict=True,
        )
        or {}
    )

def get_address_row(address_name):
    address_name = clean(address_name)
    if not address_name:
        return {}
    return (
        frappe.db.get_value(
            "Address",
            address_name,
            [
                "name",
                "address_title",
                "address_line1",
                "address_line2",
                "city",
                "state",
                "pincode",
                "country",
            ],
            as_dict=True,
        )
        or {}
    )

def get_building_row(building_name):
    building_name = clean(building_name)
    if not building_name:
        return {}
    return (
        frappe.db.get_value(
            "Building",
            building_name,
            [
                "name",
                "building_name",
                "address_line_1",
                "address_line_2",
                "city",
                "state",
                "postal_code",
                "access_method",
                "access_entrance",
                "access_entry_details",
                "has_alarm_system",
                "alarm_instructions",
                "allowed_entry_time",
                "primary_site_contact",
                "lockout_emergency_contact",
                "key_fob_handoff_details",
                "areas_to_avoid",
                "closing_instructions",
                "parking_elevator_notes",
                "first_service_notes",
                "access_details_confirmed",
                "access_details_completed_on",
                "custom_service_agreement",
                "custom_service_agreement_addendum",
            ],
            as_dict=True,
        )
        or {}
    )

def get_sales_order_row(sales_order_name):
    sales_order_name = clean(sales_order_name)
    if not sales_order_name:
        return {}
    return (
        frappe.db.get_value(
            "Sales Order",
            sales_order_name,
            [
                "name",
                "company",
                "customer",
                "customer_name",
                "currency",
                "transaction_date",
                "delivery_date",
                "selling_price_list",
                "price_list_currency",
                "plc_conversion_rate",
                "conversion_rate",
                "taxes_and_charges",
                "payment_terms_template",
                "contact_person",
                "contact_email",
                "customer_address",
                "po_no",
                "status",
                "docstatus",
                "custom_public_billing_notes",
                "custom_billing_setup_completed_on",
                "custom_billing_recipient_email",
                "custom_initial_invoice",
                "custom_building",
                "custom_access_method",
                "custom_access_entrance",
                "custom_access_entry_details",
                "custom_has_alarm_system",
                "custom_alarm_instructions",
                "custom_allowed_entry_time",
                "custom_primary_site_contact",
                "custom_lockout_emergency_contact",
                "custom_key_fob_handoff_details",
                "custom_areas_to_avoid",
                "custom_closing_instructions",
                "custom_parking_elevator_notes",
                "custom_first_service_notes",
                "custom_access_details_confirmed",
                "custom_access_details_completed_on",
                "custom_service_agreement",
                "custom_service_agreement_addendum",
            ],
            as_dict=True,
        )
        or {}
    )

def load_review_items(quote_name):
    return frappe.get_all(
        "Quotation Item",
        filters={"parent": quote_name},
        fields=["item_code", "item_name", "description", "qty", "rate", "amount"],
        order_by="idx asc",
    )

def load_accept_items(quote_name):
    return frappe.get_all(
        "Quotation Item",
        filters={"parent": quote_name},
        fields=[
            "name",
            "item_code",
            "item_name",
            "description",
            "qty",
            "rate",
            "amount",
            "warehouse",
            "uom",
            "stock_uom",
            "conversion_factor",
            "item_tax_template",
            "item_tax_rate",
        ],
        order_by="idx asc",
    )

def load_quote_taxes(quote_name):
    return frappe.get_all(
        "Sales Taxes and Charges",
        filters={"parenttype": "Quotation", "parent": quote_name},
        fields=[
            "charge_type",
            "row_id",
            "account_head",
            "description",
            "included_in_print_rate",
            "included_in_paid_amount",
            "set_by_item_tax_template",
            "is_tax_withholding_account",
            "cost_center",
            "project",
            "rate",
            "account_currency",
            "tax_amount",
            "tax_amount_after_discount_amount",
            "total",
            "dont_recompute_tax",
        ],
        order_by="idx asc",
    )

def get_active_template(template_type):
    rows = frappe.get_all(
        "Service Agreement Template",
        filters={"template_type": clean(template_type), "is_active": 1},
        fields=[
            "name",
            "template_name",
            "template_type",
            "version",
            "summary_title",
            "summary_text",
            "body_html",
        ],
        order_by="creation desc",
        limit=1,
    )
    if rows:
        return rows[0]
    return {}

def get_active_master_agreement(customer_name):
    customer_name = clean(customer_name)
    if not customer_name:
        return {}
    rows = frappe.get_all(
        "Service Agreement",
        filters={"customer": customer_name, "status": "Active"},
        fields=[
            "name",
            "agreement_name",
            "status",
            "template",
            "template_version",
            "signed_by_name",
            "signed_by_email",
            "signed_on",
        ],
        order_by="creation desc",
        limit=1,
    )
    if rows:
        return rows[0]
    return {}

def get_addendum_row(quote_name, sales_order_name):
    quote_name = clean(quote_name)
    sales_order_name = clean(sales_order_name)
    fields = [
        "name",
        "addendum_name",
        "service_agreement",
        "customer",
        "quotation",
        "sales_order",
        "initial_invoice",
        "building",
        "status",
        "term_model",
        "fixed_term_months",
        "start_date",
        "end_date",
        "template",
        "template_version",
        "signed_by_name",
        "signed_by_email",
        "signed_on",
        "billing_completed_on",
        "access_completed_on",
        "rendered_html_snapshot",
    ]

    if quote_name:
        rows = frappe.get_all(
            "Service Agreement Addendum",
            filters={"quotation": quote_name},
            fields=fields,
            order_by="creation desc",
            limit=1,
        )
        if rows:
            return rows[0]

    if sales_order_name:
        rows = frappe.get_all(
            "Service Agreement Addendum",
            filters={"sales_order": sales_order_name},
            fields=fields,
            order_by="creation desc",
            limit=1,
        )
        if rows:
            return rows[0]

    return {}

def find_customer_by_email(contact_email):
    contact_email = clean(contact_email)
    if not contact_email:
        return ""

    customer = clean(frappe.db.get_value("Customer", {"email_id": contact_email}, "name"))
    if customer:
        return customer

    rows = frappe.db.sql(
        """
        select dl.link_name as customer
        from `tabContact` c
        inner join `tabDynamic Link` dl
            on dl.parent = c.name
           and dl.parenttype = 'Contact'
           and dl.link_doctype = 'Customer'
        where ifnull(c.email_id, '') = %s
        order by c.creation asc
        limit 1
        """,
        (contact_email,),
        as_dict=True,
    )
    if rows:
        return clean(rows[0].get("customer"))
    return ""

def find_customer_for_quote(lead_name, contact_email):
    lead_name = clean(lead_name)
    contact_email = clean(contact_email)
    customer = clean(frappe.db.get_value("Customer", {"lead_name": lead_name}, "name"))
    if customer:
        return customer
    return find_customer_by_email(contact_email)

def find_contact_for_customer(customer_name, billing_email, exclude_contact_name=""):
    customer_name = clean(customer_name)
    exclude_contact_name = clean(exclude_contact_name)
    customer_row = get_customer_row(customer_name)
    primary_contact = clean(customer_row.get("customer_primary_contact"))
    if primary_contact and primary_contact != exclude_contact_name:
        return primary_contact

    billing_email = clean(billing_email).lower()
    if billing_email:
        rows = frappe.db.sql(
            """
            select c.name
            from `tabContact` c
            inner join `tabDynamic Link` dl
                on dl.parent = c.name
               and dl.parenttype = 'Contact'
               and dl.link_doctype = 'Customer'
            where dl.link_name = %s and ifnull(c.email_id, '') = %s
              and (%s = '' or c.name != %s)
            order by c.creation asc
            """,
            (customer_name, billing_email, exclude_contact_name, exclude_contact_name),
            as_dict=True,
        )
        for row in rows:
            contact_name = clean(row.get("name"))
            if contact_name and contact_name != exclude_contact_name:
                return contact_name

    rows = frappe.db.sql(
        """
        select c.name
        from `tabContact` c
        inner join `tabDynamic Link` dl
            on dl.parent = c.name
           and dl.parenttype = 'Contact'
           and dl.link_doctype = 'Customer'
        where dl.link_name = %s
          and (%s = '' or c.name != %s)
        order by c.creation asc
        """,
        (customer_name, exclude_contact_name, exclude_contact_name),
        as_dict=True,
    )
    for row in rows:
        contact_name = clean(row.get("name"))
        if contact_name and contact_name != exclude_contact_name:
            return contact_name
    return ""

def find_address_for_customer(customer_name):
    customer_name = clean(customer_name)
    customer_row = get_customer_row(customer_name)
    primary_address = clean(customer_row.get("customer_primary_address"))
    if primary_address:
        return primary_address

    rows = frappe.db.sql(
        """
        select a.name
        from `tabAddress` a
        inner join `tabDynamic Link` dl
            on dl.parent = a.name
           and dl.parenttype = 'Address'
           and dl.link_doctype = 'Customer'
        where dl.link_name = %s
        order by a.is_primary_address desc, a.creation asc
        limit 1
        """,
        (customer_name,),
        as_dict=True,
    )
    if rows:
        return clean(rows[0].get("name"))
    return ""

def find_matching_building(
    customer_name,
    service_address_line_1,
    service_address_line_2,
    service_city,
    service_state,
    service_postal_code,
):
    rows = frappe.get_all(
        "Building",
        filters={"customer": clean(customer_name), "active": 1},
        fields=["name", "address_line_1", "address_line_2", "city", "state", "postal_code"],
        order_by="creation asc",
    )
    target = (
        normalize(service_address_line_1),
        normalize(service_address_line_2),
        normalize(service_city),
        normalize(service_state),
        normalize(service_postal_code),
    )
    for row in rows or []:
        candidate = (
            normalize(row.get("address_line_1")),
            normalize(row.get("address_line_2")),
            normalize(row.get("city")),
            normalize(row.get("state")),
            normalize(row.get("postal_code")),
        )
        if candidate == target:
            return clean(row.get("name"))
    return ""

__all__ = [
    "get_quote_row",
    "get_customer_row",
    "get_lead_row",
    "get_contact_row",
    "get_address_row",
    "get_building_row",
    "get_sales_order_row",
    "load_review_items",
    "load_accept_items",
    "load_quote_taxes",
    "get_active_template",
    "get_active_master_agreement",
    "get_addendum_row",
    "find_customer_by_email",
    "find_customer_for_quote",
    "find_contact_for_customer",
    "find_address_for_customer",
    "find_matching_building",
]
