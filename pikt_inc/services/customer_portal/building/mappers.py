from __future__ import annotations

from .models import (
    BuildingRecord,
    CustomerPortalBuilding,
    CustomerPortalStorageLocation,
    StorageLocationRecord,
)


def compose_building_address(row: BuildingRecord) -> str | None:
    locality = ", ".join(part for part in (row.city, row.state) if part)
    if locality and row.postal_code:
        locality = f"{locality} {row.postal_code}"
    parts = [row.address_line_1, row.address_line_2, locality]
    address = ", ".join(part for part in parts if part)
    return address or None


def map_portal_building(row: BuildingRecord) -> CustomerPortalBuilding:
    return CustomerPortalBuilding(
        id=row.name,
        name=row.building_name or row.name,
        address=compose_building_address(row),
        notes=row.site_notes or None,
        active=row.active,
        current_checklist_template_id=row.current_checklist_template or None,
        created_at=row.creation or row.modified,
        updated_at=row.modified or row.creation,
    )


def map_portal_storage_location(row: StorageLocationRecord) -> CustomerPortalStorageLocation:
    return CustomerPortalStorageLocation(
        id=row.name,
        building_id=row.building,
        name=row.location_name or row.name,
        location_type=row.location_type or "other",
        directions=row.directions or None,
        notes=row.notes or None,
        active=row.active,
        is_primary=row.is_primary,
        created_at=row.creation or row.modified,
        updated_at=row.modified or row.creation,
    )
