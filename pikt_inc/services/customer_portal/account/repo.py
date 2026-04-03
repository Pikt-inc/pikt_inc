from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import frappe

from ...contracts.common import clean_str
from .models import (
    CustomerAccountRecord,
    EmployeeCheckinRecord,
    EmployeeRecord,
    UserAccountRecord,
)


USER_FIELDS = ["name", "full_name", "email", "custom_customer"]
CUSTOMER_FIELDS = ["name", "customer_name"]
EMPLOYEE_FIELDS = ["name", "employee_name", "company", "designation", "department", "status"]
CHECKIN_FIELDS = ["name", "log_type", "time", "latitude", "longitude", "device_id"]


def _row_payload(row: Any, fields: Iterable[str]) -> dict[str, Any]:
    return {field: row.get(field) if hasattr(row, "get") else getattr(row, field, None) for field in fields}


def get_roles(session_user: str) -> list[str]:
    get_roles_fn = getattr(frappe, "get_roles", None)
    if not callable(get_roles_fn):
        return []

    seen: set[str] = set()
    roles: list[str] = []
    for role in get_roles_fn(session_user) or []:
        cleaned = clean_str(role)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            roles.append(cleaned)
    return roles


def get_user(user_name: str) -> UserAccountRecord | None:
    user_name = clean_str(user_name)
    if not user_name:
        return None
    row = frappe.db.get_value("User", user_name, USER_FIELDS, as_dict=True)
    if not row:
        return None
    return UserAccountRecord.model_validate(row)


def get_customer(customer_name: str) -> CustomerAccountRecord | None:
    customer_name = clean_str(customer_name)
    if not customer_name:
        return None
    row = frappe.db.get_value("Customer", customer_name, CUSTOMER_FIELDS, as_dict=True)
    if not row:
        return None
    return CustomerAccountRecord.model_validate(row)


def get_employee_for_user(session_user: str) -> EmployeeRecord | None:
    rows = frappe.get_all(
        "Employee",
        filters={"user_id": clean_str(session_user)},
        fields=EMPLOYEE_FIELDS,
        limit=1,
    )
    if not rows:
        return None
    return EmployeeRecord.model_validate(rows[0])


def list_recent_checkins(employee_name: str, *, limit: int = 5) -> list[EmployeeCheckinRecord]:
    rows = frappe.get_all(
        "Employee Checkin",
        filters={"employee": clean_str(employee_name)},
        fields=CHECKIN_FIELDS,
        order_by="time desc, creation desc",
        limit=max(1, int(limit or 5)),
    )
    return [EmployeeCheckinRecord.model_validate(row) for row in rows or []]


def insert_employee_checkin(
    *,
    employee_name: str,
    log_type: str,
    time,
    latitude: float,
    longitude: float,
    device_id: str,
    geolocation: str,
) -> EmployeeCheckinRecord:
    doc = frappe.get_doc(
        {
            "doctype": "Employee Checkin",
            "employee": clean_str(employee_name),
            "log_type": clean_str(log_type),
            "time": time,
            "device_id": clean_str(device_id),
            "latitude": latitude,
            "longitude": longitude,
            "geolocation": geolocation,
        }
    )
    doc.insert()
    return EmployeeCheckinRecord.model_validate(_row_payload(doc, CHECKIN_FIELDS))
