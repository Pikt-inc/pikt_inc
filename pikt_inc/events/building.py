from __future__ import annotations

from pikt_inc.services.dispatch import planning
from pikt_inc.services import customer_desk


def before_insert(doc, _method=None):
    customer_desk.apply_customer_desk_building_defaults(doc)
    customer_desk.apply_building_access_confirmation(doc)


def before_save(doc, _method=None):
    customer_desk.apply_customer_desk_building_defaults(doc)
    customer_desk.apply_building_access_confirmation(doc)


def after_save(doc, _method=None):
    planning.handle_building_after_save(doc)


def after_insert(doc, _method=None):
    planning.handle_building_after_save(doc)


def on_update(doc, _method=None):
    planning.handle_building_after_save(doc)
