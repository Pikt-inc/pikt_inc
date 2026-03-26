from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import now_datetime

from .models import AccessSetupInput
from .payloads import build_access_setup_response, get_existing_access_setup_response
from .portal import ensure_quote_is_valid_for_portal_write
from .queries import get_addendum_row, get_sales_order_row, find_matching_building
from .shared import (
    begin_savepoint, clean, doc_db_set_values, fail, get_traceback_text, lock_document_row,
    make_access_notes, make_alarm_notes, make_site_notes, release_savepoint, rollback_savepoint, truthy, truncate_name
)

def generate_building_name(customer_display, address_line_1, city):
    parts = []
    if clean(customer_display):
        parts.append(clean(customer_display))
    if clean(address_line_1):
        parts.append(clean(address_line_1))
    if clean(city):
        parts.append(clean(city))
    base = " - ".join(parts) or "Service Site"
    base = truncate_name(base, 120)
    candidate = base
    suffix = 2
    while frappe.db.exists("Building", candidate):
        candidate = truncate_name(base, 112) + " #" + str(suffix)
        suffix += 1
    return candidate

def create_or_update_building(
    sales_order_row,
    service_address_line_1,
    service_address_line_2,
    service_city,
    service_state,
    service_postal_code,
    access_method,
    access_entrance,
    access_entry_details,
    has_alarm_system,
    alarm_instructions,
    allowed_entry_time,
    primary_site_contact,
    lockout_emergency_contact,
    key_fob_handoff_details,
    areas_to_avoid,
    closing_instructions,
    parking_elevator_notes,
    first_service_notes,
    access_details_confirmed,
    service_agreement_name,
    addendum_name,
):
    existing_building = clean(sales_order_row.get("custom_building"))
    customer_name = clean(sales_order_row.get("customer"))
    customer_display = clean(sales_order_row.get("customer_name")) or customer_name
    if not customer_name:
        fail("We could not resolve the customer for this accepted quote.")
    if frappe.db.exists("Customer", customer_name):
        lock_document_row("Customer", customer_name)

    access_completed_on = now_datetime()
    building_values = {
        "customer": customer_name,
        "active": 1,
        "address_line_1": clean(service_address_line_1),
        "address_line_2": clean(service_address_line_2),
        "city": clean(service_city),
        "state": clean(service_state),
        "postal_code": clean(service_postal_code),
        "access_method": clean(access_method),
        "access_entrance": clean(access_entrance),
        "access_entry_details": clean(access_entry_details),
        "has_alarm_system": clean(has_alarm_system) or "No",
        "alarm_instructions": clean(alarm_instructions),
        "allowed_entry_time": clean(allowed_entry_time),
        "primary_site_contact": clean(primary_site_contact),
        "lockout_emergency_contact": clean(lockout_emergency_contact),
        "key_fob_handoff_details": clean(key_fob_handoff_details),
        "areas_to_avoid": clean(areas_to_avoid),
        "closing_instructions": clean(closing_instructions),
        "parking_elevator_notes": clean(parking_elevator_notes),
        "first_service_notes": clean(first_service_notes),
        "access_details_confirmed": access_details_confirmed,
        "access_details_completed_on": access_completed_on,
        "access_notes": make_access_notes(
            access_method,
            access_entrance,
            access_entry_details,
            allowed_entry_time,
            primary_site_contact,
            lockout_emergency_contact,
            key_fob_handoff_details,
            closing_instructions,
        ),
        "alarm_notes": make_alarm_notes(has_alarm_system, alarm_instructions),
        "site_notes": make_site_notes(parking_elevator_notes, areas_to_avoid, first_service_notes),
        "custom_service_agreement": clean(service_agreement_name),
        "custom_service_agreement_addendum": clean(addendum_name),
    }

    if existing_building and frappe.db.exists("Building", existing_building):
        doc_db_set_values("Building", existing_building, building_values)
        return existing_building, access_completed_on

    matched_building = find_matching_building(
        customer_name,
        service_address_line_1,
        service_address_line_2,
        service_city,
        service_state,
        service_postal_code,
    )
    if matched_building:
        doc_db_set_values("Building", matched_building, building_values)
        return matched_building, access_completed_on

    building_doc = frappe.get_doc(
        {
            "doctype": "Building",
            "building_name": generate_building_name(customer_display, service_address_line_1, service_city),
            "customer": customer_name,
            **building_values,
        }
    )
    building_doc.flags.ignore_permissions = True
    try:
        building_doc.insert(ignore_permissions=True)
    except Exception:
        matched_building = find_matching_building(
            customer_name,
            service_address_line_1,
            service_address_line_2,
            service_city,
            service_state,
            service_postal_code,
        )
        if matched_building:
            doc_db_set_values("Building", matched_building, building_values)
            return matched_building, access_completed_on
        raise
    return building_doc.name, access_completed_on

