from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field, field_validator

from ..services.contracts.common import RequestModel, ResponseModel, clean_str
from ..services.customer_portal.checklist.models import JobStatus, StepCategory


class CustomerPortalClientOverviewRequestApi(RequestModel):
    pass


class CustomerPortalClientBuildingRequestApi(RequestModel):
    building_id: str = Field(validation_alias=AliasChoices("building_id", "building"), min_length=1)

    @field_validator("building_id", mode="before")
    @classmethod
    def clean_building_id(cls, value: Any) -> str:
        return clean_str(value)


class CustomerPortalClientJobRequestApi(RequestModel):
    session_id: str = Field(validation_alias=AliasChoices("session_id", "session"), min_length=1)

    @field_validator("session_id", mode="before")
    @classmethod
    def clean_session_id(cls, value: Any) -> str:
        return clean_str(value)


class CustomerPortalClientJobProofRequestApi(RequestModel):
    session_id: str = Field(validation_alias=AliasChoices("session_id", "session"), min_length=1)
    item_key: str = Field(min_length=1)

    @field_validator("session_id", "item_key", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)


class CustomerPortalClientBuildingSummaryPayload(ResponseModel):
    id: str
    name: str
    address: str | None
    notes: str | None
    active: bool
    current_checklist_template_id: str | None
    created_at: str
    updated_at: str


class CustomerPortalClientSessionItemPayload(ResponseModel):
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


class CustomerPortalClientSessionPayload(ResponseModel):
    id: str
    building_id: str
    checklist_template_id: str
    service_date: str
    started_at: str
    completed_at: str | None
    worker: str | None
    session_notes: str | None
    status: JobStatus
    items: list[CustomerPortalClientSessionItemPayload] = Field(default_factory=list)


class CustomerPortalClientOverviewPayload(ResponseModel):
    buildings: list[CustomerPortalClientBuildingSummaryPayload]
    completed_sessions: list[CustomerPortalClientSessionPayload]


class CustomerPortalClientBuildingPayload(ResponseModel):
    building: CustomerPortalClientBuildingSummaryPayload
    completed_sessions: list[CustomerPortalClientSessionPayload]


class CustomerPortalClientJobPayload(ResponseModel):
    building: CustomerPortalClientBuildingSummaryPayload
    session: CustomerPortalClientSessionPayload
