from __future__ import annotations

import frappe
from pydantic import ValidationError

from ._request_payload import collect_request_payload
from .checklist_portal_contracts import (
    ChecklistPortalBuildingRequestApi,
    ChecklistPortalBuildingsRequestApi,
    ChecklistPortalCompleteSessionRequestApi,
    ChecklistPortalEnsureSessionRequestApi,
    ChecklistPortalSessionTrainingMediaRequestApi,
    ChecklistPortalStepTrainingMediaRequestApi,
    ChecklistPortalUpdateSessionItemRequestApi,
    ChecklistPortalUploadIssueImageRequestApi,
    ChecklistPortalUploadProofRequestApi,
)
from .checklist_portal_serializers import (
    serialize_checklist_portal_building,
    serialize_checklist_portal_building_detail,
    serialize_checklist_portal_session,
    serialize_checklist_portal_session_item_mutation,
)
from .customer_portal_serializers import apply_customer_portal_inline_media_response
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


def _request_file():
    request = getattr(frappe, "request", None)
    files = getattr(request, "files", None)
    if files and hasattr(files, "get"):
        return files.get("file")
    return None


@frappe.whitelist()
def get_checklist_portal_buildings(activeOnly=None, **kwargs):
    payload = _payload(kwargs)
    if activeOnly is not None:
        payload["activeOnly"] = activeOnly
    request = _validate_request(ChecklistPortalBuildingsRequestApi, payload)
    try:
        response = customer_portal_service.list_checklist_buildings(active_only=request.active_only)
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return [serialize_checklist_portal_building(building).model_dump(mode="python") for building in response]


@frappe.whitelist()
def get_checklist_portal_building(building=None, serviceDate=None, **kwargs):
    payload = _payload(kwargs)
    if building is not None:
        payload["building"] = building
    if serviceDate is not None:
        payload["serviceDate"] = serviceDate
    request = _validate_request(ChecklistPortalBuildingRequestApi, payload)
    try:
        response = customer_portal_service.get_checklist_building(request.building_id, request.service_date)
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return serialize_checklist_portal_building_detail(response).model_dump(mode="python")


@frappe.whitelist()
def download_checklist_portal_step_training_media(building=None, item_key=None, **kwargs):
    payload = _payload(kwargs)
    if building is not None:
        payload["building"] = building
    if item_key is not None:
        payload["item_key"] = item_key
    request = _validate_request(ChecklistPortalStepTrainingMediaRequestApi, payload)
    try:
        response = customer_portal_service.download_checklist_step_training_media(
            request.building_id,
            request.item_key,
        )
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    apply_customer_portal_inline_media_response(response)
    return None


@frappe.whitelist()
def ensure_checklist_portal_session(building=None, serviceDate=None, **kwargs):
    payload = _payload(kwargs)
    if building is not None:
        payload["building"] = building
    if serviceDate is not None:
        payload["serviceDate"] = serviceDate
    request = _validate_request(ChecklistPortalEnsureSessionRequestApi, payload)
    try:
        response = customer_portal_service.ensure_checklist_session(request.building_id, request.service_date)
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return serialize_checklist_portal_session(response).model_dump(mode="python")


@frappe.whitelist()
def update_checklist_portal_session_item(session=None, itemKey=None, proofImage=None, **kwargs):
    payload = _payload(kwargs)
    if session is not None:
        payload["session"] = session
    if itemKey is not None:
        payload["itemKey"] = itemKey
    if proofImage is not None:
        payload["proofImage"] = proofImage
    request = _validate_request(ChecklistPortalUpdateSessionItemRequestApi, payload)
    try:
        response = customer_portal_service.update_checklist_session_item(
            request.session_id,
            request.item_key,
            completed=request.completed,
            issue_reported=request.issue_reported,
            issue_reason=request.issue_reason,
            note=request.note,
            proof_image=request.proof_image,
        )
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return serialize_checklist_portal_session_item_mutation(response).model_dump(mode="python")


@frappe.whitelist()
def complete_checklist_portal_session(session=None, **kwargs):
    payload = _payload(kwargs)
    if session is not None:
        payload["session"] = session
    request = _validate_request(ChecklistPortalCompleteSessionRequestApi, payload)
    try:
        response = customer_portal_service.complete_checklist_session(request.session_id)
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return serialize_checklist_portal_session(response).model_dump(mode="python")


@frappe.whitelist()
def upload_checklist_portal_session_item_proof(session=None, itemKey=None, **kwargs):
    payload = _payload(kwargs)
    if session is not None:
        payload["session"] = session
    if itemKey is not None:
        payload["itemKey"] = itemKey
    request = _validate_request(ChecklistPortalUploadProofRequestApi, payload)
    try:
        response = customer_portal_service.upload_checklist_session_item_proof(
            request.session_id,
            request.item_key,
            uploaded=_request_file(),
        )
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return serialize_checklist_portal_session_item_mutation(response).model_dump(mode="python")


@frappe.whitelist()
def upload_checklist_portal_session_item_issue_image(session=None, itemKey=None, **kwargs):
    payload = _payload(kwargs)
    if session is not None:
        payload["session"] = session
    if itemKey is not None:
        payload["itemKey"] = itemKey
    request = _validate_request(ChecklistPortalUploadIssueImageRequestApi, payload)
    try:
        response = customer_portal_service.upload_checklist_session_item_issue_image(
            request.session_id,
            request.item_key,
            uploaded=_request_file(),
        )
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    return serialize_checklist_portal_session_item_mutation(response).model_dump(mode="python")


@frappe.whitelist()
def download_checklist_portal_session_item_training_media(session=None, item_key=None, **kwargs):
    payload = _payload(kwargs)
    if session is not None:
        payload["session"] = session
    if item_key is not None:
        payload["item_key"] = item_key
    request = _validate_request(ChecklistPortalSessionTrainingMediaRequestApi, payload)
    try:
        response = customer_portal_service.download_checklist_session_item_training_media(
            request.session_id,
            request.item_key,
        )
    except Exception as exc:
        _raise_portal_error(exc)
        raise
    apply_customer_portal_inline_media_response(response)
    return None
