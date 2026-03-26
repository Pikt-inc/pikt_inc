from __future__ import annotations

from typing import Any

import frappe
from frappe.utils import add_to_date, now_datetime, nowdate

from pikt_inc.services import public_intake as public_intake_service

from .acceptance import accept_public_quote
from .access_setup import complete_public_quote_access_setup_v2
from .agreements import complete_public_service_agreement_signature
from .billing import complete_public_quote_billing_setup_v2
from .constants import DEFAULT_COMPANY, DEFAULT_CURRENCY, DEFAULT_PRICE_LIST
from .exceptions import PublicQuoteWorkflowError
from .models import (
    AccessSetupInput,
    AgreementSignatureInput,
    BillingSetupInput,
    PublicQuoteSmokeArtifacts,
    PublicQuoteSmokeConfig,
    PublicQuoteSmokeResult,
)
from .portal import load_public_quote_portal_state, validate_public_quote
from .queries import get_customer_row, get_quote_row, get_sales_order_row
from .shared import clean, doc_db_set_values


def resolve_public_quote_smoke_config(**kwargs: Any) -> PublicQuoteSmokeConfig:
    smoke_id = clean(kwargs.get("smoke_id")) or now_datetime().strftime("%Y%m%d%H%M%S")
    defaults = {
        "smoke_id": smoke_id,
        "prospect_name": kwargs.get("prospect_name") or f"QA Portal Smoke {smoke_id}",
        "prospect_company": kwargs.get("prospect_company") or f"QA Portal Smoke Customer {smoke_id}",
        "contact_email": kwargs.get("contact_email") or f"qa.portal.smoke.{smoke_id}@example.com",
        "billing_contact_name": kwargs.get("billing_contact_name") or kwargs.get("prospect_name") or f"QA Portal Smoke {smoke_id}",
        "billing_email": kwargs.get("billing_email") or f"billing.portal.smoke.{smoke_id}@example.com",
        "signer_name": kwargs.get("signer_name") or kwargs.get("prospect_name") or f"QA Portal Smoke {smoke_id}",
        "signer_email": kwargs.get("signer_email") or kwargs.get("contact_email") or f"qa.portal.smoke.{smoke_id}@example.com",
        "start_date": kwargs.get("start_date") or nowdate(),
    }
    payload = {**kwargs, **{key: value for key, value in defaults.items() if not clean(kwargs.get(key))}}
    return PublicQuoteSmokeConfig(**payload)


def discover_public_quote_smoke_item(config: PublicQuoteSmokeConfig) -> dict[str, Any]:
    explicit_item = clean(config.quotation_item_code)
    if explicit_item:
        item_row = frappe.db.get_value(
            "Item",
            explicit_item,
            ["name", "item_code", "item_name", "description", "stock_uom"],
            as_dict=True,
        )
        if item_row:
            return item_row
        raise PublicQuoteWorkflowError(
            "The configured smoke-test item could not be found. Provide a valid quotation_item_code and try again.",
            log_title="Public Quote Smoke - Missing Configured Item",
            internal_message="Configured smoke-test item was not found.",
            context={"item_code": explicit_item},
        )

    rows = frappe.get_all(
        "Item",
        filters={"disabled": 0, "has_variants": 0, "is_sales_item": 1},
        fields=["name", "item_code", "item_name", "description", "stock_uom", "is_stock_item"],
        order_by="is_stock_item asc, modified desc",
        limit=20,
    )
    for row in rows:
        item_code = clean(row.get("item_code")) or clean(row.get("name"))
        if item_code:
            return row

    raise PublicQuoteWorkflowError(
        "A sales item is required to run the quote smoke test. Provide quotation_item_code explicitly and try again.",
        log_title="Public Quote Smoke - No Sales Item",
        internal_message="No candidate sales item found for smoke-test quotation creation.",
    )


