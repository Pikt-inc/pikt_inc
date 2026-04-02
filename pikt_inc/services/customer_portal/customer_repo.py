from __future__ import annotations

import frappe

from ..contracts.common import ResponseModel, clean_str


USER_FIELDS = ["name", "custom_customer"]
CUSTOMER_FIELDS = ["name", "customer_name"]


class UserRecord(ResponseModel):
    name: str = ""
    custom_customer: str = ""


class CustomerRecord(ResponseModel):
    name: str = ""
    customer_name: str = ""


def get_user(user_name: str) -> UserRecord | None:
    user_name = clean_str(user_name)
    if not user_name:
        return None
    row = frappe.db.get_value("User", user_name, USER_FIELDS, as_dict=True)
    if not row:
        return None
    return UserRecord.model_validate(row)


def get_customer(customer_name: str) -> CustomerRecord | None:
    customer_name = clean_str(customer_name)
    if not customer_name:
        return None
    row = frappe.db.get_value("Customer", customer_name, CUSTOMER_FIELDS, as_dict=True)
    if not row:
        return None
    return CustomerRecord.model_validate(row)
