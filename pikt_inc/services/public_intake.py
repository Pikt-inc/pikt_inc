from __future__ import annotations

from typing import Any, Mapping

import frappe
from frappe.utils import add_to_date, get_datetime, now, now_datetime, nowdate

DEFAULT_COMPANY = "Pikt, inc."
DEFAULT_COUNTRY = "United States"
DEFAULT_EMPLOYEE_RANGE = "1-10"
DEFAULT_LANGUAGE = "en"
DEFAULT_CURRENCY = "USD"
FUNNEL_TOKEN_EXPIRY_DAYS = 30
DEDUPE_WINDOW_MINUTES = 10
MAX_WALKTHROUGH_BYTES = 100 * 1024 * 1024
ALLOWED_WALKTHROUGH_EXTENSIONS = (
    "png",
    "jpg",
    "jpeg",
    "gif",
    "webp",
    "heic",
    "heif",
    "mp4",
    "mov",
    "m4v",
    "pdf",
    "doc",
    "docx",
)


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def fail(message):
    frappe.throw(message)


def make_public_token():
    rows = frappe.db.sql(
        "select concat(replace(uuid(), '-', ''), replace(uuid(), '-', '')) as token",
        as_dict=True,
    )
    token = ""
    if rows:
        token = clean(rows[0].get("token"))
    if not token:
        fail("We could not create your estimate right now. Please try again.")
    return token


def ensure_public_token(docname, current_token, current_expiry):
    token = clean(current_token)
    expiry_dt = coerce_datetime(current_expiry)
    current_dt = now_datetime()

    if token and expiry_dt and current_dt < expiry_dt:
        return token

    token = make_public_token()
    expiry_dt = add_to_date(current_dt, days=FUNNEL_TOKEN_EXPIRY_DAYS, as_datetime=True)
    frappe.db.set_value("Opportunity", docname, "public_funnel_token", token, update_modified=False)
    frappe.db.set_value(
        "Opportunity",
        docname,
        "public_funnel_token_expires_on",
        expiry_dt,
        update_modified=False,
    )
    return token


def normalize_bathroom_traffic_level(value):
    raw = clean(value)
    lowered = raw.lower()
    mapping = {
        "": "None",
        "0": "None",
        "none": "None",
        "1-2": "Light",
        "light": "Light",
        "3-5": "Medium",
        "medium": "Medium",
        "6-10": "Heavy",
        "11+": "Heavy",
        "heavy": "Heavy",
    }
    return mapping.get(raw, mapping.get(lowered, ""))


def coerce_datetime(value):
    if not value:
        return None
    try:
        return get_datetime(value)
    except Exception:
        return None


def get_public_funnel_validation_message(opportunity, token, row):
    opportunity = clean(opportunity)
    token = clean(token)

    if not opportunity:
        return {
            "valid": 0,
            "message": (
                "This link is missing the estimate reference. Please return to the estimate page and try again."
            ),
        }

    if not token:
        return {
            "valid": 0,
            "message": (
                "This link is missing its secure access token. Please return to the estimate page and try again."
            ),
        }

    if not row:
        return {
            "valid": 0,
            "message": "We could not find that estimate. Please return to the estimate page and try again.",
        }

    stored_token = clean(row.get("public_funnel_token"))
    expires_dt = coerce_datetime(row.get("public_funnel_token_expires_on"))

    if (not stored_token) or (stored_token != token):
        return {
            "valid": 0,
            "message": (
                "This estimate link is no longer valid. Please return to the estimate page and try again."
            ),
        }

    if (not expires_dt) or (now_datetime() >= expires_dt):
        return {
            "valid": 0,
            "message": "This estimate link has expired. Please return to the estimate page to continue.",
        }

    return {"valid": 1, "opportunity": opportunity}


def validate_public_funnel_opportunity(opportunity=None, token=None):
    opportunity = clean(opportunity if opportunity is not None else frappe.form_dict.get("opportunity"))
    token = clean(token if token is not None else frappe.form_dict.get("token"))
    row = None
    if opportunity:
        row = frappe.db.get_value(
            "Opportunity",
            opportunity,
            ["name", "public_funnel_token", "public_funnel_token_expires_on"],
            as_dict=True,
        )
    return get_public_funnel_validation_message(opportunity, token, row)


def require_valid_public_funnel_opportunity(opportunity, token):
    opportunity = clean(opportunity)
    token = clean(token)
    row = frappe.db.get_value(
        "Opportunity",
        opportunity,
        ["name", "public_funnel_token", "public_funnel_token_expires_on"],
        as_dict=True,
    )
    validation = get_public_funnel_validation_message(opportunity, token, row)
    if not validation.get("valid"):
        fail(validation.get("message"))
    return row


