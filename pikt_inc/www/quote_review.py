from __future__ import annotations

from pikt_inc.www._quote_page import build_context


no_cache = 1
sitemap = 0


def get_context(context):
    return build_context(
        context,
        title="Preparing Your Billing Setup",
        description="Compatibility redirect for previously sent public quote links.",
        noindex_meta=1,
    )
