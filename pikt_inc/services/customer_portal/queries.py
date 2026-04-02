from __future__ import annotations

import frappe

from .rows import (
    AddendumRow,
    AddressRow,
    AgreementRow,
    BuildingRow,
    ChecklistSessionItemRow,
    ChecklistSessionRow,
    ContactRow,
    CustomerRow,
    InvoiceRow,
    UserRow,
)
from .shared import clean


def _load_user_row(user_name: str) -> UserRow:
    user_name = clean(user_name)
    if not user_name:
        return {}
    row = frappe.db.get_value(
        "User",
        user_name,
        ["name", "email", "custom_customer"],
        as_dict=True,
    )
    return dict(row or {})


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


def _find_customer_contact_by_email(customer_name: str, email_address: str) -> str:
    customer_name = clean(customer_name)
    email_address = clean(email_address).lower()
    if not customer_name or not email_address:
        return ""

    rows = frappe.db.sql(
        """
        select
            c.name
        from `tabContact` c
        inner join `tabDynamic Link` dl
            on dl.parent = c.name
           and dl.parenttype = 'Contact'
           and dl.link_doctype = 'Customer'
        where dl.link_name = %s
          and lower(ifnull(c.email_id, '')) = %s
        order by c.is_primary_contact desc, c.modified desc, c.creation desc
        limit 1
        """,
        (customer_name, email_address),
        as_dict=True,
    )
    if not rows:
        return ""
    return clean(rows[0].get("name"))


def _get_customer_row(customer_name: str) -> CustomerRow:
    row = frappe.db.get_value(
        "Customer",
        customer_name,
        ["name", "customer_name", "customer_primary_contact", "customer_primary_address", "tax_id"],
        as_dict=True,
    )
    return dict(row or {})


def _load_building_row(building_name: str) -> BuildingRow:
    building_name = clean(building_name)
    if not building_name:
        return {}
    row = frappe.db.get_value(
        "Building",
        building_name,
        [
            "name",
            "customer",
            "building_name",
            "active",
            "current_sop",
            "current_checklist_template",
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
            "creation",
            "modified",
        ],
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
                "customer",
                "building_name",
                "active",
                "current_sop",
                "current_checklist_template",
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
                "creation",
                "modified",
            ],
            order_by="active desc, building_name asc",
        )
        or []
    )


def _session_sort_value(row: ChecklistSessionRow) -> str:
    return str(
        row.get("completed_at")
        or row.get("started_at")
        or row.get("service_date")
        or row.get("modified")
        or row.get("creation")
        or ""
    )


def _load_checklist_session_row(session_name: str) -> ChecklistSessionRow:
    session_name = clean(session_name)
    if not session_name:
        return {}
    row = frappe.db.get_value(
        "Checklist Session",
        session_name,
        [
            "name",
            "building",
            "service_date",
            "checklist_template",
            "status",
            "started_at",
            "completed_at",
            "worker",
            "session_notes",
            "creation",
            "modified",
        ],
        as_dict=True,
    )
    return dict(row or {})


def _get_checklist_session_rows(
    customer_name: str,
    *,
    building_name: str = "",
    status: str = "",
    limit: int = 200,
) -> list[ChecklistSessionRow]:
    customer_name = clean(customer_name)
    building_name = clean(building_name)
    limit = max(1, int(limit or 200))

    if building_name:
        building_rows = [_load_building_row(building_name)]
    else:
        building_rows = _get_buildings(customer_name)

    scoped_buildings = [
        clean(row.get("name"))
        for row in building_rows
        if clean(row.get("name")) and clean(row.get("customer")) == customer_name
    ]
    if not scoped_buildings:
        return []

    rows: list[ChecklistSessionRow] = []
    per_building_limit = max(limit, 1)
    for current_building in scoped_buildings:
        filters: dict[str, object] = {"building": current_building}
        if clean(status):
            filters["status"] = clean(status)
        building_rows = frappe.get_all(
            "Checklist Session",
            filters=filters,
            fields=[
                "name",
                "building",
                "service_date",
                "checklist_template",
                "status",
                "started_at",
                "completed_at",
                "worker",
                "session_notes",
                "creation",
                "modified",
            ],
            order_by="completed_at desc, started_at desc, creation desc",
            limit=per_building_limit,
        )
        rows.extend(list(building_rows or []))

    rows.sort(key=_session_sort_value, reverse=True)
    return rows[:limit]


def _get_checklist_session_item_rows(session_name: str) -> list[ChecklistSessionItemRow]:
    session_name = clean(session_name)
    if not session_name:
        return []
    rows = frappe.get_all(
        "Checklist Session Item",
        filters={"parent": session_name, "parenttype": "Checklist Session", "parentfield": "items"},
        fields=[
            "name",
            "idx",
            "item_key",
            "category",
            "sort_order",
            "title_snapshot",
            "description_snapshot",
            "requires_image",
            "allow_notes",
            "is_required",
            "completed",
            "completed_at",
            "note",
            "proof_image",
        ],
        order_by="idx asc",
        limit=500,
    )
    return list(rows or [])
