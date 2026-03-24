from __future__ import annotations

from pikt_inc.services.dispatch import staffing


def after_save(doc, _method=None):
    staffing.handle_shift_assignment_after_save(doc)


def after_insert(doc, _method=None):
    staffing.handle_shift_assignment_after_save(doc)


def on_update(doc, _method=None):
    staffing.handle_shift_assignment_after_save(doc)


def on_submit(doc, _method=None):
    staffing.handle_shift_assignment_after_save(doc)


def on_update_after_submit(doc, _method=None):
    staffing.handle_shift_assignment_after_save(doc)
