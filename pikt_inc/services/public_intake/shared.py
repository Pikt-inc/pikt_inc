from __future__ import annotations

import frappe
from frappe.utils import get_datetime


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def fail(message):
    frappe.throw(message)


def coerce_datetime(value):
    if not value:
        return None
    try:
        return get_datetime(value)
    except Exception:
        return None
