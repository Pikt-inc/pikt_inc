from __future__ import annotations

import json

import frappe


def collect_request_payload(kwargs: dict | None = None) -> dict:
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

    request_proxy = getattr(frappe, "request", None)
    request_data = getattr(request_proxy, "data", None)
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
