from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field, field_validator

from ..services.contracts.common import RequestModel, ResponseModel, clean_str
from ..services.customer_portal.checklist.models import JobStatus, StepCategory


class ChecklistPortalBuildingsRequestApi(RequestModel):
    active_only: bool = Field(default=True, validation_alias=AliasChoices("active_only", "activeOnly"))


class ChecklistPortalBuildingRequestApi(RequestModel):
    building_id: str = Field(validation_alias=AliasChoices("building_id", "building"), min_length=1)
    service_date: str = Field(validation_alias=AliasChoices("service_date", "serviceDate"), min_length=1)

    @field_validator("building_id", "service_date", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)


class ChecklistPortalEnsureSessionRequestApi(ChecklistPortalBuildingRequestApi):
    pass


class ChecklistPortalStepTrainingMediaRequestApi(RequestModel):
    building_id: str = Field(validation_alias=AliasChoices("building_id", "building"), min_length=1)
    item_key: str = Field(validation_alias=AliasChoices("item_key", "itemKey"), min_length=1)

    @field_validator("building_id", "item_key", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)


class ChecklistPortalUpdateSessionItemRequestApi(RequestModel):
    session_id: str = Field(validation_alias=AliasChoices("session_id", "session"), min_length=1)
    item_key: str = Field(validation_alias=AliasChoices("item_key", "itemKey"), min_length=1)
    completed: bool | None = None
    note: str | None = None
    proof_image: str | None = Field(default=None, validation_alias=AliasChoices("proof_image", "proofImage"))

    @field_validator("session_id", "item_key", "note", "proof_image", mode="before")
    @classmethod
    def clean_strings(cls, value: Any):
        if value is None:
            return None
        return clean_str(value)


class ChecklistPortalCompleteSessionRequestApi(RequestModel):
    session_id: str = Field(validation_alias=AliasChoices("session_id", "session"), min_length=1)

    @field_validator("session_id", mode="before")
    @classmethod
    def clean_session_id(cls, value: Any) -> str:
        return clean_str(value)


class ChecklistPortalUploadProofRequestApi(RequestModel):
    session_id: str = Field(validation_alias=AliasChoices("session_id", "session"), min_length=1)
    item_key: str = Field(validation_alias=AliasChoices("item_key", "itemKey"), min_length=1)

    @field_validator("session_id", "item_key", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)


class ChecklistPortalSessionTrainingMediaRequestApi(RequestModel):
    session_id: str = Field(validation_alias=AliasChoices("session_id", "session"), min_length=1)
    item_key: str = Field(validation_alias=AliasChoices("item_key", "itemKey"), min_length=1)

    @field_validator("session_id", "item_key", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)


class ChecklistPortalBuildingPayload(ResponseModel):
    id: str
    name: str
    address: str | None
    notes: str | None
    active: bool
    current_checklist_template_id: str | None
    created_at: str
    updated_at: str


class ChecklistPortalStepPayload(ResponseModel):
    id: str
    building_id: str
    checklist_template_id: str | None
    category: StepCategory
    step_order: int
    title: str
    description: str | None
    target_duration_seconds: int | None = None
    training_media: str | None = None
    training_media_kind: str | None = None
    requires_image: bool
    allow_notes: bool
    is_required: bool
    active: bool


class ChecklistPortalSessionItemPayload(ResponseModel):
    id: str
    job_session_id: str | None
    item_key: str
    category: StepCategory
    step_order: int
    title: str
    description: str | None
    target_duration_seconds: int | None = None
    training_media: str | None = None
    training_media_kind: str | None = None
    requires_image: bool
    allow_notes: bool
    is_required: bool
    completed: bool
    completed_at: str | None
    proof_image: str | None
    note: str | None


class ChecklistPortalSessionPayload(ResponseModel):
    id: str
    building_id: str
    checklist_template_id: str
    service_date: str
    started_at: str
    completed_at: str | None
    server_now: str | None = None
    worker: str | None
    session_notes: str | None
    status: JobStatus
    items: list[ChecklistPortalSessionItemPayload]


class ChecklistPortalBuildingDetailPayload(ResponseModel):
    building: ChecklistPortalBuildingPayload
    checklist_template_id: str | None
    steps: list[ChecklistPortalStepPayload]
    active_session: ChecklistPortalSessionPayload | None


class ChecklistPortalSessionItemMutationPayload(ResponseModel):
    session: ChecklistPortalSessionPayload
    item: ChecklistPortalSessionItemPayload
