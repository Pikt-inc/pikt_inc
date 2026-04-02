from __future__ import annotations

from importlib import import_module
from typing import Any
from urllib.parse import quote, unquote

import frappe

from pikt_inc.permissions import customer_portal as portal_permissions

from .shared import _agreement_download_url, clean, truthy


_GENERIC_LIST_TEMPLATE = "templates/includes/list/list.html"
_GENERIC_ROW_TEMPLATE = "templates/includes/list/row_template.html"
_PORTAL_HOME_ROUTE = "/orders"
_LOGIN_PATH = "/login"
_RECORD_CONFIG = {
    "agreements": {
        "doctype": "Service Agreement",
        "list_route": "/agreements",
        "list_title": "Master Service Agreements",
        "list_description": "Review your master service agreements.",
        "no_result_message": "No master service agreements are available for this account.",
        "title_field": "agreement_name",
        "snapshot_field": "rendered_html_snapshot",
        "summary_builder": "_build_service_agreement_summary",
        "related_builder": "_build_service_agreement_related_links",
        "detail_description": "Review this master service agreement.",
        "download_builder": "_build_service_agreement_download_url",
    },
    "business_agreements": {
        "doctype": "Service Agreement Addendum",
        "list_route": "/business-agreements",
        "list_title": "Business Agreements",
        "list_description": "Review your building-specific service agreements.",
        "no_result_message": "No business agreements are available for this account.",
        "title_field": "addendum_name",
        "snapshot_field": "rendered_html_snapshot",
        "summary_builder": "_build_service_agreement_addendum_summary",
        "related_builder": "_build_service_agreement_addendum_related_links",
        "detail_description": "Review this business agreement.",
        "download_builder": "_build_service_agreement_addendum_download_url",
    },
    "buildings": {
        "doctype": "Building",
        "list_route": "/buildings",
        "list_title": "Buildings",
        "list_description": "Review the buildings linked to this account.",
        "no_result_message": "No buildings are available for this account.",
        "title_field": "building_name",
        "snapshot_field": "",
        "summary_builder": "_build_building_summary",
        "related_builder": "_build_building_related_links",
        "detail_description": "Review this building record.",
        "download_builder": "",
    },
}
_PERMISSION_CHECKS = {
    "Building": "has_building_permission",
    "Service Agreement": "has_service_agreement_permission",
    "Service Agreement Addendum": "has_service_agreement_addendum_permission",
}


def _portal_module():
    return import_module("frappe.www.portal")


def _get_value(doc: Any, fieldname: str) -> Any:
    if isinstance(doc, dict):
        return doc.get(fieldname)
    if hasattr(doc, "get"):
        try:
            return doc.get(fieldname)
        except Exception:
            pass
    return getattr(doc, fieldname, None)


def _get_display_value(doc: Any, fieldname: str) -> str:
    return clean(_get_value(doc, fieldname))


def _append_item(items: list[dict[str, str]], label: str, value: Any, *, url: str = "") -> None:
    display_value = clean(value)
    if not display_value:
        return
    items.append({"label": label, "value": display_value, "url": clean(url)})


def _encode_path_segment(value: Any) -> str:
    return quote(clean(value), safe="")


def _format_date(value: Any) -> str:
    display_value = clean(value)
    if not display_value:
        return ""
    format_date = getattr(getattr(frappe, "utils", None), "format_date", None)
    if callable(format_date):
        try:
            return clean(format_date(value))
        except TypeError:
            return clean(format_date(display_value))
        except Exception:
            return display_value
    return display_value


def _resolve_doc_title(doc: Any, title_field: str) -> str:
    title = _get_display_value(doc, title_field)
    return title or _get_display_value(doc, "name")


