from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import Field

from ..contracts.common import ResponseModel


StepCategory = Literal["access", "job_completion", "rearm_security"]
JobStatus = Literal["in_progress", "completed"]


class CustomerPortalPrincipal(ResponseModel):
    session_user: str
    customer_name: str
    customer_display: str


class CustomerPortalBuilding(ResponseModel):
    id: str
    name: str
    address: str | None
    notes: str | None
    active: bool
    current_checklist_template_id: str | None
    created_at: datetime | None
    updated_at: datetime | None


class CustomerPortalSessionItem(ResponseModel):
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


class CustomerOverview(ResponseModel):
    buildings: list[CustomerPortalBuilding]
    completed_sessions: list[CustomerPortalSession]


class CustomerBuildingHistory(ResponseModel):
    building: CustomerPortalBuilding
    completed_sessions: list[CustomerPortalSession]


class CustomerJobDetail(ResponseModel):
    building: CustomerPortalBuilding
    session: CustomerPortalSession


class ProofFileContent(ResponseModel):
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
