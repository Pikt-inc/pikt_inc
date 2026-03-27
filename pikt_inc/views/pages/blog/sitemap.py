from __future__ import annotations

from pikt_inc.services import blog
from pikt_inc.views.blog import FeedPageView


class BlogSitemapPageView(FeedPageView):
    """Concrete view for the blog sitemap endpoint."""

    sitemap = 0
    page_loader = staticmethod(lambda: blog.get_blog_sitemap_data())
