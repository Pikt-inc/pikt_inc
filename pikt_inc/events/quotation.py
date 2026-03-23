from __future__ import annotations

from pikt_inc.services import public_quote


def before_submit(doc, method=None):
    public_quote.prepare_public_quotation_acceptance(doc)


def after_insert(doc, method=None):
    public_quote.mark_opportunity_reviewed_on_quotation(doc)
