from __future__ import annotations

from collections.abc import Callable
from typing import Any

import frappe

from pikt_inc.views.portal import PortalPageView


def _as_mapping(value):
    """Backward-compatible no-op retained for legacy tests/imports.

    :param value: Any value passed through from older helper call sites.
    :returns: The original value unchanged.
    """
    return value


def _as_nav_items(items):
    """Backward-compatible no-op retained for legacy tests/imports.

    :param items: Any value passed through from older helper call sites.
    :returns: The original value unchanged.
    """
    return items


def build_context(
    context,
    *,
    page_loader: Callable[[], dict[str, Any]],
):
    """Build portal-page context through the shared portal view abstraction.

    :param context: The mutable Frappe page context object.
    :param page_loader: Callable that returns the portal page payload.
    :returns: The populated page context.
    :raises frappe.Redirect: Raised when the page payload requests a redirect.
    """
    return PortalPageView(page_loader=page_loader).build_context(context)
