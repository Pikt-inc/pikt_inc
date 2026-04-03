from __future__ import annotations

import frappe
from pydantic import ValidationError

from ._request_payload import collect_request_payload
from .admin_portal_contracts import AdminBuildingDeleteRequestApi
from ..services import admin_portal as admin_portal_service
from ..services.contracts.common import first_validation_message
from ..services.customer_portal.errors import CustomerPortalAccessError, CustomerPortalNotFoundError


def _payload(kwargs: dict) -> dict:
    return collect_request_payload(kwargs)


def _validate_request(model_cls, payload: dict):
    try:
        return model_cls.model_validate(payload)
    except ValidationError as exc:
        frappe.throw(first_validation_message(exc))


def _raise_portal_error(exc: Exception):
    if isinstance(exc, (CustomerPortalAccessError, CustomerPortalNotFoundError)):
        frappe.throw(str(exc))
    raise exc


@frappe.whitelist()
def delete_admin_building(building=None, building_id=None, **kwargs):
    payload = _payload(kwargs)
    if building is not None:
        payload["building"] = building
    if building_id is not None:
        payload["building_id"] = building_id
    request = _validate_request(AdminBuildingDeleteRequestApi, payload)
    try:
        response = admin_portal_service.delete_admin_building(request.building_id)
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return response.model_dump(mode="python")
