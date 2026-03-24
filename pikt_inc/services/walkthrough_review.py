from __future__ import annotations

import frappe


REVIEWER_ROLE = "Digital Walkthrough Reviewer"
DESK_ROLE = "Desk User"
REVIEWER_PROFILE = "Digital Walkthrough Reviewer Desk"
REVIEWER_WORKSPACE = "Digital Walkthrough Review"
REVIEWER_APP = "erpnext"


def clean(value):
    if value is None:
        return ""
    return str(value).strip()


def _get_role_name(row):
    if isinstance(row, dict):
        return clean(row.get("role"))
    return clean(getattr(row, "role", None))


def validate_submission_review_link(doc):
    opportunity_name = clean(getattr(doc, "opportunity", None))
    submission_status = clean(getattr(doc, "status", None))

    if not opportunity_name:
        if submission_status == "Reviewed":
            frappe.throw("Link this walkthrough to an opportunity before marking it reviewed.")
        return {"status": "skipped", "reason": "missing_opportunity"}

    return {"status": "ok", "opportunity": opportunity_name}


def sync_submission_to_opportunity(doc):
    validation = validate_submission_review_link(doc)
    if validation.get("status") == "skipped":
        return validation

    opportunity_name = validation["opportunity"]
    submission_status = clean(getattr(doc, "status", None))
    walkthrough_file = clean(getattr(doc, "walkthrough_file", None))
    submission_name = clean(getattr(doc, "name", None))
    opp = frappe.get_doc("Opportunity", opportunity_name)
    changed = False

    if walkthrough_file and clean(getattr(opp, "digital_walkthrough_file", None)) != walkthrough_file:
        opp.digital_walkthrough_file = walkthrough_file
        changed = True

    if clean(getattr(opp, "latest_digital_walkthrough", None)) != submission_name:
        opp.latest_digital_walkthrough = submission_name
        changed = True

    if walkthrough_file and (
        (not getattr(opp, "digital_walkthrough_received_on", None))
        or clean(getattr(opp, "digital_walkthrough_file", None)) == walkthrough_file
    ):
        opp.digital_walkthrough_received_on = frappe.utils.now()
        changed = True

    current_status = clean(getattr(opp, "digital_walkthrough_status", None))
    if submission_status == "Reviewed":
        if current_status != "Reviewed":
            opp.digital_walkthrough_status = "Reviewed"
            changed = True
    elif current_status != "Reviewed" and current_status != "Submitted":
        opp.digital_walkthrough_status = "Submitted"
        changed = True

    if changed:
        opp.save(ignore_permissions=True)

    return {
        "status": "updated" if changed else "noop",
        "opportunity": opportunity_name,
        "submission": submission_name,
    }


def apply_reviewer_module_profile(doc):
    roles = {_get_role_name(row) for row in (getattr(doc, "roles", None) or []) if _get_role_name(row)}

    if REVIEWER_ROLE in roles and DESK_ROLE not in roles:
        doc.append("roles", {"role": DESK_ROLE})
        roles.add(DESK_ROLE)

    non_reviewer_roles = roles - {REVIEWER_ROLE, DESK_ROLE}
    workspace_exists = bool(frappe.db.exists("Workspace", REVIEWER_WORKSPACE))

    if REVIEWER_ROLE in roles and not non_reviewer_roles:
        doc.module_profile = REVIEWER_PROFILE
        if workspace_exists:
            doc.default_workspace = REVIEWER_WORKSPACE
        elif clean(getattr(doc, "default_workspace", None)) == REVIEWER_WORKSPACE:
            doc.default_workspace = None
        doc.default_app = REVIEWER_APP
        return {
            "status": "reviewer_profile_applied",
            "workspace_applied": int(workspace_exists),
        }

    if clean(getattr(doc, "module_profile", None)) == REVIEWER_PROFILE:
        doc.module_profile = None
        if clean(getattr(doc, "default_workspace", None)) == REVIEWER_WORKSPACE:
            doc.default_workspace = None
        if clean(getattr(doc, "default_app", None)) == REVIEWER_APP:
            doc.default_app = None
        return {"status": "reviewer_profile_cleared"}

    return {"status": "noop"}
