from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import Field, field_validator

from .common import RequestModel, ResponseModel, clean_str, looks_like_email, normalize_email


class ContactRequestType(str, Enum):
    GENERAL_SERVICE_QUESTION = "General service question"
    WALKTHROUGH_REQUEST = "Walkthrough request"
    CUSTOM_SCOPE_REQUEST = "Custom scope or out-of-area request"
    CURRENT_CUSTOMER_SUPPORT = "Current customer support"
    CAREERS_OR_PARTNER_INQUIRY = "Careers or partner inquiry"


CONTACT_REQUEST_TYPE_OPTIONS = tuple(item.value for item in ContactRequestType)


class ContactRequestInput(RequestModel):
    first_name: str = Field(min_length=1)
    last_name: str = Field(min_length=1)
    email_id: str = Field(min_length=1)
    mobile_no: str = ""
    company_name: str = Field(min_length=1)
    city: str = Field(min_length=1)
    request_type: ContactRequestType
    message: str = Field(min_length=1)

    @field_validator(
        "first_name",
        "last_name",
        "email_id",
        "mobile_no",
        "company_name",
        "city",
        "message",
        mode="before",
    )
    @classmethod
    def clean_strings(cls, value: Any) -> str:
        return clean_str(value)

    @field_validator("email_id")
    @classmethod
    def normalize_email_field(cls, value: str) -> str:
        normalized = normalize_email(value)
        if not looks_like_email(normalized):
            raise ValueError("Value is not a valid email address.")
        return normalized


class ContactRequestSubmitted(ResponseModel):
    status: Literal["submitted"]
    message: str
    request: str
