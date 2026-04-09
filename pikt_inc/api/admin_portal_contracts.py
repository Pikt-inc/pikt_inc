from __future__ import annotations

import re
from datetime import date

from pydantic import field_validator, model_validator

from ..services.contracts.common import RequestModel, clean_str, truthy


SERVICE_DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
SERVICE_DAY_SET = set(SERVICE_DAY_KEYS)
TIME_PATTERN = re.compile(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$")
COMMERCIAL_BILLING_MODELS = {"recurring", "one_time"}
COMMERCIAL_BILLING_INTERVALS = {"day", "week", "month", "year"}


def _clean_optional_str(value):
    cleaned = clean_str(value)
    return cleaned or None


def _normalize_day_list(value) -> list[str]:
    if value in (None, "", []):
        return []

    if isinstance(value, str):
        raw_values = value.split(",")
    elif isinstance(value, (list, tuple, set)):
        raw_values = list(value)
    else:
        raise ValueError("Unavailable service days must be an array or comma-separated string.")

    normalized: list[str] = []
    for entry in raw_values:
        day = clean_str(entry).lower()
        if not day:
            continue
        if day not in SERVICE_DAY_SET:
            raise ValueError("Unavailable service days must contain valid weekday values.")
        if day not in normalized:
            normalized.append(day)

    return [day for day in SERVICE_DAY_KEYS if day in normalized]


def _normalize_time(value, field_label: str):
    normalized = clean_str(value)
    if not normalized:
        return None

    match = TIME_PATTERN.match(normalized)
    if not match:
        raise ValueError(f"{field_label} must use HH:MM format.")

    hours = int(match.group(1))
    minutes = int(match.group(2))
    if hours < 0 or hours > 23 or minutes < 0 or minutes > 59:
        raise ValueError(f"{field_label} must be a valid time of day.")

    return f"{hours:02d}:{minutes:02d}"


def _normalize_positive_amount(value):
    if value in (None, ""):
        return None

    try:
        normalized = float(value)
    except (TypeError, ValueError):
        raise ValueError("Contract amount must be a positive number.")

    if normalized <= 0:
        raise ValueError("Contract amount must be a positive number.")

    return round(normalized, 2)


def _normalize_positive_int(value, field_label: str):
    if value in (None, ""):
        return None

    try:
        normalized = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_label} must be a whole number greater than 0.")

    if normalized < 1:
        raise ValueError(f"{field_label} must be a whole number greater than 0.")

    return normalized


def _normalize_billing_model(value):
    normalized = clean_str(value).lower()
    if not normalized:
        return None
    if normalized not in COMMERCIAL_BILLING_MODELS:
        raise ValueError("Billing model must be recurring or one_time.")
    return normalized


def _normalize_billing_interval(value):
    normalized = clean_str(value).lower()
    if not normalized:
        return None
    if normalized not in COMMERCIAL_BILLING_INTERVALS:
        raise ValueError("Billing interval must be day, week, month, or year.")
    return normalized


class AdminBuildingDeleteRequestApi(RequestModel):
    building_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_building_id(cls, value):
        payload = dict(value or {})
        if payload.get("building_id") is None and payload.get("building") is not None:
            payload["building_id"] = payload.get("building")
        return payload

    @field_validator("building_id", mode="before")
    @classmethod
    def _validate_building_id(cls, value):
        return clean_str(value)

    @model_validator(mode="after")
    def _require_building_id(self):
        if not clean_str(self.building_id):
            raise ValueError("Building is required.")
        return self


