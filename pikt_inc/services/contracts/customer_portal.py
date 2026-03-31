from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator, model_validator

from .common import RequestModel, ResponseModel, clean_optional_str, clean_str, looks_like_email, normalize_email, truthy


DEFAULT_COUNTRY = "United States"


class PortalPageKey(str, Enum):
    OVERVIEW = "overview"
    AGREEMENTS = "agreements"
    BILLING = "billing"
    BILLING_INFO = "billing_info"
    LOCATIONS = "locations"


class LocationAccessMethod(str, Enum):
    DOOR_CODE = "Door code / keypad"
    LOCKBOX = "Lockbox"
    FRONT_DESK = "Front desk / building management"
    PHYSICAL_KEY = "Physical key or fob"
    STAFF_LET_IN = "Staff will let us in"
    OTHER = "Other"


class AlarmSystemValue(str, Enum):
    NO = "No"
    YES = "Yes"


LOCATION_ACCESS_METHOD_OPTIONS = tuple(item.value for item in LocationAccessMethod)
LOCATION_ALARM_OPTIONS = tuple(item.value for item in AlarmSystemValue)


class PortalMetaTags(ResponseModel):
    title: str
    description: str
    canonical: str


class PortalNavItem(ResponseModel):
    key: str
    label: str
    url: str
    is_active: bool


class PortalSummaryCard(ResponseModel):
    label: str
    value: str
    meta: str


class PortalRecentActivityItem(ResponseModel):
    label: str
    meta: str
    timestamp: str


class PortalContactDetails(ResponseModel):
    name: str
    display_name: str
    email: str
    phone: str
    designation: str


class PortalBillingAddress(ResponseModel):
    name: str
    address_line_1: str
    address_line_2: str
    city: str
    state: str
    postal_code: str
    country: str


class PortalAgreementMaster(ResponseModel):
    name: str
    title: str
    status: str
    template: str
    template_version: str
    signed_by_name: str
    signed_on_label: str
    download_url: str
    preview_html: str


class PortalAgreementAddendum(ResponseModel):
    name: str
    title: str
    document_title: str
    location_address: str
    status: str
    term_model: str
    fixed_term_months: str
    start_date_label: str
    end_date_label: str
    signed_by_name: str
    signed_on_label: str
    billing_completed_on_label: str
    access_completed_on_label: str
    quotation: str
    sales_order: str
    invoice: str
    building: str
    download_url: str
    preview_html: str
    is_active: bool


class PortalInvoiceRow(ResponseModel):
    name: str
    posting_date_label: str
    due_date_label: str
    status: str
    grand_total_label: str
    outstanding_label: str
    outstanding_amount: float
    currency: str
    building: str
    download_url: str
    is_unpaid: bool


class PortalLocationFields(ResponseModel):
    site_supervisor_name: Any = None
    site_supervisor_phone: Any = None
    site_notes: Any = None
    primary_site_contact: Any = None
    lockout_emergency_contact: Any = None
    access_method: Any = None
    access_entrance: Any = None
    access_entry_details: Any = None
    access_notes: Any = None
    alarm_notes: Any = None
    has_alarm_system: Any = None
    alarm_instructions: Any = None
    allowed_entry_time: Any = None
    key_fob_handoff_details: Any = None
    areas_to_avoid: Any = None
    closing_instructions: Any = None
    parking_elevator_notes: Any = None
    first_service_notes: Any = None
    access_details_confirmed: Any = None


class PortalLocationRow(ResponseModel):
    name: str
    title: str
    detail_url: str
    full_address: str
    active_label: str
    agreement_status_label: str
    active: bool
    modified_label: str
    fields: PortalLocationFields


class PortalLocationFormOptions(ResponseModel):
    access_methods: list[str]
    alarm_system: list[str]


class PortalChecklistProof(ResponseModel):
    name: str
    label: str
    url: str


class PortalChecklistItem(ResponseModel):
    item_id: str
    title: str
    description: str
    requires_photo_proof: bool = False
    active: bool = True
    sort_order: int = 0
    status: str = ""
    exception_note: str = ""
    proofs: list[PortalChecklistProof] = Field(default_factory=list)


