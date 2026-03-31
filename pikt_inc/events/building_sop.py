from __future__ import annotations

from pikt_inc.services import building_sop


def before_insert(doc, _method=None):
    building_sop.prepare_building_sop_for_insert(doc)


def before_save(doc, _method=None):
    building_sop.prevent_sop_mutation(doc)


def after_insert(doc, _method=None):
    building_sop.activate_building_sop(doc)
