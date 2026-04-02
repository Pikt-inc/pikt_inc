from __future__ import annotations

import frappe

from ..contracts.common import ResponseModel, clean_str


USER_FIELDS = ["name", "email", "custom_customer"]
CUSTOMER_FIELDS = ["name", "customer_name", "customer_primary_contact", "customer_primary_address", "tax_id"]
CONTACT_FIELDS = [
    "name",
    "first_name",
    "last_name",
    "email_id",
    "phone",
    "mobile_no",
    "designation",
    "address",
]


class UserRecord(ResponseModel):
    name: str = ""
    email: str = ""
    custom_customer: str = ""


class CustomerRecord(ResponseModel):
    name: str = ""
    customer_name: str = ""
    customer_primary_contact: str = ""
    customer_primary_address: str = ""
    tax_id: str = ""


class ContactRecord(ResponseModel):
    name: str = ""
    first_name: str = ""
    last_name: str = ""
    email_id: str = ""
    phone: str = ""
    mobile_no: str = ""
    designation: str = ""
    address: str = ""


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


def get_contact(contact_name: str) -> ContactRecord | None:
    contact_name = clean_str(contact_name)
    if not contact_name:
        return None
    row = frappe.db.get_value("Contact", contact_name, CONTACT_FIELDS, as_dict=True)
    if not row:
        return None
    return ContactRecord.model_validate(row)


def find_customer_contact_by_email(customer_name: str, email_address: str) -> str:
    customer_name = clean_str(customer_name)
    email_address = clean_str(email_address).lower()
    if not customer_name or not email_address:
        return ""

    rows = frappe.db.sql(
        """
        select
            c.name
        from `tabContact` c
        inner join `tabDynamic Link` dl
            on dl.parent = c.name
           and dl.parenttype = 'Contact'
           and dl.link_doctype = 'Customer'
        where dl.link_name = %s
          and lower(ifnull(c.email_id, '')) = %s
        order by c.is_primary_contact desc, c.modified desc, c.creation desc
        limit 1
        """,
        (customer_name, email_address),
        as_dict=True,
    )
    if not rows:
        return ""
    return clean_str(rows[0].get("name"))
