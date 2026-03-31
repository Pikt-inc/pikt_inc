from __future__ import annotations

from typing import Any
from urllib.parse import quote

from .. import building_sop as building_sop_service
from ..contracts.customer_portal import (
    DEFAULT_COUNTRY,
    LOCATION_ACCESS_METHOD_OPTIONS,
    LOCATION_ALARM_OPTIONS,
    PortalAgreementAddendum,
    PortalAgreementMaster,
    PortalAgreementsResponse,
    PortalBillingAddress,
    PortalBillingResponse,
    PortalBuildingSopVersion,
    PortalChecklistItem,
    PortalChecklistProof,
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
    PortalServiceHistoryRow,
    PortalSummaryCard,
)
from .constants import BUILDING_EDIT_FIELDS, PORTAL_DESCRIPTION, PORTAL_NAV_KEYS, PORTAL_PAGE_PATHS, PORTAL_PAGE_TITLES, PORTAL_SUPPORT_PATH, PORTAL_TITLE
from .formatters import _as_number, _format_currency, _format_date, _format_datetime
from .queries import _load_address_row, _load_contact_row
from .scope import PortalAccessError, PortalScope, _is_guest_session
from .shared import _agreement_download_url, _checklist_proof_download_url, _display_name, _get_site_url, _invoice_download_url, _login_path_for_page, _set_http_status, clean, truthy


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
    for key in PORTAL_NAV_KEYS:
        label = PORTAL_PAGE_TITLES[key]
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


