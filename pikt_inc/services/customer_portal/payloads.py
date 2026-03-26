from __future__ import annotations

from typing import Any

from ..contracts.customer_portal import (
    DEFAULT_COUNTRY,
    LOCATION_ACCESS_METHOD_OPTIONS,
    LOCATION_ALARM_OPTIONS,
    PortalAgreementAddendum,
    PortalAgreementMaster,
    PortalAgreementsResponse,
    PortalBillingAddress,
    PortalBillingResponse,
    PortalContactDetails,
    PortalDashboardResponse,
    PortalInvoiceRow,
    PortalLocationFields,
    PortalLocationFormOptions,
    PortalLocationRow,
    PortalLocationsResponse,
    PortalMetaTags,
    PortalNavItem,
    PortalRecentActivityItem,
    PortalSummaryCard,
)
from .constants import BUILDING_EDIT_FIELDS, PORTAL_DESCRIPTION, PORTAL_PAGE_PATHS, PORTAL_PAGE_TITLES, PORTAL_SUPPORT_PATH, PORTAL_TITLE
from .formatters import _as_number, _format_currency, _format_date, _format_datetime
from .queries import _load_address_row, _load_contact_row
from .scope import PortalAccessError, PortalScope, _is_guest_session
from .shared import _agreement_download_url, _display_name, _get_site_url, _invoice_download_url, _login_path_for_page, _set_http_status, clean, truthy


def _page_meta(page_key: str) -> PortalMetaTags:
    page_title = PORTAL_PAGE_TITLES.get(page_key, PORTAL_TITLE)
    title = f"{page_title} | {PORTAL_TITLE}" if page_title != PORTAL_TITLE else PORTAL_TITLE
    return PortalMetaTags(
        title=title,
        description=PORTAL_DESCRIPTION,
        canonical=_get_site_url(PORTAL_PAGE_PATHS.get(page_key, PORTAL_PAGE_PATHS["overview"])),
    )


def _portal_nav(active_key: str) -> list[PortalNavItem]:
    items = []
    for key, label in PORTAL_PAGE_TITLES.items():
        items.append(
            PortalNavItem(
                key=key,
                label=label.replace("Account ", "") if key == "overview" else label,
                url=PORTAL_PAGE_PATHS[key],
                is_active=key == active_key,
            )
        )
    items.append(PortalNavItem(key="contact", label="Contact", url=PORTAL_SUPPORT_PATH, is_active=False))
    items.append(PortalNavItem(key="logout", label="Log out", url="/logout", is_active=False))
    return items


def _base_page_kwargs(page_key: str) -> dict[str, Any]:
    return {
        "page_key": page_key,
        "page_title": PORTAL_PAGE_TITLES.get(page_key, PORTAL_TITLE),
        "portal_title": PORTAL_TITLE,
        "portal_description": PORTAL_DESCRIPTION,
        "portal_nav": [item.model_dump(mode="python") for item in _portal_nav(page_key)],
        "portal_contact_path": PORTAL_SUPPORT_PATH,
        "metatags": _page_meta(page_key).model_dump(mode="python"),
        "access_denied": False,
        "error_message": "",
        "error_title": "",
        "empty_state_title": "",
        "empty_state_copy": "",
        "customer_display": "",
        "http_status_code": 200,
        "login_path": "",
        "redirect_to": "",
    }


def _portal_access_error_response(page_key: str, exc: PortalAccessError) -> dict[str, Any]:
    login_path = _login_path_for_page(page_key) if _is_guest_session() else ""
    status_code = 302 if login_path else 403
    _set_http_status(status_code)
    return {
        **_base_page_kwargs(page_key),
        "access_denied": True,
        "error_title": "Portal access unavailable",
        "error_message": clean(str(exc)),
        "http_status_code": status_code,
        "login_path": login_path,
        "redirect_to": login_path,
    }


