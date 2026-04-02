from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, Field, field_validator

from ..contracts.common import RequestModel, ResponseModel, clean_str


StepCategory = Literal["access", "job_completion", "rearm_security"]
JobStatus = Literal["in_progress", "completed"]


class CustomerPortalContext(ResponseModel):
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


class ClientOverviewRequest(RequestModel):
    pass


class ClientBuildingRequest(RequestModel):
    building_id: str = Field(validation_alias=AliasChoices("building_id", "building"), min_length=1)

    @field_validator("building_id", mode="before")
    @classmethod
    def clean_building_id(cls, value: Any) -> str:
        return clean_str(value)


class ClientJobRequest(RequestModel):
    session_id: str = Field(validation_alias=AliasChoices("session_id", "session"), min_length=1)

    @field_validator("session_id", mode="before")
    @classmethod
    def clean_session_id(cls, value: Any) -> str:
        return clean_str(value)


class ClientJobProofRequest(RequestModel):
    session_id: str = Field(validation_alias=AliasChoices("session_id", "session"), min_length=1)
    item_key: str = Field(min_length=1)

    @field_validator("session_id", "item_key", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)


class ClientBuildingSummary(ResponseModel):
    id: str
    name: str
    address: str | None
    notes: str | None
    active: bool
    current_checklist_template_id: str | None
    created_at: str
    updated_at: str


class ClientSessionItem(ResponseModel):
    id: str
    job_session_id: str | None
    item_key: str
    category: StepCategory
    step_order: int
    title: str
    description: str | None
    requires_image: bool
    allow_notes: bool
    is_required: bool
    completed: bool
    completed_at: str | None
    proof_image: str | None
    note: str | None


class ClientSessionSummary(ResponseModel):
    id: str
    building_id: str
    checklist_template_id: str
    service_date: str
    started_at: str
    completed_at: str | None
    worker: str | None
    session_notes: str | None
    status: JobStatus
    items: list[ClientSessionItem] = Field(default_factory=list)


class ClientOverviewResponse(ResponseModel):
    buildings: list[ClientBuildingSummary]
    completed_sessions: list[ClientSessionSummary]


class ClientBuildingResponse(ResponseModel):
    building: ClientBuildingSummary
    completed_sessions: list[ClientSessionSummary]


class ClientJobResponse(ResponseModel):
    building: ClientBuildingSummary
    session: ClientSessionSummary


class FileDownload(ResponseModel):
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    as_attachment: bool = False
