from __future__ import annotations

from pikt_inc.services import walkthrough_review


def before_save(doc, _method=None):
    walkthrough_review.apply_reviewer_module_profile(doc)
