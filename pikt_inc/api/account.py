from __future__ import annotations

import frappe

from ._request_payload import collect_request_payload
from ..services.customer_portal import account as account_service
from ..services.customer_portal.errors import CustomerPortalAccessError


def _payload(kwargs: dict) -> dict:
    return collect_request_payload(kwargs)


def _raise_account_error(exc: Exception):
    if isinstance(exc, CustomerPortalAccessError):
        frappe.throw(str(exc))
    raise exc


@frappe.whitelist()
def get_account_summary(**_kwargs):
    try:
        return account_service.get_account_summary().model_dump(mode="python")
    except Exception as exc:
        _raise_account_error(exc)
        raise


@frappe.whitelist()
def get_portal_access(**_kwargs):
    try:
        return account_service.get_portal_access().model_dump(mode="python")
    except Exception as exc:
        _raise_account_error(exc)
        raise


@frappe.whitelist()
def log_employee_checkin(**kwargs):
    try:
        return account_service.log_employee_checkin(**_payload(kwargs)).model_dump(mode="python")
    except Exception as exc:
        _raise_account_error(exc)
        raise
