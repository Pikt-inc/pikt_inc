from __future__ import annotations

from .base import BasePageView


class PublicPageView(BasePageView):
    """Base view for public-facing pages that share common site chrome."""

    no_cache = 1
    body_class = "no-web-page-sections"
