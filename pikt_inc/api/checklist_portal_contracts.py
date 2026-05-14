from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, Field, field_validator, model_validator

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


class ChecklistPortalAssignedStepTrainingMediaRequestApi(RequestModel):
    requirement_id: str = Field(validation_alias=AliasChoices("requirement_id", "requirement"), min_length=1)
    item_key: str = Field(validation_alias=AliasChoices("item_key", "itemKey"), min_length=1)

    @field_validator("requirement_id", "item_key", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)


class ChecklistPortalUpdateSessionItemRequestApi(RequestModel):
    session_id: str = Field(validation_alias=AliasChoices("session_id", "session"), min_length=1)
    item_key: str = Field(validation_alias=AliasChoices("item_key", "itemKey"), min_length=1)
    completed: bool | None = None
    issue_reported: bool | None = Field(default=None, validation_alias=AliasChoices("issue_reported", "issueReported"))
    issue_reason: str | None = Field(default=None, validation_alias=AliasChoices("issue_reason", "issueReason"))
    note: str | None = None
    proof_image: str | None = Field(default=None, validation_alias=AliasChoices("proof_image", "proofImage"))

    @field_validator("session_id", "item_key", "issue_reason", "note", "proof_image", mode="before")
    @classmethod
    def clean_strings(cls, value: Any):
        if value is None:
            return None
        return clean_str(value)

    @model_validator(mode="after")
    def validate_issue_reason(self):
        if self.issue_reported and not clean_str(self.issue_reason):
            raise ValueError("Issue reason is required when reporting an issue.")
        return self


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


class ChecklistPortalUploadIssueImageRequestApi(RequestModel):
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


class ChecklistPortalAssignedWorkRequestApi(RequestModel):
    service_date: str | None = Field(default=None, validation_alias=AliasChoices("service_date", "serviceDate"))

    @field_validator("service_date", mode="before")
    @classmethod
    def clean_optional_service_date(cls, value: Any) -> str | None:
        cleaned = clean_str(value)
        return cleaned or None


class ChecklistPortalAssignedWorkDetailRequestApi(RequestModel):
    requirement_id: str = Field(validation_alias=AliasChoices("requirement_id", "requirement"), min_length=1)

    @field_validator("requirement_id", mode="before")
    @classmethod
    def clean_requirement_id(cls, value: Any) -> str:
        return clean_str(value)


class ChecklistPortalEnsureRequirementSessionRequestApi(ChecklistPortalAssignedWorkDetailRequestApi):
    pass


class ChecklistPortalBuildingPayload(ResponseModel):
    id: str
    name: str
    address: str | None
    notes: str | None
    active: bool
    current_checklist_template_id: str | None
    created_at: str
    updated_at: str


class ChecklistPortalAssignedWorkProgressSummaryPayload(ResponseModel):
    total_steps: int
    resolved_steps: int


class ChecklistPortalAssignedWorkPayload(ResponseModel):
    requirement_id: str
    building_id: str
    building_name: str
    short_address: str | None
    service_date: str | None
    shift_type: str | None
    arrival_window_start: str | None
    arrival_window_end: str | None
    status: str
    checked_in_at: str | None
    checklist_session_id: str | None
    progress_summary: ChecklistPortalAssignedWorkProgressSummaryPayload
    requires_clock_in: bool
    route_stop_index: int | None = None


class ChecklistPortalAssignedWorkQueuePayload(ResponseModel):
    current_shift: ChecklistPortalAssignedWorkPayload | None = None
    assigned_work: list[ChecklistPortalAssignedWorkPayload]
    upcoming_assigned_work: list[ChecklistPortalAssignedWorkPayload]


class ChecklistPortalStorageLocationPayload(ResponseModel):
    id: str
    building_id: str
    name: str
    location_type: str
    directions: str | None
    notes: str | None
    active: bool
    is_primary: bool
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
    issue_reported: bool
    issue_reason: str | None
    issue_reported_at: str | None
    issue_image: str | None
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
    storage_locations: list[ChecklistPortalStorageLocationPayload]


class ChecklistPortalAssignedWorkDetailPayload(ResponseModel):
    work: ChecklistPortalAssignedWorkPayload
    building: ChecklistPortalBuildingPayload
    checklist_template_id: str | None
    steps: list[ChecklistPortalStepPayload]
    active_session: ChecklistPortalSessionPayload | None
    storage_locations: list[ChecklistPortalStorageLocationPayload]
    access_summary: list[str]
    alarm_summary: list[str]
    site_summary: list[str]
    service_notes: str | None


class ChecklistPortalSessionItemMutationPayload(ResponseModel):
    session: ChecklistPortalSessionPayload
    item: ChecklistPortalSessionItemPayload
