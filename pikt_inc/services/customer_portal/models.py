from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from ..contracts.common import ResponseModel
from .building.models import CustomerPortalBuilding, CustomerPortalStorageLocation
from .checklist.models import ChecklistStep, CustomerPortalSession, CustomerPortalSessionItem


class CustomerOverview(ResponseModel):
    buildings: list[CustomerPortalBuilding]
    completed_sessions: list[CustomerPortalSession]


class CustomerBuildingHistory(ResponseModel):
    building: CustomerPortalBuilding
    completed_sessions: list[CustomerPortalSession]


class CustomerJobDetail(ResponseModel):
    building: CustomerPortalBuilding
    session: CustomerPortalSession


class ChecklistPortalBuildingDetail(ResponseModel):
    building: CustomerPortalBuilding
    checklist_template_id: str | None
    steps: list[ChecklistStep]
    active_session: CustomerPortalSession | None
    storage_locations: list[CustomerPortalStorageLocation] = Field(default_factory=list)


class ChecklistSessionItemMutation(ResponseModel):
    session: CustomerPortalSession
    item: CustomerPortalSessionItem


class AssignedWorkProgressSummary(ResponseModel):
    total_steps: int
    resolved_steps: int


class AssignedWorkSummary(ResponseModel):
    requirement_id: str
    building_id: str
    building_name: str
    short_address: str | None
    service_date: date | None
    shift_type: str | None
    arrival_window_start: datetime | None
    arrival_window_end: datetime | None
    status: str
    checked_in_at: datetime | None
    checklist_session_id: str | None
    progress_summary: AssignedWorkProgressSummary
    requires_clock_in: bool
    route_stop_index: int | None = None


class AssignedWorkQueue(ResponseModel):
    current_shift: AssignedWorkSummary | None = None
    assigned_work: list[AssignedWorkSummary] = Field(default_factory=list)
    upcoming_assigned_work: list[AssignedWorkSummary] = Field(default_factory=list)


class AssignedWorkDetail(ResponseModel):
    work: AssignedWorkSummary
    building: CustomerPortalBuilding
    checklist_template_id: str | None
    steps: list[ChecklistStep]
    active_session: CustomerPortalSession | None
    storage_locations: list[CustomerPortalStorageLocation] = Field(default_factory=list)
    access_summary: list[str] = Field(default_factory=list)
    alarm_summary: list[str] = Field(default_factory=list)
    site_summary: list[str] = Field(default_factory=list)
    service_notes: str | None = None


class ProofFileContent(ResponseModel):
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"


class PortalMediaContent(ResponseModel):
    filename: str
    content: bytes
    content_type: str = "application/octet-stream"
    display_content_as: str = "inline"
    http_status_code: int = 200
    headers: dict[str, str] = Field(default_factory=dict)
