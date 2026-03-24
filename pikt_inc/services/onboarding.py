from __future__ import annotations

import frappe


DEFAULT_COMPANY = "Pikt, inc."
DEFAULT_DEPARTMENT = "Operations - Pikt, inc."
DEFAULT_DESIGNATION = "Cleaner"
ONBOARDING_ROLE = "Employee Onboarding User"
PACKET_STATUS_VALUES = {"Invited", "In Progress", "Submitted", "Needs Review", "Complete"}


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def normalize_whitespace(value):
    return " ".join(clean(value).split())


def normalize_email(value, label):
    value = clean(value).lower()
    if not value:
        frappe.throw(f"{label} is required.")
    parts = value.split("@")
    if len(parts) != 2 or "." not in parts[1]:
        frappe.throw(f"Please enter a valid {label.lower()}.")
    return value


def split_name(full_name):
    full_name = normalize_whitespace(full_name)
    parts = full_name.split(" ")
    first_name = parts[0] if parts else ""
    last_name = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
    return first_name, last_name


def _role_name(row):
    if isinstance(row, dict):
        return clean(row.get("role"))
    return clean(getattr(row, "role", None))


def _set_roles(doc, rows):
    if hasattr(doc, "set"):
        doc.set("roles", rows)
    else:
        doc.roles = rows


def _assert_default_records_exist():
    checks = [
        ("Company", DEFAULT_COMPANY, "Default company Pikt, inc. was not found."),
        ("Department", DEFAULT_DEPARTMENT, "Default department Operations - Pikt, inc. was not found."),
        ("Designation", DEFAULT_DESIGNATION, "Default designation Cleaner was not found."),
    ]
    for doctype_name, record_name, message in checks:
        if not frappe.db.exists(doctype_name, record_name):
            frappe.throw(message)


def _find_existing_employee(email):
    lookups = [
        {"user_id": email},
        {"personal_email": email},
        {"company_email": email},
    ]
    for filters in lookups:
        employee_name = frappe.db.get_value("Employee", filters, "name")
        if employee_name:
            return employee_name
    return ""


def _remove_employee_role(user_doc):
    if hasattr(user_doc, "reload"):
        user_doc.reload()
    else:
        user_doc = frappe.get_doc("User", clean(getattr(user_doc, "name", None) or getattr(user_doc, "email", None)))

    roles_to_keep = []
    for role_row in getattr(user_doc, "roles", None) or []:
        role_name = _role_name(role_row)
        if role_name and role_name != "Employee":
            roles_to_keep.append({"role": role_name})
    _set_roles(user_doc, roles_to_keep)
    user_doc.user_type = "System User"
    user_doc.save(ignore_permissions=True)
    return user_doc


