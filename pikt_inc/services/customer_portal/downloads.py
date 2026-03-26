from __future__ import annotations

import frappe
from pydantic import ValidationError

from .. import public_quote as public_quote_service
from ..contracts.common import first_validation_message
from ..contracts.customer_portal import PortalAgreementDownloadInput, PortalInvoiceDownloadInput
from .scope import _require_portal_scope
from .shared import _set_download_response, _throw, clean


def render_invoice_pdf(invoice_name: str) -> bytes:
    from frappe.utils.pdf import get_pdf

    local = getattr(frappe, "local", None)
    flags = getattr(local, "flags", None)
    if flags is None and local is not None:
        from types import SimpleNamespace

        flags = SimpleNamespace()
        local.flags = flags

    had_flag = hasattr(flags, "ignore_print_permissions") if flags is not None else False
    original_flag = getattr(flags, "ignore_print_permissions", None) if flags is not None else None
    if flags is not None:
        flags.ignore_print_permissions = True
    try:
        html = frappe.get_print("Sales Invoice", invoice_name, as_pdf=False)
        return get_pdf(html)
    finally:
        if flags is None:
            pass
        elif had_flag:
            flags.ignore_print_permissions = original_flag
        else:
            try:
                delattr(flags, "ignore_print_permissions")
            except Exception:
                flags.ignore_print_permissions = None


def download_customer_portal_invoice(invoice: str | None = None, **kwargs):
    scope = _require_portal_scope()
    try:
        payload = PortalInvoiceDownloadInput.model_validate({"invoice": invoice or kwargs.get("invoice")})
    except ValidationError as exc:
        _throw(first_validation_message(exc))

    invoice_row = frappe.db.get_value(
        "Sales Invoice",
        payload.invoice,
        ["name", "customer", "docstatus"],
        as_dict=True,
    )
    if not invoice_row or clean(invoice_row.get("customer")) != scope.customer_name or int(invoice_row.get("docstatus") or 0) == 2:
        _throw("That invoice is not available in this portal account.")

    pdf_content = render_invoice_pdf(payload.invoice)
    _set_download_response(f"{payload.invoice}.pdf", pdf_content, "application/pdf")
    return None


def download_customer_portal_agreement_snapshot(addendum: str | None = None, agreement: str | None = None, **kwargs):
    scope = _require_portal_scope()
    try:
        payload = PortalAgreementDownloadInput.model_validate(
            {"addendum": addendum or kwargs.get("addendum"), "agreement": agreement or kwargs.get("agreement")}
        )
    except ValidationError as exc:
        _throw(first_validation_message(exc))

    doctype = "Service Agreement Addendum" if payload.addendum else "Service Agreement"
    record_name = payload.addendum or payload.agreement
    title_field = "addendum_name" if payload.addendum else "agreement_name"
    row = frappe.db.get_value(
        doctype,
        record_name,
        ["name", "customer", title_field, "rendered_html_snapshot"],
        as_dict=True,
    )
    if not row or clean(row.get("customer")) != scope.customer_name:
        _throw("That agreement is not available in this portal account.")

    html = clean(row.get("rendered_html_snapshot"))
    if not html:
        _throw("No rendered agreement snapshot is available for this record.")

    title = clean(row.get(title_field)) or record_name
    filename = public_quote_service.truncate_name(title.replace("/", "-"), 90) or record_name
    _set_download_response(f"{filename}.html", html.encode("utf-8"), "text/html; charset=utf-8")
    return None
