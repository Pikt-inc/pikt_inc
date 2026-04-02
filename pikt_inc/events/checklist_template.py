from __future__ import annotations

from pikt_inc.services import checklist_model


def before_save(doc, _method=None):
    checklist_model.prepare_checklist_template(doc)


def after_insert(doc, _method=None):
    checklist_model.sync_active_checklist_template(doc)


def on_update(doc, _method=None):
    checklist_model.sync_active_checklist_template(doc)
