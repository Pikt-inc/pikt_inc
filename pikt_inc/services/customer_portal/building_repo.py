from __future__ import annotations

from datetime import datetime

import frappe
from pydantic import field_validator

from ..contracts.common import ResponseModel, clean_str, truthy


BUILDING_FIELDS = [
    "name",
    "customer",
    "building_name",
    "active",
    "current_checklist_template",
    "address_line_1",
    "address_line_2",
    "city",
    "state",
    "postal_code",
    "site_notes",
    "creation",
    "modified",
]


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


def get_building(building_name: str) -> BuildingRecord | None:
    building_name = clean_str(building_name)
    if not building_name:
        return None
    row = frappe.db.get_value("Building", building_name, BUILDING_FIELDS, as_dict=True)
    if not row:
        return None
    return BuildingRecord.model_validate(row)


def get_customer_buildings(customer_name: str) -> list[BuildingRecord]:
    customer_name = clean_str(customer_name)
    if not customer_name:
        return []
    rows = frappe.get_all(
        "Building",
        filters={"customer": customer_name},
        fields=BUILDING_FIELDS,
        order_by="active desc, building_name asc",
    )
    return [BuildingRecord.model_validate(row) for row in rows or []]
