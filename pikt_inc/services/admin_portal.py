from __future__ import annotations

from datetime import date
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
COMPANY_DOCTYPE = "Company"
CUSTOMER_DOCTYPE = "Customer"
PROJECT_DOCTYPE = "Project"
COST_CENTER_DOCTYPE = "Cost Center"
SUBSCRIPTION_PLAN_DOCTYPE = "Subscription Plan"
SUBSCRIPTION_DOCTYPE = "Subscription"
CONTRACT_DOCTYPE = "Contract"
ITEM_DOCTYPE = "Item"
SALES_ORDER_DOCTYPE = "Sales Order"
CURRENT_TEMPLATE_FIELD = "current_checklist_template"
SSR_SOP_FIELD = "custom_building_sop"
SSR_CALLOUT_FIELD = "call_out_record"
COMMERCIAL_SERVICE_ITEM_CONFIG_KEY = "pikt_commercial_service_item_code"
DEFAULT_COMMERCIAL_SERVICE_ITEM_CODE = "General Cleaning"
DEFAULT_COMMERCIAL_CONTRACT_TERMS = (
    "Recurring general cleaning services will be provided for the linked project and billed according "
    "to the associated ERPNext subscription. Site schedule, checklist requirements, and operational "
    "notes are maintained on the building and project records."
)

COMMERCIAL_BUILDING_LINK_FIELDS = (
    ("Opportunity", "custom_building"),
    ("Quotation", "custom_building"),
    ("Sales Order", "custom_building"),
    ("Sales Invoice", "custom_building"),
)


class AdminBuildingDeleteResult(ResponseModel):
    building_id: str
    redirect_to: str = ADMIN_HOME_PATH


class AdminCommercialOption(ResponseModel):
    id: str
    label: str


class AdminBuildingCommercialOptionsResult(ResponseModel):
    service_item_code: str
    customers: list[AdminCommercialOption]
    companies: list[AdminCommercialOption]


class AdminBuildingUpdateResult(ResponseModel):
    building_id: str
    project: str | None = None
    cost_center: str | None = None
    subscription_plan: str | None = None
    subscription: str | None = None
    sales_order: str | None = None
    contract: str | None = None


BUILDING_UPDATE_FIELDS = [
    "name",
    "building_name",
    "customer",
    "company",
    "active",
    "address_line_1",
    "address_line_2",
    "city",
    "state",
    "postal_code",
    "site_notes",
    "unavailable_service_days",
    "service_frequency",
    "preferred_service_start_time",
    "preferred_service_end_time",
    "billing_model",
    "contract_amount",
    "billing_interval",
    "billing_interval_count",
    "contract_start_date",
    "contract_end_date",
    "auto_renew",
    "project",
    "cost_center",
    "subscription_plan",
    "subscription",
    "sales_order",
    "contract",
]


def _throw(message: str) -> None:
    frappe.throw(message)


def _site_config_value(key: str) -> str:
    conf = getattr(frappe, "conf", None)
    if conf is None:
        return ""
    if isinstance(conf, dict):
        return clean_str(conf.get(key))
    getter = getattr(conf, "get", None)
    if callable(getter):
        return clean_str(getter(key))
    return clean_str(getattr(conf, key, None))


def _configured_service_item_code() -> str:
    return _site_config_value(COMMERCIAL_SERVICE_ITEM_CONFIG_KEY) or DEFAULT_COMMERCIAL_SERVICE_ITEM_CODE


def _default_contract_terms() -> str:
    return DEFAULT_COMMERCIAL_CONTRACT_TERMS


def _clean_optional_name(value) -> str | None:
    cleaned = clean_str(value)
    return cleaned or None


def _bool_int(value) -> int:
    return 1 if bool(value) else 0


