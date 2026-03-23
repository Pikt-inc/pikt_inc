from __future__ import annotations

import frappe
from frappe.utils import add_to_date, get_datetime, getdate, now_datetime, nowdate

DEFAULT_COMPANY = "Pikt, inc."
DEFAULT_COUNTRY = "United States"
DEFAULT_CURRENCY = "USD"
DEFAULT_PRICE_LIST = "Standard Selling"
DEFAULT_WAREHOUSE = "Stores - Pikt, inc."


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def fail(message):
    frappe.throw(message)


def get_datetime_safe(value):
    if not value:
        return None
    try:
        return get_datetime(value)
    except Exception:
        return None


def get_date_safe(value):
    if not value:
        return None
    try:
        return getdate(value)
    except Exception:
        return None


def make_accept_token(docname=""):
    rows = frappe.db.sql("select replace(uuid(), '-', '') as token", as_dict=True)
    token = clean((rows or [{}])[0].get("token"))
    if token:
        return token
    return "%s-%s" % (
        clean(docname) or "quote",
        now_datetime().strftime("%Y%m%d%H%M%S%f"),
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
            ["name", "address_line1", "address_line2", "city", "state", "pincode", "country"],
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
                "customer",
                "customer_name",
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
    return payload


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


def get_public_quote_access_result(quote_name=None, token=None):
    quote_name = clean(quote_name if quote_name is not None else frappe.form_dict.get("quote"))
    token = clean(token if token is not None else frappe.form_dict.get("token"))

    if not quote_name:
        return {
            "state": "invalid",
            "message": "Missing quotation reference. Please return to your quote email and try again.",
        }

    if not token:
        return {
            "state": "invalid",
            "message": "Missing secure access token. Please return to your quote email and try again.",
        }

    row = get_quote_row(quote_name)
    if not row:
        return {
            "state": "invalid",
            "message": "We could not find that quotation. Please return to your quote email and try again.",
        }

    if clean(row.get("custom_accept_token")) != token:
        return {
            "state": "invalid",
            "message": "This quotation link is no longer valid. Please return to your quote email and try again.",
            "row": row,
        }

    if int(row.get("docstatus") or 0) == 2 or clean(row.get("status")) == "Cancelled":
        return {
            "state": "cancelled",
            "message": "This quotation has been cancelled and can no longer be accepted.",
            "row": row,
        }

    expires_dt = get_datetime_safe(row.get("custom_accept_token_expires_on"))
    if (not expires_dt) or (now_datetime() >= expires_dt):
        return {
            "state": "expired",
            "message": "This quotation link has expired. Please contact our team if you still need service.",
            "row": row,
        }

    valid_till = get_date_safe(row.get("valid_till"))
    if valid_till and nowdate() > str(valid_till):
        return {
            "state": "expired",
            "message": "This quotation is past its valid-through date. Please contact our team to refresh it.",
            "row": row,
        }

    if int(row.get("docstatus") or 0) != 1:
        return {
            "state": "invalid",
            "message": "This quotation is not ready for public review yet.",
            "row": row,
        }

    accepted_sales_order = clean(row.get("custom_accepted_sales_order"))
    if accepted_sales_order and frappe.db.exists("Sales Order", accepted_sales_order):
        return {
            "state": "accepted",
            "message": "This quotation has already been accepted.",
            "row": row,
            "sales_order": accepted_sales_order,
        }

    if clean(row.get("quotation_to")) not in ("Lead", "Customer") or not clean(row.get("party_name")):
        return {
            "state": "invalid",
            "message": "This quotation is not available through the public review flow.",
            "row": row,
        }

    return {
        "state": "ready",
        "message": "",
        "row": row,
        "sales_order": "",
    }


def validate_public_quote(quote=None, token=None):
    result = get_public_quote_access_result(quote_name=quote, token=token)
    if result.get("state") in ("ready", "accepted"):
        items = load_review_items(clean((result.get("row") or {}).get("name")))
        return build_validate_payload(
            result.get("state"),
            result.get("message", ""),
            row=result.get("row"),
            items=items,
        )
    return build_validate_payload(result.get("state"), result.get("message", ""))


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


def ensure_customer(quote_row, lead_row):
    lead_name = clean((quote_row or {}).get("party_name"))
    contact_email = clean((quote_row or {}).get("contact_email")) or clean((lead_row or {}).get("email_id"))

    customer = clean(frappe.db.get_value("Customer", {"lead_name": lead_name}, "name"))
    if not customer:
        customer = find_customer_by_email(contact_email)

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
    customer_doc.insert(ignore_permissions=True)
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
    quote_items = load_accept_items(quote_name)
    quote_taxes = load_quote_taxes(quote_name)
    current_target = clean((row or {}).get("quotation_to"))

    try:
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
            row = get_quote_row(quote_name)
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
        return build_accept_payload(
            "accepted",
            "Your quotation has been accepted.",
            row=row,
            items=quote_items,
            sales_order_name=sales_order.name,
        )
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Accept Public Quotation")
        return build_accept_payload(
            "invalid",
            "We could not accept this quotation right now. Please contact our team for help.",
        )


def load_public_quote_portal_state(quote=None, token=None):
    result = get_public_quote_access_result(quote_name=quote, token=token)
    if result.get("state") in ("ready", "accepted"):
        return build_load_portal_state_response(
            result.get("state"),
            result.get("message", ""),
            row=result.get("row"),
        )
    return build_load_portal_state_response(result.get("state"), result.get("message", ""))
