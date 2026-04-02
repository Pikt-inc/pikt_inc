from __future__ import annotations

import frappe

from .. import public_quote as public_quote_service
from . import agreements, billing, checklist, dashboard, downloads, locations, payloads
from .agreements import get_customer_portal_agreements_data
from .billing import get_customer_portal_billing_data, update_customer_portal_billing
from .checklist import (
    download_customer_portal_client_job_proof,
    get_customer_portal_client_building,
    get_customer_portal_client_job,
    get_customer_portal_client_overview,
)
from .dashboard import get_customer_portal_dashboard_data
from .downloads import (
    download_customer_portal_agreement_snapshot,
    download_customer_portal_checklist_proof,
    download_customer_portal_invoice,
    render_invoice_pdf,
)
from .locations import (
    get_customer_portal_locations_data,
    update_customer_portal_building_sop,
    update_customer_portal_location,
)
from .scope import PortalAccessError, PortalScope

__all__ = [
    "PortalAccessError",
    "PortalScope",
    "agreements",
    "billing",
    "checklist",
    "dashboard",
    "downloads",
    "frappe",
    "get_customer_portal_agreements_data",
    "get_customer_portal_billing_data",
    "get_customer_portal_client_building",
    "get_customer_portal_client_job",
    "get_customer_portal_client_overview",
    "get_customer_portal_dashboard_data",
    "get_customer_portal_locations_data",
    "locations",
    "payloads",
    "public_quote_service",
    "render_invoice_pdf",
    "download_customer_portal_agreement_snapshot",
    "download_customer_portal_checklist_proof",
    "download_customer_portal_client_job_proof",
    "download_customer_portal_invoice",
    "update_customer_portal_billing",
    "update_customer_portal_building_sop",
    "update_customer_portal_location",
]