def create_public_quote_smoke_quotation(
    config: PublicQuoteSmokeConfig,
    opportunity_name: str,
    lead_name: str,
) -> tuple[str, str]:
    item_row = discover_public_quote_smoke_item(config)
    item_code = clean(item_row.get("item_code")) or clean(item_row.get("name"))
    stock_uom = clean(item_row.get("stock_uom")) or "Nos"

    quote_doc = frappe.get_doc(
        {
            "doctype": "Quotation",
            "naming_series": "SAL-QTN-.YYYY.-",
            "quotation_to": "Lead",
            "party_name": clean(lead_name),
            "customer_name": clean(config.prospect_company),
            "contact_email": clean(config.contact_email).lower(),
            "company": DEFAULT_COMPANY,
            "transaction_date": nowdate(),
            "valid_till": add_to_date(nowdate(), days=30),
            "currency": DEFAULT_CURRENCY,
            "conversion_rate": 1,
            "selling_price_list": DEFAULT_PRICE_LIST,
            "price_list_currency": DEFAULT_CURRENCY,
            "plc_conversion_rate": 1,
            "order_type": "Sales",
            "opportunity": clean(opportunity_name),
            "items": [
                {
                    "item_code": item_code,
                    "qty": config.quotation_item_qty,
                    "rate": config.quotation_item_rate,
                    "uom": stock_uom,
                    "stock_uom": stock_uom,
                    "conversion_factor": 1,
                    "description": clean(item_row.get("description")) or clean(item_row.get("item_name")) or item_code,
                }
            ],
        }
    )
    quote_doc.insert(ignore_permissions=True)
    if int(quote_doc.docstatus or 0) == 0:
        quote_doc.submit()

    quote_row = get_quote_row(quote_doc.name)
    token = clean(quote_row.get("custom_accept_token"))
    if token:
        return quote_doc.name, token

    raise PublicQuoteWorkflowError(
        "The smoke-test quotation did not receive a public token. Check quotation hooks and try again.",
        log_title="Public Quote Smoke - Missing Token",
        internal_message="Submitted smoke-test quotation is missing custom_accept_token.",
        context={"quotation": quote_doc.name},
    )


def create_public_quote_smoke_artifacts(config: PublicQuoteSmokeConfig) -> PublicQuoteSmokeArtifacts:
    intake_result = public_intake_service.create_instant_quote_opportunity(
        form_dict={
            "prospect_name": config.prospect_name,
            "phone": config.phone,
            "contact_email": config.contact_email,
            "prospect_company": config.prospect_company,
            "building_type": config.building_type,
            "building_size": str(config.building_size),
            "service_frequency": config.service_frequency,
            "service_interest": config.service_interest,
            "bathroom_count_range": config.bathroom_count_range,
        }
    )
    opportunity_name = clean(intake_result.get("opp") or intake_result.get("name"))
    lead_name = clean(frappe.db.get_value("Opportunity", opportunity_name, "party_name"))
    if not opportunity_name or not lead_name:
        raise PublicQuoteWorkflowError(
            "The smoke-test opportunity could not be prepared. Check the public intake flow and try again.",
            log_title="Public Quote Smoke - Missing Intake Records",
            internal_message="Smoke-test intake did not create an opportunity/lead pair.",
            context={"opportunity": opportunity_name or "(blank)", "lead": lead_name or "(blank)"},
        )

    quote_name, token = create_public_quote_smoke_quotation(config, opportunity_name, lead_name)
    return PublicQuoteSmokeArtifacts(
        lead=lead_name,
        opportunity=opportunity_name,
        quote=quote_name,
        token=token,
    )


def delete_public_quote_smoke_doc(
    doctype: str,
    name: str,
    *,
    cancel_first: bool = False,
) -> tuple[str, str]:
    record_name = clean(name)
    if not record_name:
        return "missing", ""
    if not frappe.db.exists(doctype, record_name):
        return "missing", record_name

    doc = frappe.get_doc(doctype, record_name)
    if cancel_first and int(doc.docstatus or 0) == 1:
        doc.flags.ignore_permissions = True
        doc.cancel()
    frappe.delete_doc(doctype, record_name, force=1, ignore_permissions=True)
    return "deleted", record_name


