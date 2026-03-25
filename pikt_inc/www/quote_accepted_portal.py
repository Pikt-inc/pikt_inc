from __future__ import annotations

from pikt_inc.www._quote_page import build_context


no_cache = 1
sitemap = 0


def get_context(context):
    return build_context(
        context,
        title="Quote Accepted",
        description="Accept your quote, set up billing, and confirm your service site access in one secure portal.",
        noindex_meta=1,
    )
