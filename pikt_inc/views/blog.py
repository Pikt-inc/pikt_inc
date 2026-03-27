from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .base import BasePageView, as_mapping
from .public import PublicPageView


class BlogPageView(PublicPageView):
    """Base view for blog HTML pages backed by a loader callable."""

    page_loader: Callable[[], dict[str, Any]] | None = None
    noindex_meta = None

    def __init__(self, *, page_loader: Callable[[], dict[str, Any]] | None = None):
        """Initialize a blog page view.

        :param page_loader: Optional callable that returns the blog payload.
            When omitted, subclasses may provide ``page_loader`` as a class
            attribute.
        """
        configured_loader = page_loader or getattr(type(self), "page_loader", None)
        if configured_loader is None:
            raise ValueError("BlogPageView requires a page_loader callable.")
        self._page_loader = configured_loader

    def get_page_data(self) -> dict[str, Any]:
        """Return the raw blog payload from the configured loader.

        :returns: A blog page payload dictionary.
        """
        return self._page_loader() or {}

    def resolve_page_title(self, data: dict[str, Any]) -> str:
        """Resolve the blog page title from nested metatags or payload fields.

        :param data: The normalized blog payload.
        :returns: The page title for the rendered context.
        """
        metatags = as_mapping(data.get("metatags"))
        return str(metatags.get("title") or data.get("page_title") or data.get("title") or "")

    def resolve_meta_description(self, data: dict[str, Any]) -> str:
        """Resolve the blog meta description from nested metatags or payload fields.

        :param data: The normalized blog payload.
        :returns: The meta description for the rendered context.
        """
        metatags = as_mapping(data.get("metatags"))
        return str(metatags.get("description") or data.get("description") or "")

    def resolve_http_status_code(self, data: dict[str, Any]) -> int | None:
        """Resolve the blog HTTP status code.

        :param data: The normalized blog payload.
        :returns: The blog HTTP status code when defined.
        """
        if "http_status_code" in data:
            return int(data.get("http_status_code") or 200)
        if data.get("not_found"):
            return 404
        return None

    def apply_defaults(self, context, data: dict[str, Any]):
        """Apply blog defaults and dynamic noindex handling.

        :param context: The mutable Frappe page context object.
        :param data: The normalized blog payload.
        """
        super().apply_defaults(context, data)
        if "noindex_meta" in data:
            context.noindex_meta = int(data.get("noindex_meta") or 0)


class FeedPageView(BasePageView):
    """Base view for XML-like feed endpoints backed by a loader callable."""

    page_loader: Callable[[], dict[str, Any]] | None = None
    body_class = None
    noindex_meta = None

    def __init__(self, *, page_loader: Callable[[], dict[str, Any]] | None = None):
        """Initialize a feed page view.

        :param page_loader: Optional callable that returns the feed payload.
            When omitted, subclasses may provide ``page_loader`` as a class
            attribute.
        """
        configured_loader = page_loader or getattr(type(self), "page_loader", None)
        if configured_loader is None:
            raise ValueError("FeedPageView requires a page_loader callable.")
        self._page_loader = configured_loader

    def get_page_data(self) -> dict[str, Any]:
        """Return the raw feed payload from the configured loader.

        :returns: A feed payload dictionary.
        """
        return self._page_loader() or {}
