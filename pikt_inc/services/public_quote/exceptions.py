from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PublicQuoteWorkflowError(RuntimeError):
    public_message: str
    log_title: str = "Public Quote Workflow"
    internal_message: str = ""
    context: dict[str, Any] | None = None

    def __post_init__(self):
        RuntimeError.__init__(self, self.internal_message or self.public_message)

    def log_message(self) -> str:
        message = self.internal_message or self.public_message
        if not self.context:
            return message
        pairs = [f"{key}={value}" for key, value in sorted(self.context.items())]
        return f"{message}\n" + "\n".join(pairs)


__all__ = ["PublicQuoteWorkflowError"]