class AdminBuildingUpdateRequestApi(RequestModel):
    building_id: str | None = None
    active: bool | None = None
    name: str | None = None
    address: str | None = None
    notes: str | None = None
    unavailable_service_days: list[str] = []
    service_frequency: int | None = None
    preferred_service_start_time: str | None = None
    preferred_service_end_time: str | None = None
    customer: str | None = None
    company: str | None = None
    billing_model: str | None = None
    contract_amount: float | None = None
    billing_interval: str | None = None
    billing_interval_count: int | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    auto_renew: bool = False

    @model_validator(mode="before")
    @classmethod
    def _coerce_building_id(cls, value):
        payload = dict(value or {})
        if payload.get("building_id") is None and payload.get("building") is not None:
            payload["building_id"] = payload.get("building")
        return payload

    @field_validator("building_id", "name", mode="before")
    @classmethod
    def _normalize_required_text(cls, value):
        return clean_str(value)

    @field_validator("address", "notes", "customer", "company", mode="before")
    @classmethod
    def _normalize_optional_text(cls, value):
        return _clean_optional_str(value)

    @field_validator("active", "auto_renew", mode="before")
    @classmethod
    def _normalize_booleans(cls, value):
        if value is None or value == "":
            return None if value is None else False
        if isinstance(value, bool):
            return value
        return truthy(value)

    @field_validator("unavailable_service_days", mode="before")
    @classmethod
    def _normalize_unavailable_service_days(cls, value):
        return _normalize_day_list(value)

    @field_validator("service_frequency", mode="before")
    @classmethod
    def _normalize_service_frequency(cls, value):
        frequency = _normalize_positive_int(value, "Service frequency")
        if frequency is None:
            return None
        if frequency > 7:
            raise ValueError("Service frequency must be a whole number between 1 and 7.")
        return frequency

    @field_validator("preferred_service_start_time", mode="before")
    @classmethod
    def _normalize_start_time(cls, value):
        return _normalize_time(value, "Preferred service start time")

    @field_validator("preferred_service_end_time", mode="before")
    @classmethod
    def _normalize_end_time(cls, value):
        return _normalize_time(value, "Preferred service end time")

    @field_validator("billing_model", mode="before")
    @classmethod
    def _normalize_billing_model_field(cls, value):
        return _normalize_billing_model(value)

    @field_validator("contract_amount", mode="before")
    @classmethod
    def _normalize_contract_amount(cls, value):
        return _normalize_positive_amount(value)

    @field_validator("billing_interval", mode="before")
    @classmethod
    def _normalize_billing_interval_field(cls, value):
        return _normalize_billing_interval(value)

    @field_validator("billing_interval_count", mode="before")
    @classmethod
    def _normalize_billing_interval_count(cls, value):
        return _normalize_positive_int(value, "Billing interval count")

    @model_validator(mode="after")
    def _validate_building_update(self):
        if not clean_str(self.building_id):
            raise ValueError("Building is required.")

        has_schedule = any(
            [
                bool(self.unavailable_service_days),
                self.service_frequency is not None,
                bool(self.preferred_service_start_time),
                bool(self.preferred_service_end_time),
            ]
        )

        if has_schedule:
            if len(self.unavailable_service_days) == len(SERVICE_DAY_KEYS):
                raise ValueError("Unavailable days cannot include all 7 weekdays.")
            if self.service_frequency is None:
                raise ValueError("Service frequency is required when a preferred service schedule is set.")
            if not self.preferred_service_start_time or not self.preferred_service_end_time:
                raise ValueError("Start and end times are required when a preferred service schedule is set.")
            if self.preferred_service_end_time <= self.preferred_service_start_time:
                raise ValueError("Service end time must be after the start time.")
            available_days = len(SERVICE_DAY_KEYS) - len(self.unavailable_service_days)
            if self.service_frequency > available_days:
                raise ValueError("Service frequency cannot exceed the number of available service days.")

        has_commercial_values = any(
            [
                self.company,
                self.billing_model,
                self.contract_amount is not None,
                self.billing_interval,
                self.billing_interval_count is not None,
                self.contract_start_date is not None,
                self.contract_end_date is not None,
                self.auto_renew,
            ]
        )

        if has_commercial_values and not self.billing_model:
            raise ValueError("Billing model is required when commercial setup is configured.")

        if self.billing_model:
            if not self.customer:
                raise ValueError("Customer is required when commercial setup is configured.")
            if not self.company:
                raise ValueError("Company is required when commercial setup is configured.")
            if self.contract_amount is None:
                raise ValueError("Contract amount is required when commercial setup is configured.")
            if self.contract_start_date is None:
                raise ValueError("Contract start date is required when commercial setup is configured.")
            if (
                self.contract_end_date is not None
                and self.contract_end_date < self.contract_start_date
            ):
                raise ValueError("Contract end date must be on or after the start date.")

            if self.billing_model == "recurring":
                if not self.billing_interval:
                    raise ValueError("Billing interval is required for recurring commercial setup.")
                if self.billing_interval_count is None:
                    raise ValueError("Billing interval count is required for recurring commercial setup.")

        return self
