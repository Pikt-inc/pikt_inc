from __future__ import annotations

import frappe

from pikt_inc.services import blog
from pikt_inc.views.blog import BlogPageView


class BlogHomePageView(BlogPageView):
    """Concrete view for the public blog index page."""

    sitemap = 0
    page_loader = staticmethod(
        lambda: blog.get_blog_index_data(
            page=frappe.form_dict.get("page"),
            category=frappe.form_dict.get("category"),
        )
    )
