from __future__ import annotations

from typing import Any

from frappe.utils import get_datetime

from .shared import clean


def _format_date(value: Any) -> str:
    if not value:
        return ""
    try:
        dt = get_datetime(value)
    except Exception:
        return clean(value)
    return dt.strftime("%b %d, %Y")


def _format_datetime(value: Any) -> str:
    if not value:
        return ""
    try:
        dt = get_datetime(value)
    except Exception:
        return clean(value)
    return dt.strftime("%b %d, %Y %I:%M %p")


def _as_number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _format_currency(amount: Any, currency: str = "USD") -> str:
    symbol = "$" if clean(currency).upper() == "USD" else f"{clean(currency).upper()} "
    return f"{symbol}{_as_number(amount):,.2f}"
