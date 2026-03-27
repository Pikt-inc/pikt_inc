from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe


def _as_mapping(value):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="python")
    if isinstance(value, dict):
        return value
    return {}


def _as_nav_items(items):
    normalized = []
    for item in items or []:
        if hasattr(item, "model_dump"):
            normalized.append(item.model_dump(mode="python"))
        elif isinstance(item, dict):
            normalized.append(item)
    return normalized


def build_context(
    context,
    *,
    page_loader: Callable[[], dict[str, Any]],
):
    data = page_loader() or {}
    for key, value in data.items():
        setattr(context, key, value)

    context.no_cache = 1
    context.body_class = "no-web-page-sections"
    context.noindex_meta = 1

    metatags = _as_mapping(data.get("metatags"))
    portal_nav = _as_nav_items(data.get("portal_nav"))
    context.page_title = metatags.get("title") or data.get("page_title") or data.get("portal_title")
    context.meta_description = metatags.get("description") or data.get("portal_description") or ""
    context.description = context.meta_description
    context.http_status_code = int(data.get("http_status_code") or 200)
    context.primary_nav = [item for item in portal_nav if item.get("key") not in {"contact", "logout"}]
    context.utility_nav = [item for item in portal_nav if item.get("key") in {"contact", "logout"}]
    context.redirect_to = data.get("redirect_to") or ""

    if context.redirect_to:
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
        response["http_status_code"] = context.http_status_code
        raise frappe.Redirect(context.http_status_code)
    return context
