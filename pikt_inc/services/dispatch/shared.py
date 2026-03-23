from __future__ import annotations

import html

import frappe


DEFAULT_ESCALATION_ROLE = "HR Manager"
DEFAULT_GRACE_MINUTES = 15
DEFAULT_MAX_DISTANCE_MILES = 25.0
DEFAULT_MAX_OVERTIME_HOURS = 2.0
DEFAULT_SENDER_EMAIL = "patten@piktparts.com"


def clean(value) -> str:
    return str(value or "").strip()


def as_int(value, default=0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def as_float(value, default=0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def is_truthy(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def to_datetime(value):
    if not value:
        return None
    try:
        return frappe.utils.get_datetime(value)
    except Exception:
        return None


def now():
    return frappe.utils.now()


def now_datetime():
    return frappe.utils.get_datetime(now())


def today():
    return frappe.utils.getdate(frappe.utils.nowdate())


def get_system_timezone() -> str:
    try:
        return clean(frappe.db.get_single_value("System Settings", "time_zone")) or "UTC"
    except Exception:
        return "UTC"


def normalize_timezone(raw_timezone) -> str:
    return clean(raw_timezone) or get_system_timezone()


def get_local_today(timezone_value):
    try:
        return frappe.utils.get_datetime_in_timezone(normalize_timezone(timezone_value)).date()
    except Exception:
        return today()


def make_calendar_subject(building, shift_type, slot_index, employee, status, timezone_value) -> str:
    building_label = clean(building) or "Unknown Building"
    shift_label = clean(shift_type) or "Unknown Shift"
    slot_label = f"S{as_int(slot_index, 1)}"
    employee_label = clean(employee) or "Unassigned"
    status_label = clean(status) or "Draft"
    timezone_label = clean(timezone_value) or "System TZ"
    return (
        f"{building_label} | {shift_label} | {slot_label} | "
        f"{employee_label} | {status_label} | {timezone_label}"
    )


def get_dispatch_settings() -> dict:
    settings = {
        "max_overtime_hours": DEFAULT_MAX_OVERTIME_HOURS,
        "max_distance_miles": DEFAULT_MAX_DISTANCE_MILES,
        "default_grace_minutes": DEFAULT_GRACE_MINUTES,
        "escalation_role": DEFAULT_ESCALATION_ROLE,
        "sender_email": DEFAULT_SENDER_EMAIL,
        "unfilled_close_delay_minutes": 120,
    }
    try:
        doc = frappe.get_doc("Dispatch Automation Settings", "Dispatch Automation Settings")
    except Exception:
        return settings

    settings["max_overtime_hours"] = as_float(doc.max_overtime_hours, DEFAULT_MAX_OVERTIME_HOURS)
    settings["max_distance_miles"] = as_float(doc.max_distance_miles, DEFAULT_MAX_DISTANCE_MILES)
    settings["default_grace_minutes"] = max(1, as_int(doc.default_grace_minutes, DEFAULT_GRACE_MINUTES))
    settings["escalation_role"] = clean(doc.escalation_role) or DEFAULT_ESCALATION_ROLE
    sender_email = clean(getattr(doc, "custom_sender_email", None))
    settings["sender_email"] = sender_email if "@" in sender_email and "." in sender_email else DEFAULT_SENDER_EMAIL
    settings["unfilled_close_delay_minutes"] = max(1, as_int(doc.unfilled_close_delay_minutes, 120))
    return settings


def get_role_users(role: str) -> list[str]:
    if not clean(role):
        return []

    users = set()
    try:
        rows = frappe.get_all("Has Role", filters={"role": role}, fields=["parent"], limit=5000)
    except Exception:
        return []

    for row in rows:
        user = clean(row.get("parent"))
        if not user or user == "Guest" or "@" not in user:
            continue
        if frappe.db.get_value("User", user, "enabled"):
            users.add(user)
    return sorted(users)


def escape_text(value) -> str:
    try:
        return frappe.utils.escape_html(str(value or ""))
    except Exception:
        return html.escape(str(value or ""))


def escape_multiline(value) -> str:
    text = escape_text(value).replace("\r\n", "\n").replace("\r", "\n")
    return text.replace("\n", "<br>")


def get_building_fields(building_name, fields):
    building_name = clean(building_name)
    if not building_name:
        return None
    return frappe.db.get_value("Building", building_name, fields, as_dict=True)


def get_rule_snapshot_hash(rule, timezone_value, grace_minutes) -> str:
    raw = "|".join(
        [
            clean(rule.name),
            str(rule.active or 0),
            clean(rule.building),
            clean(rule.shift_type),
            clean(rule.shift_location),
            clean(timezone_value),
            str(rule.start_time or ""),
            str(rule.estimated_hours or ""),
            str(rule.required_headcount or ""),
            clean(rule.priority),
            str(rule.must_fill or 0),
            clean(rule.days_of_week),
            str(rule.effective_from or ""),
            str(rule.effective_to or ""),
            str(rule.generation_horizon_days or ""),
            str(grace_minutes or ""),
            clean(rule.service_notes_template),
        ]
    )
    return raw[:140]