def update_linked_portal_records(
    building_name,
    quote_row,
    sales_order_name,
    invoice_name,
    service_agreement_name,
    addendum_name,
):
    opportunity_name = clean((quote_row or {}).get("opportunity"))
    if opportunity_name and frappe.db.exists("Opportunity", opportunity_name):
        doc_db_set_values(
            "Opportunity",
            opportunity_name,
            {
                "custom_building": clean(building_name),
                "custom_service_agreement": clean(service_agreement_name),
            },
        )
    if clean((quote_row or {}).get("name")) and frappe.db.exists("Quotation", clean(quote_row.get("name"))):
        doc_db_set_values(
            "Quotation",
            clean(quote_row.get("name")),
            {
                "custom_building": clean(building_name),
                "custom_service_agreement": clean(service_agreement_name),
                "custom_service_agreement_addendum": clean(addendum_name),
            },
        )
    if clean(sales_order_name) and frappe.db.exists("Sales Order", clean(sales_order_name)):
        doc_db_set_values(
            "Sales Order",
            clean(sales_order_name),
            {
                "custom_building": clean(building_name),
                "custom_service_agreement": clean(service_agreement_name),
                "custom_service_agreement_addendum": clean(addendum_name),
            },
        )
    if clean(invoice_name) and frappe.db.exists("Sales Invoice", clean(invoice_name)):
        doc_db_set_values(
            "Sales Invoice",
            clean(invoice_name),
            {
                "custom_building": clean(building_name),
                "custom_service_agreement": clean(service_agreement_name),
                "custom_service_agreement_addendum": clean(addendum_name),
            },
        )

def update_sales_order_access_snapshot(
    sales_order_name,
    access_method,
    access_entrance,
    access_entry_details,
    has_alarm_system,
    alarm_instructions,
    allowed_entry_time,
    primary_site_contact,
    lockout_emergency_contact,
    key_fob_handoff_details,
    areas_to_avoid,
    closing_instructions,
    parking_elevator_notes,
    first_service_notes,
    access_details_confirmed,
    access_completed_on,
):
    doc_db_set_values(
        "Sales Order",
        sales_order_name,
        {
            "custom_access_method": clean(access_method),
            "custom_access_entrance": clean(access_entrance),
            "custom_access_entry_details": clean(access_entry_details),
            "custom_has_alarm_system": clean(has_alarm_system) or "No",
            "custom_alarm_instructions": clean(alarm_instructions),
            "custom_allowed_entry_time": clean(allowed_entry_time),
            "custom_primary_site_contact": clean(primary_site_contact),
            "custom_lockout_emergency_contact": clean(lockout_emergency_contact),
            "custom_key_fob_handoff_details": clean(key_fob_handoff_details),
            "custom_areas_to_avoid": clean(areas_to_avoid),
            "custom_closing_instructions": clean(closing_instructions),
            "custom_parking_elevator_notes": clean(parking_elevator_notes),
            "custom_first_service_notes": clean(first_service_notes),
            "custom_access_details_confirmed": access_details_confirmed,
            "custom_access_details_completed_on": access_completed_on,
        },
    )

def update_addendum_after_access(addendum_name, building_name, access_completed_on):
    addendum_doc = frappe.get_doc("Service Agreement Addendum", addendum_name)
    if clean(addendum_doc.status) in ("Cancelled", "Expired"):
        fail("This service agreement addendum is no longer active.")
    doc_db_set_values(
        "Service Agreement Addendum",
        addendum_name,
        {
            "building": clean(building_name),
            "access_completed_on": access_completed_on,
            "status": "Active",
        },
    )
    return "Active"

