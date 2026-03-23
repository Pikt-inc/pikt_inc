from __future__ import annotations

from pikt_inc.services.dispatch import planning, routing


def before_save(doc, _method=None):
    planning.normalize_site_shift_requirement(doc)


def after_save(doc, _method=None):
    routing.handle_site_shift_requirement_after_save(doc)
