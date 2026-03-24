from __future__ import annotations

from pikt_inc.services import onboarding


def before_save(doc, _method=None):
    onboarding.sync_employee_onboarding_packet(doc)
