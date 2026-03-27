from __future__ import annotations

from pikt_inc.services import blog
from pikt_inc.views.blog import FeedPageView


class BlogRssPageView(FeedPageView):
    """Concrete view for the blog RSS feed endpoint."""

    sitemap = 0
    page_loader = staticmethod(lambda: blog.get_rss_feed_data())
