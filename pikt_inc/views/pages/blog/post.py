from __future__ import annotations

import frappe

from pikt_inc.services import blog
from pikt_inc.views.blog import BlogPageView


class BlogPostPageView(BlogPageView):
    """Concrete view for individual blog article pages."""

    sitemap = 0
    page_loader = staticmethod(
        lambda: blog.get_blog_post_data(
            slug=frappe.form_dict.get("slug"),
            preview=frappe.form_dict.get("preview"),
        )
    )
