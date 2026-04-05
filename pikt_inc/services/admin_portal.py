from __future__ import annotations

from typing import Iterable

import frappe

from .contracts.common import ResponseModel, clean_str
from .customer_portal.account.service import require_portal_section
from .customer_portal.errors import CustomerPortalNotFoundError


ADMIN_HOME_PATH = "/portal/admin"
BUILDING_DOCTYPE = "Building"
CHECKLIST_SESSION_DOCTYPE = "Checklist Session"
CHECKLIST_TEMPLATE_DOCTYPE = "Checklist Template"
FILE_DOCTYPE = "File"
BUILDING_SOP_DOCTYPE = "Building SOP"
DISPATCH_RECOMMENDATION_DOCTYPE = "Dispatch Recommendation"
CALL_OUT_DOCTYPE = "Call Out"
SITE_SHIFT_REQUIREMENT_DOCTYPE = "Site Shift Requirement"
RECURRING_SERVICE_RULE_DOCTYPE = "Recurring Service Rule"
SERVICE_AGREEMENT_ADDENDUM_DOCTYPE = "Service Agreement Addendum"
STORAGE_LOCATION_DOCTYPE = "Storage Location"
CURRENT_TEMPLATE_FIELD = "current_checklist_template"
SSR_SOP_FIELD = "custom_building_sop"
SSR_CALLOUT_FIELD = "call_out_record"

COMMERCIAL_BUILDING_LINK_FIELDS = (
    ("Opportunity", "custom_building"),
    ("Quotation", "custom_building"),
    ("Sales Order", "custom_building"),
    ("Sales Invoice", "custom_building"),
)


class AdminBuildingDeleteResult(ResponseModel):
    building_id: str
    redirect_to: str = ADMIN_HOME_PATH


def _list_doc_names(doctype: str, filters) -> list[str]:
    rows = frappe.get_all(doctype, filters=filters, fields=["name"], limit=10000)
    return [
        clean_str((row or {}).get("name"))
        for row in rows or []
        if clean_str((row or {}).get("name"))
    ]


def _unique_names(names: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for name in names:
        record_name = clean_str(name)
        if not record_name or record_name in seen:
            continue
        seen.add(record_name)
        ordered.append(record_name)
    return ordered


def _delete_doc_if_exists(doctype: str, name: str) -> None:
    record_name = clean_str(name)
    if not record_name or not frappe.db.exists(doctype, record_name):
        return
    frappe.delete_doc(doctype, record_name, ignore_permissions=True, force=True)


def _delete_doc_names(doctype: str, names: Iterable[str]) -> None:
    for record_name in _unique_names(names):
        _delete_doc_if_exists(doctype, record_name)


def _clear_doc_field(doctype: str, name: str, fieldname: str) -> None:
    record_name = clean_str(name)
    if not record_name or not frappe.db.exists(doctype, record_name):
        return
    frappe.db.set_value(doctype, record_name, fieldname, "", update_modified=False)


def _unlink_reference_only_docs(building_name: str) -> None:
    for doctype, fieldname in COMMERCIAL_BUILDING_LINK_FIELDS:
        for record_name in _list_doc_names(doctype, {fieldname: building_name}):
            _clear_doc_field(doctype, record_name, fieldname)

    for record_name in _list_doc_names(SERVICE_AGREEMENT_ADDENDUM_DOCTYPE, {"building": building_name}):
        _clear_doc_field(SERVICE_AGREEMENT_ADDENDUM_DOCTYPE, record_name, "building")


def _clear_building_template_link(building_name: str) -> None:
    current_template = clean_str(frappe.db.get_value(BUILDING_DOCTYPE, building_name, CURRENT_TEMPLATE_FIELD))
    if current_template:
        _clear_doc_field(BUILDING_DOCTYPE, building_name, CURRENT_TEMPLATE_FIELD)


def _clear_ssr_backlinks(ssr_names: Iterable[str]) -> None:
    for ssr_name in _unique_names(ssr_names):
        _clear_doc_field(SITE_SHIFT_REQUIREMENT_DOCTYPE, ssr_name, SSR_SOP_FIELD)
        _clear_doc_field(SITE_SHIFT_REQUIREMENT_DOCTYPE, ssr_name, SSR_CALLOUT_FIELD)


def delete_admin_building(building_id: str) -> AdminBuildingDeleteResult:
    require_portal_section("admin")
    building_name = clean_str(building_id)
    if not building_name or not frappe.db.exists(BUILDING_DOCTYPE, building_name):
        raise CustomerPortalNotFoundError("That building could not be found.")

    session_names = _list_doc_names(CHECKLIST_SESSION_DOCTYPE, {"building": building_name})
    template_names = _list_doc_names(CHECKLIST_TEMPLATE_DOCTYPE, {"building": building_name})
    current_template = clean_str(frappe.db.get_value(BUILDING_DOCTYPE, building_name, CURRENT_TEMPLATE_FIELD))
    if current_template:
        template_names.append(current_template)

    sop_names = _list_doc_names(BUILDING_SOP_DOCTYPE, {"building": building_name})
    ssr_names = _list_doc_names(SITE_SHIFT_REQUIREMENT_DOCTYPE, {"building": building_name})
    call_out_names = _list_doc_names(CALL_OUT_DOCTYPE, {"building": building_name})
    recurring_rule_names = _list_doc_names(RECURRING_SERVICE_RULE_DOCTYPE, {"building": building_name})
    storage_location_names = _list_doc_names(STORAGE_LOCATION_DOCTYPE, {"building": building_name})

    recommendation_names: list[str] = []
    if ssr_names:
        recommendation_names = _list_doc_names(
            DISPATCH_RECOMMENDATION_DOCTYPE,
            {"site_shift_requirement": ["in", _unique_names(ssr_names)]},
        )

    file_names: list[str] = []
    if session_names:
        file_names = _list_doc_names(
            FILE_DOCTYPE,
            [
                ["attached_to_doctype", "=", CHECKLIST_SESSION_DOCTYPE],
                ["attached_to_name", "in", _unique_names(session_names)],
            ],
        )

    _unlink_reference_only_docs(building_name)
    _clear_building_template_link(building_name)
    _clear_ssr_backlinks(ssr_names)

    _delete_doc_names(FILE_DOCTYPE, file_names)
    _delete_doc_names(CHECKLIST_SESSION_DOCTYPE, session_names)
    _delete_doc_names(CHECKLIST_TEMPLATE_DOCTYPE, template_names)
    _delete_doc_names(BUILDING_SOP_DOCTYPE, sop_names)
    _delete_doc_names(DISPATCH_RECOMMENDATION_DOCTYPE, recommendation_names)
    _delete_doc_names(CALL_OUT_DOCTYPE, call_out_names)
    _delete_doc_names(SITE_SHIFT_REQUIREMENT_DOCTYPE, ssr_names)
    _delete_doc_names(RECURRING_SERVICE_RULE_DOCTYPE, recurring_rule_names)
    _delete_doc_names(STORAGE_LOCATION_DOCTYPE, storage_location_names)
    _delete_doc_if_exists(BUILDING_DOCTYPE, building_name)

    return AdminBuildingDeleteResult(building_id=building_name)