def set_public_quote_smoke_backlinks(
    doctype: str,
    name: str,
    values: dict[str, Any],
) -> None:
    record_name = clean(name)
    if not record_name or not frappe.db.exists(doctype, record_name):
        return

    meta = frappe.get_meta(doctype)
    available_fields = {df.fieldname for df in meta.fields}
    filtered_values = {
        fieldname: value for fieldname, value in (values or {}).items() if fieldname in available_fields
    }
    if filtered_values:
        doc_db_set_values(doctype, record_name, filtered_values)


def cleanup_public_quote_smoke_records(
    artifacts: PublicQuoteSmokeArtifacts | dict[str, Any] | None = None,
) -> dict[str, list[str] | list[dict[str, str]]]:
    artifact_model = (
        artifacts
        if isinstance(artifacts, PublicQuoteSmokeArtifacts)
        else PublicQuoteSmokeArtifacts(**(artifacts or {}))
    )
    deleted: list[str] = []
    missing: list[str] = []
    errors: list[dict[str, str]] = []

    set_public_quote_smoke_backlinks(
        "Sales Order",
        artifact_model.sales_order,
        {
            "custom_service_agreement": "",
            "custom_service_agreement_addendum": "",
            "custom_building": "",
        },
    )
    set_public_quote_smoke_backlinks(
        "Quotation",
        artifact_model.quote,
        {
            "custom_accepted_sales_order": "",
            "custom_building": "",
        },
    )
    set_public_quote_smoke_backlinks(
        "Opportunity",
        artifact_model.opportunity,
        {
            "custom_quotation": "",
            "custom_building": "",
        },
    )

    order = [
        ("Auto Repeat", artifact_model.auto_repeat, False),
        ("Sales Invoice", artifact_model.invoice, True),
        ("Service Agreement Addendum", artifact_model.addendum, False),
        ("Service Agreement", artifact_model.service_agreement, False),
        ("Building", artifact_model.building, False),
        ("Sales Order", artifact_model.sales_order, True),
        ("Quotation", artifact_model.quote, True),
        ("Address", artifact_model.address, False),
        ("Contact", artifact_model.contact, False),
        ("Customer", artifact_model.customer, False),
        ("Opportunity", artifact_model.opportunity, False),
        ("Lead", artifact_model.lead, False),
    ]

    for doctype, name, cancel_first in order:
        record_name = clean(name)
        if not record_name:
            continue
        try:
            status, resolved_name = delete_public_quote_smoke_doc(
                doctype,
                record_name,
                cancel_first=cancel_first,
            )
        except Exception as exc:
            frappe.db.rollback()
            errors.append({"record": f"{doctype}/{record_name}", "error": str(exc)})
            continue
        frappe.db.commit()
        if status == "deleted":
            deleted.append(f"{doctype}/{resolved_name}")
        elif status == "missing":
            missing.append(f"{doctype}/{resolved_name}")

    return {"deleted": deleted, "missing": missing, "errors": errors}


