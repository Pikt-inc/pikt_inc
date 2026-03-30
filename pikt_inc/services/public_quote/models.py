from __future__ import annotations

from typing import Any, Literal

import frappe
from pydantic import BaseModel, ConfigDict, Field, model_validator


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _truthy(value: Any) -> bool:
    return _clean(value).lower() in {"1", "true", "yes", "on"}


def _form_value(form_data: Any, key: str) -> Any:
    getter = getattr(form_data, 'get', None)
    if callable(getter):
        return getter(key)
    return None


class QuoteModel(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    quote: str = ''
    token: str = ''


class AgreementSignatureInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    quote: str = ''
    token: str = ''
    signer_name: str = ''
    signer_title: str = ''
    signer_email: str = ''
    assent_confirmed: int = 0
    term_model: str = ''
    fixed_term_months: str = ''
    start_date: str = ''

    @classmethod
    def from_request(cls, quote: Any = None, token: Any = None, **kwargs: Any) -> 'AgreementSignatureInput':
        form_data = getattr(frappe, 'form_dict', {})
        return cls(
            quote=_clean(quote if quote is not None else kwargs.get('quote') or _form_value(form_data, 'quote')),
            token=_clean(token if token is not None else kwargs.get('token') or _form_value(form_data, 'token')),
            signer_name=_clean(kwargs.get('signer_name') or _form_value(form_data, 'signer_name')),
            signer_title=_clean(kwargs.get('signer_title') or _form_value(form_data, 'signer_title')),
            signer_email=_clean(kwargs.get('signer_email') or _form_value(form_data, 'signer_email')).lower(),
            assent_confirmed=1 if _truthy(kwargs.get('assent_confirmed') or _form_value(form_data, 'assent_confirmed')) else 0,
            term_model=_clean(kwargs.get('term_model') or _form_value(form_data, 'term_model')),
            fixed_term_months=_clean(kwargs.get('fixed_term_months') or _form_value(form_data, 'fixed_term_months')),
            start_date=_clean(kwargs.get('start_date') or _form_value(form_data, 'start_date')),
        )


class BillingSetupInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    quote: str = ''
    token: str = ''
    billing_contact_name: str = ''
    billing_email: str = ''
    billing_phone: str = ''
    billing_address_line_1: str = ''
    billing_address_line_2: str = ''
    billing_city: str = ''
    billing_state: str = ''
    billing_postal_code: str = ''
    billing_country: str = ''
    tax_id: str = ''

    @classmethod
    def from_request(cls, quote: Any = None, token: Any = None, **kwargs: Any) -> 'BillingSetupInput':
        form_data = getattr(frappe, 'form_dict', {})
        return cls(
            quote=_clean(quote if quote is not None else kwargs.get('quote') or _form_value(form_data, 'quote')),
            token=_clean(token if token is not None else kwargs.get('token') or _form_value(form_data, 'token')),
            billing_contact_name=_clean(kwargs.get('billing_contact_name') or _form_value(form_data, 'billing_contact_name')),
            billing_email=_clean(kwargs.get('billing_email') or _form_value(form_data, 'billing_email')).lower(),
            billing_phone=_clean(kwargs.get('billing_phone') or _form_value(form_data, 'billing_phone')),
            billing_address_line_1=_clean(kwargs.get('billing_address_line_1') or _form_value(form_data, 'billing_address_line_1')),
            billing_address_line_2=_clean(kwargs.get('billing_address_line_2') or _form_value(form_data, 'billing_address_line_2')),
            billing_city=_clean(kwargs.get('billing_city') or _form_value(form_data, 'billing_city')),
            billing_state=_clean(kwargs.get('billing_state') or _form_value(form_data, 'billing_state')),
            billing_postal_code=_clean(kwargs.get('billing_postal_code') or _form_value(form_data, 'billing_postal_code')),
            billing_country=_clean(kwargs.get('billing_country') or _form_value(form_data, 'billing_country')),
            tax_id=_clean(kwargs.get('tax_id') or _form_value(form_data, 'tax_id')),
        )


class AccessSetupInput(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    quote: str = ''
    token: str = ''
    service_address_line_1: str = ''
    service_address_line_2: str = ''
    service_city: str = ''
    service_state: str = ''
    service_postal_code: str = ''
    access_method: str = ''
    access_entrance: str = ''
    access_entry_details: str = ''
    has_alarm_system: str = 'No'
    alarm_instructions: str = ''
    allowed_entry_time: str = ''
    primary_site_contact: str = ''
    lockout_emergency_contact: str = ''
    key_fob_handoff_details: str = ''
    areas_to_avoid: str = ''
    closing_instructions: str = ''
    parking_elevator_notes: str = ''
    first_service_notes: str = ''
    access_details_confirmed: int = 0

    @classmethod
    def from_request(cls, quote: Any = None, token: Any = None, **kwargs: Any) -> 'AccessSetupInput':
        form_data = getattr(frappe, 'form_dict', {})
        return cls(
            quote=_clean(quote if quote is not None else kwargs.get('quote') or _form_value(form_data, 'quote')),
            token=_clean(token if token is not None else kwargs.get('token') or _form_value(form_data, 'token')),
            service_address_line_1=_clean(kwargs.get('service_address_line_1') or _form_value(form_data, 'service_address_line_1')),
            service_address_line_2=_clean(kwargs.get('service_address_line_2') or _form_value(form_data, 'service_address_line_2')),
            service_city=_clean(kwargs.get('service_city') or _form_value(form_data, 'service_city')),
            service_state=_clean(kwargs.get('service_state') or _form_value(form_data, 'service_state')),
            service_postal_code=_clean(kwargs.get('service_postal_code') or _form_value(form_data, 'service_postal_code')),
            access_method=_clean(kwargs.get('access_method') or _form_value(form_data, 'access_method')),
            access_entrance=_clean(kwargs.get('access_entrance') or _form_value(form_data, 'access_entrance')),
            access_entry_details=_clean(kwargs.get('access_entry_details') or _form_value(form_data, 'access_entry_details')),
            has_alarm_system=_clean(kwargs.get('has_alarm_system') or _form_value(form_data, 'has_alarm_system')) or 'No',
            alarm_instructions=_clean(kwargs.get('alarm_instructions') or _form_value(form_data, 'alarm_instructions')),
            allowed_entry_time=_clean(kwargs.get('allowed_entry_time') or _form_value(form_data, 'allowed_entry_time')),
            primary_site_contact=_clean(kwargs.get('primary_site_contact') or _form_value(form_data, 'primary_site_contact')),
            lockout_emergency_contact=_clean(kwargs.get('lockout_emergency_contact') or _form_value(form_data, 'lockout_emergency_contact')),
            key_fob_handoff_details=_clean(kwargs.get('key_fob_handoff_details') or _form_value(form_data, 'key_fob_handoff_details')),
            areas_to_avoid=_clean(kwargs.get('areas_to_avoid') or _form_value(form_data, 'areas_to_avoid')),
            closing_instructions=_clean(kwargs.get('closing_instructions') or _form_value(form_data, 'closing_instructions')),
            parking_elevator_notes=_clean(kwargs.get('parking_elevator_notes') or _form_value(form_data, 'parking_elevator_notes')),
            first_service_notes=_clean(kwargs.get('first_service_notes') or _form_value(form_data, 'first_service_notes')),
            access_details_confirmed=1 if _truthy(kwargs.get('access_details_confirmed') or _form_value(form_data, 'access_details_confirmed')) else 0,
        )


class ValidateQuotePayload(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    state: str
    message: str
    quote: str
    lead: str = ''
    company_name: str = ''
    contact_name: str = ''
    contact_email: str = ''
    currency: str = ''
    grand_total: Any = ''
    rounded_total: Any = ''
    transaction_date: Any = ''
    valid_till: Any = ''
    terms: str = ''
    sales_order: str = ''
    initial_invoice: str = ''
    billing_setup_completed_on: Any = ''
    billing_recipient_email: str = ''
    building: str = ''
    building_name: str = ''
    service_address_line_1: str = ''
    service_address_line_2: str = ''
    service_city: str = ''
    service_state: str = ''
    service_postal_code: str = ''
    access_method: str = ''
    access_entrance: str = ''
    access_entry_details: str = ''
    has_alarm_system: str = 'No'
    alarm_instructions: str = ''
    allowed_entry_time: str = ''
    primary_site_contact: str = ''
    lockout_emergency_contact: str = ''
    key_fob_handoff_details: str = ''
    areas_to_avoid: str = ''
    closing_instructions: str = ''
    parking_elevator_notes: str = ''
    first_service_notes: str = ''
    access_details_confirmed: int = 0
    access_details_completed_on: Any = ''
    items: list[dict[str, Any]] = Field(default_factory=list)


class AcceptPayload(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    status: str
    quote: str
    sales_order: str
    portal: dict[str, Any]


class AgreementPayload(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    agreement_mode: str
    agreement_step_complete: int
    billing_step_complete: int
    access_step_complete: int
    service_agreement: str = ''
    addendum: str = ''
    addendum_status: str = ''
    master_template: str = ''
    master_template_version: str = ''
    addendum_template: str = ''
    addendum_template_version: str = ''
    master_summary_title: str = ''
    master_summary_text: str = ''
    addendum_summary_title: str = ''
    addendum_summary_text: str = ''
    rendered_html: str = ''
    customer_name: str = ''
    term_label: str = ''
    start_date: Any = ''
    end_date: Any = ''
    fixed_term_months: str = ''
    term_model: str = ''
    signed_by_name: str = ''
    signed_by_email: str = ''
    signed_on: Any = ''


class PortalStateResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    state: str
    message: str
    quote: str
    sales_order: str = ''
    agreement: dict[str, Any]


class ServiceAgreementSignatureResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    status: Literal['ok']
    service_agreement: str
    addendum: str
    addendum_status: str
    start_date: Any = ''
    end_date: Any = ''
    term_model: str = ''
    fixed_term_months: str = ''


class BillingSetupResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    status: Literal['ok']
    quote: str
    sales_order: str
    invoice: str
    auto_repeat: str
    service_agreement: str
    addendum: str
    addendum_status: str


class AccessSetupResponse(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    status: Literal['ok']
    quote: str
    sales_order: str
    invoice: str
    building: str
    service_agreement: str
    addendum: str
    addendum_status: str
    access_completed_on: Any


class PublicQuoteSmokeConfig(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    cleanup: bool = True
    smoke_id: str = ''
    prospect_name: str = ''
    prospect_company: str = ''
    contact_email: str = ''
    phone: str = '5125550189'
    building_type: str = 'Office'
    building_size: int = 2500
    service_frequency: str = 'Weekly'
    service_interest: str = 'Recurring standard cleaning'
    bathroom_count_range: str = 'Light'
    quotation_item_code: str = ''
    quotation_item_qty: int = 1
    quotation_item_rate: float = 1250.0
    billing_contact_name: str = ''
    billing_email: str = ''
    billing_phone: str = '5125550189'
    billing_address_line_1: str = '500 Billing Test Way'
    billing_address_line_2: str = 'Suite 100'
    billing_city: str = 'Austin'
    billing_state: str = 'TX'
    billing_postal_code: str = '78701'
    billing_country: str = 'United States'
    tax_id: str = ''
    signer_name: str = ''
    signer_title: str = 'Operations Manager'
    signer_email: str = ''
    term_model: Literal['Month-to-month', 'Fixed'] = 'Month-to-month'
    fixed_term_months: str = ''
    start_date: str = ''
    service_address_line_1: str = '500 Service Test Way'
    service_address_line_2: str = 'Floor 2'
    service_city: str = 'Austin'
    service_state: str = 'TX'
    service_postal_code: str = '78701'
    access_method: str = 'Door code / keypad'
    access_entrance: str = 'Front entrance'
    access_entry_details: str = 'Code 1357'
    has_alarm_system: str = 'No'
    alarm_instructions: str = ''
    allowed_entry_time: str = 'After 6:00 PM'
    primary_site_contact: str = 'Site Lead - 512-555-0100'
    lockout_emergency_contact: str = 'Lockout Line - 512-555-0101'
    key_fob_handoff_details: str = ''
    areas_to_avoid: str = ''
    closing_instructions: str = 'Lock the front entrance after service.'
    parking_elevator_notes: str = 'Use visitor parking in the south lot.'
    first_service_notes: str = 'Confirm consumables closet location with site contact.'

    @model_validator(mode='after')
    def validate_fields(self) -> 'PublicQuoteSmokeConfig':
        if self.building_size <= 0:
            raise ValueError('building_size must be greater than 0')
        if self.quotation_item_qty <= 0:
            raise ValueError('quotation_item_qty must be greater than 0')
        if self.quotation_item_rate <= 0:
            raise ValueError('quotation_item_rate must be greater than 0')
        if self.term_model == 'Fixed' and self.fixed_term_months not in {'3', '6', '12'}:
            raise ValueError('fixed_term_months must be 3, 6, or 12 for a fixed-term smoke test')
        return self


class PublicQuoteSmokeArtifacts(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    request: str = ''
    lead: str = ''
    opportunity: str = ''
    quote: str = ''
    token: str = ''
    customer: str = ''
    sales_order: str = ''
    invoice: str = ''
    auto_repeat: str = ''
    building: str = ''
    service_agreement: str = ''
    addendum: str = ''
    contact: str = ''
    address: str = ''


class PublicQuoteSmokeResult(BaseModel):
    model_config = ConfigDict(extra='forbid', frozen=True)

    status: Literal['ok']
    cleanup_performed: bool
    artifacts: PublicQuoteSmokeArtifacts
    validation: dict[str, Any]
    accept: dict[str, Any]
    portal_state: dict[str, Any]
    agreement: dict[str, Any]
    billing: dict[str, Any]
    billing_retry: dict[str, Any]
    access: dict[str, Any]
    access_retry: dict[str, Any]
    cleanup_result: dict[str, list[str] | list[dict[str, str]] | str] = Field(default_factory=dict)


__all__ = [
    'AccessSetupInput',
    'AccessSetupResponse',
    'AcceptPayload',
    'AgreementPayload',
    'AgreementSignatureInput',
    'BillingSetupInput',
    'BillingSetupResponse',
    'PortalStateResponse',
    'PublicQuoteSmokeArtifacts',
    'PublicQuoteSmokeConfig',
    'PublicQuoteSmokeResult',
    'QuoteModel',
    'ServiceAgreementSignatureResponse',
    'ValidateQuotePayload',
]
