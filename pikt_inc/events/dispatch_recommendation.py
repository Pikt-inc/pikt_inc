from __future__ import annotations

from pikt_inc.services.dispatch import incidents


def after_insert(doc, _method=None):
    incidents.handle_dispatch_recommendation_after_save(doc)


def on_update(doc, _method=None):
    incidents.handle_dispatch_recommendation_after_save(doc)
