from __future__ import annotations

from .payloads import _build_dashboard_response, _portal_access_error_response
from .queries import _get_agreements, _get_buildings, _get_invoices
from .scope import PortalAccessError, _resolve_portal_scope_or_error


def get_customer_portal_dashboard_data() -> dict:
    try:
        scope = _resolve_portal_scope_or_error()
    except PortalAccessError as exc:
        return _portal_access_error_response("overview", exc)

    agreements, addenda = _get_agreements(scope.customer_name)
    invoices = _get_invoices(scope.customer_name)
    buildings = _get_buildings(scope.customer_name)
    return _build_dashboard_response(scope, agreements, addenda, invoices, buildings).model_dump(mode="python")
