from __future__ import annotations

from pikt_inc.services.dispatch import routing


def before_save(doc, _method=None):
    routing.normalize_dispatch_route(doc)
