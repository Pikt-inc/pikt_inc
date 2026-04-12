from __future__ import annotations

from datetime import datetime

from pydantic import field_validator

from ...contracts.common import ResponseModel, clean_str, truthy


class BuildingRecord(ResponseModel):
    name: str = ""
    customer: str = ""
    building_name: str = ""
    active: bool = False
    current_checklist_template: str = ""
    address_line_1: str = ""
    address_line_2: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    site_notes: str = ""
    creation: datetime | None = None
    modified: datetime | None = None

    @field_validator(
        "name",
        "customer",
        "building_name",
        "current_checklist_template",
        "address_line_1",
        "address_line_2",
        "city",
        "state",
        "postal_code",
        "site_notes",
        mode="before",
    )
    @classmethod
    def clean_strings(cls, value: object) -> str:
        return clean_str(value)

    @field_validator("active", mode="before")
    @classmethod
    def normalize_active(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        return truthy(value)

    @field_validator("creation", "modified", mode="before")
    @classmethod
    def empty_temporal_to_none(cls, value: object):
        if value in (None, ""):
            return None
        return value


class CustomerPortalBuilding(ResponseModel):
    id: str
    name: str
    address: str | None
    notes: str | None
    active: bool
    current_checklist_template_id: str | None
    created_at: datetime | None
    updated_at: datetime | None


class StorageLocationRecord(ResponseModel):
    name: str = ""
    building: str = ""
    location_name: str = ""
    location_type: str = ""
    directions: str = ""
    notes: str = ""
    active: bool = False
    is_primary: bool = False
    creation: datetime | None = None
    modified: datetime | None = None

    @field_validator(
        "name",
        "building",
        "location_name",
        "location_type",
        "directions",
        "notes",
        mode="before",
    )
    @classmethod
    def clean_storage_strings(cls, value: object) -> str:
        return clean_str(value)

    @field_validator("active", "is_primary", mode="before")
    @classmethod
    def normalize_storage_flags(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        return truthy(value)

    @field_validator("creation", "modified", mode="before")
    @classmethod
    def empty_storage_temporal_to_none(cls, value: object):
        if value in (None, ""):
            return None
        return value


class CustomerPortalStorageLocation(ResponseModel):
    id: str
    building_id: str
    name: str
    location_type: str
    directions: str | None
    notes: str | None
    active: bool
    is_primary: bool
    created_at: datetime | None
    updated_at: datetime | None
