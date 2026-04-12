from __future__ import annotations

import frappe

from ...contracts.common import clean_str
from .models import BuildingRecord, StorageLocationRecord


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

STORAGE_LOCATION_FIELDS = [
    "name",
    "building",
    "location_name",
    "location_type",
    "directions",
    "notes",
    "active",
    "is_primary",
    "creation",
    "modified",
]


def get_building(building_name: str) -> BuildingRecord | None:
    building_name = clean_str(building_name)
    if not building_name:
        return None
    row = frappe.db.get_value("Building", building_name, BUILDING_FIELDS, as_dict=True)
    if not row:
        return None
    return BuildingRecord.model_validate(row)


def list_buildings(*, active_only: bool | None = None) -> list[BuildingRecord]:
    filters: dict[str, object] | None = None
    if active_only is True:
        filters = {"active": 1}
    elif active_only is False:
        filters = {"active": 0}

    rows = frappe.get_all(
        "Building",
        filters=filters,
        fields=BUILDING_FIELDS,
        order_by="active desc, building_name asc",
        limit=500,
    )
    return [BuildingRecord.model_validate(row) for row in rows or []]


def list_customer_buildings(customer_name: str) -> list[BuildingRecord]:
    customer_name = clean_str(customer_name)
    if not customer_name:
        return []
    rows = frappe.get_all(
        "Building",
        filters={"customer": customer_name},
        fields=BUILDING_FIELDS,
        order_by="active desc, building_name asc",
        limit=500,
    )
    return [BuildingRecord.model_validate(row) for row in rows or []]


def list_storage_locations(building_name: str) -> list[StorageLocationRecord]:
    building_name = clean_str(building_name)
    if not building_name:
        return []

    rows = frappe.get_all(
        "Storage Location",
        filters={"building": building_name},
        fields=STORAGE_LOCATION_FIELDS,
        order_by="is_primary desc, active desc, location_name asc",
        limit=200,
    )
    return [StorageLocationRecord.model_validate(row) for row in rows or []]