def _serialize_date(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _serialize_time(value: str | None) -> str | None:
    return f"{value}:00" if clean_str(value) else None


def _serialize_day_list(values: list[str]) -> str | None:
    cleaned = [clean_str(value).lower() for value in values or [] if clean_str(value)]
    return ",".join(cleaned) if cleaned else None


def _row(doctype: str, filters, fields: list[str], order_by: str | None = None):
    rows = frappe.get_all(
        doctype,
        filters=filters,
        fields=fields,
        order_by=order_by,
        limit=1,
    )
    return dict(rows[0]) if rows else None


def _building_row(building_name: str):
    return _row(BUILDING_DOCTYPE, {"name": building_name}, BUILDING_UPDATE_FIELDS)


def _company_row(company: str):
    return _row(
        COMPANY_DOCTYPE,
        {"name": company},
        ["name", "company_name", "abbr", "default_currency", "cost_center"],
    )


def _cost_center_row(name: str):
    cost_center_name = clean_str(name)
    if not cost_center_name:
        return None
    return _row(
        COST_CENTER_DOCTYPE,
        {"name": cost_center_name},
        ["name", "company", "parent_cost_center", "is_group"],
    )


def _company_group_cost_centers(company: str) -> list[dict]:
    company_name = clean_str(company)
    if not company_name:
        return []
    return [
        dict(row)
        for row in frappe.get_all(
            COST_CENTER_DOCTYPE,
            filters={"company": company_name, "is_group": 1},
            fields=["name", "parent_cost_center"],
            order_by="lft asc",
            limit=100,
        )
    ]


def _resolve_company_group_cost_center(company_row: dict | None) -> str:
    row = company_row or {}
    company_name = clean_str(row.get("name"))
    configured_cost_center = clean_str(row.get("cost_center"))

    if configured_cost_center:
        configured_row = _cost_center_row(configured_cost_center) or {}
        if clean_str(configured_row.get("company")) == company_name:
            if int(configured_row.get("is_group") or 0) == 1:
                return configured_cost_center

            parent_cost_center = clean_str(configured_row.get("parent_cost_center"))
            if parent_cost_center:
                parent_row = _cost_center_row(parent_cost_center) or {}
                if clean_str(parent_row.get("company")) == company_name and int(parent_row.get("is_group") or 0) == 1:
                    return parent_cost_center

    group_rows = _company_group_cost_centers(company_name)
    if not group_rows:
        return ""

    for candidate in group_rows:
        candidate_name = clean_str(candidate.get("name"))
        if candidate_name and not clean_str(candidate.get("parent_cost_center")):
            return candidate_name

    return clean_str(group_rows[0].get("name"))


def _project_type_name() -> str | None:
    row = _row("Project Type", {"name": "External"}, ["name"])
    return clean_str((row or {}).get("name")) or None


def _load_doc(doctype: str, name: str):
    record_name = clean_str(name)
    if not record_name or not frappe.db.exists(doctype, record_name):
        return None
    return frappe.get_doc(doctype, record_name)


def _insert_doc(payload: dict):
    doc = frappe.get_doc(payload)
    doc.flags.ignore_permissions = True
    doc.insert(ignore_permissions=True)
    return doc


def _save_doc(doc):
    doc.flags.ignore_permissions = True
    doc.save(ignore_permissions=True)
    return doc


def _ensure_company(company: str):
    company_name = clean_str(company)
    if not company_name or not frappe.db.exists(COMPANY_DOCTYPE, company_name):
        _throw("Company could not be found.")
    row = _company_row(company_name) or {}
    if not clean_str(row.get("default_currency")):
        _throw("Selected company is missing a default currency.")
    group_cost_center = _resolve_company_group_cost_center(row)
    if not group_cost_center:
        _throw("Selected company is missing a group cost center.")
    row["cost_center"] = group_cost_center
    return row


def _ensure_customer(customer: str):
    customer_name = clean_str(customer)
    if not customer_name or not frappe.db.exists(CUSTOMER_DOCTYPE, customer_name):
        _throw("Customer could not be found.")
    return customer_name


def _ensure_service_item(item_code: str):
    service_item_code = clean_str(item_code)
    if not service_item_code or not frappe.db.exists(ITEM_DOCTYPE, service_item_code):
        _throw(f"Configured service item {service_item_code or '(blank)'} could not be found.")
    return service_item_code


def _commercial_state_from_row(row: dict | None):
    record = row or {}
    contract_amount_raw = record.get("contract_amount")
    contract_amount = None
    if contract_amount_raw not in (None, ""):
        try:
            contract_amount = round(float(contract_amount_raw), 2)
        except (TypeError, ValueError):
            contract_amount = None

    interval_count = None
    if record.get("billing_interval_count") not in (None, ""):
        try:
            interval_count = int(record.get("billing_interval_count"))
        except (TypeError, ValueError):
            interval_count = None

    return {
        "customer": _clean_optional_name(record.get("customer")),
        "company": _clean_optional_name(record.get("company")),
        "billing_model": _clean_optional_name(record.get("billing_model")),
        "contract_amount": contract_amount,
        "billing_interval": _clean_optional_name(record.get("billing_interval")),
        "billing_interval_count": interval_count,
        "contract_start_date": _clean_optional_name(record.get("contract_start_date")),
        "contract_end_date": _clean_optional_name(record.get("contract_end_date")),
        "auto_renew": bool(record.get("auto_renew")),
    }


def _commercial_state_from_request(request):
    return {
        "customer": _clean_optional_name(request.customer),
        "company": _clean_optional_name(request.company),
        "billing_model": _clean_optional_name(request.billing_model),
        "contract_amount": round(float(request.contract_amount), 2) if request.contract_amount is not None else None,
        "billing_interval": _clean_optional_name(request.billing_interval),
        "billing_interval_count": int(request.billing_interval_count) if request.billing_interval_count is not None else None,
        "contract_start_date": _serialize_date(request.contract_start_date),
        "contract_end_date": _serialize_date(request.contract_end_date),
        "auto_renew": bool(request.auto_renew) if clean_str(request.billing_model) == "recurring" else False,
    }


def _commercial_links_missing(row: dict | None) -> bool:
    state = _commercial_state_from_row(row)
    billing_model = clean_str(state.get("billing_model"))
    record = row or {}
    if billing_model == "recurring":
        return any(
            not clean_str(record.get(fieldname))
            for fieldname in ("project", "cost_center", "subscription_plan", "subscription", "contract")
        )
    if billing_model == "one_time":
        return any(
            not clean_str(record.get(fieldname))
            for fieldname in ("project", "cost_center", "sales_order")
        )
    return False


def _rename_building(old_name: str, new_name: str) -> str:
    old_record_name = clean_str(old_name)
    new_record_name = clean_str(new_name)
    if not new_record_name or new_record_name == old_record_name:
        return old_record_name

    try:
        from frappe.model.rename_doc import rename_doc as frappe_rename_doc
    except Exception:
        frappe_rename_doc = None

    if frappe_rename_doc is None:
        _throw("Building rename is unavailable in this environment.")

    renamed = frappe_rename_doc(
        BUILDING_DOCTYPE,
        old_record_name,
        new_record_name,
        merge=False,
        ignore_permissions=True,
    )
    return clean_str(renamed) or new_record_name


def _upsert_cost_center(*, linked_name: str | None, building_display_name: str, company_row: dict):
    company = clean_str(company_row.get("name"))
    parent_cost_center = clean_str(company_row.get("cost_center"))
    linked = _load_doc(COST_CENTER_DOCTYPE, linked_name or "")

    if linked and clean_str(getattr(linked, "company", None)) != company:
        linked = None

    if linked is None:
        existing = _row(
            COST_CENTER_DOCTYPE,
            {"cost_center_name": building_display_name, "company": company},
            ["name"],
        )
        linked = _load_doc(COST_CENTER_DOCTYPE, (existing or {}).get("name"))

    if linked is None:
        linked = _insert_doc(
            {
                "doctype": COST_CENTER_DOCTYPE,
                "cost_center_name": building_display_name,
                "company": company,
                "parent_cost_center": parent_cost_center,
                "is_group": 0,
                "disabled": 0,
            }
        )
        return linked.name

    linked.cost_center_name = building_display_name
    linked.company = company
    linked.parent_cost_center = parent_cost_center
    linked.is_group = 0
    linked.disabled = 0
    _save_doc(linked)
    return linked.name


def _upsert_project(*, linked_name: str | None, building_display_name: str, customer: str, company_row: dict, cost_center_name: str):
    company = clean_str(company_row.get("name"))
    linked = _load_doc(PROJECT_DOCTYPE, linked_name or "")

    if linked is None:
        existing = _row(
            PROJECT_DOCTYPE,
            {"project_name": building_display_name, "company": company},
            ["name"],
        )
        linked = _load_doc(PROJECT_DOCTYPE, (existing or {}).get("name"))

    project_type = _project_type_name()
    if linked is None:
        payload = {
            "doctype": PROJECT_DOCTYPE,
            "naming_series": "PROJ-.####",
            "project_name": building_display_name,
            "status": "Open",
            "company": company,
            "customer": customer,
            "cost_center": cost_center_name,
        }
        if project_type:
            payload["project_type"] = project_type
        linked = _insert_doc(payload)
        return linked.name

    linked.project_name = building_display_name
    linked.status = clean_str(getattr(linked, "status", None)) or "Open"
    linked.company = company
    linked.customer = customer
    linked.cost_center = cost_center_name
    if project_type:
        linked.project_type = project_type
    _save_doc(linked)
    return linked.name


def _upsert_subscription_plan(
    *,
    linked_name: str | None,
    building_display_name: str,
    company_row: dict,
    cost_center_name: str,
    service_item_code: str,
    contract_amount: float,
    billing_interval: str,
    billing_interval_count: int,
):
    linked = _load_doc(SUBSCRIPTION_PLAN_DOCTYPE, linked_name or "")
    if linked is None:
        linked = _insert_doc(
            {
                "doctype": SUBSCRIPTION_PLAN_DOCTYPE,
                "plan_name": f"{building_display_name} General Cleaning",
                "currency": clean_str(company_row.get("default_currency")),
                "item": service_item_code,
                "price_determination": "Fixed Rate",
                "cost": contract_amount,
                "billing_interval": billing_interval.capitalize(),
                "billing_interval_count": billing_interval_count,
                "cost_center": cost_center_name,
            }
        )
        return linked.name

    linked.plan_name = clean_str(getattr(linked, "plan_name", None)) or f"{building_display_name} General Cleaning"
    linked.currency = clean_str(company_row.get("default_currency"))
    linked.item = service_item_code
    linked.price_determination = "Fixed Rate"
    linked.price_list = ""
    linked.cost = contract_amount
    linked.billing_interval = billing_interval.capitalize()
    linked.billing_interval_count = billing_interval_count
    linked.cost_center = cost_center_name
    _save_doc(linked)
    return linked.name


def _subscription_locked(doc) -> bool:
    status = clean_str(getattr(doc, "status", None)).lower()
    return status in {"active", "grace period", "cancelled", "unpaid", "completed"}


def _contract_locked(doc) -> bool:
    status = clean_str(getattr(doc, "status", None)).lower()
    return status in {"active", "inactive", "cancelled"}


def _sales_order_locked(doc) -> bool:
    try:
        docstatus = int(getattr(doc, "docstatus", 0) or 0)
    except (TypeError, ValueError):
        docstatus = 0
    status = clean_str(getattr(doc, "status", None)).lower()
    return docstatus != 0 or status not in {"", "draft"}


def _upsert_subscription(
    *,
    linked_name: str | None,
    customer: str,
    company_row: dict,
    plan_name: str,
    cost_center_name: str,
    contract_start_date: str | None,
    contract_end_date: str | None,
):
    linked = _load_doc(SUBSCRIPTION_DOCTYPE, linked_name or "")
    if linked and _subscription_locked(linked):
        _throw("The linked subscription is already active or finalized and cannot be updated automatically.")

    if linked is None:
        linked = _insert_doc(
            {
                "doctype": SUBSCRIPTION_DOCTYPE,
                "party_type": "Customer",
                "party": customer,
                "company": clean_str(company_row.get("name")),
                "start_date": contract_start_date,
                "end_date": contract_end_date,
                "submit_invoice": 1,
                "cost_center": cost_center_name,
                "plans": [{"plan": plan_name, "qty": 1}],
            }
        )
        return linked.name

    linked.party_type = "Customer"
    linked.party = customer
    linked.company = clean_str(company_row.get("name"))
    linked.start_date = contract_start_date
    linked.end_date = contract_end_date
    linked.submit_invoice = 1
    linked.cost_center = cost_center_name
    linked.plans = [{"plan": plan_name, "qty": 1}]
    _save_doc(linked)
    return linked.name


def _upsert_contract(
    *,
    linked_name: str | None,
    customer: str,
    project_name: str,
    contract_start_date: str | None,
    contract_end_date: str | None,
):
    linked = _load_doc(CONTRACT_DOCTYPE, linked_name or "")
    if linked and _contract_locked(linked):
        _throw("The linked contract is already active or finalized and cannot be updated automatically.")

    if linked is None:
        linked = _insert_doc(
            {
                "doctype": CONTRACT_DOCTYPE,
                "party_type": "Customer",
                "party_name": customer,
                "status": "Unsigned",
                "start_date": contract_start_date,
                "end_date": contract_end_date,
                "contract_terms": _default_contract_terms(),
                "document_type": "Project",
                "document_name": project_name,
            }
        )
        return linked.name

    linked.party_type = "Customer"
    linked.party_name = customer
    linked.start_date = contract_start_date
    linked.end_date = contract_end_date
    if not clean_str(getattr(linked, "contract_terms", None)):
        linked.contract_terms = _default_contract_terms()
    linked.document_type = "Project"
    linked.document_name = project_name
    linked.status = clean_str(getattr(linked, "status", None)) or "Unsigned"
    _save_doc(linked)
    return linked.name


def _upsert_sales_order(
    *,
    linked_name: str | None,
    building_name: str,
    customer: str,
    company_row: dict,
    project_name: str,
    cost_center_name: str,
    service_item_code: str,
    contract_amount: float,
    contract_start_date: str | None,
    contract_end_date: str | None,
):
    linked = _load_doc(SALES_ORDER_DOCTYPE, linked_name or "")
    if linked and _sales_order_locked(linked):
        _throw("The linked sales order is already submitted or finalized and cannot be updated automatically.")

    delivery_date = contract_end_date or contract_start_date

    item_row = {
        "item_code": service_item_code,
        "qty": 1,
        "rate": contract_amount,
        "delivery_date": delivery_date,
        "project": project_name,
        "cost_center": cost_center_name,
    }

    if linked is None:
        linked = _insert_doc(
            {
                "doctype": SALES_ORDER_DOCTYPE,
                "company": clean_str(company_row.get("name")),
                "customer": customer,
                "order_type": "Sales",
                "transaction_date": contract_start_date,
                "delivery_date": delivery_date,
                "project": project_name,
                "cost_center": cost_center_name,
                "custom_building": building_name,
                "items": [item_row],
            }
        )
        return linked.name

    linked.company = clean_str(company_row.get("name"))
    linked.customer = customer
    linked.order_type = "Sales"
    linked.transaction_date = contract_start_date
    linked.delivery_date = delivery_date
    linked.project = project_name
    linked.cost_center = cost_center_name
    if hasattr(linked, "custom_building"):
        linked.custom_building = building_name
    linked.items = [item_row]
    _save_doc(linked)
    return linked.name


def _building_update_payload(request, desired_building_name: str):
    payload = {
        "building_name": desired_building_name,
        "customer": clean_str(request.customer) or None,
        "company": clean_str(request.company) or None,
        "address_line_1": clean_str(request.address) or None,
        "address_line_2": None,
        "city": None,
        "state": None,
        "postal_code": None,
        "site_notes": clean_str(request.notes) or None,
        "unavailable_service_days": _serialize_day_list(request.unavailable_service_days),
        "service_frequency": request.service_frequency,
        "preferred_service_start_time": _serialize_time(request.preferred_service_start_time),
        "preferred_service_end_time": _serialize_time(request.preferred_service_end_time),
        "billing_model": clean_str(request.billing_model) or None,
        "contract_amount": request.contract_amount,
        "billing_interval": clean_str(request.billing_interval) or None,
        "billing_interval_count": int(request.billing_interval_count) if request.billing_interval_count is not None else "",
        "contract_start_date": _serialize_date(request.contract_start_date),
        "contract_end_date": _serialize_date(request.contract_end_date),
        "auto_renew": _bool_int(bool(request.auto_renew) and clean_str(request.billing_model) == "recurring"),
    }
    if request.active is not None:
        payload["active"] = _bool_int(request.active)
    return payload


def _compact_updates(values: dict) -> dict:
    return {key: value for key, value in values.items() if value is not None}


def get_admin_building_commercial_options() -> AdminBuildingCommercialOptionsResult:
    require_portal_section("admin")

    customers = [
        AdminCommercialOption(
            id=clean_str(row.get("name")),
            label=clean_str(row.get("customer_name")) or clean_str(row.get("name")),
        )
        for row in frappe.get_all(
            CUSTOMER_DOCTYPE,
            fields=["name", "customer_name"],
            order_by="customer_name asc",
            limit=500,
        )
        if clean_str((row or {}).get("name"))
    ]
    companies = [
        AdminCommercialOption(
            id=clean_str(row.get("name")),
            label=clean_str(row.get("company_name")) or clean_str(row.get("name")),
        )
        for row in frappe.get_all(
            COMPANY_DOCTYPE,
            fields=["name", "company_name"],
            order_by="company_name asc",
            limit=100,
        )
        if clean_str((row or {}).get("name"))
    ]

    return AdminBuildingCommercialOptionsResult(
        service_item_code=_configured_service_item_code(),
        customers=customers,
        companies=companies,
    )


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


def update_admin_building(request) -> AdminBuildingUpdateResult:
    require_portal_section("admin")
    original_building_name = clean_str(request.building_id)
    initial_row = _building_row(original_building_name)
    if not initial_row:
        raise CustomerPortalNotFoundError("That building could not be found.")

    desired_building_name = clean_str(request.name) or clean_str(initial_row.get("building_name")) or original_building_name
    building_name = _rename_building(original_building_name, desired_building_name)
    current_row = _building_row(building_name) or {}

    base_updates = _building_update_payload(request, desired_building_name)
    frappe.db.set_value(BUILDING_DOCTYPE, building_name, base_updates)

    requested_commercial_state = _commercial_state_from_request(request)
    current_commercial_state = _commercial_state_from_row(current_row)
    commercial_changed = requested_commercial_state != current_commercial_state
    link_updates: dict[str, str] = {}

    billing_model = clean_str(request.billing_model)
    if billing_model and (commercial_changed or _commercial_links_missing(current_row)):
        customer = _ensure_customer(request.customer)
        company_row = _ensure_company(request.company)
        service_item_code = _ensure_service_item(_configured_service_item_code())

        cost_center_name = _upsert_cost_center(
            linked_name=_clean_optional_name(current_row.get("cost_center")),
            building_display_name=desired_building_name,
            company_row=company_row,
        )
        project_name = _upsert_project(
            linked_name=_clean_optional_name(current_row.get("project")),
            building_display_name=desired_building_name,
            customer=customer,
            company_row=company_row,
            cost_center_name=cost_center_name,
        )

        link_updates.update(
            {
                "project": project_name,
                "cost_center": cost_center_name,
            }
        )

        if billing_model == "recurring":
            subscription_plan_name = _upsert_subscription_plan(
                linked_name=_clean_optional_name(current_row.get("subscription_plan")),
                building_display_name=desired_building_name,
                company_row=company_row,
                cost_center_name=cost_center_name,
                service_item_code=service_item_code,
                contract_amount=float(request.contract_amount or 0),
                billing_interval=clean_str(request.billing_interval),
                billing_interval_count=int(request.billing_interval_count or 1),
            )
            subscription_name = _upsert_subscription(
                linked_name=_clean_optional_name(current_row.get("subscription")),
                customer=customer,
                company_row=company_row,
                plan_name=subscription_plan_name,
                cost_center_name=cost_center_name,
                contract_start_date=_serialize_date(request.contract_start_date),
                contract_end_date=_serialize_date(request.contract_end_date),
            )
            contract_name = _upsert_contract(
                linked_name=_clean_optional_name(current_row.get("contract")),
                customer=customer,
                project_name=project_name,
                contract_start_date=_serialize_date(request.contract_start_date),
                contract_end_date=_serialize_date(request.contract_end_date),
            )
            link_updates.update(
                {
                    "subscription_plan": subscription_plan_name,
                    "subscription": subscription_name,
                    "contract": contract_name,
                    "sales_order": "",
                }
            )
        elif billing_model == "one_time":
            sales_order_name = _upsert_sales_order(
                linked_name=_clean_optional_name(current_row.get("sales_order")),
                building_name=building_name,
                customer=customer,
                company_row=company_row,
                project_name=project_name,
                cost_center_name=cost_center_name,
                service_item_code=service_item_code,
                contract_amount=float(request.contract_amount or 0),
                contract_start_date=_serialize_date(request.contract_start_date),
                contract_end_date=_serialize_date(request.contract_end_date),
            )
            link_updates.update(
                {
                    "sales_order": sales_order_name,
                    "subscription_plan": "",
                    "subscription": "",
                    "contract": "",
                }
            )

    if link_updates:
        frappe.db.set_value(BUILDING_DOCTYPE, building_name, link_updates)

    final_row = _building_row(building_name) or {}
    return AdminBuildingUpdateResult(
        building_id=building_name,
        project=_clean_optional_name(final_row.get("project")),
        cost_center=_clean_optional_name(final_row.get("cost_center")),
        subscription_plan=_clean_optional_name(final_row.get("subscription_plan")),
        subscription=_clean_optional_name(final_row.get("subscription")),
        sales_order=_clean_optional_name(final_row.get("sales_order")),
        contract=_clean_optional_name(final_row.get("contract")),
    )


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
