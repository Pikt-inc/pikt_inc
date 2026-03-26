from __future__ import annotations

from typing import Any, TypedDict


class PortalContactLinkRow(TypedDict, total=False):
    contact_name: str
    first_name: str
    last_name: str
    email_id: str
    phone: str
    mobile_no: str
    designation: str
    address_name: str
    is_primary_contact: int
    is_billing_contact: int
    customer_name: str


class CustomerRow(TypedDict, total=False):
    name: str
    customer_name: str
    customer_primary_contact: str
    customer_primary_address: str
    tax_id: str


class ContactRow(TypedDict, total=False):
    name: str
    first_name: str
    last_name: str
    email_id: str
    phone: str
    mobile_no: str
    designation: str
    company_name: str
    address: str
    user: str
    is_primary_contact: int
    is_billing_contact: int


class AddressRow(TypedDict, total=False):
    name: str
    address_title: str
    address_type: str
    address_line1: str
    address_line2: str
    city: str
    state: str
    pincode: str
    country: str


class AgreementRow(TypedDict, total=False):
    name: str
    agreement_name: str
    status: str
    template: str
    template_version: str
    signed_by_name: str
    signed_by_title: str
    signed_by_email: str
    signed_on: Any
    rendered_html_snapshot: str
    modified: Any


class AddendumRow(TypedDict, total=False):
    name: str
    addendum_name: str
    service_agreement: str
    quotation: str
    sales_order: str
    initial_invoice: str
    building: str
    status: str
    term_model: str
    fixed_term_months: str
    start_date: Any
    end_date: Any
    template: str
    template_version: str
    signed_by_name: str
    signed_by_title: str
    signed_by_email: str
    signed_on: Any
    billing_completed_on: Any
    access_completed_on: Any
    rendered_html_snapshot: str
    modified: Any


class InvoiceRow(TypedDict, total=False):
    name: str
    posting_date: Any
    due_date: Any
    status: str
    currency: str
    grand_total: Any
    outstanding_amount: Any
    docstatus: int
    customer: str
    customer_name: str
    custom_building: str
    custom_service_agreement: str
    custom_service_agreement_addendum: str
    modified: Any


class BuildingRow(TypedDict, total=False):
    name: str
    customer: str
    building_name: str
    active: int
    address_line_1: str
    address_line_2: str
    city: str
    state: str
    postal_code: str
    site_supervisor_name: str
    site_supervisor_phone: str
    site_notes: str
    access_notes: str
    alarm_notes: str
    access_method: str
    access_entrance: str
    access_entry_details: str
    has_alarm_system: str
    alarm_instructions: str
    allowed_entry_time: str
    primary_site_contact: str
    lockout_emergency_contact: str
    key_fob_handoff_details: str
    areas_to_avoid: str
    closing_instructions: str
    parking_elevator_notes: str
    first_service_notes: str
    access_details_confirmed: Any
    access_details_completed_on: Any
    custom_service_agreement: str
    custom_service_agreement_addendum: str
    modified: Any
