from __future__ import annotations

from .. import public_quote as public_quote_service
from ..contracts.customer_portal import LOCATION_ACCESS_METHOD_OPTIONS, LOCATION_ALARM_OPTIONS


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
    "billing_info": "Billing Information",
    "locations": "Locations",
}
PORTAL_PAGE_PATHS = {
    "overview": PORTAL_HOME_PATH,
    "agreements": "/portal/agreements",
    "billing": "/portal/billing",
    "billing_info": "/portal/billing-info",
    "locations": "/portal/locations",
}
PORTAL_NAV_KEYS = ("overview", "agreements", "billing", "locations")
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
