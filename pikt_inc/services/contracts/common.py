from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True, validate_default=True)


class ResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def clean_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def clean_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return clean_str(value)


def normalize_email(value: Any) -> str:
    return clean_str(value).lower()


def looks_like_email(value: Any) -> bool:
    normalized = normalize_email(value)
    if not normalized:
        return False
    return re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized) is not None


def truthy(value: Any) -> bool:
    return clean_str(value).lower() in {"1", "true", "yes", "on"}


def first_validation_message(exc: ValidationError) -> str:
    errors = exc.errors()
    if not errors:
        return "Invalid request payload."
    return clean_str(errors[0].get("msg")) or "Invalid request payload."
