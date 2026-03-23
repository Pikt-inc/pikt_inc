from __future__ import annotations

from pikt_inc.services.dispatch import planning


def after_save(doc, _method=None):
    planning.handle_recurring_service_rule_after_save(doc)
