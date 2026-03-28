from __future__ import annotations

from pikt_inc.services import customer_desk, walkthrough_review


def before_save(doc, _method=None):
    walkthrough_review.apply_reviewer_module_profile(doc)
    customer_desk.apply_customer_desk_module_profile(doc)
