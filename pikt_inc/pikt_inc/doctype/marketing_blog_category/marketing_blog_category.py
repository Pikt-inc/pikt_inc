from __future__ import annotations

from frappe.model.document import Document

from pikt_inc.services import blog


class MarketingBlogCategory(Document):
    def validate(self):
        blog.prepare_blog_category_for_save(self)
