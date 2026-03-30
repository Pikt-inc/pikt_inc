from __future__ import annotations

from pikt_inc.services import contact_request


def before_insert(doc, method=None):
    contact_request.prepare_contact_request(doc)
