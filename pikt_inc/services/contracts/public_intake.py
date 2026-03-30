from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from .common import RequestModel, ResponseModel, clean_str, looks_like_email, normalize_email


class BathroomTrafficLevel(str, Enum):
    NONE = "None"
    LIGHT = "Light"
    MEDIUM = "Medium"
    HEAVY = "Heavy"


class InstantQuoteRequestInput(RequestModel):
    prospect_name: str = Field(min_length=1)
    phone: str = ""
    contact_email: str = Field(min_length=1)
    prospect_company: str = Field(min_length=1)
    building_type: str = Field(min_length=1)
    building_size: int
    service_frequency: str = Field(min_length=1)
    service_interest: str = Field(min_length=1)
    bathroom_count_range: BathroomTrafficLevel = BathroomTrafficLevel.NONE

    @field_validator(
        "prospect_name",
        "phone",
        "contact_email",
        "prospect_company",
        "building_type",
        "service_frequency",
        "service_interest",
        mode="before",
    )
    @classmethod
    def clean_strings(cls, value: Any) -> str:
        return clean_str(value)

    @field_validator("contact_email")
    @classmethod
    def normalize_email_field(cls, value: str) -> str:
        normalized = normalize_email(value)
        if not looks_like_email(normalized):
            raise ValueError("Value is not a valid email address.")
        return normalized

    @field_validator("building_size", mode="before")
    @classmethod
    def normalize_building_size(cls, value: Any) -> int:
        raw = clean_str(value).replace(",", "")
        if not raw:
            raise ValueError("Input should be a valid integer.")
        try:
            normalized = int(float(raw))
        except Exception as exc:
            raise ValueError("Input should be a valid integer.") from exc
        return normalized

    @field_validator("bathroom_count_range", mode="before")
    @classmethod
    def normalize_bathroom_range(cls, value: Any) -> BathroomTrafficLevel:
        raw = clean_str(value)
        lowered = raw.lower()
        mapping = {
            "": BathroomTrafficLevel.NONE,
            "0": BathroomTrafficLevel.NONE,
            "none": BathroomTrafficLevel.NONE,
            "1-2": BathroomTrafficLevel.LIGHT,
            "light": BathroomTrafficLevel.LIGHT,
            "3-5": BathroomTrafficLevel.MEDIUM,
            "medium": BathroomTrafficLevel.MEDIUM,
            "6-10": BathroomTrafficLevel.HEAVY,
            "11+": BathroomTrafficLevel.HEAVY,
            "heavy": BathroomTrafficLevel.HEAVY,
        }
        normalized = mapping.get(raw, mapping.get(lowered))
        if normalized is None:
            raise ValueError("Input should be a valid bathroom traffic level.")
        return normalized

    @model_validator(mode="after")
    def validate_building_size(self):
        if self.building_size <= 0:
            raise ValueError("Building size must be greater than 0.")
        return self


class PublicFunnelValidationInput(RequestModel):
    opportunity: str = ""
    token: str = ""

    @field_validator("opportunity", "token", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)


class PublicQuoteRequestStateInput(RequestModel):
    request: str = ""
    token: str = ""

    @field_validator("request", "token", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)


class WalkthroughUploadInput(RequestModel):
    request: str = Field(min_length=1)
    token: str = Field(min_length=1)
    uploaded: Any = None

    @field_validator("request", "token", mode="before")
    @classmethod
    def clean_values(cls, value: Any) -> str:
        return clean_str(value)

    @model_validator(mode="after")
    def require_upload(self):
        if self.uploaded is None:
            raise ValueError("Please choose your walkthrough file before submitting.")
        return self


class InstantQuoteResponse(ResponseModel):
    request: str = ""
    name: str
    opp: str
    low: float
    high: float
    risk: str
    currency: str
    final_price: float
    token: str
    duplicate: Literal[0, 1]


class PublicQuoteRequestStateResponse(ResponseModel):
    valid: Literal[1]
    request: str
    low: float
    high: float
    risk: str
    currency: str
    final_price: float
    token: str


class WalkthroughUploadResponse(ResponseModel):
    request: str
    digital_walkthrough_file: str
    digital_walkthrough_status: str
    digital_walkthrough_received_on: str
