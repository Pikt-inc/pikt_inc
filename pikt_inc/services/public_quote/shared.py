from __future__ import annotations

from datetime import date, datetime
from typing import Any

import frappe
from frappe.utils import add_to_date, get_datetime, getdate, now_datetime, nowdate

from .constants import SAVEPOINT_PREFIX

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

def child_value(row, fieldname):
    if isinstance(row, dict):
        return row.get(fieldname)
    return getattr(row, fieldname, None)

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

__all__ = [
    "clean",
    "fail",
    "truthy",
    "valid_email",
    "split_name",
    "normalize",
    "truncate_name",
    "make_unique_name",
    "doc_db_set_values",
    "sanitize_identifier",
    "normalize_savepoint_name",
    "get_traceback_text",
    "begin_savepoint",
    "rollback_savepoint",
    "release_savepoint",
    "lock_document_row",
    "get_datetime_safe",
    "get_date_safe",
    "make_accept_token",
    "calculate_end_date",
    "get_request_ip",
    "get_user_agent",
    "child_value",
    "make_access_notes",
    "make_alarm_notes",
    "make_site_notes",
]
