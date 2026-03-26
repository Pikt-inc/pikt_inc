from __future__ import annotations

from typing import Any, TypedDict


class QuotationRow(TypedDict, total=False):
    name: str
    quotation_to: str
    party_name: str
    contact_email: str
    customer_name: str
    currency: str
    conversion_rate: float
    selling_price_list: str
    price_list_currency: str
    plc_conversion_rate: float
    taxes_and_charges: str
    grand_total: float
    rounded_total: float
    transaction_date: Any
    valid_till: Any
    terms: str
    company: str
    order_type: str
    docstatus: int
    status: str
    custom_accept_token: str
    custom_accept_token_expires_on: Any
    custom_accepted_sales_order: str
    opportunity: str
    custom_building: str
    custom_service_agreement: str
    custom_service_agreement_addendum: str


class CustomerRow(TypedDict, total=False):
    name: str
    customer_name: str
    lead_name: str
    email_id: str
    mobile_no: str
    customer_primary_contact: str
    customer_primary_address: str
    tax_id: str


class LeadRow(TypedDict, total=False):
    first_name: str
    last_name: str
    company_name: str
    email_id: str
    phone: str


class ContactRow(TypedDict, total=False):
    name: str
    full_name: str
    first_name: str
    last_name: str
    email_id: str


class AddressRow(TypedDict, total=False):
    name: str
    address_title: str
    address_line1: str
    address_line2: str
    city: str
    state: str
    pincode: str
    country: str


class BuildingRow(TypedDict, total=False):
    name: str
    building_name: str
    address_line_1: str
    address_line_2: str
    city: str
    state: str
    postal_code: str
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
    access_details_confirmed: int
    access_details_completed_on: Any
    custom_service_agreement: str
    custom_service_agreement_addendum: str


class SalesOrderRow(TypedDict, total=False):
    name: str
    company: str
    customer: str
    customer_name: str
    currency: str
    transaction_date: Any
    delivery_date: Any
    selling_price_list: str
    price_list_currency: str
    plc_conversion_rate: float
    conversion_rate: float
    taxes_and_charges: str
    payment_terms_template: str
    contact_person: str
    contact_email: str
    customer_address: str
    po_no: str
    status: str
    docstatus: int
    custom_public_billing_notes: str
    custom_billing_setup_completed_on: Any
    custom_billing_recipient_email: str
    custom_initial_invoice: str
    custom_building: str
    custom_access_method: str
    custom_access_entrance: str
    custom_access_entry_details: str
    custom_has_alarm_system: str
    custom_alarm_instructions: str
    custom_allowed_entry_time: str
    custom_primary_site_contact: str
    custom_lockout_emergency_contact: str
    custom_key_fob_handoff_details: str
    custom_areas_to_avoid: str
    custom_closing_instructions: str
    custom_parking_elevator_notes: str
    custom_first_service_notes: str
    custom_access_details_confirmed: int
    custom_access_details_completed_on: Any
    custom_service_agreement: str
    custom_service_agreement_addendum: str


class ServiceAgreementTemplateRow(TypedDict, total=False):
    name: str
    template_name: str
    template_type: str
    version: str
    summary_title: str
    summary_text: str
    body_html: str


class ServiceAgreementRow(TypedDict, total=False):
    name: str
    agreement_name: str
    status: str
    template: str
    template_version: str
    signed_by_name: str
    signed_by_email: str
    signed_on: Any


class AddendumRow(TypedDict, total=False):
    name: str
    addendum_name: str
    service_agreement: str
    customer: str
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
    signed_by_email: str
    signed_on: Any
    billing_completed_on: Any
    access_completed_on: Any
    rendered_html_snapshot: str


__all__ = [
    "AddendumRow",
    "AddressRow",
    "BuildingRow",
    "ContactRow",
    "CustomerRow",
    "LeadRow",
    "QuotationRow",
    "SalesOrderRow",
    "ServiceAgreementRow",
    "ServiceAgreementTemplateRow",
]
