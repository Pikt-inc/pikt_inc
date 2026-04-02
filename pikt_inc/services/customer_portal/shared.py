from __future__ import annotations

from typing import Any

import frappe

from .. import public_quote as public_quote_service
from ..contracts.common import clean_str
from .constants import PORTAL_HOME_PATH, PORTAL_PAGE_PATHS


def clean(value: Any) -> str:
    return clean_str(value)


def truthy(value: Any) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "on"}


def _throw(message: str):
    frappe.throw(message)


def _get_site_url(path: str = "") -> str:
    path = clean(path)
    if path and not path.startswith("/"):
        path = "/" + path
    get_url = getattr(frappe.utils, "get_url", None)
    if callable(get_url):
        return get_url(path or "/")
    return path or "/"


def _set_http_status(code: int):
    local = getattr(frappe, "local", None)
    if local is None:
        return
    response = getattr(local, "response", None)
    if response is None:
        local.response = {}
        response = local.response
    response["http_status_code"] = int(code)


def _login_path_for_page(page_key: str) -> str:
    from urllib.parse import quote

    next_path = PORTAL_PAGE_PATHS.get(page_key, PORTAL_HOME_PATH)
    return f"/login?redirect-to={quote(next_path, safe='/')}"


def _display_name(first_name: Any, last_name: Any) -> str:
    full_name = " ".join(part for part in (clean(first_name), clean(last_name)) if part)
    return full_name or ""


def _invoice_download_url(invoice_name: str) -> str:
    return f"/api/method/pikt_inc.api.customer_portal.download_customer_portal_invoice?invoice={clean(invoice_name)}"


def _agreement_download_url(addendum_name: str = "", agreement_name: str = "") -> str:
    if clean(addendum_name):
        return (
            "/api/method/pikt_inc.api.customer_portal.download_customer_portal_agreement_snapshot"
            f"?addendum={clean(addendum_name)}"
        )
    return (
        "/api/method/pikt_inc.api.customer_portal.download_customer_portal_agreement_snapshot"
        f"?agreement={clean(agreement_name)}"
    )


def _checklist_proof_download_url(proof_name: str) -> str:
    return (
        "/api/method/pikt_inc.api.customer_portal.download_customer_portal_checklist_proof"
        f"?proof={clean(proof_name)}"
    )


def _job_checklist_proof_download_url(session_name: str, item_key: str) -> str:
    return (
        "/api/method/pikt_inc.api.customer_portal.download_customer_portal_client_job_proof"
        f"?session={clean(session_name)}&item_key={clean(item_key)}"
    )


def _contact_updates(display_name: str, phone: str, designation: str, address_name: str = "") -> dict[str, Any]:
    name_parts = public_quote_service.split_name(display_name)
    updates = {
        "first_name": name_parts.get("first_name"),
        "last_name": name_parts.get("last_name"),
        "phone": clean(phone),
        "mobile_no": clean(phone),
        "designation": clean(designation),
        "status": "Open",
    }
    if clean(address_name):
        updates["address"] = clean(address_name)
    return updates


def _shared_contact_updates(
    portal_display_name: str,
    portal_phone: str,
    portal_designation: str,
    billing_display_name: str,
    billing_phone: str,
    billing_designation: str,
    billing_address_name: str,
    portal_address_name: str = "",
) -> dict[str, Any]:
    return _contact_updates(
        portal_display_name or billing_display_name,
        billing_phone or portal_phone,
        billing_designation or portal_designation,
        billing_address_name or portal_address_name,
    )


def _should_split_billing_contact(
    scope,
    portal_contact_name: str,
    portal_contact_phone: str,
    portal_contact_title: str,
    billing_contact_name: str,
    billing_email: str,
    billing_phone: str,
    billing_title: str,
) -> bool:
    if clean(scope.portal_contact_name) != clean(scope.billing_contact_name):
        return False
    if clean(billing_email).lower() != clean(scope.portal_contact_email).lower():
        return False

    portal_signature = (
        clean(portal_contact_name),
        clean(portal_contact_phone),
        clean(portal_contact_title),
    )
    billing_signature = (
        clean(billing_contact_name),
        clean(billing_phone),
        clean(billing_title),
    )
    return portal_signature != billing_signature


def _set_file_response(
    filename: str,
    content: Any,
    content_type: str = "application/octet-stream",
    *,
    as_attachment: bool,
):
    local = getattr(frappe, "local", None)
    if local is None:
        return
    response = getattr(local, "response", None)
    if response is None:
        local.response = {}
        response = local.response
    response["filename"] = clean(filename)
    response["filecontent"] = content
    response["type"] = "download" if as_attachment else "binary"
    response["content_type"] = clean(content_type) or "application/octet-stream"


def _set_download_response(filename: str, content: Any, content_type: str = "application/octet-stream"):
    _set_file_response(filename, content, content_type, as_attachment=True)
