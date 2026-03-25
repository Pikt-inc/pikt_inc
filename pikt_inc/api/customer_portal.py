from __future__ import annotations

import json

import frappe

from ..services import customer_portal as customer_portal_service


def _payload(kwargs: dict) -> dict:
    payload = dict(kwargs or {})
    request = getattr(frappe.local, "request", None)
    get_json = getattr(request, "get_json", None)
    if callable(get_json):
        try:
            body = get_json(silent=True) or {}
        except TypeError:
            body = get_json() or {}
        except Exception:
            body = {}
        if isinstance(body, dict):
            payload.update(body)
    data = getattr(frappe, "request", None)
    request_data = getattr(data, "data", None)
    if request_data and isinstance(request_data, (bytes, str)):
        try:
            decoded = request_data.decode("utf-8") if isinstance(request_data, bytes) else request_data
            body = json.loads(decoded or "{}")
        except Exception:
            body = {}
        if isinstance(body, dict):
            payload.update(body)
    form_dict = getattr(frappe, "form_dict", None)
    if form_dict:
        payload.update({key: value for key, value in dict(form_dict).items() if key not in {"cmd"}})
    return payload


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
