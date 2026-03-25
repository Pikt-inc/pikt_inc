from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import frappe
from frappe.utils import get_datetime, now_datetime

from . import public_quote as public_quote_service


PORTAL_ROLE = "Customer Portal User"
PORTAL_HOME = "portal"
PORTAL_HOME_PATH = "/portal"
PORTAL_SUPPORT_PATH = "/contact"
PORTAL_TITLE = "Customer Portal"
PORTAL_DESCRIPTION = "Secure account access for agreements, billing, and service locations."
DEFAULT_COUNTRY = public_quote_service.DEFAULT_COUNTRY
PORTAL_PAGE_TITLES = {
    "overview": "Account Overview",
    "agreements": "Agreements",
    "billing": "Billing",
    "locations": "Locations",
}
PORTAL_PAGE_PATHS = {
    "overview": PORTAL_HOME_PATH,
    "agreements": "/portal/agreements",
    "billing": "/portal/billing",
    "locations": "/portal/locations",
}
BUILDING_EDIT_FIELDS = (
    "site_supervisor_name",
    "site_supervisor_phone",
    "site_notes",
    "primary_site_contact",
    "lockout_emergency_contact",
    "access_method",
    "access_entrance",
    "access_entry_details",
    "access_notes",
    "alarm_notes",
    "has_alarm_system",
    "alarm_instructions",
    "allowed_entry_time",
    "key_fob_handoff_details",
    "areas_to_avoid",
    "closing_instructions",
    "parking_elevator_notes",
    "first_service_notes",
    "access_details_confirmed",
)


class PortalAccessError(Exception):
    pass


@dataclass
class PortalScope:
    session_user: str
    customer_name: str
    customer_display: str
    portal_contact_name: str
    portal_contact_email: str
    portal_contact_phone: str
    portal_contact_designation: str
    portal_address_name: str
    billing_contact_name: str
    billing_contact_email: str
    billing_contact_phone: str
    billing_contact_designation: str
    billing_address_name: str
    tax_id: str


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


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


def _page_meta(page_key: str) -> dict[str, str]:
    page_title = PORTAL_PAGE_TITLES.get(page_key, PORTAL_TITLE)
    title = f"{page_title} | {PORTAL_TITLE}" if page_title != PORTAL_TITLE else PORTAL_TITLE
    return {
        "title": title,
        "description": PORTAL_DESCRIPTION,
        "canonical": _get_site_url(PORTAL_PAGE_PATHS.get(page_key, PORTAL_HOME_PATH)),
    }


def _portal_nav(active_key: str) -> list[dict[str, Any]]:
    items = []
    for key, label in PORTAL_PAGE_TITLES.items():
        items.append(
            {
                "key": key,
                "label": label.replace("Account ", "") if key == "overview" else label,
                "url": PORTAL_PAGE_PATHS[key],
                "is_active": key == active_key,
            }
        )
    items.append({"key": "contact", "label": "Contact", "url": PORTAL_SUPPORT_PATH, "is_active": False})
    items.append({"key": "logout", "label": "Log out", "url": "/logout", "is_active": False})
    return items


def _base_page_data(page_key: str) -> dict[str, Any]:
    return {
        "page_key": page_key,
        "page_title": PORTAL_PAGE_TITLES.get(page_key, PORTAL_TITLE),
        "portal_title": PORTAL_TITLE,
        "portal_description": PORTAL_DESCRIPTION,
        "portal_nav": _portal_nav(page_key),
        "portal_contact_path": PORTAL_SUPPORT_PATH,
        "metatags": _page_meta(page_key),
        "access_denied": False,
        "error_message": "",
        "error_title": "",
        "empty_state_title": "",
        "empty_state_copy": "",
        "customer_display": "",
    }


def _error_page_data(page_key: str, title: str, message: str, status_code: int = 403) -> dict[str, Any]:
    _set_http_status(status_code)
    data = _base_page_data(page_key)
    data.update(
        {
            "access_denied": True,
            "error_title": clean(title) or "Portal access unavailable",
            "error_message": clean(message),
        }
    )
    return data