def apply_instant_quote_pricing(doc):
    building_type = clean(doc.get("building_type") or "Other")
    service_frequency = clean(doc.get("service_frequency") or "Monthly").replace("\u2014", "-").replace(
        "\u2013", "-"
    )
    service_interest = clean(doc.get("service_interest") or "Recurring standard cleaning").replace(
        "\u2014", "-"
    ).replace("\u2013", "-")
    bathroom_count_range = normalize_bathroom_traffic_level(doc.get("bathroom_count_range")) or "None"

    sq_ft_raw = clean(doc.get("building_size") or "0").replace(",", "")
    try:
        sq_ft = float(sq_ft_raw)
    except Exception:
        sq_ft = 0.0

    pricing_low = {
        "Office": 0.18,
        "Warehouse": 0.10,
        "Retail": 0.16,
        "Medical": 0.22,
        "Industrial": 0.18,
        "Educational": 0.15,
        "Other": 0.17,
    }
    pricing_high = {
        "Office": 0.285,
        "Warehouse": 0.16,
        "Retail": 0.24,
        "Medical": 0.36,
        "Industrial": 0.30,
        "Educational": 0.24,
        "Other": 0.28,
    }
    frequency_factors = {
        "5x/week": 1.00,
        "3x/week": 1.08,
        "2x/week": 1.18,
        "Weekly": 1.35,
        "Biweekly": 1.60,
        "Monthly": 1.95,
    }
    service_factors = {
        "Recurring standard cleaning": 1.00,
        "Recurring cleaning + restocking": 1.08,
        "Recurring cleaning + disinfection": 1.12,
        "Not sure - need recommendation": 1.05,
        "Special request / custom scope": 1.20,
    }
    bathroom_low_adders = {
        "None": 0.00,
        "Light": 125.00,
        "Medium": 425.00,
        "Heavy": 1050.00,
    }
    bathroom_high_adders = {
        "None": 0.00,
        "Light": 225.00,
        "Medium": 725.00,
        "Heavy": 1700.00,
    }

    if bathroom_count_range not in bathroom_low_adders:
        bathroom_count_range = "None"

    if sq_ft <= 0:
        size_factor = 1.00
    elif sq_ft < 2000:
        size_factor = 1.15
    else:
        size_factor = 1.00

    low_rate = pricing_low.get(building_type, 0.17)
    high_rate = pricing_high.get(building_type, 0.28)
    frequency_factor = frequency_factors.get(service_frequency, 1.95)
    service_factor = service_factors.get(service_interest, 1.00)

    low_monthly = sq_ft * low_rate * frequency_factor * service_factor * size_factor
    high_monthly = sq_ft * high_rate * frequency_factor * service_factor * size_factor
    low_monthly += bathroom_low_adders.get(bathroom_count_range, 0.0)
    high_monthly += bathroom_high_adders.get(bathroom_count_range, 0.0)

    minimum_monthly = 600.00
    if low_monthly < minimum_monthly:
        low_monthly = minimum_monthly
    if high_monthly < minimum_monthly:
        high_monthly = minimum_monthly

    low_monthly = round(low_monthly, 2)
    high_monthly = round(high_monthly, 2)
    mid_estimate = round((low_monthly + high_monthly) / 2, 2)
    green_firm_quote = low_monthly + ((high_monthly - low_monthly) * 0.70)

    if green_firm_quote < 2000:
        green_firm_quote = round(green_firm_quote / 25.0) * 25.0
    elif green_firm_quote < 5000:
        green_firm_quote = round(green_firm_quote / 50.0) * 50.0
    else:
        green_firm_quote = round(green_firm_quote / 100.0) * 100.0

    green_firm_quote = round(green_firm_quote, 2)

    risk_score = 0
    risk_score += {
        "Office": 0,
        "Warehouse": 3,
        "Retail": 1,
        "Medical": 2,
        "Industrial": 3,
        "Educational": 1,
        "Other": 1,
    }.get(building_type, 1)
    risk_score += {
        "5x/week": 0,
        "3x/week": 0,
        "2x/week": 1,
        "Weekly": 2,
        "Biweekly": 3,
        "Monthly": 4,
    }.get(service_frequency, 2)
    risk_score += {
        "Recurring standard cleaning": 0,
        "Recurring cleaning + restocking": 1,
        "Recurring cleaning + disinfection": 1,
        "Not sure - need recommendation": 2,
        "Special request / custom scope": 4,
    }.get(service_interest, 1)

    if sq_ft <= 0:
        risk_score += 4

    if service_interest == "Special request / custom scope":
        risk_level = "Red"
    elif risk_score <= 2:
        risk_level = "Green"
    elif risk_score <= 6:
        risk_level = "Yellow"
    else:
        risk_level = "Red"

    doc.bathroom_count_range = bathroom_count_range
    doc.custom_estimate_low = low_monthly
    doc.custom_estimate_high = high_monthly
    doc.opportunity_amount = green_firm_quote if risk_level == "Green" else mid_estimate
    doc.risk_level = risk_level

    if not doc.get("status"):
        doc.status = "Open"
    if not doc.get("company"):
        doc.company = DEFAULT_COMPANY
    if not doc.get("currency"):
        doc.currency = DEFAULT_CURRENCY
    if not doc.get("naming_series"):
        doc.naming_series = "CRM-OPP-.YYYY.-"

    if not (doc.custom_estimate_low and doc.custom_estimate_high):
        frappe.log_error(
            (
                "Instant quote range missing after calculation. building_type={0}, "
                "service_frequency={1}, service_interest={2}, building_size={3}, "
                "bathroom_traffic_level={4}"
            ).format(
                building_type,
                service_frequency,
                service_interest,
                sq_ft_raw,
                bathroom_count_range,
            ),
            "Instant Quote Range Missing",
        )

    return {
        "low": low_monthly,
        "high": high_monthly,
        "final_price": doc.opportunity_amount,
        "risk": risk_level,
        "currency": doc.get("currency") or DEFAULT_CURRENCY,
    }


