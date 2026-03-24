from __future__ import annotations

from pikt_inc.services import onboarding


def before_insert(doc, _method=None):
    onboarding.provision_employee_onboarding_request(doc)
