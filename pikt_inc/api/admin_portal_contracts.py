from __future__ import annotations

from pydantic import field_validator, model_validator

from ..services.contracts.common import RequestModel, clean_str


class AdminBuildingDeleteRequestApi(RequestModel):
    building_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_building_id(cls, value):
        payload = dict(value or {})
        if payload.get("building_id") is None and payload.get("building") is not None:
            payload["building_id"] = payload.get("building")
        return payload

    @field_validator("building_id", mode="before")
    @classmethod
    def _validate_building_id(cls, value):
        return clean_str(value)

    @model_validator(mode="after")
    def _require_building_id(self):
        if not clean_str(self.building_id):
            raise ValueError("Building is required.")
        return self
