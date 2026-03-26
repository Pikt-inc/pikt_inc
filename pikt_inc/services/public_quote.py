from __future__ import annotations

import frappe
from frappe.utils import add_to_date, get_datetime, getdate, now_datetime, nowdate

DEFAULT_COMPANY = "Pikt, inc."
DEFAULT_COUNTRY = "United States"
DEFAULT_CURRENCY = "USD"
DEFAULT_PRICE_LIST = "Standard Selling"
DEFAULT_WAREHOUSE = "Stores - Pikt, inc."
SAVEPOINT_PREFIX = "pikt_public_quote"


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def fail(message):
    frappe.throw(message)


def truthy(value):
    return clean(value).lower() in ("1", "true", "yes", "on")


def valid_email(value):
    value = clean(value).lower()
    if not value or "@" not in value:
        return False
    parts = value.split("@")
    if len(parts) != 2:
        return False
    return "." in parts[1]


def split_name(full_name):
    full_name = clean(full_name)
    if not full_name:
        return {"first_name": "", "last_name": ""}
    parts = full_name.split()
    if len(parts) == 1:
        return {"first_name": parts[0], "last_name": ""}
    return {"first_name": parts[0], "last_name": " ".join(parts[1:])}


def normalize(value):
    value = clean(value).lower()
    collapsed = []
    last_space = False
    for char in value:
        if char in ("\r", "\n", "\t"):
            char = " "
        if char == " ":
            if last_space:
                continue
            last_space = True
            collapsed.append(char)
            continue
        last_space = False
        collapsed.append(char)
    return "".join(collapsed).strip()


def truncate_name(value, limit):
    value = clean(value)
    if len(value) <= limit:
        return value
    return value[:limit].rstrip(" -")


def make_unique_name(doctype_name, base_value):
    base_value = truncate_name(base_value or doctype_name, 120)
    candidate = base_value
    suffix = 2
    while frappe.db.exists(doctype_name, candidate):
        candidate = truncate_name(base_value, 112) + " #" + str(suffix)
        suffix += 1
    return candidate


def doc_db_set_values(doctype_name, record_name, values):
    record_name = clean(record_name)
    if (not record_name) or (not values):
        return
    doc = frappe.get_doc(doctype_name, record_name)
    doc.flags.ignore_permissions = True
    items = list(values.items())
    total = len(items)
    index = 0
    for fieldname, value in items:
        index += 1
        doc.db_set(clean(fieldname), value, update_modified=(index == total))


def sanitize_identifier(value, fallback="step"):
    value = clean(value).lower()
    tokens = []
    for char in value:
        if char.isalnum():
            tokens.append(char)
            continue
        if tokens and tokens[-1] != "_":
            tokens.append("_")
    identifier = "".join(tokens).strip("_")
    return (identifier or fallback)[:48]


def normalize_savepoint_name(savepoint_name):
    savepoint_name = clean(savepoint_name)
    if not savepoint_name:
        return ""
    if any((not char.isalnum()) and char != "_" for char in savepoint_name):
        return ""
    return savepoint_name


def get_traceback_text():
    try:
        return frappe.get_traceback()
    except Exception:
        return ""


def begin_savepoint(step_name):
    now_value = now_datetime()
    timestamp = (
        now_value.strftime("%H%M%S%f")
        if hasattr(now_value, "strftime")
        else sanitize_identifier(now_value, "now")
    )
    identifier = (
        f"{SAVEPOINT_PREFIX}_{sanitize_identifier(step_name)}_{timestamp}"
    )
    try:
        frappe.db.sql(f"SAVEPOINT {identifier}")
        return identifier
    except Exception:
        return ""