def complete_public_quote_access_setup_v2(quote=None, token=None, **kwargs):
    payload = AccessSetupInput.from_request(quote=quote, token=token, **kwargs)
    quote_name = payload.quote
    token = payload.token
    service_address_line_1 = payload.service_address_line_1
    service_address_line_2 = payload.service_address_line_2
    service_city = payload.service_city
    service_state = payload.service_state
    service_postal_code = payload.service_postal_code
    access_method = payload.access_method
    access_entrance = payload.access_entrance
    access_entry_details = payload.access_entry_details
    has_alarm_system = payload.has_alarm_system or "No"
    alarm_instructions = payload.alarm_instructions
    allowed_entry_time = payload.allowed_entry_time
    primary_site_contact = payload.primary_site_contact
    lockout_emergency_contact = payload.lockout_emergency_contact
    key_fob_handoff_details = payload.key_fob_handoff_details
    areas_to_avoid = payload.areas_to_avoid
    closing_instructions = payload.closing_instructions
    parking_elevator_notes = payload.parking_elevator_notes
    first_service_notes = payload.first_service_notes
    access_details_confirmed = payload.access_details_confirmed

    allowed_methods = (
        "Door code / keypad",
        "Lockbox",
        "Front desk / building management",
        "Physical key or fob",
        "Staff will let us in",
        "Other",
    )

    if not quote_name:
        fail("Missing quotation reference. Please return to your quote email and try again.")
    if not token:
        fail("Missing secure access token. Please return to your quote email and try again.")
    if not service_address_line_1:
        fail("Service address line 1 is required.")
    if not service_city:
        fail("Service city is required.")
    if not service_state:
        fail("Service state is required.")
    if not service_postal_code:
        fail("Service postal code is required.")
    if access_method not in allowed_methods:
        fail("Select how our team will access the building.")
    if not access_entrance:
        fail("Tell us which entrance our team should use.")
    if has_alarm_system not in ("No", "Yes"):
        fail("Select whether there is an alarm or security system.")
    if not allowed_entry_time:
        fail("Tell us when our team is allowed to enter the building.")
    if not primary_site_contact:
        fail("Primary site contact is required.")
    if not access_details_confirmed:
        fail(
            "Please confirm the access details will be accurate and ready before the first scheduled service."
        )

    quote_row = ensure_quote_is_valid_for_portal_write(
        quote_name,
        token,
        "This quotation has been cancelled and can no longer be updated.",
        "This quotation is not ready for access setup.",
    )
    sales_order_name = clean(quote_row.get("custom_accepted_sales_order"))
    if not sales_order_name or not frappe.db.exists("Sales Order", sales_order_name):
        fail("We could not find the accepted sales order for this quote. Please contact our team.")

    sales_order_row = get_sales_order_row(sales_order_name)
    if int(sales_order_row.get("docstatus") or 0) == 2:
        fail("This accepted sales order is no longer active.")

    addendum_row = get_addendum_row(quote_name, sales_order_name)
    if not clean(addendum_row.get("name")):
        fail("Complete the service agreement before submitting service-site details.")
    if clean(addendum_row.get("status")) in ("Cancelled", "Expired"):
        fail("This service agreement addendum is no longer active.")

    invoice_name = clean(sales_order_row.get("custom_initial_invoice")) or clean(
        addendum_row.get("initial_invoice")
    )
    if not invoice_name:
        fail("Complete billing setup before submitting access details.")
    if not clean(addendum_row.get("billing_completed_on")):
        fail("Complete billing setup before submitting access details.")

    service_agreement_name = clean(addendum_row.get("service_agreement")) or clean(
        sales_order_row.get("custom_service_agreement")
    )
    existing_response = get_existing_access_setup_response(
        quote_name,
        sales_order_name,
        addendum_row=addendum_row,
        sales_order_row=sales_order_row,
    )
    if existing_response:
        return existing_response
    savepoint_name = begin_savepoint("quote_access_setup")

    try:
        lock_document_row("Sales Order", sales_order_name)
        sales_order_row = get_sales_order_row(sales_order_name)
        addendum_row = get_addendum_row(quote_name, sales_order_name)
        service_agreement_name = clean(addendum_row.get("service_agreement")) or clean(
            sales_order_row.get("custom_service_agreement")
        )
        existing_response = get_existing_access_setup_response(
            quote_name,
            sales_order_name,
            addendum_row=addendum_row,
            sales_order_row=sales_order_row,
        )
        if existing_response:
            release_savepoint(savepoint_name)
            return existing_response

        building_name, access_completed_on = create_or_update_building(
            sales_order_row,
            service_address_line_1,
            service_address_line_2,
            service_city,
            service_state,
            service_postal_code,
            access_method,
            access_entrance,
            access_entry_details,
            has_alarm_system,
            alarm_instructions,
            allowed_entry_time,
            primary_site_contact,
            lockout_emergency_contact,
            key_fob_handoff_details,
            areas_to_avoid,
            closing_instructions,
            parking_elevator_notes,
            first_service_notes,
            access_details_confirmed,
            service_agreement_name,
            clean(addendum_row.get("name")),
        )
        update_linked_portal_records(
            building_name,
            quote_row,
            sales_order_name,
            invoice_name,
            service_agreement_name,
            clean(addendum_row.get("name")),
        )
        update_sales_order_access_snapshot(
            sales_order_name,
            access_method,
            access_entrance,
            access_entry_details,
            has_alarm_system,
            alarm_instructions,
            allowed_entry_time,
            primary_site_contact,
            lockout_emergency_contact,
            key_fob_handoff_details,
            areas_to_avoid,
            closing_instructions,
            parking_elevator_notes,
            first_service_notes,
            access_details_confirmed,
            access_completed_on,
        )
        addendum_status = update_addendum_after_access(
            clean(addendum_row.get("name")),
            building_name,
            access_completed_on,
        )
        release_savepoint(savepoint_name)
        return build_access_setup_response(
            quote_name,
            sales_order_name,
            invoice_name,
            building_name,
            service_agreement_name,
            clean(addendum_row.get("name")),
            addendum_status,
            access_completed_on,
        )
    except Exception:
        rollback_savepoint(savepoint_name)
        existing_response = get_existing_access_setup_response(quote_name, sales_order_name)
        if existing_response:
            return existing_response
        frappe.log_error(get_traceback_text(), "Complete Public Quote Access Setup V2")
        fail("We could not save building access details right now. Please try again or contact our team.")

__all__ = [
    "generate_building_name",
    "create_or_update_building",
    "update_linked_portal_records",
    "update_sales_order_access_snapshot",
    "update_addendum_after_access",
    "complete_public_quote_access_setup_v2",
]
