from __future__ import annotations

from pikt_inc.services.dispatch import staffing


def after_insert(doc, _method=None):
    staffing.handle_employee_checkin_after_insert(doc)
