from __future__ import annotations

import frappe
from pydantic import ValidationError

from ._request_payload import collect_request_payload
from .admin_portal_contracts import AdminBuildingDeleteRequestApi, AdminBuildingUpdateRequestApi
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


@frappe.whitelist()
def get_admin_building_commercial_options(**kwargs):
    _payload(kwargs)
    try:
        response = admin_portal_service.get_admin_building_commercial_options()
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return response.model_dump(mode="python")


@frappe.whitelist()
def update_admin_building(
    building=None,
    building_id=None,
    active=None,
    name=None,
    address=None,
    notes=None,
    unavailable_service_days=None,
    service_frequency=None,
    preferred_service_start_time=None,
    preferred_service_end_time=None,
    customer=None,
    company=None,
    billing_model=None,
    contract_amount=None,
    billing_interval=None,
    billing_interval_count=None,
    contract_start_date=None,
    contract_end_date=None,
    auto_renew=None,
    **kwargs,
):
    payload = _payload(kwargs)
    if building is not None:
        payload["building"] = building
    if building_id is not None:
        payload["building_id"] = building_id
    if active is not None:
        payload["active"] = active
    if name is not None:
        payload["name"] = name
    if address is not None:
        payload["address"] = address
    if notes is not None:
        payload["notes"] = notes
    if unavailable_service_days is not None:
        payload["unavailable_service_days"] = unavailable_service_days
    if service_frequency is not None:
        payload["service_frequency"] = service_frequency
    if preferred_service_start_time is not None:
        payload["preferred_service_start_time"] = preferred_service_start_time
    if preferred_service_end_time is not None:
        payload["preferred_service_end_time"] = preferred_service_end_time
    if customer is not None:
        payload["customer"] = customer
    if company is not None:
        payload["company"] = company
    if billing_model is not None:
        payload["billing_model"] = billing_model
    if contract_amount is not None:
        payload["contract_amount"] = contract_amount
    if billing_interval is not None:
        payload["billing_interval"] = billing_interval
    if billing_interval_count is not None:
        payload["billing_interval_count"] = billing_interval_count
    if contract_start_date is not None:
        payload["contract_start_date"] = contract_start_date
    if contract_end_date is not None:
        payload["contract_end_date"] = contract_end_date
    if auto_renew is not None:
        payload["auto_renew"] = auto_renew

    request = _validate_request(AdminBuildingUpdateRequestApi, payload)
    try:
        response = admin_portal_service.update_admin_building(request)
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return response.model_dump(mode="python")
