from __future__ import annotations

import frappe

from ._request_payload import collect_request_payload
from pikt_inc.services import contact_request as contact_request_service


@frappe.whitelist(allow_guest=True)
def submit_contact_request(**kwargs):
    return contact_request_service.submit_contact_request(form_dict=collect_request_payload(kwargs))
