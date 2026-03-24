from __future__ import annotations

from pikt_inc.services.dispatch import planning


def after_save(doc, _method=None):
    planning.handle_building_after_save(doc)


def after_insert(doc, _method=None):
    planning.handle_building_after_save(doc)


def on_update(doc, _method=None):
    planning.handle_building_after_save(doc)
