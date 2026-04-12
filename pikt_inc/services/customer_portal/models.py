from __future__ import annotations

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