def validate_and_normalize_quote_request(form_dict: Mapping[str, Any] | None = None):
    data = form_dict or frappe.form_dict
    prospect_name = clean(data.get("prospect_name"))
    phone = clean(data.get("phone"))
    contact_email = clean(data.get("contact_email")).lower()
    prospect_company = clean(data.get("prospect_company"))
    building_type = clean(data.get("building_type"))
    building_size_input = clean(data.get("building_size")).replace(",", "")
    service_frequency = clean(data.get("service_frequency"))
    service_interest = clean(data.get("service_interest"))
    bathroom_count_range = normalize_bathroom_traffic_level(data.get("bathroom_count_range")) or "None"
    allowed_bathroom_ranges = ("None", "Light", "Medium", "Heavy")

    if not prospect_name:
        fail("Full name is required")
    if not contact_email:
        fail("Email address is required")
    if "@" not in contact_email or "." not in contact_email:
        fail("Enter a valid email address")
    if not prospect_company:
        fail("Company name is required")
    if not building_type:
        fail("Building type is required")
    if not service_frequency:
        fail("Service frequency is required")
    if not service_interest:
        fail("Service interest is required")
    if bathroom_count_range not in allowed_bathroom_ranges:
        fail("Select a valid bathroom traffic level")

    try:
        building_size_value = int(float(building_size_input or "0"))
    except Exception:
        fail("Building size must be a valid number")

    if building_size_value <= 0:
        fail("Building size must be greater than 0")

    return {
        "prospect_name": prospect_name,
        "phone": phone,
        "contact_email": contact_email,
        "prospect_company": prospect_company,
        "building_type": building_type,
        "building_size_value": building_size_value,
        "service_frequency": service_frequency,
        "service_interest": service_interest,
        "bathroom_count_range": bathroom_count_range,
    }


def split_prospect_name(prospect_name):
    name_parts = prospect_name.split()
    first_name = prospect_name
    last_name = ""
    if len(name_parts) > 0:
        first_name = name_parts[0]
    if len(name_parts) > 1:
        last_name = " ".join(name_parts[1:])
    return first_name, last_name


