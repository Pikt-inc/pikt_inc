from __future__ import annotations

from pikt_inc.services import blog

base_template_path = "www/blog/rss.xml"
no_cache = 1
sitemap = 0


def get_context(context):
    context.no_cache = 1
    return blog.get_rss_feed_data()
