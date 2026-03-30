from __future__ import annotations

from pikt_inc.services import public_intake


def before_insert(doc, method=None):
    public_intake.prepare_instant_quote_request(doc)
