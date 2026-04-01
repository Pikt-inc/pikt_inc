from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe

from .public import PublicPageView
from .base import as_mapping, as_mapping_list


class PortalPageView(PublicPageView):
    """Base view for authenticated portal pages with nav and redirect logic."""

    noindex_meta = 1
    page_loader: Callable[[], dict[str, Any]] | None = None
    retired_redirect_to: str | None = None
    retired_http_status_code: int = 302

    def __init__(self, *, page_loader: Callable[[], dict[str, Any]] | None = None):
        """Initialize a portal page view.

        :param page_loader: Optional callable that returns the portal page
            payload. When omitted, subclasses may provide ``page_loader`` as a
            class attribute.
        """
        configured_loader = page_loader or getattr(self, "page_loader", None)
        if configured_loader is None:
            raise ValueError("PortalPageView requires a page_loader callable.")
        self.page_loader = configured_loader

    def get_page_data(self) -> dict[str, Any]:
        """Return the raw portal payload from the configured loader.

        :returns: A portal page payload dictionary.
        """
        if self.retired_redirect_to:
            return {
                "redirect_to": self.retired_redirect_to,
                "http_status_code": self.retired_http_status_code,
            }
        return self.page_loader() or {}

    def resolve_page_title(self, data: dict[str, Any]) -> str:
        """Resolve the portal page title from metatags or payload fields.

        :param data: The normalized page payload.
        :returns: The page title to expose in the context.
        """
        metatags = as_mapping(data.get("metatags"))
        return str(metatags.get("title") or data.get("page_title") or data.get("portal_title") or "")

    def resolve_meta_description(self, data: dict[str, Any]) -> str:
        """Resolve the portal meta description from metatags or payload fields.

        :param data: The normalized page payload.
        :returns: The description to expose in the context.
        """
        metatags = as_mapping(data.get("metatags"))
        return str(metatags.get("description") or data.get("portal_description") or "")

    def resolve_http_status_code(self, data: dict[str, Any]) -> int | None:
        """Resolve the portal HTTP status code.

        :param data: The normalized page payload.
        :returns: The HTTP status code for the portal response.
        """
        return int(data.get("http_status_code") or 200)

    def apply_payload(self, context, data: dict[str, Any]):
        """Apply portal payload fields and split navigation into shell groups.

        :param context: The mutable Frappe page context object.
        :param data: The normalized portal page payload.
        """
        super().apply_payload(context, data)
        portal_nav = as_mapping_list(data.get("portal_nav"))
        context.primary_nav = [item for item in portal_nav if item.get("key") not in {"contact", "logout"}]
        context.utility_nav = [item for item in portal_nav if item.get("key") in {"contact", "logout"}]
        context.redirect_to = data.get("redirect_to") or ""

    def finalize_context(self, context, data: dict[str, Any]):
        """Finalize the portal context and trigger redirects when requested.

        :param context: The mutable Frappe page context object.
        :param data: The normalized portal page payload.
        :returns: The final context when no redirect is requested.
        :raises frappe.Redirect: Raised when the payload requests a redirect.
        """
        if getattr(context, "redirect_to", ""):
            flags = getattr(getattr(frappe, "local", None), "flags", None)
            if flags is None:
                frappe.local.flags = type("Flags", (), {})()
                flags = frappe.local.flags
            flags.redirect_location = context.redirect_to
            response = getattr(getattr(frappe, "local", None), "response", None)
            if response is None:
                frappe.local.response = {}
                response = frappe.local.response
            response["type"] = "redirect"
            response["location"] = context.redirect_to
            response["http_status_code"] = getattr(context, "http_status_code", 302)
            raise frappe.Redirect(getattr(context, "http_status_code", 302))
        return context
