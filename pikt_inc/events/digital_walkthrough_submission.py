from __future__ import annotations

from pikt_inc.services import walkthrough_review


def before_save(doc, _method=None):
    walkthrough_review.sync_submission_to_opportunity(doc)
