from __future__ import annotations

import frappe
from frappe.utils import now_datetime
from pydantic import ValidationError

from .. import public_quote as public_quote_service
from ..contracts.common import first_validation_message, truthy
from ..contracts.customer_portal import CustomerPortalLocationUpdateInput, PortalLocationsUpdateResponse
from .payloads import _build_locations_response, _portal_access_error_response
from .queries import _get_buildings
from .scope import PortalAccessError, _require_portal_scope, _resolve_portal_scope_or_error
from .shared import _throw, clean


def get_customer_portal_locations_data() -> dict:
    try:
        scope = _resolve_portal_scope_or_error()
    except PortalAccessError as exc:
        return _portal_access_error_response("locations", exc)
    return _build_locations_response(scope, _get_buildings(scope.customer_name)).model_dump(mode="python")


def update_customer_portal_location(**kwargs):
    scope = _require_portal_scope()
    try:
        payload = CustomerPortalLocationUpdateInput.model_validate(kwargs)
    except ValidationError as exc:
        _throw(first_validation_message(exc))

    building_row = frappe.db.get_value(
        "Building",
        payload.building_name,
        ["name", "customer", "access_details_completed_on"],
        as_dict=True,
    )
    if not building_row or clean(building_row.get("customer")) != scope.customer_name:
        _throw("That service location is not available in this portal account.")

    updates = payload.updates()
    if "access_details_confirmed" in updates:
        updates["access_details_confirmed"] = 1 if truthy(updates["access_details_confirmed"]) else 0
        if updates["access_details_confirmed"] and not building_row.get("access_details_completed_on"):
            updates["access_details_completed_on"] = now_datetime()

    public_quote_service.doc_db_set_values("Building", payload.building_name, updates)
    response = _build_locations_response(scope, _get_buildings(scope.customer_name))
    return PortalLocationsUpdateResponse(
        **response.model_dump(mode="python"),
        status="updated",
        message="Location details updated.",
    ).model_dump(mode="python")
