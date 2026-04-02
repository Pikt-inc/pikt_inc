from __future__ import annotations

from ..contracts.common import ResponseModel
from .building_repo import BuildingRecord
from .checklist_repo import ChecklistSessionItemRecord, ChecklistSessionRecord


class ScopedCompletedSessionRead(ResponseModel):
    session: ChecklistSessionRecord


class ScopedOverviewRead(ResponseModel):
    buildings: list[BuildingRecord]
    completed_sessions: list[ScopedCompletedSessionRead]


class ScopedBuildingHistoryRead(ResponseModel):
    building: BuildingRecord
    completed_sessions: list[ScopedCompletedSessionRead]


class ScopedJobDetailRead(ResponseModel):
    building: BuildingRecord
    session: ChecklistSessionRecord
    items: list[ChecklistSessionItemRecord]


class ScopedJobProofRead(ResponseModel):
    session: ChecklistSessionRecord
    item: ChecklistSessionItemRecord
