from __future__ import annotations

import json
from typing import Any

import frappe

from ...contracts.common import clean_str
from ..errors import CustomerPortalAccessError
from . import repo
from .models import (
    AccountEmployeeDetails,
    AccountSummary,
    ClockState,
    CustomerPortalPrincipal,
    EmployeeCheckinActionResult,
    EmployeeCheckinSummary,
    PortalAccessSummary,
)


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


def _require_session_user(message: str = "Authentication required.") -> str:
    session_user = clean_str(getattr(getattr(frappe, "session", None), "user", None))
    if not session_user or session_user == "Guest":
        raise CustomerPortalAccessError(message)
    return session_user


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


def _require_float(value: Any, label: str, minimum: float, maximum: float) -> float:
    try:
        parsed = float(value)
    except Exception as exc:
        raise CustomerPortalAccessError(f"{label} is required.") from exc

    if parsed < minimum or parsed > maximum:
        raise CustomerPortalAccessError(f"{label} must be between {minimum} and {maximum}.")
    return parsed


def _has_customer_portal_scope(user_name: str) -> bool:
    user_row = repo.get_user(user_name)
    return bool(clean_str(user_row.custom_customer if user_row else ""))


def _build_portal_access(session_user: str, roles: list[str]) -> PortalAccessSummary:
    matched_roles: list[str] = []
    for role in roles:
        if role == CUSTOMER_ROLE and not _has_customer_portal_scope(session_user):
            continue
        if role in PORTAL_ROLE_CONFIG:
            matched_roles.append(role)

    if len(matched_roles) == 1:
        config = PORTAL_ROLE_CONFIG[matched_roles[0]]
        return PortalAccessSummary(
            user_id=session_user,
            roles=roles,
            portal_persona=config["portal_persona"],
            allowed_sections=list(config["allowed_sections"]),
            home_path=config["home_path"],
        )

    if len(matched_roles) > 1:
        return PortalAccessSummary(
            user_id=session_user,
            roles=roles,
            portal_persona="mixed",
            allowed_sections=[],
            home_path="/desk",
        )

    return PortalAccessSummary(
        user_id=session_user,
        roles=roles,
        portal_persona="none",
        allowed_sections=[],
        home_path="/desk",
    )


def _map_checkin_summary(row) -> EmployeeCheckinSummary:
    latitude = row.latitude
    longitude = row.longitude
    return EmployeeCheckinSummary(
        id=row.name,
        log_type=clean_str(row.log_type) or "OUT",
        time=row.time,
        latitude=latitude,
        longitude=longitude,
        device_id=clean_str(row.device_id) or None,
        has_geolocation=latitude is not None and longitude is not None,
    )


def _build_clock_state(latest_checkin: EmployeeCheckinSummary | None) -> ClockState:
    if latest_checkin and clean_str(latest_checkin.log_type) == "IN":
        return ClockState(
            status="clocked_in",
            next_action="clock_out",
            last_checkin=latest_checkin,
        )

    return ClockState(
        status="clocked_out",
        next_action="clock_in",
        last_checkin=latest_checkin,
    )


def resolve_customer_principal() -> CustomerPortalPrincipal:
    session_user = _require_session_user("Sign in to access your customer portal.")
    roles = repo.get_roles(session_user)
    if CUSTOMER_ROLE not in roles:
        raise CustomerPortalAccessError("This account does not have customer portal access.")

    user_row = repo.get_user(session_user)
    customer_name = clean_str(user_row.custom_customer if user_row else "")
    if not customer_name:
        raise CustomerPortalAccessError("This customer portal account is missing a linked customer.")

    customer_row = repo.get_customer(customer_name)
    if not customer_row:
        raise CustomerPortalAccessError("The linked customer record could not be loaded.")

    return CustomerPortalPrincipal(
        session_user=session_user,
        customer_name=customer_name,
        customer_display=clean_str(customer_row.customer_name) or customer_name,
    )


def get_portal_access() -> PortalAccessSummary:
    session_user = _require_session_user()
    roles = repo.get_roles(session_user)
    return _build_portal_access(session_user, roles)


def require_portal_section(section: str) -> PortalAccessSummary:
    access = get_portal_access()
    if section not in access.allowed_sections:
        raise CustomerPortalAccessError("This account does not have portal access to that section.")
    return access


