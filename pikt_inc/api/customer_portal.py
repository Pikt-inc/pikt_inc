from __future__ import annotations

import frappe
from pydantic import ValidationError

from ._request_payload import collect_request_payload
from .customer_portal_contracts import (
    CustomerPortalClientBuildingRequestApi,
    CustomerPortalClientJobProofRequestApi,
    CustomerPortalClientJobRequestApi,
    CustomerPortalClientOverviewRequestApi,
)
from .customer_portal_serializers import (
    apply_customer_portal_file_download,
    serialize_customer_portal_building_history,
    serialize_customer_portal_job_detail,
    serialize_customer_portal_overview,
)
from ..services import customer_portal as customer_portal_service
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
def get_customer_portal_client_overview(**kwargs):
    _validate_request(CustomerPortalClientOverviewRequestApi, _payload(kwargs))
    try:
        response = customer_portal_service.get_client_overview()
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return serialize_customer_portal_overview(response).model_dump(mode="python")


@frappe.whitelist()
def get_customer_portal_client_building(building=None, **kwargs):
    payload = _payload(kwargs)
    if building is not None:
        payload["building"] = building
    request = _validate_request(CustomerPortalClientBuildingRequestApi, payload)
    try:
        response = customer_portal_service.get_client_building(request.building_id)
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return serialize_customer_portal_building_history(response).model_dump(mode="python")


@frappe.whitelist()
def get_customer_portal_client_job(session=None, **kwargs):
    payload = _payload(kwargs)
    if session is not None:
        payload["session"] = session
    request = _validate_request(CustomerPortalClientJobRequestApi, payload)
    try:
        response = customer_portal_service.get_client_job(request.session_id)
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return serialize_customer_portal_job_detail(response).model_dump(mode="python")


@frappe.whitelist()
def download_customer_portal_client_job_proof(session=None, item_key=None, **kwargs):
    payload = _payload(kwargs)
    if session is not None:
        payload["session"] = session
    if item_key is not None:
        payload["item_key"] = item_key
    request = _validate_request(CustomerPortalClientJobProofRequestApi, payload)
    try:
        response = customer_portal_service.download_client_job_proof(request.session_id, request.item_key)
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    apply_customer_portal_file_download(response)
    return None