def _base_page_kwargs(page_key: str, *, nav_active_key: str | None = None) -> dict[str, Any]:
    return {
        "page_key": page_key,
        "page_title": PORTAL_PAGE_TITLES.get(page_key, PORTAL_TITLE),
        "portal_title": PORTAL_TITLE,
        "portal_description": PORTAL_DESCRIPTION,
        "portal_nav": [item.model_dump(mode="python") for item in _portal_nav(nav_active_key or page_key)],
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


def _portal_access_error_response(page_key: str, exc: PortalAccessError, *, nav_active_key: str | None = None) -> dict[str, Any]:
    login_path = _login_path_for_page(page_key) if _is_guest_session() else ""
    status_code = 302 if login_path else 403
    _set_http_status(status_code)
    return {
        **_base_page_kwargs(page_key, nav_active_key=nav_active_key),
        "access_denied": True,
        "error_title": "Portal access unavailable",
        "error_message": clean(str(exc)),
        "http_status_code": status_code,
        "login_path": login_path,
        "redirect_to": login_path,
    }


def _full_building_address(row: dict[str, Any]) -> str:
    address_bits = [clean(row.get("address_line_1")), clean(row.get("address_line_2"))]
    city_line = ", ".join(bit for bit in (clean(row.get("city")), clean(row.get("state"))) if bit)
    postal = clean(row.get("postal_code"))
    if city_line and postal:
        city_line = f"{city_line} {postal}"
    return ", ".join(part for part in [", ".join(bit for bit in address_bits if bit), city_line] if part)


def _location_agreement_status_label(row: dict[str, Any]) -> str:
    if clean(row.get("custom_service_agreement_addendum")):
        return "Location exhibit on file"
    if clean(row.get("custom_service_agreement")):
        return "Master agreement on file"
    return "No agreement on file"


def _shape_agreement_rows(
    agreements: list[dict[str, Any]],
    addenda: list[dict[str, Any]],
    buildings: list[dict[str, Any]],
) -> tuple[PortalAgreementMaster | None, list[PortalAgreementAddendum]]:
    active_master = None
    building_lookup = {clean(row.get("name")): row for row in buildings if clean(row.get("name"))}
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
        building_name = clean(row.get("building"))
        building_row = building_lookup.get(building_name, {})
        location_title = clean(building_row.get("building_name")) or building_name or clean(row.get("addendum_name")) or clean(row.get("name"))
        shaped_addenda.append(
            PortalAgreementAddendum(
                name=clean(row.get("name")),
                title=location_title,
                document_title=clean(row.get("addendum_name")) or clean(row.get("name")),
                location_address=_full_building_address(building_row),
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
                building=location_title,
                download_url=_agreement_download_url(addendum_name=clean(row.get("name"))),
                preview_html=clean(row.get("rendered_html_snapshot")),
                is_active=status == "Active",
            )
        )
    shaped_addenda.sort(key=lambda row: (not row.is_active, clean(row.title).lower(), clean(row.document_title).lower()))
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
        full_address = _full_building_address(row)
        shaped.append(
            PortalLocationRow(
                name=clean(row.get("name")),
                title=clean(row.get("building_name")) or clean(row.get("name")),
                detail_url=f"{PORTAL_PAGE_PATHS['locations']}?building={quote(clean(row.get('name')))}",
                full_address=full_address,
                active_label="Active" if truthy(row.get("active")) else "Inactive",
                agreement_status_label=_location_agreement_status_label(row),
                active=truthy(row.get("active")),
                modified_label=_format_datetime(row.get("modified")),
                fields=PortalLocationFields(**{fieldname: row.get(fieldname) for fieldname in BUILDING_EDIT_FIELDS}),
            )
        )
    return shaped


def _shape_portal_checklist_items(items: list[dict[str, Any]]) -> list[PortalChecklistItem]:
    shaped: list[PortalChecklistItem] = []
    for row in items or []:
        shaped.append(
            PortalChecklistItem(
                item_id=clean(row.get("item_id")),
                title=clean(row.get("title")),
                description=clean(row.get("description")),
                requires_photo_proof=truthy(row.get("requires_photo_proof")),
                active=truthy(row.get("active") or 1),
                sort_order=int(_as_number(row.get("sort_order"))),
                status=clean(row.get("status")),
                exception_note=clean(row.get("exception_note")),
                proofs=[
                    PortalChecklistProof(
                        name=clean(proof.get("name")),
                        label=clean(proof.get("label")),
                        url=clean(proof.get("url")) or _checklist_proof_download_url(clean(proof.get("name"))),
                    )
                    for proof in row.get("proofs") or []
                ],
            )
        )
    return shaped


def _history_page_url(building_name: str, page_number: int) -> str:
    page_number = max(1, int(page_number or 1))
    return f"{PORTAL_PAGE_PATHS['locations']}?building={quote(clean(building_name))}&history_page={page_number}"


def _shape_service_history(history_payload: dict[str, Any]) -> tuple[list[PortalServiceHistoryRow], int, bool]:
    visits = []
    for row in history_payload.get("visits") or []:
        start_label = _format_datetime(row.get("arrival_window_start"))
        end_label = _format_datetime(row.get("arrival_window_end"))
        arrival_window_label = ""
        if start_label and end_label:
            arrival_window_label = f"{start_label} to {end_label}"
        else:
            arrival_window_label = start_label or end_label
        visits.append(
            PortalServiceHistoryRow(
                name=clean(row.get("name")),
                service_date_label=_format_date(row.get("service_date")),
                arrival_window_label=arrival_window_label,
                status=clean(row.get("status")) or "Scheduled",
                employee_label=clean(row.get("employee_label")) or "Unassigned",
                sop_version_label=clean(row.get("sop_name")) or "No checklist snapshot",
                has_checklist=truthy(row.get("has_checklist")),
                checklist_items=_shape_portal_checklist_items(row.get("checklist_items") or []),
            )
        )
    return visits, int(history_payload.get("page") or 1), truthy(history_payload.get("has_more"))


def _build_recent_activity(addenda: list[dict[str, Any]], invoices: list[dict[str, Any]], buildings: list[dict[str, Any]]) -> list[PortalRecentActivityItem]:
    activity: list[PortalRecentActivityItem] = []
    building_lookup = {clean(row.get("name")): row for row in buildings if clean(row.get("name"))}
    for row in addenda[:3]:
        building_row = building_lookup.get(clean(row.get("building")), {})
        activity.append(
            PortalRecentActivityItem(
                label=clean(building_row.get("building_name")) or clean(row.get("building")) or clean(row.get("addendum_name")) or clean(row.get("name")),
                meta=f"Location exhibit {clean(row.get('status')).lower() or 'updated'}",
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
    active_master, shaped_addenda = _shape_agreement_rows(agreements, addenda, buildings)
    shaped_invoices, unpaid_total = _shape_invoice_rows(invoices)
    shaped_buildings = _shape_building_rows(buildings)
    data = _base_page_kwargs("overview")
    data.update(
        {
            "customer_display": scope.customer_display,
            "summary_cards": [
            PortalSummaryCard(
                label="Agreement status",
                value=("Active" if active_master else "Pending"),
                meta=(
                    f"Signed {active_master.signed_on_label}"
                    if active_master and active_master.signed_on_label
                    else ("Master agreement on file" if active_master else "No active master agreement")
                ),
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


def _build_agreements_response(
    scope: PortalScope,
    agreements: list[dict[str, Any]],
    addenda: list[dict[str, Any]],
    buildings: list[dict[str, Any]],
) -> PortalAgreementsResponse:
    active_master, shaped_addenda = _shape_agreement_rows(agreements, addenda, buildings)
    data = _base_page_kwargs("agreements")
    data.update(
        {
            "customer_display": scope.customer_display,
            "active_master": active_master,
            "addenda": shaped_addenda,
            "empty_state_title": "No agreements are available yet.",
            "empty_state_copy": "Your master services agreement and location exhibits will appear here once your account is active.",
        }
    )
    return PortalAgreementsResponse(**data)


def _build_billing_response(
    scope: PortalScope,
    invoices: list[dict[str, Any]],
    *,
    page_key: str = "billing",
    nav_active_key: str | None = None,
) -> PortalBillingResponse:
    shaped_invoices, unpaid_total = _shape_invoice_rows(invoices)
    data = _base_page_kwargs(page_key, nav_active_key=nav_active_key)
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


def _build_locations_response(
    scope: PortalScope,
    buildings: list[dict[str, Any]],
    *,
    selected_building_name: str = "",
    history_page: int = 1,
) -> PortalLocationsResponse:
    shaped_buildings = _shape_building_rows(buildings)
    selected_name = clean(selected_building_name)
    selected_building = next((row for row in shaped_buildings if row.name == selected_name), None)
    selected_building_sop = None
    selected_building_checklist: list[PortalChecklistItem] = []
    service_history: list[PortalServiceHistoryRow] = []
    service_history_has_more = False
    service_history_page = max(1, int(history_page or 1))
    service_history_next_url = ""
    if selected_building:
        sop_payload = building_sop_service.shape_portal_sop_payload(selected_building.name)
        if sop_payload.get("version"):
            version = sop_payload["version"]
            selected_building_sop = PortalBuildingSopVersion(
                name=clean(version.get("name")),
                version_number=int(version.get("version_number") or 0),
                updated_label=_format_datetime(version.get("updated_on")),
                updated_by=clean(version.get("updated_by")),
                item_count=int(version.get("item_count") or 0),
            )
        selected_building_checklist = _shape_portal_checklist_items(sop_payload.get("items") or [])
        history_payload = building_sop_service.get_building_service_history(selected_building.name, page=service_history_page)
        service_history, service_history_page, service_history_has_more = _shape_service_history(history_payload)
        if service_history_has_more:
            service_history_next_url = _history_page_url(selected_building.name, service_history_page + 1)
    data = _base_page_kwargs("locations")
    data.update(
        {
            "customer_display": scope.customer_display,
            "buildings": shaped_buildings,
            "selected_building": selected_building,
            "location_form_options": PortalLocationFormOptions(
                access_methods=list(LOCATION_ACCESS_METHOD_OPTIONS),
                alarm_system=list(LOCATION_ALARM_OPTIONS),
            ),
            "selected_building_sop": selected_building_sop,
            "selected_building_checklist": selected_building_checklist,
            "service_history": service_history,
            "service_history_page": service_history_page,
            "service_history_has_more": service_history_has_more,
            "service_history_next_url": service_history_next_url,
            "empty_state_title": "No service locations are linked to your account yet.",
            "empty_state_copy": "Once service locations are added, you will be able to review and update access details here.",
        }
    )
    return PortalLocationsResponse(**data)