class PortalBuildingSopVersion(ResponseModel):
    name: str
    version_number: int
    updated_label: str
    updated_by: str
    item_count: int


class PortalServiceHistoryRow(ResponseModel):
    name: str
    service_date_label: str
    arrival_window_label: str
    status: str
    employee_label: str
    sop_version_label: str
    has_checklist: bool = False
    checklist_items: list[PortalChecklistItem] = Field(default_factory=list)


class PortalPageResponse(ResponseModel):
    page_key: str
    page_title: str
    portal_title: str
    portal_description: str
    portal_nav: list[PortalNavItem]
    portal_contact_path: str
    metatags: PortalMetaTags
    access_denied: bool = False
    error_message: str = ""
    error_title: str = ""
    empty_state_title: str = ""
    empty_state_copy: str = ""
    customer_display: str = ""
    http_status_code: int = 200
    login_path: str = ""
    redirect_to: str = ""


class PortalDashboardResponse(PortalPageResponse):
    summary_cards: list[PortalSummaryCard] = Field(default_factory=list)
    active_master: PortalAgreementMaster | None = None
    latest_invoices: list[PortalInvoiceRow] = Field(default_factory=list)
    latest_locations: list[PortalLocationRow] = Field(default_factory=list)
    recent_activity: list[PortalRecentActivityItem] = Field(default_factory=list)


class PortalAgreementsResponse(PortalPageResponse):
    active_master: PortalAgreementMaster | None = None
    addenda: list[PortalAgreementAddendum] = Field(default_factory=list)


class PortalBillingResponse(PortalPageResponse):
    portal_contact: PortalContactDetails | None = None
    billing_contact: PortalContactDetails | None = None
    billing_address: PortalBillingAddress | None = None
    tax_id: str = ""
    invoices: list[PortalInvoiceRow] = Field(default_factory=list)
    unpaid_total_label: str = ""


class PortalBillingUpdateResponse(PortalBillingResponse):
    status: Literal["updated"]
    message: str


class PortalLocationsResponse(PortalPageResponse):
    buildings: list[PortalLocationRow] = Field(default_factory=list)
    selected_building: PortalLocationRow | None = None
    location_form_options: PortalLocationFormOptions
    selected_building_sop: PortalBuildingSopVersion | None = None
    selected_building_checklist: list[PortalChecklistItem] = Field(default_factory=list)
    service_history: list[PortalServiceHistoryRow] = Field(default_factory=list)
    service_history_page: int = 1
    service_history_has_more: bool = False
    service_history_next_url: str = ""


class PortalLocationsUpdateResponse(PortalLocationsResponse):
    status: Literal["updated"]
    message: str


class PortalBuildingSopUpdateResponse(PortalLocationsResponse):
    status: Literal["updated"]
    message: str


class CustomerPortalBillingInput(RequestModel):
    portal_contact_name: str = ""
    portal_contact_phone: str = ""
    portal_contact_title: str = ""
    billing_contact_name: str = ""
    billing_email: str = ""
    billing_contact_phone: str = ""
    billing_contact_title: str = ""
    billing_address_line_1: str = Field(min_length=1)
    billing_address_line_2: str = ""
    billing_city: str = Field(min_length=1)
    billing_state: str = Field(min_length=1)
    billing_postal_code: str = Field(min_length=1)
    billing_country: str = DEFAULT_COUNTRY
    tax_id: str = ""

    @field_validator(
        "portal_contact_name",
        "portal_contact_phone",
        "portal_contact_title",
        "billing_contact_name",
        "billing_email",
        "billing_contact_phone",
        "billing_contact_title",
        "billing_address_line_1",
        "billing_address_line_2",
        "billing_city",
        "billing_state",
        "billing_postal_code",
        "billing_country",
        "tax_id",
        mode="before",
    )
    @classmethod
    def clean_strings(cls, value: Any) -> str:
        return clean_str(value)

    @field_validator("billing_email")
    @classmethod
    def normalize_email_field(cls, value: str) -> str:
        normalized = normalize_email(value)
        if normalized and not looks_like_email(normalized):
            raise ValueError("Value is not a valid email address.")
        return normalized