def upsert_lead_for_quote_request(request_data):
    first_name, last_name = split_prospect_name(request_data["prospect_name"])
    lead_rows = frappe.get_all(
        "Lead",
        filters={
            "email_id": request_data["contact_email"],
            "company_name": request_data["prospect_company"],
            "disabled": 0,
        },
        fields=["name"],
        order_by="creation asc",
        limit=1,
    )

    if lead_rows:
        lead = frappe.get_doc("Lead", lead_rows[0].get("name"))
        lead_changed = 0
        if not clean(lead.get("first_name")) and first_name:
            lead.first_name = first_name
            lead_changed = 1
        if not clean(lead.get("last_name")) and last_name:
            lead.last_name = last_name
            lead_changed = 1
        if not clean(lead.get("email_id")) and request_data["contact_email"]:
            lead.email_id = request_data["contact_email"]
            lead_changed = 1
        if not clean(lead.get("phone")) and request_data["phone"]:
            lead.phone = request_data["phone"]
            lead_changed = 1
        if not clean(lead.get("company_name")) and request_data["prospect_company"]:
            lead.company_name = request_data["prospect_company"]
            lead_changed = 1
        if not clean(lead.get("company")):
            lead.company = DEFAULT_COMPANY
            lead_changed = 1
        if not clean(lead.get("country")):
            lead.country = DEFAULT_COUNTRY
            lead_changed = 1
        if not clean(lead.get("no_of_employees")):
            lead.no_of_employees = DEFAULT_EMPLOYEE_RANGE
            lead_changed = 1
        if clean(lead.get("status")) != "Opportunity":
            lead.status = "Opportunity"
            lead_changed = 1
        if lead_changed:
            lead.save(ignore_permissions=True)
        return lead

    lead = frappe.get_doc({"doctype": "Lead"})
    lead.naming_series = lead.get("naming_series") or "CRM-LEAD-.YYYY.-"
    lead.first_name = first_name
    lead.last_name = last_name
    lead.email_id = request_data["contact_email"]
    lead.phone = request_data["phone"]
    lead.company_name = request_data["prospect_company"]
    lead.company = DEFAULT_COMPANY
    lead.country = DEFAULT_COUNTRY
    lead.status = "Opportunity"
    lead.no_of_employees = DEFAULT_EMPLOYEE_RANGE
    lead.insert(ignore_permissions=True)
    return lead


def build_quote_request_response(row, token, duplicate):
    opportunity_name = row.get("name")
    return {
        "name": opportunity_name,
        "opp": opportunity_name,
        "low": row.get("custom_estimate_low") or 0,
        "high": row.get("custom_estimate_high") or 0,
        "risk": row.get("risk_level") or "",
        "currency": row.get("currency") or DEFAULT_CURRENCY,
        "final_price": row.get("opportunity_amount") or 0,
        "token": token,
        "duplicate": duplicate,
    }


