from __future__ import annotations

import json
from typing import Any

import frappe


EMPLOYEE_ROLE = "Employee"
CUSTOMER_ROLE = "Customer"
CLEANER_ROLE = "Cleaner"
SYSTEM_MANAGER_ROLE = "System Manager"
CLOCK_IN_ACTION = "clock_in"
CLOCK_OUT_ACTION = "clock_out"
DEVICE_ID = "Web Account Page"

PORTAL_ROLE_CONFIG = {
    CUSTOMER_ROLE: {
        "portal_persona": "customer",
        "allowed_sections": ["client", "account"],
        "home_path": "/portal/client",
    },
    CLEANER_ROLE: {
        "portal_persona": "cleaner",
        "allowed_sections": ["checklist", "account"],
        "home_path": "/portal/checklist",
    },
    SYSTEM_MANAGER_ROLE: {
        "portal_persona": "system_manager",
        "allowed_sections": ["admin", "account"],
        "home_path": "/portal/admin",
    },
}


def clean(value: Any) -> str:
    return str(value or "").strip()


def _row_value(row: Any, fieldname: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(fieldname, default)
    if hasattr(row, "get"):
        try:
            value = row.get(fieldname)
        except Exception:
            value = default
        if value is not None:
            return value
    return getattr(row, fieldname, default)


def _require_session_user() -> str:
    session_user = clean(getattr(getattr(frappe, "session", None), "user", None))
    if not session_user or session_user == "Guest":
        frappe.throw("Authentication required.")
    return session_user


def _get_roles(session_user: str) -> list[str]:
    get_roles = getattr(frappe, "get_roles", None)
    if not callable(get_roles):
        return []

    seen: set[str] = set()
    roles: list[str] = []
    for role in get_roles(session_user) or []:
        cleaned = clean(role)
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            roles.append(cleaned)
    return roles


def _get_user_row(session_user: str) -> dict[str, Any]:
    return (
        frappe.db.get_value(
            "User",
            session_user,
            ["name", "full_name", "email"],
            as_dict=True,
        )
        or {}
    )


def _get_employee_row(session_user: str) -> dict[str, Any] | None:
    rows = frappe.get_all(
        "Employee",
        filters={"user_id": session_user},
        fields=["name", "employee_name", "company", "designation", "department", "status"],
        limit=1,
    )
    return (rows or [None])[0]


def _get_recent_checkin_rows(employee_name: str, limit: int = 5) -> list[dict[str, Any]]:
    rows = frappe.get_all(
        "Employee Checkin",
        filters={"employee": clean(employee_name)},
        fields=["name", "log_type", "time", "latitude", "longitude", "device_id"],
        order_by="time desc, creation desc",
        limit=limit,
    )
    return list(rows or [])


def _map_checkin(row: Any) -> dict[str, Any]:
    latitude = _row_value(row, "latitude")
    longitude = _row_value(row, "longitude")
    has_geolocation = latitude not in (None, "") and longitude not in (None, "")

    return {
        "id": clean(_row_value(row, "name")),
        "log_type": clean(_row_value(row, "log_type")) or "OUT",
        "time": _row_value(row, "time"),
        "latitude": latitude if latitude not in ("", None) else None,
        "longitude": longitude if longitude not in ("", None) else None,
        "device_id": clean(_row_value(row, "device_id")) or None,
        "has_geolocation": has_geolocation,
    }


def _build_clock_state(latest_checkin: dict[str, Any] | None) -> dict[str, Any]:
    if latest_checkin and clean(latest_checkin.get("log_type")) == "IN":
        return {
            "status": "clocked_in",
            "next_action": CLOCK_OUT_ACTION,
            "last_checkin": latest_checkin,
        }

    return {
        "status": "clocked_out",
        "next_action": CLOCK_IN_ACTION,
        "last_checkin": latest_checkin,
    }


def _require_float(value: Any, label: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        frappe.throw(f"{label} is required.")

    if parsed < minimum or parsed > maximum:
        frappe.throw(f"{label} must be between {minimum} and {maximum}.")
    return parsed


def _build_geolocation(latitude: float, longitude: float) -> str:
    return json.dumps(
        {
            "type": "FeatureCollection",
            "features": [
                {
                    "type": "Feature",
                    "properties": {"device_id": DEVICE_ID},
                    "geometry": {
                        "type": "Point",
                        "coordinates": [longitude, latitude],
                    },
                }
            ],
        }
    )


def _build_portal_access(roles: list[str]) -> dict[str, Any]:
    matched_roles = [role for role in roles if role in PORTAL_ROLE_CONFIG]

    if len(matched_roles) == 1:
        config = PORTAL_ROLE_CONFIG[matched_roles[0]]
        return {
            "portal_persona": config["portal_persona"],
            "allowed_sections": list(config["allowed_sections"]),
            "home_path": config["home_path"],
        }

    if len(matched_roles) > 1:
        return {
            "portal_persona": "mixed",
            "allowed_sections": [],
            "home_path": "/desk",
        }

    return {
        "portal_persona": "none",
        "allowed_sections": [],
        "home_path": "/desk",
    }


def get_portal_access() -> dict[str, Any]:
    session_user = _require_session_user()
    roles = _get_roles(session_user)

    return {
        "user_id": session_user,
        "roles": roles,
        **_build_portal_access(roles),
    }


def get_account_summary() -> dict[str, Any]:
    session_user = _require_session_user()
    roles = _get_roles(session_user)
    has_employee_role = EMPLOYEE_ROLE in roles

    user_row = _get_user_row(session_user)
    employee_row = _get_employee_row(session_user)

    recent_checkins: list[dict[str, Any]] = []
    clock_state = None
    can_clock = False

    if has_employee_role and employee_row:
        recent_checkins = [_map_checkin(row) for row in _get_recent_checkin_rows(employee_row.get("name"), limit=5)]
        clock_state = _build_clock_state(recent_checkins[0] if recent_checkins else None)
        can_clock = True

    employee = None
    if employee_row:
        employee = {
            "id": clean(employee_row.get("name")),
            "employee_name": clean(employee_row.get("employee_name")) or clean(employee_row.get("name")),
            "company": clean(employee_row.get("company")) or None,
            "designation": clean(employee_row.get("designation")) or None,
            "department": clean(employee_row.get("department")) or None,
            "status": clean(employee_row.get("status")) or None,
        }

    return {
        "user_id": clean(user_row.get("name")) or session_user,
        "email": clean(user_row.get("email")) or session_user,
        "full_name": clean(user_row.get("full_name")) or session_user,
        "roles": roles,
        "has_employee_role": has_employee_role,
        "can_clock": can_clock,
        "employee": employee,
        "clock_state": clock_state,
        "recent_checkins": recent_checkins,
    }


def log_employee_checkin(action=None, latitude=None, longitude=None, **_kwargs) -> dict[str, Any]:
    session_user = _require_session_user()
    roles = _get_roles(session_user)
    if EMPLOYEE_ROLE not in roles:
        frappe.throw("Only users with the Employee role can clock in or out.")

    employee_row = _get_employee_row(session_user)
    if not employee_row:
        frappe.throw("No Employee record is linked to this account.")

    requested_action = clean(action).lower()
    if requested_action not in {CLOCK_IN_ACTION, CLOCK_OUT_ACTION}:
        frappe.throw("Action must be clock_in or clock_out.")

    parsed_latitude = _require_float(latitude, "Latitude", -90.0, 90.0)
    parsed_longitude = _require_float(longitude, "Longitude", -180.0, 180.0)

    latest_rows = _get_recent_checkin_rows(employee_row.get("name"), limit=1)
    latest_checkin = _map_checkin(latest_rows[0]) if latest_rows else None
    clock_state = _build_clock_state(latest_checkin)
    expected_action = clean(clock_state.get("next_action"))

    if requested_action != expected_action:
        if expected_action == CLOCK_OUT_ACTION:
            frappe.throw("Employee is currently clocked in. Clock out first.")
        frappe.throw("Employee is currently clocked out. Clock in first.")

    checkin_doc = frappe.get_doc(
        {
            "doctype": "Employee Checkin",
            "employee": clean(employee_row.get("name")),
            "log_type": "IN" if requested_action == CLOCK_IN_ACTION else "OUT",
            "time": frappe.utils.now_datetime(),
            "device_id": DEVICE_ID,
            "latitude": parsed_latitude,
            "longitude": parsed_longitude,
            "geolocation": _build_geolocation(parsed_latitude, parsed_longitude),
        }
    )
    checkin_doc.insert()

    created_checkin = _map_checkin(checkin_doc)
    recent_checkins = [_map_checkin(row) for row in _get_recent_checkin_rows(employee_row.get("name"), limit=5)]

    return {
        "checkin": created_checkin,
        "clock_state": _build_clock_state(created_checkin),
        "recent_checkins": recent_checkins,
    }