def provision_employee_onboarding_request(doc):
    email = normalize_email(getattr(doc, "employee_email", None), "Email address")
    full_name = normalize_whitespace(getattr(doc, "full_name", None))
    if not full_name:
        frappe.throw("Full name is required.")
    if not getattr(doc, "start_date", None):
        frappe.throw("Start date is required.")

    doc.employee_email = email
    doc.full_name = full_name
    doc.manager_email = frappe.session.user

    if frappe.db.exists("User", email):
        frappe.throw("A User already exists for this email address.")

    existing_employee = _find_existing_employee(email)
    if existing_employee:
        frappe.throw("An Employee already exists for this email address.")

    if frappe.db.exists("Employee Onboarding Packet", email) or frappe.db.exists(
        "Employee Onboarding Packet", {"employee_email": email}
    ):
        frappe.throw("An onboarding packet already exists for this email address.")

    _assert_default_records_exist()

    first_name, last_name = split_name(full_name)

    user_doc = frappe.get_doc(
        {
            "doctype": "User",
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "enabled": 1,
            "user_type": "System User",
            "send_welcome_email": 1,
            "roles": [{"role": ONBOARDING_ROLE}],
        }
    )
    user_doc.insert(ignore_permissions=True)

    employee_doc = frappe.get_doc(
        {
            "doctype": "Employee",
            "naming_series": "HR-EMP-",
            "first_name": first_name,
            "last_name": last_name,
            "date_of_joining": doc.start_date,
            "status": "Active",
            "company": DEFAULT_COMPANY,
            "department": DEFAULT_DEPARTMENT,
            "designation": DEFAULT_DESIGNATION,
            "personal_email": email,
            "prefered_contact_email": "Personal Email",
            "user_id": email,
            "create_user_permission": 1,
        }
    )
    employee_doc.insert(ignore_permissions=True)

    user_doc = _remove_employee_role(user_doc)

    packet_doc = frappe.get_doc(
        {
            "doctype": "Employee Onboarding Packet",
            "user_id": email,
            "employee": employee_doc.name,
            "employee_name": clean(getattr(employee_doc, "employee_name", None)) or full_name,
            "employee_email": email,
            "start_date": doc.start_date,
            "manager_email": doc.manager_email,
            "first_name": first_name,
            "last_name": last_name,
            "personal_email": email,
            "packet_status": "Invited",
            "invited_on": frappe.utils.today(),
        }
    )
    packet_doc.insert(ignore_permissions=True)

    frappe.db.set_value("Employee Onboarding Packet", packet_doc.name, "owner", email, update_modified=False)
    frappe.db.set_value("Employee", employee_doc.name, "custom_onboarding_packet", packet_doc.name, update_modified=False)

    doc.user = user_doc.name
    doc.employee = employee_doc.name
    doc.onboarding_packet = packet_doc.name
    doc.request_status = "Invited"
    doc.provisioned_on = frappe.utils.now()
    doc.error_message = ""

    return {
        "user": user_doc.name,
        "employee": employee_doc.name,
        "packet": packet_doc.name,
        "request_status": doc.request_status,
    }


def _is_complete_packet(doc):
    missing = []
    required_fields = [
        ("first_name", "First Name"),
        ("mobile_number", "Mobile Number"),
        ("personal_email", "Personal Email"),
        ("street_address", "Street Address"),
        ("city", "City"),
        ("state", "State"),
        ("postal_code", "Postal Code"),
        ("emergency_contact_name", "Emergency Contact Name"),
        ("emergency_contact_phone", "Emergency Contact Phone"),
        ("emergency_contact_relationship", "Emergency Contact Relationship"),
        ("transportation_status", "Transportation Status"),
        ("preferred_shift_preference", "Preferred Shift"),
        ("availability_notes", "Availability Notes"),
        ("government_id_upload", "Government ID Upload"),
        ("acknowledge_attendance_policy", "Attendance Policy Acknowledgement"),
        ("acknowledge_site_safety_policy", "Site Safety Policy Acknowledgement"),
        ("acknowledge_communication_policy", "Communication Policy Acknowledgement"),
        ("acknowledge_data_handling_policy", "Data Handling Policy Acknowledgement"),
    ]
    for fieldname, label in required_fields:
        if not getattr(doc, fieldname, None):
            missing.append(label)
    return missing


def _compose_current_address(doc):
    address_line = ""
    if getattr(doc, "city", None) or getattr(doc, "state", None) or getattr(doc, "postal_code", None):
        address_line = ", ".join([part for part in [clean(getattr(doc, "city", None)), clean(getattr(doc, "state", None))] if part]).strip()
        postal_code = clean(getattr(doc, "postal_code", None))
        if postal_code:
            address_line = f"{address_line} {postal_code}".strip()

    current_address = clean(getattr(doc, "street_address", None))
    if address_line:
        current_address = f"{current_address}\n{address_line}".strip()
    return current_address


