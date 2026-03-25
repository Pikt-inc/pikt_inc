from __future__ import annotations

from frappe.model.document import Document

from pikt_inc.services import blog


class MarketingBlogPost(Document):
    def validate(self):
        blog.prepare_blog_post_for_save(self)
