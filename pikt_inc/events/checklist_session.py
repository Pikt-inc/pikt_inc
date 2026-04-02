from __future__ import annotations

from pikt_inc.services import checklist_model


def before_insert(doc, _method=None):
    checklist_model.prepare_checklist_session_for_insert(doc)


def before_save(doc, _method=None):
    checklist_model.validate_checklist_session(doc)