def _shape_agreement_rows(agreements: list[dict[str, Any]], addenda: list[dict[str, Any]]) -> tuple[PortalAgreementMaster | None, list[PortalAgreementAddendum]]:
    active_master = None
    if agreements:
        preferred = next((row for row in agreements if clean(row.get("status")) == "Active"), agreements[0])
        active_master = PortalAgreementMaster(
            name=clean(preferred.get("name")),
            title=clean(preferred.get("agreement_name")) or clean(preferred.get("name")),
            status=clean(preferred.get("status")) or "Active",
            template=clean(preferred.get("template")),
            template_version=clean(preferred.get("template_version")),
            signed_by_name=clean(preferred.get("signed_by_name")),
            signed_on_label=_format_datetime(preferred.get("signed_on")),
            download_url=_agreement_download_url(agreement_name=clean(preferred.get("name"))),
            preview_html=clean(preferred.get("rendered_html_snapshot")),
        )

    shaped_addenda: list[PortalAgreementAddendum] = []
    for row in addenda:
        status = clean(row.get("status"))
        shaped_addenda.append(
            PortalAgreementAddendum(
                name=clean(row.get("name")),
                title=clean(row.get("addendum_name")) or clean(row.get("name")),
                status=status,
                term_model=clean(row.get("term_model")) or "Month-to-month",
                fixed_term_months=clean(row.get("fixed_term_months")),
                start_date_label=_format_date(row.get("start_date")),
                end_date_label=_format_date(row.get("end_date")),
                signed_by_name=clean(row.get("signed_by_name")),
                signed_on_label=_format_datetime(row.get("signed_on")),
                billing_completed_on_label=_format_datetime(row.get("billing_completed_on")),
                access_completed_on_label=_format_datetime(row.get("access_completed_on")),
                quotation=clean(row.get("quotation")),
                sales_order=clean(row.get("sales_order")),
                invoice=clean(row.get("initial_invoice")),
                building=clean(row.get("building")),
                download_url=_agreement_download_url(addendum_name=clean(row.get("name"))),
                preview_html=clean(row.get("rendered_html_snapshot")),
                is_active=status == "Active",
            )
        )
    return active_master, shaped_addenda


def _shape_invoice_rows(invoices: list[dict[str, Any]]) -> tuple[list[PortalInvoiceRow], float]:
    shaped: list[PortalInvoiceRow] = []
    unpaid_total = 0.0
    for row in invoices:
        outstanding = _as_number(row.get("outstanding_amount"))
        currency = clean(row.get("currency")) or "USD"
        unpaid_total += max(outstanding, 0.0)
        shaped.append(
            PortalInvoiceRow(
                name=clean(row.get("name")),
                posting_date_label=_format_date(row.get("posting_date")),
                due_date_label=_format_date(row.get("due_date")),
                status=clean(row.get("status")) or "Draft",
                grand_total_label=_format_currency(row.get("grand_total"), currency),
                outstanding_label=_format_currency(outstanding, currency),
                outstanding_amount=outstanding,
                currency=currency,
                building=clean(row.get("custom_building")),
                download_url=_invoice_download_url(clean(row.get("name"))),
                is_unpaid=outstanding > 0.009,
            )
        )
    return shaped, unpaid_total


def _shape_building_rows(buildings: list[dict[str, Any]]) -> list[PortalLocationRow]:
    shaped: list[PortalLocationRow] = []
    for row in buildings:
        address_bits = [clean(row.get("address_line_1")), clean(row.get("address_line_2"))]
        city_line = ", ".join(bit for bit in (clean(row.get("city")), clean(row.get("state"))) if bit)
        postal = clean(row.get("postal_code"))
        if city_line and postal:
            city_line = f"{city_line} {postal}"
        full_address = ", ".join(part for part in [", ".join(bit for bit in address_bits if bit), city_line] if part)
        shaped.append(
            PortalLocationRow(
                name=clean(row.get("name")),
                title=clean(row.get("building_name")) or clean(row.get("name")),
                full_address=full_address,
                active_label="Active" if truthy(row.get("active")) else "Inactive",
                active=truthy(row.get("active")),
                modified_label=_format_datetime(row.get("modified")),
                fields=PortalLocationFields(**{fieldname: row.get(fieldname) for fieldname in BUILDING_EDIT_FIELDS}),
            )
        )
    return shaped


def _build_recent_activity(addenda: list[dict[str, Any]], invoices: list[dict[str, Any]], buildings: list[dict[str, Any]]) -> list[PortalRecentActivityItem]:
    activity: list[PortalRecentActivityItem] = []
    for row in addenda[:3]:
        activity.append(
            PortalRecentActivityItem(
                label=clean(row.get("addendum_name")) or clean(row.get("name")),
                meta=clean(row.get("status")) or "Agreement",
                timestamp=_format_datetime(row.get("modified") or row.get("signed_on")),
            )
        )
    for row in invoices[:3]:
        activity.append(
            PortalRecentActivityItem(
                label=clean(row.get("name")),
                meta=clean(row.get("status")) or "Invoice",
                timestamp=_format_datetime(row.get("modified") or row.get("posting_date")),
            )
        )
    for row in buildings[:3]:
        activity.append(
            PortalRecentActivityItem(
                label=clean(row.get("building_name")) or clean(row.get("name")),
                meta="Location updated",
                timestamp=_format_datetime(row.get("modified")),
            )
        )
    return sorted(activity, key=lambda item: clean(item.timestamp), reverse=True)[:5]


def _portal_contact_payload(scope: PortalScope) -> PortalContactDetails:
    row = _load_contact_row(scope.portal_contact_name)
    return PortalContactDetails(
        name=clean(row.get("name")) or scope.portal_contact_name,
        display_name=_display_name(row.get("first_name"), row.get("last_name")) or scope.portal_contact_name,
        email=clean(row.get("email_id")) or scope.portal_contact_email,
        phone=clean(row.get("phone")) or clean(row.get("mobile_no")) or scope.portal_contact_phone,
        designation=clean(row.get("designation")) or scope.portal_contact_designation,
    )


