from __future__ import annotations

from pikt_inc.www._quote_page import build_context


no_cache = 1
sitemap = 0


def get_context(context):
    return build_context(
        context,
        title="Digital Walkthrough Received",
        description="Confirmation that your digital walkthrough has been received.",
        noindex_meta=1,
    )