def get_account_summary() -> AccountSummary:
    session_user = _require_session_user()
    roles = repo.get_roles(session_user)
    has_employee_role = EMPLOYEE_ROLE in roles

    user_row = repo.get_user(session_user)
    employee_row = repo.get_employee_for_user(session_user)

    recent_checkins: list[EmployeeCheckinSummary] = []
    clock_state: ClockState | None = None
    can_clock = False

    if has_employee_role and employee_row:
        recent_checkins = [
            _map_checkin_summary(row)
            for row in repo.list_recent_checkins(employee_row.name, limit=5)
        ]
        clock_state = _build_clock_state(recent_checkins[0] if recent_checkins else None)
        can_clock = True

    employee = None
    if employee_row:
        employee = AccountEmployeeDetails(
            id=employee_row.name,
            employee_name=clean_str(employee_row.employee_name) or employee_row.name,
            company=clean_str(employee_row.company) or None,
            designation=clean_str(employee_row.designation) or None,
            department=clean_str(employee_row.department) or None,
            status=clean_str(employee_row.status) or None,
        )

    return AccountSummary(
        user_id=clean_str(user_row.name if user_row else "") or session_user,
        email=clean_str(user_row.email if user_row else "") or session_user,
        full_name=clean_str(user_row.full_name if user_row else "") or session_user,
        roles=roles,
        has_employee_role=has_employee_role,
        can_clock=can_clock,
        employee=employee,
        clock_state=clock_state,
        recent_checkins=recent_checkins,
    )


def require_checklist_work_access() -> AccountSummary:
    summary = get_account_summary()
    if summary.can_clock and summary.clock_state and summary.clock_state.status == "clocked_in":
        return summary
    if summary.can_clock:
        raise CustomerPortalAccessError("Clock in from the Account page before starting or updating checklists.")
    raise CustomerPortalAccessError(
        "This account must be set up for time tracking before working checklists. Visit Account for details."
    )


def log_employee_checkin(action=None, latitude=None, longitude=None, **_kwargs) -> EmployeeCheckinActionResult:
    session_user = _require_session_user()
    roles = repo.get_roles(session_user)
    if EMPLOYEE_ROLE not in roles:
        raise CustomerPortalAccessError("Only users with the Employee role can clock in or out.")

    employee_row = repo.get_employee_for_user(session_user)
    if not employee_row:
        raise CustomerPortalAccessError("No Employee record is linked to this account.")

    requested_action = clean_str(action).lower()
    if requested_action not in {CLOCK_IN_ACTION, CLOCK_OUT_ACTION}:
        raise CustomerPortalAccessError("Action must be clock_in or clock_out.")

    parsed_latitude = _require_float(latitude, "Latitude", -90.0, 90.0)
    parsed_longitude = _require_float(longitude, "Longitude", -180.0, 180.0)

    latest_rows = repo.list_recent_checkins(employee_row.name, limit=1)
    latest_checkin = _map_checkin_summary(latest_rows[0]) if latest_rows else None
    clock_state = _build_clock_state(latest_checkin)
    expected_action = clean_str(clock_state.next_action)

    if requested_action != expected_action:
        if expected_action == CLOCK_OUT_ACTION:
            raise CustomerPortalAccessError("Employee is currently clocked in. Clock out first.")
        raise CustomerPortalAccessError("Employee is currently clocked out. Clock in first.")

    created_checkin = repo.insert_employee_checkin(
        employee_name=employee_row.name,
        log_type="IN" if requested_action == CLOCK_IN_ACTION else "OUT",
        time=frappe.utils.now_datetime(),
        latitude=parsed_latitude,
        longitude=parsed_longitude,
        device_id=DEVICE_ID,
        geolocation=_build_geolocation(parsed_latitude, parsed_longitude),
    )
    created_summary = _map_checkin_summary(created_checkin)
    recent_checkins = [
        _map_checkin_summary(row)
        for row in repo.list_recent_checkins(employee_row.name, limit=5)
    ]

    return EmployeeCheckinActionResult(
        checkin=created_summary,
        clock_state=_build_clock_state(created_summary),
        recent_checkins=recent_checkins,
    )