def rollback_savepoint(savepoint_name):
    savepoint_name = normalize_savepoint_name(savepoint_name)
    if not savepoint_name:
        return
    try:
        frappe.db.sql(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
    except Exception:
        pass


def release_savepoint(savepoint_name):
    savepoint_name = normalize_savepoint_name(savepoint_name)
    if not savepoint_name:
        return
    try:
        frappe.db.sql(f"RELEASE SAVEPOINT {savepoint_name}")
    except Exception:
        pass


def lock_document_row(doctype_name, record_name):
    doctype_name = clean(doctype_name).replace("`", "")
    record_name = clean(record_name)
    if not doctype_name or not record_name:
        return False
    try:
        frappe.db.sql(
            f"select name from `tab{doctype_name}` where name = %s for update",
            (record_name,),
        )
        return True
    except Exception:
        return False


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


def get_existing_accept_response(
    quote_name,
    row=None,
    message="This quotation has already been accepted.",
    sales_order_name="",
):
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


def find_customer_for_quote(lead_name, contact_email):
    lead_name = clean(lead_name)
    contact_email = clean(contact_email)
    customer = clean(frappe.db.get_value("Customer", {"lead_name": lead_name}, "name"))
    if customer:
        return customer
    return find_customer_by_email(contact_email)


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


def load_public_quote_portal_state(quote=None, token=None):
    result = get_public_quote_access_result(quote_name=quote, token=token)
    if result.get("state") in ("ready", "accepted"):
        return build_load_portal_state_response(
            result.get("state"),
            result.get("message", ""),
            row=result.get("row"),
        )
    return build_load_portal_state_response(result.get("state"), result.get("message", ""))


def ensure_quote_is_valid_for_portal_write(quote_name, token, cancelled_message, not_ready_message):
    quote_row = get_quote_row(quote_name)
    if not quote_row:
        fail("We could not find that quotation. Please return to your quote email and try again.")
    if clean(quote_row.get("custom_accept_token")) != clean(token):
        fail("This quotation link is no longer valid. Please return to your quote email and try again.")
    if int(quote_row.get("docstatus") or 0) == 2 or clean(quote_row.get("status")) == "Cancelled":
        fail(cancelled_message)

    expires_dt = get_datetime_safe(quote_row.get("custom_accept_token_expires_on"))
    if (not expires_dt) or (now_datetime() >= expires_dt):
        fail("This quotation link has expired. Please contact our team if you still need service.")

    valid_till = get_date_safe(quote_row.get("valid_till"))
    if valid_till and nowdate() > str(valid_till):
        fail("This quotation is past its valid-through date. Please contact our team to refresh it.")

    if int(quote_row.get("docstatus") or 0) != 1:
        fail(not_ready_message)

    return quote_row


def calculate_end_date(start_date, term_model, fixed_term_months):
    if clean(term_model) != "Fixed":
        return None
    months = clean(fixed_term_months)
    if months not in ("3", "6", "12"):
        return None
    try:
        return frappe.utils.add_months(getdate(start_date), int(months))
    except Exception:
        return None


def get_request_ip():
    try:
        value = clean(frappe.request.headers.get("CF-Connecting-IP"))
        if value:
            return clean(value.split(",")[0])
    except Exception:
        pass
    try:
        value = clean(frappe.request.headers.get("X-Forwarded-For"))
        if value:
            return clean(value.split(",")[0])
    except Exception:
        pass
    try:
        value = clean(frappe.request.headers.get("X-Real-IP"))
        if value:
            return clean(value.split(",")[0])
    except Exception:
        pass
    try:
        value = clean(frappe.request.environ.get("REMOTE_ADDR"))
        if value:
            return clean(value.split(",")[0])
    except Exception:
        pass
    try:
        value = clean(frappe.local.request_ip)
        if value:
            return clean(value.split(",")[0])
    except Exception:
        pass
    return ""


def get_user_agent():
    try:
        return clean(frappe.get_request_header("User-Agent"))
    except Exception:
        try:
            return clean(frappe.request.headers.get("User-Agent"))
        except Exception:
            return ""


def build_service_agreement_signature_response(
    service_agreement_name,
    addendum_name,
    addendum_status,
    start_date,
    end_date,
    term_model,
    fixed_term_months,
):
    return {
        "status": "ok",
        "service_agreement": clean(service_agreement_name),
        "addendum": clean(addendum_name),
        "addendum_status": clean(addendum_status),
        "start_date": clean(start_date),
        "end_date": clean(end_date),
        "term_model": clean(term_model),
        "fixed_term_months": clean(fixed_term_months),
    }


def get_existing_service_agreement_signature_response(
    quote_name,
    sales_order_name,
    quote_row=None,
    sales_order_row=None,
):
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


def link_quote_agreement_records(master_name, addendum_name, quote_row, sales_order_row):
    master_name = clean(master_name)
    addendum_name = clean(addendum_name)
    quote_name = clean((quote_row or {}).get("name"))
    sales_order_name = clean((sales_order_row or {}).get("name"))
    opportunity_name = clean((quote_row or {}).get("opportunity"))

    if opportunity_name and frappe.db.exists("Opportunity", opportunity_name):
        doc_db_set_values(
            "Opportunity",
            opportunity_name,
            {"custom_service_agreement": master_name},
        )
    if quote_name and frappe.db.exists("Quotation", quote_name):
        doc_db_set_values(
            "Quotation",
            quote_name,
            {
                "custom_service_agreement": master_name,
                "custom_service_agreement_addendum": addendum_name,
            },
        )
    if sales_order_name and frappe.db.exists("Sales Order", sales_order_name):
        doc_db_set_values(
            "Sales Order",
            sales_order_name,
            {
                "custom_service_agreement": master_name,
                "custom_service_agreement_addendum": addendum_name,
            },
        )


def complete_public_service_agreement_signature(quote=None, token=None, **kwargs):
    quote_name = clean(quote if quote is not None else kwargs.get("quote") or frappe.form_dict.get("quote"))
    token = clean(token if token is not None else kwargs.get("token") or frappe.form_dict.get("token"))
    signer_name = clean(kwargs.get("signer_name") or frappe.form_dict.get("signer_name"))
    signer_title = clean(kwargs.get("signer_title") or frappe.form_dict.get("signer_title"))
    signer_email = clean(kwargs.get("signer_email") or frappe.form_dict.get("signer_email")).lower()
    assent_confirmed = 1 if truthy(kwargs.get("assent_confirmed") or frappe.form_dict.get("assent_confirmed")) else 0
    term_model = clean(kwargs.get("term_model") or frappe.form_dict.get("term_model"))
    fixed_term_months = clean(
        kwargs.get("fixed_term_months") or frappe.form_dict.get("fixed_term_months")
    )
    start_date = clean(kwargs.get("start_date") or frappe.form_dict.get("start_date"))

    if not quote_name:
        fail("Missing quotation reference. Please return to your quote email and try again.")
    if not token:
        fail("Missing secure access token. Please return to your quote email and try again.")
    if not signer_name:
        fail("Signer name is required.")
    if not signer_title:
        fail("Signer title is required.")
    if not valid_email(signer_email):
        fail("Enter a valid signer email address.")
    if term_model not in ("Month-to-month", "Fixed"):
        fail("Select a term for this agreement.")
    if term_model == "Fixed" and fixed_term_months not in ("3", "6", "12"):
        fail("Select a fixed term length of 3, 6, or 12 months.")
    if not start_date:
        fail("Agreement start date is required.")
    try:
        getdate(start_date)
    except Exception:
        fail("Enter a valid agreement start date.")
    if not assent_confirmed:
        fail("Please confirm that you agree to the service agreement terms.")

    quote_row = ensure_quote_is_valid_for_portal_write(
        quote_name,
        token,
        "This quotation has been cancelled and can no longer be updated.",
        "This quotation is not ready for service agreement setup.",
    )
    sales_order_name = clean(quote_row.get("custom_accepted_sales_order"))
    if not sales_order_name or not frappe.db.exists("Sales Order", sales_order_name):
        fail("We could not prepare the agreement for this quote. Please reload the page or contact our team.")

    sales_order_row = get_sales_order_row(sales_order_name)
    customer_name = clean(sales_order_row.get("customer"))
    if not customer_name or not frappe.db.exists("Customer", customer_name):
        fail("We could not resolve the customer for this agreement. Please contact our team.")

    customer_row = get_customer_row(customer_name)
    customer_display = (
        clean(customer_row.get("customer_name"))
        or clean(sales_order_row.get("customer_name"))
        or customer_name
    )

    existing_response = get_existing_service_agreement_signature_response(
        quote_name,
        sales_order_name,
        quote_row=quote_row,
        sales_order_row=sales_order_row,
    )
    if existing_response:
        return existing_response

    active_master = get_active_master_agreement(customer_name)
    master_name = clean(active_master.get("name"))
    master_template = get_active_template("Master")
    addendum_template = get_active_template("Addendum")
    if not clean(master_template.get("name")):
        fail("No active master service agreement template is available yet.")
    if not clean(addendum_template.get("name")):
        fail("No active service agreement addendum template is available yet.")

    signer_ip = get_request_ip()
    signer_user_agent = get_user_agent()
    signed_on = now_datetime()
    end_date = calculate_end_date(start_date, term_model, fixed_term_months)
    replacements = {
        "customer_name": customer_display,
        "quote_name": quote_name,
        "sales_order_name": sales_order_name,
        "start_date": start_date,
        "term_label": get_term_label(term_model, fixed_term_months),
    }
    savepoint_name = begin_savepoint("service_agreement_signature")

    try:
        lock_document_row("Sales Order", sales_order_name)
        sales_order_row = get_sales_order_row(sales_order_name)
        existing_response = get_existing_service_agreement_signature_response(
            quote_name,
            sales_order_name,
            quote_row=quote_row,
            sales_order_row=sales_order_row,
        )
        if existing_response:
            release_savepoint(savepoint_name)
            return existing_response

        if not master_name:
            master_doc = frappe.get_doc(
                {
                    "doctype": "Service Agreement",
                    "agreement_name": make_unique_name(
                        "Service Agreement",
                        customer_display + " - Master Agreement",
                    ),
                    "customer": customer_name,
                    "status": "Active",
                    "template": clean(master_template.get("name")),
                    "template_version": clean(master_template.get("version")),
                    "rendered_html_snapshot": render_template_html(
                        master_template.get("body_html"),
                        replacements,
                    ),
                    "signed_by_name": signer_name,
                    "signed_by_title": signer_title,
                    "signed_by_email": signer_email,
                    "signed_on": signed_on,
                    "signer_ip": signer_ip,
                    "signer_user_agent": signer_user_agent,
                }
            )
            master_doc.flags.ignore_permissions = True
            master_doc.insert(ignore_permissions=True)
            master_name = master_doc.name

        addendum_doc = frappe.get_doc(
            {
                "doctype": "Service Agreement Addendum",
                "addendum_name": make_unique_name(
                    "Service Agreement Addendum",
                    customer_display + " - " + quote_name + " Addendum",
                ),
                "service_agreement": master_name,
                "customer": customer_name,
                "quotation": quote_name,
                "sales_order": sales_order_name,
                "status": "Pending Billing",
                "term_model": term_model,
                "fixed_term_months": fixed_term_months if term_model == "Fixed" else "",
                "start_date": start_date,
                "end_date": end_date,
                "template": clean(addendum_template.get("name")),
                "template_version": clean(addendum_template.get("version")),
                "rendered_html_snapshot": render_template_html(
                    addendum_template.get("body_html"),
                    replacements,
                ),
                "signed_by_name": signer_name,
                "signed_by_title": signer_title,
                "signed_by_email": signer_email,
                "signed_on": signed_on,
                "signer_ip": signer_ip,
                "signer_user_agent": signer_user_agent,
            }
        )
        addendum_doc.flags.ignore_permissions = True
        addendum_doc.insert(ignore_permissions=True)

        link_quote_agreement_records(master_name, addendum_doc.name, quote_row, sales_order_row)
        release_savepoint(savepoint_name)
        return build_service_agreement_signature_response(
            master_name,
            addendum_doc.name,
            "Pending Billing",
            start_date,
            end_date,
            term_model,
            fixed_term_months if term_model == "Fixed" else "",
        )
    except Exception:
        rollback_savepoint(savepoint_name)
        existing_response = get_existing_service_agreement_signature_response(
            quote_name,
            sales_order_name,
            quote_row=quote_row,
            sales_order_row=sales_order_row,
        )
        if existing_response:
            return existing_response
        frappe.log_error(get_traceback_text(), "Complete Public Service Agreement Signature")
        fail("We could not save the service agreement right now. Please try again or contact our team.")


def build_billing_setup_response(
    quote_name,
    sales_order_name,
    invoice_name,
    auto_repeat_name,
    service_agreement_name,
    addendum_name,
    addendum_status,
):
    return {
        "status": "ok",
        "quote": clean(quote_name),
        "sales_order": clean(sales_order_name),
        "invoice": clean(invoice_name),
        "auto_repeat": clean(auto_repeat_name),
        "service_agreement": clean(service_agreement_name),
        "addendum": clean(addendum_name),
        "addendum_status": clean(addendum_status),
    }


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


def ensure_signed_addendum(quote_name, sales_order_name):
    addendum_row = get_addendum_row(quote_name, sales_order_name)
    if not clean(addendum_row.get("name")):
        fail("Complete the service agreement before setting up billing.")
    status = clean(addendum_row.get("status"))
    if status in ("Cancelled", "Expired"):
        fail("This service agreement addendum is no longer active.")
    return addendum_row


def find_contact_for_customer(customer_name, billing_email):
    customer_name = clean(customer_name)
    customer_row = get_customer_row(customer_name)
    primary_contact = clean(customer_row.get("customer_primary_contact"))
    if primary_contact:
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
            order by c.creation asc
            limit 1
            """,
            (customer_name, billing_email),
            as_dict=True,
        )
        if rows:
            return clean(rows[0].get("name"))

    rows = frappe.db.sql(
        """
        select c.name
        from `tabContact` c
        inner join `tabDynamic Link` dl
            on dl.parent = c.name
           and dl.parenttype = 'Contact'
           and dl.link_doctype = 'Customer'
        where dl.link_name = %s
        order by c.creation asc
        limit 1
        """,
        (customer_name,),
        as_dict=True,
    )
    if rows:
        return clean(rows[0].get("name"))
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


def ensure_contact(customer_name, customer_display, billing_contact_name, billing_email):
    if customer_name and frappe.db.exists("Customer", customer_name):
        lock_document_row("Customer", customer_name)

    name_parts = split_name(billing_contact_name)
    contact_name = find_contact_for_customer(customer_name, billing_email)
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
        contact_name = find_contact_for_customer(customer_name, billing_email)
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


def child_value(row, fieldname):
    if isinstance(row, dict):
        return row.get(fieldname)
    return getattr(row, fieldname, None)


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
    quote_name = clean(quote if quote is not None else kwargs.get("quote") or frappe.form_dict.get("quote"))
    token = clean(token if token is not None else kwargs.get("token") or frappe.form_dict.get("token"))
    billing_contact_name = clean(
        kwargs.get("billing_contact_name") or frappe.form_dict.get("billing_contact_name")
    )
    billing_email = clean(kwargs.get("billing_email") or frappe.form_dict.get("billing_email")).lower()
    billing_address_line_1 = clean(
        kwargs.get("billing_address_line_1") or frappe.form_dict.get("billing_address_line_1")
    )
    billing_address_line_2 = clean(
        kwargs.get("billing_address_line_2") or frappe.form_dict.get("billing_address_line_2")
    )
    billing_city = clean(kwargs.get("billing_city") or frappe.form_dict.get("billing_city"))
    billing_state = clean(kwargs.get("billing_state") or frappe.form_dict.get("billing_state"))
    billing_postal_code = clean(
        kwargs.get("billing_postal_code") or frappe.form_dict.get("billing_postal_code")
    )
    billing_country = clean(kwargs.get("billing_country") or frappe.form_dict.get("billing_country")) or DEFAULT_COUNTRY
    po_number = clean(kwargs.get("po_number") or frappe.form_dict.get("po_number"))
    tax_id = clean(kwargs.get("tax_id") or frappe.form_dict.get("tax_id"))
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
    return {
        "status": "ok",
        "quote": clean(quote_name),
        "sales_order": clean(sales_order_name),
        "invoice": clean(invoice_name),
        "building": clean(building_name),
        "service_agreement": clean(service_agreement_name),
        "addendum": clean(addendum_name),
        "addendum_status": clean(addendum_status),
        "access_completed_on": str(access_completed_on),
    }


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


def make_access_notes(
    access_method,
    access_entrance,
    access_entry_details,
    allowed_entry_time,
    primary_site_contact,
    lockout_emergency_contact,
    key_fob_handoff_details,
    closing_instructions,
):
    lines = []
    if access_method:
        lines.append("Access method: " + clean(access_method))
    if access_entrance:
        lines.append("Entrance: " + clean(access_entrance))
    if allowed_entry_time:
        lines.append("Allowed entry time: " + clean(allowed_entry_time))
    if primary_site_contact:
        lines.append("Primary site contact: " + clean(primary_site_contact))
    if lockout_emergency_contact:
        lines.append("Lockout / emergency contact: " + clean(lockout_emergency_contact))
    if access_entry_details:
        lines.append("Entry details: " + clean(access_entry_details))
    if key_fob_handoff_details:
        lines.append("Key / fob handoff: " + clean(key_fob_handoff_details))
    if closing_instructions:
        lines.append("Closing instructions: " + clean(closing_instructions))
    return "\n".join(lines)


def make_alarm_notes(has_alarm_system, alarm_instructions):
    if clean(has_alarm_system) == "Yes" and clean(alarm_instructions):
        return "Alarm system: Yes\n" + clean(alarm_instructions)
    if clean(has_alarm_system) == "Yes":
        return "Alarm system: Yes"
    return "Alarm system: No"


def make_site_notes(parking_elevator_notes, areas_to_avoid, first_service_notes):
    lines = []
    if parking_elevator_notes:
        lines.append("Parking / elevator / building notes: " + clean(parking_elevator_notes))
    if areas_to_avoid:
        lines.append("Areas to avoid or special restrictions: " + clean(areas_to_avoid))
    if first_service_notes:
        lines.append("Before first service: " + clean(first_service_notes))
    return "\n".join(lines)


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
    quote_name = clean(quote if quote is not None else kwargs.get("quote") or frappe.form_dict.get("quote"))
    token = clean(token if token is not None else kwargs.get("token") or frappe.form_dict.get("token"))
    service_address_line_1 = clean(
        kwargs.get("service_address_line_1") or frappe.form_dict.get("service_address_line_1")
    )
    service_address_line_2 = clean(
        kwargs.get("service_address_line_2") or frappe.form_dict.get("service_address_line_2")
    )
    service_city = clean(kwargs.get("service_city") or frappe.form_dict.get("service_city"))
    service_state = clean(kwargs.get("service_state") or frappe.form_dict.get("service_state"))
    service_postal_code = clean(
        kwargs.get("service_postal_code") or frappe.form_dict.get("service_postal_code")
    )
    access_method = clean(kwargs.get("access_method") or frappe.form_dict.get("access_method"))
    access_entrance = clean(kwargs.get("access_entrance") or frappe.form_dict.get("access_entrance"))
    access_entry_details = clean(
        kwargs.get("access_entry_details") or frappe.form_dict.get("access_entry_details")
    )
    has_alarm_system = clean(
        kwargs.get("has_alarm_system") or frappe.form_dict.get("has_alarm_system")
    ) or "No"
    alarm_instructions = clean(
        kwargs.get("alarm_instructions") or frappe.form_dict.get("alarm_instructions")
    )
    allowed_entry_time = clean(
        kwargs.get("allowed_entry_time") or frappe.form_dict.get("allowed_entry_time")
    )
    primary_site_contact = clean(
        kwargs.get("primary_site_contact") or frappe.form_dict.get("primary_site_contact")
    )
    lockout_emergency_contact = clean(
        kwargs.get("lockout_emergency_contact") or frappe.form_dict.get("lockout_emergency_contact")
    )
    key_fob_handoff_details = clean(
        kwargs.get("key_fob_handoff_details") or frappe.form_dict.get("key_fob_handoff_details")
    )
    areas_to_avoid = clean(kwargs.get("areas_to_avoid") or frappe.form_dict.get("areas_to_avoid"))
    closing_instructions = clean(
        kwargs.get("closing_instructions") or frappe.form_dict.get("closing_instructions")
    )
    parking_elevator_notes = clean(
        kwargs.get("parking_elevator_notes") or frappe.form_dict.get("parking_elevator_notes")
    )
    first_service_notes = clean(
        kwargs.get("first_service_notes") or frappe.form_dict.get("first_service_notes")
    )
    access_details_confirmed = 1 if truthy(
        kwargs.get("access_details_confirmed") or frappe.form_dict.get("access_details_confirmed")
    ) else 0

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