def sync_employee_onboarding_packet(doc):
    current_user = clean(frappe.session.user)
    if current_user == clean(getattr(doc, "user_id", None)) and clean(getattr(doc, "packet_status", None)) == "Complete":
        frappe.throw("This onboarding packet is already complete and can no longer be edited.")

    doc.first_name = normalize_whitespace(getattr(doc, "first_name", None))
    doc.last_name = normalize_whitespace(getattr(doc, "last_name", None))
    doc.employee_name = normalize_whitespace(f"{doc.first_name} {doc.last_name}") or clean(getattr(doc, "employee_name", None))

    personal_email = clean(getattr(doc, "personal_email", None))
    if personal_email:
        doc.personal_email = normalize_email(personal_email, "Personal email address")
    else:
        doc.personal_email = clean(getattr(doc, "employee_email", None))

    if not getattr(doc, "invited_on", None):
        doc.invited_on = frappe.utils.today()

    missing = _is_complete_packet(doc)
    is_complete = len(missing) == 0
    packet_status = clean(getattr(doc, "packet_status", None)) or "Invited"
    if packet_status not in PACKET_STATUS_VALUES:
        packet_status = "Invited"

    if packet_status == "Complete":
        if not is_complete:
            frappe.throw(f"Cannot mark onboarding complete. Missing: {', '.join(missing)}")
        if not getattr(doc, "completed_on", None):
            doc.completed_on = frappe.utils.now()
        if not getattr(doc, "submitted_on", None):
            doc.submitted_on = frappe.utils.now()
    elif packet_status == "Needs Review":
        if is_complete and not getattr(doc, "submitted_on", None):
            doc.submitted_on = frappe.utils.now()
    elif is_complete:
        doc.packet_status = "Submitted"
        if not getattr(doc, "submitted_on", None):
            doc.submitted_on = frappe.utils.now()
        doc.completed_on = None
    elif packet_status == "Invited":
        if current_user == clean(getattr(doc, "user_id", None)):
            doc.packet_status = "In Progress"
        doc.completed_on = None
    else:
        doc.packet_status = "In Progress"
        doc.completed_on = None

    current_address = _compose_current_address(doc)

    employee_name = clean(getattr(doc, "employee", None))
    if employee_name and frappe.db.exists("Employee", employee_name):
        frappe.db.set_value(
            "Employee",
            employee_name,
            {
                "first_name": doc.first_name,
                "last_name": doc.last_name,
                "personal_email": doc.personal_email or clean(getattr(doc, "employee_email", None)),
                "prefered_contact_email": "Personal Email",
                "cell_number": clean(getattr(doc, "mobile_number", None)),
                "current_address": current_address,
                "person_to_be_contacted": clean(getattr(doc, "emergency_contact_name", None)),
                "emergency_phone_number": clean(getattr(doc, "emergency_contact_phone", None)),
                "relation": clean(getattr(doc, "emergency_contact_relationship", None)),
                "user_id": clean(getattr(doc, "user_id", None)),
                "date_of_joining": getattr(doc, "start_date", None),
                "custom_onboarding_packet": doc.name,
            },
            update_modified=False,
        )

    user_id = clean(getattr(doc, "user_id", None))
    if user_id and frappe.db.exists("User", user_id):
        frappe.db.set_value(
            "User",
            user_id,
            {
                "first_name": doc.first_name,
                "last_name": doc.last_name,
                "phone": clean(getattr(doc, "mobile_number", None)),
                "mobile_no": clean(getattr(doc, "mobile_number", None)),
            },
            update_modified=False,
        )

    request_name = frappe.db.get_value("Employee Onboarding Request", {"onboarding_packet": doc.name}, "name")
    if request_name:
        frappe.db.set_value(
            "Employee Onboarding Request",
            request_name,
            {
                "request_status": clean(getattr(doc, "packet_status", None)),
                "employee": employee_name,
                "user": user_id,
                "error_message": "",
            },
            update_modified=False,
        )

    return {
        "packet": doc.name,
        "packet_status": clean(getattr(doc, "packet_status", None)),
        "missing_count": len(missing),
    }