class CustomerPortalLocationUpdateInput(RequestModel):
    building_name: str = Field(validation_alias=AliasChoices("building_name", "building"), min_length=1)
    site_supervisor_name: str | None = None
    site_supervisor_phone: str | None = None
    site_notes: str | None = None
    primary_site_contact: str | None = None
    lockout_emergency_contact: str | None = None
    access_method: str | None = None
    access_entrance: str | None = None
    access_entry_details: str | None = None
    access_notes: str | None = None
    alarm_notes: str | None = None
    has_alarm_system: str | None = None
    alarm_instructions: str | None = None
    allowed_entry_time: str | None = None
    key_fob_handoff_details: str | None = None
    areas_to_avoid: str | None = None
    closing_instructions: str | None = None
    parking_elevator_notes: str | None = None
    first_service_notes: str | None = None
    access_details_confirmed: bool | None = None

    @field_validator(
        "building_name",
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
        mode="before",
    )
    @classmethod
    def clean_optional_strings(cls, value: Any) -> str | None:
        return clean_optional_str(value)

    @field_validator("access_details_confirmed", mode="before")
    @classmethod
    def normalize_access_details_confirmed(cls, value: Any) -> bool | None:
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return value
        return truthy(value)

    @field_validator("access_method")
    @classmethod
    def validate_access_method(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        if value not in LOCATION_ACCESS_METHOD_OPTIONS:
            raise ValueError("Input should be a valid access method.")
        return value

    @field_validator("has_alarm_system")
    @classmethod
    def validate_alarm_value(cls, value: str | None) -> str | None:
        if value is None or value == "":
            return value
        if value not in LOCATION_ALARM_OPTIONS:
            raise ValueError("Input should be a valid alarm system value.")
        return value

    @model_validator(mode="after")
    def validate_shape(self):
        if not self.updates():
            raise ValueError("No location updates were provided.")
        return self

    def updates(self) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        for fieldname in self.model_fields_set:
            if fieldname == "building_name":
                continue
            updates[fieldname] = getattr(self, fieldname)
        return updates


class CustomerPortalBuildingSopItemInput(RequestModel):
    item_id: str = ""
    title: str = Field(min_length=1)
    description: str = ""
    requires_photo_proof: bool = False

    @field_validator("item_id", "title", "description", mode="before")
    @classmethod
    def clean_item_values(cls, value: Any) -> str:
        return clean_str(value)

    @field_validator("requires_photo_proof", mode="before")
    @classmethod
    def normalize_requires_photo_proof(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return truthy(value)


class CustomerPortalBuildingSopUpdateInput(RequestModel):
    building_name: str = Field(validation_alias=AliasChoices("building_name", "building"), min_length=1)
    items: list[CustomerPortalBuildingSopItemInput] = Field(default_factory=list)

    @field_validator("building_name", mode="before")
    @classmethod
    def clean_building_name(cls, value: Any) -> str:
        return clean_str(value)


class PortalInvoiceDownloadInput(RequestModel):
    invoice: str = Field(min_length=1)

    @field_validator("invoice", mode="before")
    @classmethod
    def clean_invoice(cls, value: Any) -> str:
        return clean_str(value)


class PortalAgreementDownloadInput(RequestModel):
    addendum: str = ""
    agreement: str = ""

    @field_validator("addendum", "agreement", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)

    @model_validator(mode="after")
    def validate_identifier(self):
        if not self.addendum and not self.agreement:
            raise ValueError("Either addendum or agreement is required.")
        return self


class PortalChecklistProofDownloadInput(RequestModel):
    proof: str = Field(min_length=1)

    @field_validator("proof", mode="before")
    @classmethod
    def clean_proof(cls, value: Any) -> str:
        return clean_str(value)
