from __future__ import annotations

from typing import Any


def model_dump_python(value: Any):
    """Serialize a model-like value into Python primitives when supported.

    :param value: Any raw value or model-like object.
    :returns: A Python-native representation when ``model_dump`` is available,
        otherwise the original value.
    """
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    return value


def as_mapping(value: Any) -> dict[str, Any]:
    """Normalize a model-like value into a dictionary.

    :param value: Any raw value or model-like object.
    :returns: A dictionary when the value resolves to a mapping, otherwise an
        empty dictionary.
    """
    dumped = model_dump_python(value)
    if isinstance(dumped, dict):
        return dumped
    return {}


def as_mapping_list(items: Any) -> list[dict[str, Any]]:
    """Normalize a sequence of model-like values into dictionaries.

    :param items: Any iterable of raw values or model-like objects.
    :returns: A list containing only normalized dictionary items.
    """
    normalized: list[dict[str, Any]] = []
    for item in items or []:
        dumped = model_dump_python(item)
        if isinstance(dumped, dict):
            normalized.append(dumped)
    return normalized


class BasePageView:
    no_cache: int | None = 1
    sitemap: int = 0
    body_class: str | None = "no-web-page-sections"
    noindex_meta: int | None = None
    page_title: str = ""
    meta_description: str = ""
    default_page_title: str = ""
    default_meta_description: str = ""

    def get_page_data(self) -> dict[str, Any]:
        """Return the raw page payload before context shaping.

        :returns: A mapping of page data attributes.
        """
        return {}

    def apply_payload(self, context, data: dict[str, Any]):
        """Apply the raw payload keys directly onto the context object.

        :param context: The mutable Frappe page context object.
        :param data: The normalized page payload.
        """
        for key, value in data.items():
            setattr(context, key, value)

    def resolve_page_title(self, data: dict[str, Any]) -> str:
        """Resolve the page title for the current payload.

        :param data: The normalized page payload.
        :returns: The title that should be placed on the page context.
        """
        return str(data.get("page_title") or self.page_title or self.default_page_title or "")

    def resolve_meta_description(self, data: dict[str, Any]) -> str:
        """Resolve the meta description for the current payload.

        :param data: The normalized page payload.
        :returns: The description that should be placed on the page context.
        """
        return str(
            data.get("meta_description")
            or data.get("description")
            or self.meta_description
            or self.default_meta_description
            or ""
        )

    def resolve_http_status_code(self, data: dict[str, Any]) -> int | None:
        """Resolve the HTTP status code for the current payload.

        :param data: The normalized page payload.
        :returns: The HTTP status code to apply, or ``None`` when the payload
            does not define one.
        """
        if "http_status_code" not in data:
            return None
        return int(data.get("http_status_code") or 200)

    def apply_defaults(self, context, data: dict[str, Any]):
        """Apply common page defaults and derived metadata to the context.

        :param context: The mutable Frappe page context object.
        :param data: The normalized page payload.
        """
        if self.no_cache is not None:
            context.no_cache = 1 if self.no_cache else 0
        if self.body_class is not None:
            context.body_class = self.body_class
        if self.noindex_meta is not None:
            context.noindex_meta = 1 if self.noindex_meta else 0

        page_title = self.resolve_page_title(data)
        if page_title or not hasattr(context, "page_title"):
            context.page_title = page_title

        meta_description = self.resolve_meta_description(data)
        context.meta_description = meta_description
        context.description = meta_description

        http_status_code = self.resolve_http_status_code(data)
        if http_status_code is not None:
            context.http_status_code = http_status_code

    def finalize_context(self, context, data: dict[str, Any]):
        """Finalize the context after payload and defaults are applied.

        :param context: The mutable Frappe page context object.
        :param data: The normalized page payload.
        :returns: The final context object.
        """
        return context

    def build_context(self, context):
        """Build and return a fully populated page context.

        :param context: The mutable Frappe page context object.
        :returns: The final page context after payload, defaults, and
            finalization logic are applied.
        """
        raw_data = self.get_page_data() or {}
        data = model_dump_python(raw_data)
        if not isinstance(data, dict):
            data = {}
        self.apply_payload(context, data)
        self.apply_defaults(context, data)
        return self.finalize_context(context, data)
