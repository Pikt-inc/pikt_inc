from __future__ import annotations

from pydantic import ValidationError

from .. import public_quote as public_quote_service
from ..contracts.common import first_validation_message
from ..contracts.customer_portal import CustomerPortalBillingInput, PortalBillingUpdateResponse
from .constants import DEFAULT_COUNTRY
from .payloads import _build_billing_response, _portal_access_error_response, _portal_contact_payload
from .queries import _get_invoices
from .scope import PortalAccessError, _require_portal_scope, _resolve_portal_scope_or_error
from .shared import _contact_updates, _shared_contact_updates, _should_split_billing_contact, _throw, clean


def _submitted_or_existing(payload: CustomerPortalBillingInput, fieldname: str, current_value: str) -> str:
    if fieldname in payload.model_fields_set:
        return getattr(payload, fieldname)
    return current_value


def get_customer_portal_billing_data() -> dict:
    try:
        scope = _resolve_portal_scope_or_error()
    except PortalAccessError as exc:
        return _portal_access_error_response("billing", exc)
    invoices = _get_invoices(scope.customer_name)
    return _build_billing_response(scope, invoices).model_dump(mode="python")


def update_customer_portal_billing(**kwargs):
    scope = _require_portal_scope()
    try:
        payload = CustomerPortalBillingInput.model_validate(kwargs)
    except ValidationError as exc:
        _throw(first_validation_message(exc))

    portal_contact_name = payload.portal_contact_name or _portal_contact_payload(scope).display_name or scope.portal_contact_name
    portal_contact_phone = _submitted_or_existing(payload, "portal_contact_phone", scope.portal_contact_phone)
    portal_contact_title = payload.portal_contact_title or scope.portal_contact_designation

    billing_contact_name = payload.billing_contact_name or payload.portal_contact_name or scope.customer_display
    billing_email = payload.billing_email or scope.billing_contact_email or scope.portal_contact_email
    if not public_quote_service.valid_email(billing_email):
        _throw("Enter a valid billing email address.")

    billing_phone = _submitted_or_existing(payload, "billing_contact_phone", scope.billing_contact_phone)
    billing_title = payload.billing_contact_title or scope.billing_contact_designation

    address_name = public_quote_service.ensure_address(
        scope.customer_name,
        scope.customer_display,
        payload.billing_address_line_1,
        payload.billing_address_line_2,
        payload.billing_city,
        payload.billing_state,
        payload.billing_postal_code,
        payload.billing_country or DEFAULT_COUNTRY,
    )
    contact_kwargs = {}
    if _should_split_billing_contact(
        scope,
        portal_contact_name,
        portal_contact_phone,
        portal_contact_title,
        billing_contact_name,
        billing_email,
        billing_phone,
        billing_title,
    ):
        contact_kwargs["exclude_contact_name"] = scope.portal_contact_name
    contact_name = public_quote_service.ensure_contact(
        scope.customer_name,
        scope.customer_display,
        billing_contact_name,
        billing_email,
        **contact_kwargs,
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
        payload.tax_id,
    )

    if clean(scope.portal_contact_name) and clean(scope.portal_contact_name) == clean(contact_name):
        public_quote_service.doc_db_set_values(
            "Contact",
            contact_name,
            _shared_contact_updates(
                portal_contact_name,
                portal_contact_phone,
                portal_contact_title,
                billing_contact_name,
                billing_phone,
                billing_title,
                address_name,
                clean(scope.portal_address_name),
            ),
        )
    elif clean(scope.portal_contact_name):
        public_quote_service.doc_db_set_values(
            "Contact",
            scope.portal_contact_name,
            _contact_updates(portal_contact_name, portal_contact_phone, portal_contact_title, clean(scope.portal_address_name)),
        )

    response = _build_billing_response(scope, _get_invoices(scope.customer_name))
    return PortalBillingUpdateResponse(
        **response.model_dump(mode="python"),
        status="updated",
        message="Billing details updated.",
    ).model_dump(mode="python")