def _build_service_agreement_summary(doc: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    _append_item(items, "Customer", _get_value(doc, "customer"))
    _append_item(items, "Status", _get_value(doc, "status"))
    _append_item(items, "Template", _get_value(doc, "template"))
    _append_item(items, "Template Version", _get_value(doc, "template_version"))
    _append_item(items, "Signed By", _get_value(doc, "signed_by_name"))
    _append_item(items, "Signer Title", _get_value(doc, "signed_by_title"))
    _append_item(items, "Signer Email", _get_value(doc, "signed_by_email"))
    _append_item(items, "Signed On", _format_date(_get_value(doc, "signed_on")))
    return items


def _build_service_agreement_related_links(_doc: Any) -> list[dict[str, str]]:
    return [{"label": "Business Agreements", "url": "/business-agreements"}]


def _build_service_agreement_addendum_summary(doc: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    _append_item(items, "Customer", _get_value(doc, "customer"))
    _append_item(items, "Status", _get_value(doc, "status"))
    _append_item(items, "Building", _get_value(doc, "building"))
    _append_item(items, "Term Model", _get_value(doc, "term_model"))
    _append_item(items, "Fixed Term (Months)", _get_value(doc, "fixed_term_months"))
    _append_item(items, "Start Date", _format_date(_get_value(doc, "start_date")))
    _append_item(items, "End Date", _format_date(_get_value(doc, "end_date")))
    _append_item(items, "Signed By", _get_value(doc, "signed_by_name"))
    _append_item(items, "Signed On", _format_date(_get_value(doc, "signed_on")))
    return items


def _build_service_agreement_addendum_related_links(doc: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    agreement_name = _get_display_value(doc, "service_agreement")
    if agreement_name:
        items.append(
            {
                "label": "Open Master Service Agreement",
                "url": f"/agreements/{_encode_path_segment(agreement_name)}",
            }
        )

    quotation_name = _get_display_value(doc, "quotation")
    if quotation_name:
        items.append({"label": "Open Quotation", "url": f"/quotations/{_encode_path_segment(quotation_name)}"})

    sales_order_name = _get_display_value(doc, "sales_order")
    if sales_order_name:
        items.append({"label": "Open Order", "url": f"/orders/{_encode_path_segment(sales_order_name)}"})

    building_name = _get_display_value(doc, "building")
    if building_name:
        items.append({"label": "Open Building", "url": f"/buildings/{_encode_path_segment(building_name)}"})

    return items


def _build_building_summary(doc: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    active_value = clean(_get_value(doc, "active"))
    if active_value:
        _append_item(items, "Status", "Active" if truthy(active_value) else "Inactive")
    _append_item(items, "Customer", _get_value(doc, "customer"))
    _append_item(items, "Primary Site Contact", _get_value(doc, "primary_site_contact"))
    _append_item(items, "Site Supervisor", _get_value(doc, "site_supervisor_name"))
    _append_item(items, "Supervisor Phone", _get_value(doc, "site_supervisor_phone"))
    _append_item(items, "Access Method", _get_value(doc, "access_method"))
    _append_item(items, "Entry Window", _get_value(doc, "allowed_entry_time"))
    _append_item(items, "Alarm System", "Yes" if truthy(_get_value(doc, "has_alarm_system")) else "No")
    _append_item(
        items,
        "Access Confirmed",
        "Yes" if truthy(_get_value(doc, "access_details_confirmed")) else "No",
    )
    return items


def _build_building_related_links(doc: Any) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    agreement_name = _get_display_value(doc, "custom_service_agreement")
    if agreement_name:
        items.append(
            {
                "label": "Open Master Service Agreement",
                "url": f"/agreements/{_encode_path_segment(agreement_name)}",
            }
        )

    addendum_name = _get_display_value(doc, "custom_service_agreement_addendum")
    if addendum_name:
        items.append(
            {
                "label": "Open Business Agreement",
                "url": f"/business-agreements/{_encode_path_segment(addendum_name)}",
            }
        )

    return items


def _build_service_agreement_download_url(doc: Any) -> str:
    return _agreement_download_url(agreement_name=_get_display_value(doc, "name"))


def _build_service_agreement_addendum_download_url(doc: Any) -> str:
    return _agreement_download_url(addendum_name=_get_display_value(doc, "name"))


def _ensure_record_access(doctype_name: str, doc: Any) -> None:
    if clean(getattr(getattr(frappe, "session", None), "user", None)) in {"", "Guest"}:
        frappe.throw("Login to view")

    permission_check_name = clean(_PERMISSION_CHECKS.get(doctype_name))
    permission_check = getattr(portal_permissions, permission_check_name, None) if permission_check_name else None
    if callable(permission_check):
        result = permission_check(doc, getattr(frappe.session, "user", None), "read")
        if result is False:
            frappe.throw("Not permitted")
        if result is True:
            return

    has_permission = getattr(doc, "has_permission", None)
    if callable(has_permission) and not has_permission("read"):
        frappe.throw("Not permitted")


def _load_portal_record(doctype_name: str, record_name: str) -> Any:
    decoded_name = unquote(clean(record_name))
    if not decoded_name:
        frappe.throw("Not permitted")

    doc = frappe.get_doc(doctype_name, decoded_name)
    _ensure_record_access(doctype_name, doc)
    return doc


def build_portal_list_context(context, record_key: str):
    config = _RECORD_CONFIG[record_key]
    portal_module = _portal_module()
    context = portal_module.get_context(context, doctype=config["doctype"])
    context.no_cache = 1
    context.no_breadcrumbs = 1
    context.show_search = True
    context.title = config["list_title"]
    context.page_title = config["list_title"]
    context.meta_description = config["list_description"]
    context.description = config["list_description"]
    context.list_template = _GENERIC_LIST_TEMPLATE
    context.row_template = _GENERIC_ROW_TEMPLATE
    context.home_page = _PORTAL_HOME_ROUTE
    context.no_result_message = config["no_result_message"]
    return context


def build_portal_detail_context(context, record_key: str, record_name: str):
    config = _RECORD_CONFIG[record_key]
    doc = _load_portal_record(config["doctype"], record_name)

    title_field = config["title_field"]
    page_title = _resolve_doc_title(doc, title_field)
    snapshot_field = clean(config.get("snapshot_field"))
    snapshot_html = _get_display_value(doc, snapshot_field) if snapshot_field else ""

    summary_builder = globals()[config["summary_builder"]]
    related_builder = globals()[config["related_builder"]]
    download_builder_name = clean(config.get("download_builder"))
    download_builder = globals()[download_builder_name] if download_builder_name else None

    context.no_cache = 1
    context.no_breadcrumbs = 1
    context.show_sidebar = True
    context.home_page = _PORTAL_HOME_ROUTE
    context.title = page_title
    context.page_title = page_title
    context.meta_description = config["detail_description"]
    context.description = config["detail_description"]
    context.doc = doc
    context.record_title = page_title
    context.record_name = _get_display_value(doc, "name")
    context.record_status = _get_display_value(doc, "status")
    context.back_to_label = config["list_title"]
    context.back_to_url = config["list_route"]
    context.summary_items = summary_builder(doc)
    context.related_links = related_builder(doc)
    context.snapshot_html = snapshot_html
    context.snapshot_download_url = download_builder(doc) if download_builder else ""
    context.login_path = _LOGIN_PATH
    return context