def create_instant_quote_opportunity(form_dict: Mapping[str, Any] | None = None):
    request_data = validate_and_normalize_quote_request(form_dict=form_dict)
    recent_cutoff = add_to_date(now(), minutes=-DEDUPE_WINDOW_MINUTES)
    existing_rows = frappe.get_all(
        "Opportunity",
        filters=[
            ["Opportunity", "creation", ">=", recent_cutoff],
            ["Opportunity", "contact_email", "=", request_data["contact_email"]],
            ["Opportunity", "prospect_name", "=", request_data["prospect_name"]],
            ["Opportunity", "prospect_company", "=", request_data["prospect_company"]],
            ["Opportunity", "building_type", "=", request_data["building_type"]],
            ["Opportunity", "building_size", "=", str(request_data["building_size_value"])],
            ["Opportunity", "service_frequency", "=", request_data["service_frequency"]],
            ["Opportunity", "service_interest", "=", request_data["service_interest"]],
            ["Opportunity", "bathroom_count_range", "=", request_data["bathroom_count_range"]],
        ],
        fields=[
            "name",
            "custom_estimate_low",
            "custom_estimate_high",
            "risk_level",
            "currency",
            "opportunity_amount",
            "public_funnel_token",
            "public_funnel_token_expires_on",
        ],
        order_by="creation desc",
        limit=1,
    )

    if existing_rows:
        row = existing_rows[0]
        token = ensure_public_token(
            row.get("name"),
            row.get("public_funnel_token"),
            row.get("public_funnel_token_expires_on"),
        )
        return build_quote_request_response(row, token, duplicate=1)

    try:
        lead = upsert_lead_for_quote_request(request_data)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Instant Quote Opportunity - Lead Upsert")
        fail("We could not create your estimate right now. Please try again.")

    try:
        token = make_public_token()
        expires_on = add_to_date(now_datetime(), days=FUNNEL_TOKEN_EXPIRY_DAYS, as_datetime=True)
        opportunity = frappe.get_doc(
            {
                "doctype": "Opportunity",
                "naming_series": "CRM-OPP-.YYYY.-",
                "opportunity_from": "Lead",
                "party_name": lead.name,
                "status": "Open",
                "opportunity_type": "Sales",
                "sales_stage": "Prospecting",
                "company": DEFAULT_COMPANY,
                "transaction_date": nowdate(),
                "currency": DEFAULT_CURRENCY,
                "conversion_rate": 1,
                "title": request_data["prospect_name"],
                "customer_name": request_data["prospect_name"],
                "prospect_name": request_data["prospect_name"],
                "prospect_company": request_data["prospect_company"],
                "building_type": request_data["building_type"],
                "building_size": str(request_data["building_size_value"]),
                "bathroom_count_range": request_data["bathroom_count_range"],
                "service_frequency": request_data["service_frequency"],
                "service_interest": request_data["service_interest"],
                "contact_email": request_data["contact_email"],
                "phone": request_data["phone"],
                "country": DEFAULT_COUNTRY,
                "language": DEFAULT_LANGUAGE,
                "no_of_employees": DEFAULT_EMPLOYEE_RANGE,
                "digital_walkthrough_status": "Not Requested",
                "public_funnel_token": token,
                "public_funnel_token_expires_on": expires_on,
            }
        )
        opportunity.insert(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Create Instant Quote Opportunity - Opportunity Insert")
        fail("We could not create your estimate right now. Please try again.")

    return build_quote_request_response(opportunity, token, duplicate=0)


def save_opportunity_walkthrough_upload(opportunity=None, token=None, uploaded=None):
    opportunity = clean(opportunity if opportunity is not None else frappe.form_dict.get("opportunity"))
    token = clean(token if token is not None else frappe.form_dict.get("token"))
    uploaded = uploaded or (
        frappe.request.files.get("walkthrough_upload")
        if getattr(frappe, "request", None) and getattr(frappe.request, "files", None)
        else None
    )

    if not opportunity:
        fail("Missing estimate reference. Please return to the estimate page and try again.")
    if not token:
        fail("This link is missing its secure access token. Please return to the estimate page and try again.")

    require_valid_public_funnel_opportunity(opportunity, token)

    if not uploaded:
        fail("Please choose your walkthrough file before submitting.")

    file_name = clean(getattr(uploaded, "filename", "")) or "digital-walkthrough-upload"
    extension = ""
    if "." in file_name:
        extension = file_name.rsplit(".", 1)[1].lower().strip()

    if not extension or extension not in ALLOWED_WALKTHROUGH_EXTENSIONS:
        fail("We could not read that file. Please upload a standard image, video, or document under 100 MB.")

    content = uploaded.read()
    if not content:
        fail("Uploaded file was empty. Please choose the file again.")
    if len(content) > MAX_WALKTHROUGH_BYTES:
        fail("That file is larger than the 100 MB upload limit. Please choose a smaller file.")

    existing_files = frappe.get_all(
        "File",
        filters={
            "attached_to_doctype": "Opportunity",
            "attached_to_name": opportunity,
            "attached_to_field": "digital_walkthrough_file",
        },
        fields=["name", "file_url"],
    )

    try:
        file_doc = frappe.get_doc(
            {
                "doctype": "File",
                "file_name": file_name,
                "is_private": 1,
                "attached_to_doctype": "Opportunity",
                "attached_to_name": opportunity,
                "attached_to_field": "digital_walkthrough_file",
                "content": content,
            }
        )
        file_doc.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Save Opportunity Walkthrough Upload")
        fail("We could not read that file. Please upload a standard image, video, or document under 100 MB.")

    try:
        doc = frappe.get_doc("Opportunity", opportunity)
        doc.digital_walkthrough_file = file_doc.file_url
        doc.digital_walkthrough_status = "Submitted"
        doc.digital_walkthrough_received_on = now()
        doc.latest_digital_walkthrough = ""
        doc.save(ignore_permissions=True)
    except Exception:
        frappe.log_error(frappe.get_traceback(), "Save Opportunity Walkthrough Upload - Opportunity Update")
        fail("We could not attach the walkthrough to your estimate. Please try again.")

    for existing in existing_files:
        if existing.get("name") and existing.get("name") != file_doc.name:
            try:
                old_file = frappe.get_doc("File", existing.get("name"))
                old_file.delete(ignore_permissions=True)
            except Exception:
                frappe.log_error(frappe.get_traceback(), "Cleanup Replaced Walkthrough File")

    return {
        "opportunity": doc.name,
        "digital_walkthrough_file": doc.digital_walkthrough_file,
        "digital_walkthrough_status": doc.digital_walkthrough_status,
        "digital_walkthrough_received_on": doc.digital_walkthrough_received_on,
    }
