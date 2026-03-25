from __future__ import annotations

from pikt_inc.www._quote_page import build_context


no_cache = 1
sitemap = 0


def get_context(context):
    return build_context(
        context,
        title="Digital Walkthrough",
        description="Upload your completed digital walkthrough for commercial cleaning review.",
        noindex_meta=1,
    )
