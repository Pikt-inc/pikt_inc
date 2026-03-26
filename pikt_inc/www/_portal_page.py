from __future__ import annotations

from collections.abc import Callable
from typing import Any


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

    metatags = data.get("metatags") or {}
    context.page_title = metatags.get("title") or data.get("page_title") or data.get("portal_title")
    context.meta_description = metatags.get("description") or data.get("portal_description") or ""
    context.description = context.meta_description
    context.http_status_code = int(data.get("http_status_code") or 200)
    context.primary_nav = [item for item in data.get("portal_nav", []) if item.get("key") not in {"contact", "logout"}]
    context.utility_nav = [item for item in data.get("portal_nav", []) if item.get("key") in {"contact", "logout"}]
    return context
