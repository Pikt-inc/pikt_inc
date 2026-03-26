from __future__ import annotations

import frappe

from ._request_payload import collect_request_payload
from ..services import customer_portal as customer_portal_service


def _payload(kwargs: dict) -> dict:
    return collect_request_payload(kwargs)


@frappe.whitelist()
def get_customer_portal_dashboard_data(**kwargs):
    return customer_portal_service.get_customer_portal_dashboard_data()


@frappe.whitelist()
def get_customer_portal_agreements_data(**kwargs):
    return customer_portal_service.get_customer_portal_agreements_data()


@frappe.whitelist()
def get_customer_portal_billing_data(**kwargs):
    return customer_portal_service.get_customer_portal_billing_data()


@frappe.whitelist()
def get_customer_portal_locations_data(**kwargs):
    return customer_portal_service.get_customer_portal_locations_data()


@frappe.whitelist()
def update_customer_portal_billing(**kwargs):
    return customer_portal_service.update_customer_portal_billing(**_payload(kwargs))


@frappe.whitelist()
def update_customer_portal_location(**kwargs):
    return customer_portal_service.update_customer_portal_location(**_payload(kwargs))


@frappe.whitelist()
def download_customer_portal_invoice(invoice=None, **kwargs):
    payload = _payload(kwargs)
    if invoice is not None:
        payload["invoice"] = invoice
    return customer_portal_service.download_customer_portal_invoice(**payload)


@frappe.whitelist()
def download_customer_portal_agreement_snapshot(addendum=None, agreement=None, **kwargs):
    payload = _payload(kwargs)
    if addendum is not None:
        payload["addendum"] = addendum
    if agreement is not None:
        payload["agreement"] = agreement
    return customer_portal_service.download_customer_portal_agreement_snapshot(**payload)
