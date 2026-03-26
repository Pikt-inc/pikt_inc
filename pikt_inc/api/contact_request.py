from __future__ import annotations

import frappe

from pikt_inc.services import contact_request as contact_request_service


@frappe.whitelist(allow_guest=True)
def submit_contact_request(**kwargs):
    return contact_request_service.submit_contact_request(form_dict=kwargs or frappe.form_dict)