def run_public_quote_smoke_test(**kwargs: Any) -> dict[str, Any]:
    config = resolve_public_quote_smoke_config(**kwargs)
    artifacts = PublicQuoteSmokeArtifacts()
    cleanup_result: dict[str, list[str] | list[dict[str, str]]] = {"deleted": [], "missing": [], "errors": []}

    try:
        artifacts = create_public_quote_smoke_artifacts(config)

        validation = validate_public_quote(quote=artifacts.quote, token=artifacts.token)
        accept_response = accept_public_quote(quote=artifacts.quote, token=artifacts.token)
        portal_state = load_public_quote_portal_state(quote=artifacts.quote, token=artifacts.token)

        sales_order_name = clean(accept_response.get("sales_order"))
        sales_order_row = get_sales_order_row(sales_order_name)
        customer_name = clean(sales_order_row.get("customer"))
        artifacts = artifacts.model_copy(
            update={
                "sales_order": sales_order_name,
                "customer": customer_name,
            }
        )

        agreement_payload = AgreementSignatureInput(
            quote=artifacts.quote,
            token=artifacts.token,
            signer_name=config.signer_name,
            signer_title=config.signer_title,
            signer_email=config.signer_email.lower(),
            assent_confirmed=1,
            term_model=config.term_model,
            fixed_term_months=config.fixed_term_months,
            start_date=config.start_date,
        )
        agreement_response = complete_public_service_agreement_signature(**agreement_payload.model_dump())

        billing_payload = BillingSetupInput(
            quote=artifacts.quote,
            token=artifacts.token,
            billing_contact_name=config.billing_contact_name,
            billing_email=config.billing_email.lower(),
            billing_phone=config.billing_phone,
            billing_address_line_1=config.billing_address_line_1,
            billing_address_line_2=config.billing_address_line_2,
            billing_city=config.billing_city,
            billing_state=config.billing_state,
            billing_postal_code=config.billing_postal_code,
            billing_country=config.billing_country,
            tax_id=config.tax_id,
        )
        billing_response = complete_public_quote_billing_setup_v2(**billing_payload.model_dump())
        billing_retry_response = complete_public_quote_billing_setup_v2(**billing_payload.model_dump())

        customer_row = get_customer_row(customer_name)
        artifacts = artifacts.model_copy(
            update={
                "invoice": clean(billing_response.get("invoice")),
                "auto_repeat": clean(billing_response.get("auto_repeat")),
                "service_agreement": clean(billing_response.get("service_agreement")),
                "addendum": clean(billing_response.get("addendum")),
                "contact": clean(customer_row.get("customer_primary_contact")),
                "address": clean(customer_row.get("customer_primary_address")),
            }
        )

        access_payload = AccessSetupInput(
            quote=artifacts.quote,
            token=artifacts.token,
            service_address_line_1=config.service_address_line_1,
            service_address_line_2=config.service_address_line_2,
            service_city=config.service_city,
            service_state=config.service_state,
            service_postal_code=config.service_postal_code,
            access_method=config.access_method,
            access_entrance=config.access_entrance,
            access_entry_details=config.access_entry_details,
            has_alarm_system=config.has_alarm_system,
            alarm_instructions=config.alarm_instructions,
            allowed_entry_time=config.allowed_entry_time,
            primary_site_contact=config.primary_site_contact,
            lockout_emergency_contact=config.lockout_emergency_contact,
            key_fob_handoff_details=config.key_fob_handoff_details,
            areas_to_avoid=config.areas_to_avoid,
            closing_instructions=config.closing_instructions,
            parking_elevator_notes=config.parking_elevator_notes,
            first_service_notes=config.first_service_notes,
            access_details_confirmed=1,
        )
        access_response = complete_public_quote_access_setup_v2(**access_payload.model_dump())
        access_retry_response = complete_public_quote_access_setup_v2(**access_payload.model_dump())

        artifacts = artifacts.model_copy(update={"building": clean(access_response.get("building"))})

        if config.cleanup:
            cleanup_result = cleanup_public_quote_smoke_records(artifacts)

        return PublicQuoteSmokeResult(
            status="ok",
            cleanup_performed=config.cleanup,
            artifacts=artifacts,
            validation=validation,
            accept=accept_response,
            portal_state=portal_state,
            agreement=agreement_response,
            billing=billing_response,
            billing_retry=billing_retry_response,
            access=access_response,
            access_retry=access_retry_response,
            cleanup_result=cleanup_result,
        ).model_dump()
    except Exception as exc:
        if config.cleanup:
            cleanup_result = cleanup_public_quote_smoke_records(artifacts)
        raise RuntimeError(
            "Public quote smoke test failed: "
            f"{exc}. Cleanup deleted={len(cleanup_result.get('deleted', []))}, "
            f"errors={len(cleanup_result.get('errors', []))}."
        )


__all__ = [
    "resolve_public_quote_smoke_config",
    "discover_public_quote_smoke_item",
    "create_public_quote_smoke_quotation",
    "create_public_quote_smoke_artifacts",
    "delete_public_quote_smoke_doc",
    "set_public_quote_smoke_backlinks",
    "cleanup_public_quote_smoke_records",
    "run_public_quote_smoke_test",
]
