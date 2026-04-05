from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field, field_validator

from ...contracts.common import ResponseModel, clean_str, truthy


StepCategory = Literal["access", "job_completion", "rearm_security"]
JobStatus = Literal["in_progress", "completed"]


class ChecklistTemplateItemRecord(ResponseModel):
    name: str = ""
    idx: int = 0
    item_key: str = ""
    category: str = ""
    sort_order: int = 0
    title: str = ""
    description: str = ""
    target_duration_seconds: int | None = None
    training_media: str = ""
    training_media_kind: str = ""
    requires_image: bool = False
    allow_notes: bool = True
    is_required: bool = True
    active: bool = True

    @field_validator(
        "name",
        "item_key",
        "category",
        "title",
        "description",
        "training_media",
        "training_media_kind",
        mode="before",
    )
    @classmethod
    def clean_strings(cls, value: object) -> str:
        return clean_str(value)

    @field_validator("idx", "sort_order", mode="before")
    @classmethod
    def normalize_ints(cls, value: object) -> int:
        return int(value or 0)

    @field_validator("target_duration_seconds", mode="before")
    @classmethod
    def normalize_optional_int(cls, value: object):
        if value in (None, "", 0, "0"):
            return None
        return int(value)

    @field_validator("requires_image", "allow_notes", "is_required", "active", mode="before")
    @classmethod
    def normalize_flags(cls, value: object) -> bool:
        if isinstance(value, bool):
            return value
        if value in (None, ""):
            return False
        return truthy(value)


class ChecklistSessionRecord(ResponseModel):
    name: str = ""
    building: str = ""
    service_date: date | None = None
    checklist_template: str = ""
    status: str = ""
    started_at: datetime | None = None
    completed_at: datetime | None = None
    worker: str = ""
    session_notes: str = ""
    creation: datetime | None = None
    modified: datetime | None = None

    @field_validator("name", "building", "checklist_template", "status", "worker", "session_notes", mode="before")
    @classmethod
    def clean_strings(cls, value: object) -> str:
        return clean_str(value)

    @field_validator("service_date", "started_at", "completed_at", "creation", "modified", mode="before")
    @classmethod
    def empty_temporal_to_none(cls, value: object):
        if value in (None, ""):
            return None
        return value


class ChecklistSessionItemRecord(ResponseModel):
    name: str = ""
    idx: int = 0
    item_key: str = ""
    category: str = ""
    sort_order: int = 0
    title_snapshot: str = ""
    description_snapshot: str = ""
    target_duration_seconds: int | None = None
    training_media: str = ""
    training_media_kind: str = ""
    requires_image: bool = False
    allow_notes: bool | None = None
    is_required: bool | None = None
    completed: bool = False
    completed_at: datetime | None = None
    note: str = ""
    proof_image: str = ""

    @field_validator(
        "name",
        "item_key",
        "category",
        "title_snapshot",
        "description_snapshot",
        "training_media",
        "training_media_kind",
        "note",
        "proof_image",
        mode="before",
    )
    @classmethod
    def clean_strings(cls, value: object) -> str:
        return clean_str(value)

    @field_validator("idx", "sort_order", mode="before")
    @classmethod
    def normalize_ints(cls, value: object) -> int:
        return int(value or 0)

    @field_validator("target_duration_seconds", mode="before")
    @classmethod
    def normalize_optional_int(cls, value: object):
        if value in (None, "", 0, "0"):
            return None
        return int(value)

    @field_validator("requires_image", "completed", mode="before")
    @classmethod
    def normalize_required_flags(cls, value: object) -> bool:
        if value in (None, ""):
            return False
        if isinstance(value, bool):
            return value
        return truthy(value)

    @field_validator("allow_notes", "is_required", mode="before")
    @classmethod
    def normalize_optional_flags(cls, value: object):
        if value in (None, ""):
            return None
        if isinstance(value, bool):
            return value
        return truthy(value)

    @field_validator("completed_at", mode="before")
    @classmethod
    def empty_completed_at_to_none(cls, value: object):
        if value in (None, ""):
            return None
        return value


class ChecklistStep(ResponseModel):
    id: str
    building_id: str
    checklist_template_id: str | None
    category: StepCategory
    step_order: int
    title: str
    description: str | None
    target_duration_seconds: int | None = None
    training_media_path: str | None = None
    training_media_kind: str | None = None
    requires_image: bool
    allow_notes: bool
    is_required: bool
    active: bool


class CustomerPortalSessionItem(ResponseModel):
    id: str
    job_session_id: str | None
    item_key: str
    category: StepCategory
    step_order: int
    title: str
    description: str | None
    target_duration_seconds: int | None = None
    training_media_path: str | None = None
    training_media_kind: str | None = None
    requires_image: bool
    allow_notes: bool
    is_required: bool
    completed: bool
    completed_at: datetime | None
    proof_image_path: str | None
    note: str | None


class CustomerPortalSession(ResponseModel):
    id: str
    building_id: str
    checklist_template_id: str
    service_date: date | None
    started_at: datetime | None
    completed_at: datetime | None
    worker: str | None
    session_notes: str | None
    status: JobStatus
    items: list[CustomerPortalSessionItem] = Field(default_factory=list)