def _billing_contact_payload(scope: PortalScope) -> PortalContactDetails:
    row = _load_contact_row(scope.billing_contact_name)
    return PortalContactDetails(
        name=clean(row.get("name")) or scope.billing_contact_name,
        display_name=_display_name(row.get("first_name"), row.get("last_name")) or clean(row.get("name")),
        email=clean(row.get("email_id")) or scope.billing_contact_email,
        phone=clean(row.get("phone")) or clean(row.get("mobile_no")) or scope.billing_contact_phone,
        designation=clean(row.get("designation")) or scope.billing_contact_designation,
    )


def _billing_address_payload(scope: PortalScope) -> PortalBillingAddress:
    row = _load_address_row(scope.billing_address_name)
    return PortalBillingAddress(
        name=clean(row.get("name")) or scope.billing_address_name,
        address_line_1=clean(row.get("address_line1")),
        address_line_2=clean(row.get("address_line2")),
        city=clean(row.get("city")),
        state=clean(row.get("state")),
        postal_code=clean(row.get("pincode")),
        country=clean(row.get("country")) or DEFAULT_COUNTRY,
    )


def _build_dashboard_response(scope: PortalScope, agreements: list[dict[str, Any]], addenda: list[dict[str, Any]], invoices: list[dict[str, Any]], buildings: list[dict[str, Any]]) -> PortalDashboardResponse:
    active_master, shaped_addenda = _shape_agreement_rows(agreements, addenda)
    shaped_invoices, unpaid_total = _shape_invoice_rows(invoices)
    shaped_buildings = _shape_building_rows(buildings)
    data = _base_page_kwargs("overview")
    data.update(
        {
            "customer_display": scope.customer_display,
            "summary_cards": [
            PortalSummaryCard(
                label="Active agreement",
                value=(active_master.title if active_master else ("Ready" if shaped_addenda else "Not yet available")),
                meta=(active_master.status if active_master else (shaped_addenda[0].status if shaped_addenda else "Pending")),
            ),
            PortalSummaryCard(
                label="Unpaid invoices",
                value=str(sum(1 for row in invoices if _as_number(row.get("outstanding_amount")) > 0.009)),
                meta=_format_currency(unpaid_total),
            ),
            PortalSummaryCard(
                label="Active locations",
                value=str(sum(1 for row in buildings if truthy(row.get("active")))),
                meta=f"{len(buildings)} total",
            ),
            PortalSummaryCard(
                label="Portal contact",
                value=_portal_contact_payload(scope).display_name or scope.portal_contact_email,
                meta=scope.portal_contact_email,
            ),
        ],
            "active_master": active_master,
            "latest_invoices": shaped_invoices[:3],
            "latest_locations": shaped_buildings[:3],
            "recent_activity": _build_recent_activity(addenda, invoices, buildings),
            "empty_state_title": "Your account is ready.",
            "empty_state_copy": "Agreements, invoices, and service locations will appear here as your account activity grows.",
        }
    )
    return PortalDashboardResponse(**data)


def _build_agreements_response(scope: PortalScope, agreements: list[dict[str, Any]], addenda: list[dict[str, Any]]) -> PortalAgreementsResponse:
    active_master, shaped_addenda = _shape_agreement_rows(agreements, addenda)
    data = _base_page_kwargs("agreements")
    data.update(
        {
            "customer_display": scope.customer_display,
            "active_master": active_master,
            "addenda": shaped_addenda,
            "empty_state_title": "No agreements are available yet.",
            "empty_state_copy": "Signed service agreements and quote addenda will appear here once your account is active.",
        }
    )
    return PortalAgreementsResponse(**data)


def _build_billing_response(scope: PortalScope, invoices: list[dict[str, Any]]) -> PortalBillingResponse:
    shaped_invoices, unpaid_total = _shape_invoice_rows(invoices)
    data = _base_page_kwargs("billing")
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
    return PortalBillingResponse(**data)


def _build_locations_response(scope: PortalScope, buildings: list[dict[str, Any]]) -> PortalLocationsResponse:
    data = _base_page_kwargs("locations")
    data.update(
        {
            "customer_display": scope.customer_display,
            "buildings": _shape_building_rows(buildings),
            "location_form_options": PortalLocationFormOptions(
                access_methods=list(LOCATION_ACCESS_METHOD_OPTIONS),
                alarm_system=list(LOCATION_ALARM_OPTIONS),
            ),
            "empty_state_title": "No service locations are linked to your account yet.",
            "empty_state_copy": "Once service locations are added, you will be able to review and update access details here.",
        }
    )
    return PortalLocationsResponse(**data)
