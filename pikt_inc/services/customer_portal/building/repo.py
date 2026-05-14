from __future__ import annotations

import frappe

from ...contracts.common import clean_str

SITE_SHIFT_REQUIREMENT_BUILDING_FIELDS = ["building"]
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

BUILDING_CONTEXT_FIELDS = BUILDING_FIELDS + [
    "access_method",
    "access_entrance",
    "access_entry_details",
    "has_alarm_system",
    "alarm_instructions",
    "allowed_entry_time",
    "primary_site_contact",
    "lockout_emergency_contact",
    "key_fob_handoff_details",
    "areas_to_avoid",
    "closing_instructions",
    "parking_elevator_notes",
    "first_service_notes",
    "access_notes",
    "alarm_notes",
    "site_supervisor_name",
    "site_supervisor_phone",
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


def get_building_context(building_name: str) -> dict | None:
    building_name = clean_str(building_name)
    if not building_name:
        return None
    return frappe.db.get_value("Building", building_name, BUILDING_CONTEXT_FIELDS, as_dict=True)


def list_buildings(
    *, active_only: bool | None = None, building_names: list[str] | None = None
) -> list[BuildingRecord]:
    filters: dict[str, object] | None = None
    if active_only is True:
        filters = {"active": 1}
    elif active_only is False:
        filters = {"active": 0}

    if building_names is not None:
        scoped_building_names = [clean_str(name) for name in building_names if clean_str(name)]
        if not scoped_building_names:
            return []
        filters = dict(filters or {})
        filters["name"] = ["in", scoped_building_names]

    rows = frappe.get_all(
        "Building",
        filters=filters,
        fields=BUILDING_FIELDS,
        order_by="active desc, building_name asc",
        limit=500,
    )
    return [BuildingRecord.model_validate(row) for row in rows or []]


def list_assigned_building_names_for_employee(employee_name: str, service_date) -> list[str]:
    employee_name = clean_str(employee_name)
    if not employee_name or service_date in (None, ""):
        return []

    rows = frappe.get_all(
        "Site Shift Requirement",
        filters={
            "current_employee": employee_name,
            "service_date": service_date,
        },
        fields=SITE_SHIFT_REQUIREMENT_BUILDING_FIELDS,
        order_by="creation asc",
        limit=500,
    )

    seen: set[str] = set()
    building_names: list[str] = []
    for row in rows or []:
        building_name = clean_str((row or {}).get("building"))
        if building_name and building_name not in seen:
            seen.add(building_name)
            building_names.append(building_name)

    return building_names


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