def _format_date(value: Any) -> str:
    if not value:
        return ""
    try:
        dt = get_datetime(value)
    except Exception:
        return clean(value)
    return dt.strftime("%b %d, %Y")


def _format_datetime(value: Any) -> str:
    if not value:
        return ""
    try:
        dt = get_datetime(value)
    except Exception:
        return clean(value)
    return dt.strftime("%b %d, %Y %I:%M %p")


def _as_number(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def _format_currency(amount: Any, currency: str = "USD") -> str:
    symbol = "$" if clean(currency).upper() == "USD" else f"{clean(currency).upper()} "
    return f"{symbol}{_as_number(amount):,.2f}"


def _load_contact_row(contact_name: str) -> dict[str, Any]:
    contact_name = clean(contact_name)
    if not contact_name:
        return {}
    row = frappe.db.get_value(
        "Contact",
        contact_name,
        [
            "name",
            "first_name",
            "last_name",
            "email_id",
            "phone",
            "mobile_no",
            "designation",
            "company_name",
            "address",
            "user",
            "is_primary_contact",
            "is_billing_contact",
        ],
        as_dict=True,
    )
    return dict(row or {})


def _load_address_row(address_name: str) -> dict[str, Any]:
    address_name = clean(address_name)
    if not address_name:
        return {}
    row = frappe.db.get_value(
        "Address",
        address_name,
        [
            "name",
            "address_title",
            "address_type",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "pincode",
            "country",
        ],
        as_dict=True,
    )
    return dict(row or {})


def _display_name(first_name: Any, last_name: Any) -> str:
    full_name = " ".join(part for part in (clean(first_name), clean(last_name)) if part)
    return full_name or ""


def _resolve_portal_scope_or_error() -> PortalScope:
    session_user = clean(getattr(getattr(frappe, "session", None), "user", None))
    if not session_user or session_user == "Guest":
        raise PortalAccessError("Sign in to access your customer portal.")

    rows = frappe.db.sql(
        """
        select
            c.name as contact_name,
            ifnull(c.first_name, '') as first_name,
            ifnull(c.last_name, '') as last_name,
            ifnull(c.email_id, '') as email_id,
            ifnull(c.phone, '') as phone,
            ifnull(c.mobile_no, '') as mobile_no,
            ifnull(c.designation, '') as designation,
            ifnull(c.address, '') as address_name,
            ifnull(c.is_primary_contact, 0) as is_primary_contact,
            ifnull(c.is_billing_contact, 0) as is_billing_contact,
            dl.link_name as customer_name
        from `tabContact` c
        inner join `tabDynamic Link` dl
            on dl.parent = c.name
           and dl.parenttype = 'Contact'
           and dl.link_doctype = 'Customer'
        where ifnull(c.user, '') = %s
        order by c.is_primary_contact desc, c.is_billing_contact desc, c.modified desc, c.creation desc
        """,
        (session_user,),
        as_dict=True,
    )
    if not rows:
        raise PortalAccessError("This portal account is not linked to a customer contact yet.")

    customer_names = {clean(row.get("customer_name")) for row in rows if clean(row.get("customer_name"))}
    if not customer_names:
        raise PortalAccessError("This portal account is missing a customer link.")
    if len(customer_names) != 1:
        raise PortalAccessError("This portal account is linked to multiple customers. Contact support.")

    customer_name = next(iter(customer_names))
    customer_row = frappe.db.get_value(
        "Customer",
        customer_name,
        ["name", "customer_name", "customer_primary_contact", "customer_primary_address", "tax_id"],
        as_dict=True,
    )
    if not customer_row:
        raise PortalAccessError("The linked customer record could not be loaded.")

    portal_row = dict(rows[0])
    portal_contact_name = clean(portal_row.get("contact_name"))
    portal_contact_email = clean(portal_row.get("email_id")) or session_user
    portal_phone = clean(portal_row.get("phone")) or clean(portal_row.get("mobile_no"))

    billing_contact_name = clean(public_quote_service.find_contact_for_customer(customer_name, portal_contact_email))
    billing_contact_row = _load_contact_row(billing_contact_name)
    billing_contact_email = clean(billing_contact_row.get("email_id")) or portal_contact_email
    billing_phone = clean(billing_contact_row.get("phone")) or clean(billing_contact_row.get("mobile_no"))

    billing_address_name = clean(public_quote_service.find_address_for_customer(customer_name))
    return PortalScope(
        session_user=session_user,
        customer_name=customer_name,
        customer_display=clean(customer_row.get("customer_name")) or customer_name,
        portal_contact_name=portal_contact_name,
        portal_contact_email=portal_contact_email,
        portal_contact_phone=portal_phone,
        portal_contact_designation=clean(portal_row.get("designation")),
        portal_address_name=clean(portal_row.get("address_name")),
        billing_contact_name=billing_contact_name,
        billing_contact_email=billing_contact_email,
        billing_contact_phone=billing_phone,
        billing_contact_designation=clean(billing_contact_row.get("designation")),
        billing_address_name=billing_address_name or clean(customer_row.get("customer_primary_address")),
        tax_id=clean(customer_row.get("tax_id")),
    )


def _require_portal_scope() -> PortalScope:
    try:
        return _resolve_portal_scope_or_error()
    except PortalAccessError as exc:
        _throw(str(exc))
        raise


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


def _get_agreements(customer_name: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    agreements = frappe.get_all(
        "Service Agreement",
        filters={"customer": customer_name},
        fields=[
            "name",
            "agreement_name",
            "status",
            "template",
            "template_version",
            "signed_by_name",
            "signed_by_title",
            "signed_by_email",
            "signed_on",
            "rendered_html_snapshot",
            "modified",
        ],
        order_by="signed_on desc, modified desc",
    )
    addenda = frappe.get_all(
        "Service Agreement Addendum",
        filters={"customer": customer_name},
        fields=[
            "name",
            "addendum_name",
            "service_agreement",
            "quotation",
            "sales_order",
            "initial_invoice",
            "building",
            "status",
            "term_model",
            "fixed_term_months",
            "start_date",
            "end_date",
            "template",
            "template_version",
            "signed_by_name",
            "signed_by_title",
            "signed_by_email",
            "signed_on",
            "billing_completed_on",
            "access_completed_on",
            "rendered_html_snapshot",
            "modified",
        ],
        order_by="start_date desc, modified desc",
    )
    return list(agreements or []), list(addenda or [])


def _get_invoices(customer_name: str) -> list[dict[str, Any]]:
    return list(
        frappe.get_all(
            "Sales Invoice",
            filters={"customer": customer_name, "docstatus": ["!=", 2]},
            fields=[
                "name",
                "posting_date",
                "due_date",
                "status",
                "currency",
                "grand_total",
                "outstanding_amount",
                "docstatus",
                "customer",
                "customer_name",
                "custom_building",
                "custom_service_agreement",
                "custom_service_agreement_addendum",
                "modified",
            ],
            order_by="posting_date desc, modified desc",
        )
        or []
    )


def _get_buildings(customer_name: str) -> list[dict[str, Any]]:
    return list(
        frappe.get_all(
            "Building",
            filters={"customer": customer_name},
            fields=[
                "name",
                "building_name",
                "active",
                "address_line_1",
                "address_line_2",
                "city",
                "state",
                "postal_code",
                "site_supervisor_name",
                "site_supervisor_phone",
                "site_notes",
                "access_notes",
                "alarm_notes",
                "access_method",
                "access_entrance",
                "access_entry_details",
                "has_alarm_system",
                "alarm_instructions",
                "allowed_entry_time",
                "primary_site_contact",
                "lockout_emergency_contact",
                "key_fob_handoff_details",
                "areas_to_avoid",
                "closing_instructions",
                "parking_elevator_notes",
                "first_service_notes",
                "access_details_confirmed",
                "access_details_completed_on",
                "custom_service_agreement",
                "custom_service_agreement_addendum",
                "modified",
            ],
            order_by="active desc, building_name asc",
        )
        or []
    )


def _shape_agreement_rows(
    agreements: list[dict[str, Any]],
    addenda: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    active_master = {}
    if agreements:
        preferred = next((row for row in agreements if clean(row.get("status")) == "Active"), agreements[0])
        active_master = {
            "name": clean(preferred.get("name")),
            "title": clean(preferred.get("agreement_name")) or clean(preferred.get("name")),
            "status": clean(preferred.get("status")) or "Active",
            "template": clean(preferred.get("template")),
            "template_version": clean(preferred.get("template_version")),
            "signed_by_name": clean(preferred.get("signed_by_name")),
            "signed_on_label": _format_datetime(preferred.get("signed_on")),
            "download_url": _agreement_download_url(agreement_name=clean(preferred.get("name"))),
            "preview_html": clean(preferred.get("rendered_html_snapshot")),
        }

    shaped_addenda = []
    for row in addenda:
        status = clean(row.get("status"))
        shaped_addenda.append(
            {
                "name": clean(row.get("name")),
                "title": clean(row.get("addendum_name")) or clean(row.get("name")),
                "status": status,
                "term_model": clean(row.get("term_model")) or "Month-to-month",
                "fixed_term_months": clean(row.get("fixed_term_months")),
                "start_date_label": _format_date(row.get("start_date")),
                "end_date_label": _format_date(row.get("end_date")),
                "signed_by_name": clean(row.get("signed_by_name")),
                "signed_on_label": _format_datetime(row.get("signed_on")),
                "billing_completed_on_label": _format_datetime(row.get("billing_completed_on")),
                "access_completed_on_label": _format_datetime(row.get("access_completed_on")),
                "quotation": clean(row.get("quotation")),
                "sales_order": clean(row.get("sales_order")),
                "invoice": clean(row.get("initial_invoice")),
                "building": clean(row.get("building")),
                "download_url": _agreement_download_url(addendum_name=clean(row.get("name"))),
                "preview_html": clean(row.get("rendered_html_snapshot")),
                "is_active": status == "Active",
            }
        )
    return active_master, shaped_addenda


def _shape_invoice_rows(invoices: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], float]:
    shaped = []
    unpaid_total = 0.0
    for row in invoices:
        outstanding = _as_number(row.get("outstanding_amount"))
        currency = clean(row.get("currency")) or "USD"
        unpaid_total += max(outstanding, 0.0)
        shaped.append(
            {
                "name": clean(row.get("name")),
                "posting_date_label": _format_date(row.get("posting_date")),
                "due_date_label": _format_date(row.get("due_date")),
                "status": clean(row.get("status")) or "Draft",
                "grand_total_label": _format_currency(row.get("grand_total"), currency),
                "outstanding_label": _format_currency(outstanding, currency),
                "outstanding_amount": outstanding,
                "currency": currency,
                "building": clean(row.get("custom_building")),
                "download_url": _invoice_download_url(clean(row.get("name"))),
                "is_unpaid": outstanding > 0.009,
            }
        )
    return shaped, unpaid_total


def _shape_building_rows(buildings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shaped = []
    for row in buildings:
        address_bits = [clean(row.get("address_line_1")), clean(row.get("address_line_2"))]
        city_line = ", ".join(bit for bit in (clean(row.get("city")), clean(row.get("state"))) if bit)
        postal = clean(row.get("postal_code"))
        if city_line and postal:
            city_line = f"{city_line} {postal}"
        full_address = ", ".join(part for part in [", ".join(bit for bit in address_bits if bit), city_line] if part)
        shaped.append(
            {
                "name": clean(row.get("name")),
                "title": clean(row.get("building_name")) or clean(row.get("name")),
                "full_address": full_address,
                "active_label": "Active" if truthy(row.get("active")) else "Inactive",
                "active": truthy(row.get("active")),
                "modified_label": _format_datetime(row.get("modified")),
                "fields": {fieldname: row.get(fieldname) for fieldname in BUILDING_EDIT_FIELDS},
            }
        )
    return shaped


def _build_recent_activity(
    addenda: list[dict[str, Any]],
    invoices: list[dict[str, Any]],
    buildings: list[dict[str, Any]],
) -> list[dict[str, str]]:
    activity = []
    for row in addenda[:3]:
        activity.append(
            {
                "label": clean(row.get("addendum_name")) or clean(row.get("name")),
                "meta": clean(row.get("status")) or "Agreement",
                "timestamp": _format_datetime(row.get("modified") or row.get("signed_on")),
            }
        )
    for row in invoices[:3]:
        activity.append(
            {
                "label": clean(row.get("name")),
                "meta": clean(row.get("status")) or "Invoice",
                "timestamp": _format_datetime(row.get("modified") or row.get("posting_date")),
            }
        )
    for row in buildings[:3]:
        activity.append(
            {
                "label": clean(row.get("building_name")) or clean(row.get("name")),
                "meta": "Location updated",
                "timestamp": _format_datetime(row.get("modified")),
            }
        )
    return sorted(activity, key=lambda item: clean(item.get("timestamp")), reverse=True)[:5]


def _portal_contact_payload(scope: PortalScope) -> dict[str, Any]:
    row = _load_contact_row(scope.portal_contact_name)
    return {
        "name": clean(row.get("name")) or scope.portal_contact_name,
        "display_name": _display_name(row.get("first_name"), row.get("last_name")) or scope.portal_contact_name,
        "email": clean(row.get("email_id")) or scope.portal_contact_email,
        "phone": clean(row.get("phone")) or clean(row.get("mobile_no")) or scope.portal_contact_phone,
        "designation": clean(row.get("designation")) or scope.portal_contact_designation,
    }


def _billing_contact_payload(scope: PortalScope) -> dict[str, Any]:
    row = _load_contact_row(scope.billing_contact_name)
    return {
        "name": clean(row.get("name")) or scope.billing_contact_name,
        "display_name": _display_name(row.get("first_name"), row.get("last_name")) or clean(row.get("name")),
        "email": clean(row.get("email_id")) or scope.billing_contact_email,
        "phone": clean(row.get("phone")) or clean(row.get("mobile_no")) or scope.billing_contact_phone,
        "designation": clean(row.get("designation")) or scope.billing_contact_designation,
    }


def _billing_address_payload(scope: PortalScope) -> dict[str, Any]:
    row = _load_address_row(scope.billing_address_name)
    return {
        "name": clean(row.get("name")) or scope.billing_address_name,
        "address_line_1": clean(row.get("address_line1")),
        "address_line_2": clean(row.get("address_line2")),
        "city": clean(row.get("city")),
        "state": clean(row.get("state")),
        "postal_code": clean(row.get("pincode")),
        "country": clean(row.get("country")) or DEFAULT_COUNTRY,
    }


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


def _set_download_response(filename: str, content: Any, content_type: str = "application/octet-stream"):
    local = getattr(frappe, "local", None)
    if local is None:
        return
    response = getattr(local, "response", None)
    if response is None:
        local.response = {}
        response = local.response
    response["filename"] = clean(filename)
    response["filecontent"] = content
    response["type"] = "download"
    response["content_type"] = clean(content_type) or "application/octet-stream"


def render_invoice_pdf(invoice_name: str) -> bytes:
    from frappe.utils.pdf import get_pdf

    html = frappe.get_print("Sales Invoice", invoice_name, as_pdf=False)
    return get_pdf(html)


def get_customer_portal_dashboard_data() -> dict[str, Any]:
    try:
        scope = _resolve_portal_scope_or_error()
    except PortalAccessError as exc:
        return _error_page_data("overview", "Portal access unavailable", str(exc))

    agreements, addenda = _get_agreements(scope.customer_name)
    invoices = _get_invoices(scope.customer_name)
    buildings = _get_buildings(scope.customer_name)
    active_master, shaped_addenda = _shape_agreement_rows(agreements, addenda)
    shaped_invoices, unpaid_total = _shape_invoice_rows(invoices)
    shaped_buildings = _shape_building_rows(buildings)

    data = _base_page_data("overview")
    data.update(
        {
            "customer_display": scope.customer_display,
            "summary_cards": [
                {
                    "label": "Active agreement",
                    "value": active_master.get("title") or ("Ready" if shaped_addenda else "Not yet available"),
                    "meta": active_master.get("status") or (shaped_addenda[0]["status"] if shaped_addenda else "Pending"),
                },
                {
                    "label": "Unpaid invoices",
                    "value": str(sum(1 for row in invoices if _as_number(row.get("outstanding_amount")) > 0.009)),
                    "meta": _format_currency(unpaid_total),
                },
                {
                    "label": "Active locations",
                    "value": str(sum(1 for row in buildings if truthy(row.get("active")))),
                    "meta": f"{len(buildings)} total",
                },
                {
                    "label": "Portal contact",
                    "value": _portal_contact_payload(scope)["display_name"] or scope.portal_contact_email,
                    "meta": scope.portal_contact_email,
                },
            ],
            "active_master": active_master,
            "latest_invoices": shaped_invoices[:3],
            "latest_locations": shaped_buildings[:3],
            "recent_activity": _build_recent_activity(addenda, invoices, buildings),
            "empty_state_title": "Your account is ready.",
            "empty_state_copy": "Agreements, invoices, and service locations will appear here as your account activity grows.",
        }
    )
    return data


def get_customer_portal_agreements_data() -> dict[str, Any]:
    try:
        scope = _resolve_portal_scope_or_error()
    except PortalAccessError as exc:
        return _error_page_data("agreements", "Portal access unavailable", str(exc))

    agreements, addenda = _get_agreements(scope.customer_name)
    active_master, shaped_addenda = _shape_agreement_rows(agreements, addenda)

    data = _base_page_data("agreements")
    data.update(
        {
            "customer_display": scope.customer_display,
            "active_master": active_master,
            "addenda": shaped_addenda,
            "empty_state_title": "No agreements are available yet.",
            "empty_state_copy": "Signed service agreements and quote addenda will appear here once your account is active.",
        }
    )
    return data


def get_customer_portal_billing_data() -> dict[str, Any]:
    try:
        scope = _resolve_portal_scope_or_error()
    except PortalAccessError as exc:
        return _error_page_data("billing", "Portal access unavailable", str(exc))

    invoices = _get_invoices(scope.customer_name)
    shaped_invoices, unpaid_total = _shape_invoice_rows(invoices)

    data = _base_page_data("billing")
    data.update(
        {
            "customer_display": scope.customer_display,
            "portal_contact": _portal_contact_payload(scope),
            "billing_contact": _billing_contact_payload(scope),
            "billing_address": _billing_address_payload(scope),
            "tax_id": scope.tax_id,
            "invoices": shaped_invoices,
            "unpaid_total_label": _format_currency(unpaid_total),
            "empty_state_title": "Billing will appear here once your account is invoiced.",
            "empty_state_copy": "You can keep your billing contact and address current here in the meantime.",
        }
    )
    return data


def get_customer_portal_locations_data() -> dict[str, Any]:
    try:
        scope = _resolve_portal_scope_or_error()
    except PortalAccessError as exc:
        return _error_page_data("locations", "Portal access unavailable", str(exc))

    data = _base_page_data("locations")
    data.update(
        {
            "customer_display": scope.customer_display,
            "buildings": _shape_building_rows(_get_buildings(scope.customer_name)),
            "empty_state_title": "No service locations are linked to your account yet.",
            "empty_state_copy": "Once service locations are added, you will be able to review and update access details here.",
        }
    )
    return data


def update_customer_portal_billing(**kwargs):
    scope = _require_portal_scope()
    portal_contact_name = clean(kwargs.get("portal_contact_name")) or _portal_contact_payload(scope).get("display_name") or scope.portal_contact_name
    portal_contact_phone = clean(kwargs.get("portal_contact_phone")) or scope.portal_contact_phone
    portal_contact_title = clean(kwargs.get("portal_contact_title")) or scope.portal_contact_designation

    billing_contact_name = clean(kwargs.get("billing_contact_name")) or clean(kwargs.get("portal_contact_name")) or scope.customer_display
    billing_email = clean(kwargs.get("billing_email")).lower() or scope.billing_contact_email or scope.portal_contact_email
    if not public_quote_service.valid_email(billing_email):
        _throw("Enter a valid billing email address.")

    billing_phone = clean(kwargs.get("billing_contact_phone")) or scope.billing_contact_phone
    billing_title = clean(kwargs.get("billing_contact_title")) or scope.billing_contact_designation
    address_line_1 = clean(kwargs.get("billing_address_line_1"))
    city = clean(kwargs.get("billing_city"))
    state = clean(kwargs.get("billing_state"))
    postal_code = clean(kwargs.get("billing_postal_code"))
    if not address_line_1 or not city or not state or not postal_code:
        _throw("Billing address line 1, city, state, and postal code are required.")

    address_name = public_quote_service.ensure_address(
        scope.customer_name,
        scope.customer_display,
        address_line_1,
        clean(kwargs.get("billing_address_line_2")),
        city,
        state,
        postal_code,
        clean(kwargs.get("billing_country")) or DEFAULT_COUNTRY,
    )
    contact_name = public_quote_service.ensure_contact(
        scope.customer_name,
        scope.customer_display,
        billing_contact_name,
        billing_email,
    )
    public_quote_service.doc_db_set_values(
        "Contact",
        contact_name,
        _contact_updates(billing_contact_name, billing_phone, billing_title, address_name),
    )
    public_quote_service.sync_customer(
        scope.customer_name,
        billing_email,
        contact_name,
        address_name,
        clean(kwargs.get("tax_id")),
    )

    if clean(scope.portal_contact_name):
        public_quote_service.doc_db_set_values(
            "Contact",
            scope.portal_contact_name,
            _contact_updates(portal_contact_name, portal_contact_phone, portal_contact_title, clean(scope.portal_address_name)),
        )

    response = get_customer_portal_billing_data()
    response.update({"status": "updated", "message": "Billing details updated."})
    return response


def update_customer_portal_location(**kwargs):
    scope = _require_portal_scope()
    building_name = clean(kwargs.get("building") or kwargs.get("building_name"))
    if not building_name:
        _throw("Choose a service location to update.")

    building_row = frappe.db.get_value(
        "Building",
        building_name,
        ["name", "customer", "access_details_completed_on"],
        as_dict=True,
    )
    if not building_row or clean(building_row.get("customer")) != scope.customer_name:
        _throw("That service location is not available in this portal account.")

    updates = {}
    for fieldname in BUILDING_EDIT_FIELDS:
        if fieldname in kwargs:
            updates[fieldname] = kwargs.get(fieldname)
    if not updates:
        _throw("No location updates were provided.")

    if "access_details_confirmed" in updates:
        updates["access_details_confirmed"] = 1 if truthy(updates["access_details_confirmed"]) else 0
        if updates["access_details_confirmed"] and not building_row.get("access_details_completed_on"):
            updates["access_details_completed_on"] = now_datetime()

    public_quote_service.doc_db_set_values("Building", building_name, updates)
    response = get_customer_portal_locations_data()
    response.update({"status": "updated", "message": "Location details updated."})
    return response


def download_customer_portal_invoice(invoice: str | None = None, **kwargs):
    scope = _require_portal_scope()
    invoice_name = clean(invoice or kwargs.get("invoice"))
    if not invoice_name:
        _throw("Choose an invoice to download.")
    invoice_row = frappe.db.get_value(
        "Sales Invoice",
        invoice_name,
        ["name", "customer", "docstatus"],
        as_dict=True,
    )
    if not invoice_row or clean(invoice_row.get("customer")) != scope.customer_name or int(invoice_row.get("docstatus") or 0) == 2:
        _throw("That invoice is not available in this portal account.")

    pdf_content = render_invoice_pdf(invoice_name)
    _set_download_response(f"{invoice_name}.pdf", pdf_content, "application/pdf")
    return None


def download_customer_portal_agreement_snapshot(addendum: str | None = None, agreement: str | None = None, **kwargs):
    scope = _require_portal_scope()
    addendum_name = clean(addendum or kwargs.get("addendum"))
    agreement_name = clean(agreement or kwargs.get("agreement"))
    if not addendum_name and not agreement_name:
        _throw("Choose an agreement to download.")

    doctype = "Service Agreement Addendum" if addendum_name else "Service Agreement"
    record_name = addendum_name or agreement_name
    title_field = "addendum_name" if addendum_name else "agreement_name"
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
