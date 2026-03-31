from __future__ import annotations

import frappe

from .rows import AddendumRow, AddressRow, AgreementRow, BuildingRow, ContactRow, CustomerRow, InvoiceRow, PortalContactLinkRow
from .shared import clean


def _load_contact_row(contact_name: str) -> ContactRow:
    contact_name = clean(contact_name)
    if not contact_name:
        return {}
    row = frappe.db.get_value(
        "Contact",
        contact_name,
        [
            "name",
            "first_name",
            "last_name",
            "email_id",
            "phone",
            "mobile_no",
            "designation",
            "company_name",
            "address",
            "user",
            "is_primary_contact",
            "is_billing_contact",
        ],
        as_dict=True,
    )
    return dict(row or {})


def _load_address_row(address_name: str) -> AddressRow:
    address_name = clean(address_name)
    if not address_name:
        return {}
    row = frappe.db.get_value(
        "Address",
        address_name,
        [
            "name",
            "address_title",
            "address_type",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "pincode",
            "country",
        ],
        as_dict=True,
    )
    return dict(row or {})


def _get_portal_contact_links(session_user: str) -> list[PortalContactLinkRow]:
    rows = frappe.db.sql(
        """
        select
            c.name as contact_name,
            ifnull(c.first_name, '') as first_name,
            ifnull(c.last_name, '') as last_name,
            ifnull(c.email_id, '') as email_id,
            ifnull(c.phone, '') as phone,
            ifnull(c.mobile_no, '') as mobile_no,
            ifnull(c.designation, '') as designation,
            ifnull(c.address, '') as address_name,
            ifnull(c.is_primary_contact, 0) as is_primary_contact,
            ifnull(c.is_billing_contact, 0) as is_billing_contact,
            dl.link_name as customer_name
        from `tabContact` c
        inner join `tabDynamic Link` dl
            on dl.parent = c.name
           and dl.parenttype = 'Contact'
           and dl.link_doctype = 'Customer'
        where ifnull(c.user, '') = %s
        order by c.is_primary_contact desc, c.is_billing_contact desc, c.modified desc, c.creation desc
        """,
        (session_user,),
        as_dict=True,
    )
    return [dict(row) for row in rows or []]


def _get_customer_row(customer_name: str) -> CustomerRow:
    row = frappe.db.get_value(
        "Customer",
        customer_name,
        ["name", "customer_name", "customer_primary_contact", "customer_primary_address", "tax_id"],
        as_dict=True,
    )
    return dict(row or {})


def _get_agreements(customer_name: str) -> tuple[list[AgreementRow], list[AddendumRow]]:
    agreements = frappe.get_all(
        "Service Agreement",
        filters={"customer": customer_name},
        fields=[
            "name",
            "agreement_name",
            "status",
            "template",
            "template_version",
            "signed_by_name",
            "signed_by_title",
            "signed_by_email",
            "signed_on",
            "rendered_html_snapshot",
            "modified",
        ],
        order_by="signed_on desc, modified desc",
    )
    addenda = frappe.get_all(
        "Service Agreement Addendum",
        filters={"customer": customer_name},
        fields=[
            "name",
            "addendum_name",
            "service_agreement",
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
            "signed_by_title",
            "signed_by_email",
            "signed_on",
            "billing_completed_on",
            "access_completed_on",
            "rendered_html_snapshot",
            "modified",
        ],
        order_by="start_date desc, modified desc",
    )
    return list(agreements or []), list(addenda or [])


def _get_invoices(customer_name: str) -> list[InvoiceRow]:
    return list(
        frappe.get_all(
            "Sales Invoice",
            filters={"customer": customer_name, "docstatus": ["!=", 2]},
            fields=[
                "name",
                "posting_date",
                "due_date",
                "status",
                "currency",
                "grand_total",
                "outstanding_amount",
                "docstatus",
                "customer",
                "customer_name",
                "custom_building",
                "custom_service_agreement",
                "custom_service_agreement_addendum",
                "modified",
            ],
            order_by="posting_date desc, modified desc",
        )
        or []
    )


def _get_buildings(customer_name: str) -> list[BuildingRow]:
    return list(
        frappe.get_all(
            "Building",
            filters={"customer": customer_name},
            fields=[
                "name",
                "building_name",
                "active",
                "current_sop",
                "address_line_1",
                "address_line_2",
                "city",
                "state",
                "postal_code",
                "site_supervisor_name",
                "site_supervisor_phone",
                "site_notes",
                "access_notes",
                "alarm_notes",
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
                "modified",
            ],
            order_by="active desc, building_name asc",
        )
        or []
    )
