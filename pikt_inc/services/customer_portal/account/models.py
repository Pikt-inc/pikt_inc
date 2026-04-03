from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import field_validator

from ...contracts.common import ResponseModel, clean_str


PortalPersona = Literal["customer", "cleaner", "system_manager", "none", "mixed"]
PortalSection = Literal["admin", "checklist", "client", "account"]
EmployeeClockAction = Literal["clock_in", "clock_out"]
EmployeeClockStatus = Literal["clocked_in", "clocked_out"]


class UserAccountRecord(ResponseModel):
    name: str = ""
    full_name: str = ""
    email: str = ""
    custom_customer: str = ""

    @field_validator("name", "full_name", "email", "custom_customer", mode="before")
    @classmethod
    def clean_strings(cls, value: object) -> str:
        return clean_str(value)


class CustomerAccountRecord(ResponseModel):
    name: str = ""
    customer_name: str = ""

    @field_validator("name", "customer_name", mode="before")
    @classmethod
    def clean_strings(cls, value: object) -> str:
        return clean_str(value)


class EmployeeRecord(ResponseModel):
    name: str = ""
    employee_name: str = ""
    company: str = ""
    designation: str = ""
    department: str = ""
    status: str = ""

    @field_validator("name", "employee_name", "company", "designation", "department", "status", mode="before")
    @classmethod
    def clean_strings(cls, value: object) -> str:
        return clean_str(value)


class EmployeeCheckinRecord(ResponseModel):
    name: str = ""
    log_type: str = "OUT"
    time: datetime | None = None
    latitude: float | None = None
    longitude: float | None = None
    device_id: str = ""

    @field_validator("name", "log_type", "device_id", mode="before")
    @classmethod
    def clean_strings(cls, value: object) -> str:
        return clean_str(value)

    @field_validator("time", mode="before")
    @classmethod
    def empty_temporal_to_none(cls, value: object):
        if value in (None, ""):
            return None
        return value

    @field_validator("latitude", "longitude", mode="before")
    @classmethod
    def normalize_floats(cls, value: object):
        if value in (None, ""):
            return None
        try:
            return float(value)
        except Exception:
            return None


class CustomerPortalPrincipal(ResponseModel):
    session_user: str
    customer_name: str
    customer_display: str


class PortalAccessSummary(ResponseModel):
    user_id: str
    roles: list[str]
    portal_persona: PortalPersona
    allowed_sections: list[PortalSection]
    home_path: str


class AccountEmployeeDetails(ResponseModel):
    id: str
    employee_name: str
    company: str | None
    designation: str | None
    department: str | None
    status: str | None


class EmployeeCheckinSummary(ResponseModel):
    id: str
    log_type: str
    time: datetime | None
    latitude: float | None
    longitude: float | None
    device_id: str | None
    has_geolocation: bool


class ClockState(ResponseModel):
    status: EmployeeClockStatus
    next_action: EmployeeClockAction
    last_checkin: EmployeeCheckinSummary | None


class AccountSummary(ResponseModel):
    user_id: str
    email: str
    full_name: str
    roles: list[str]
    has_employee_role: bool
    can_clock: bool
    employee: AccountEmployeeDetails | None
    clock_state: ClockState | None
    recent_checkins: list[EmployeeCheckinSummary]


class EmployeeCheckinActionResult(ResponseModel):
    checkin: EmployeeCheckinSummary
    clock_state: ClockState
    recent_checkins: list[EmployeeCheckinSummary]
