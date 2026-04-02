from __future__ import annotations

import frappe

from ._request_payload import collect_request_payload
from ..services import account as account_service


def _payload(kwargs: dict) -> dict:
    return collect_request_payload(kwargs)


@frappe.whitelist()
def get_account_summary(**_kwargs):
    return account_service.get_account_summary()


@frappe.whitelist()
def log_employee_checkin(**kwargs):
    return account_service.log_employee_checkin(**_payload(kwargs))
