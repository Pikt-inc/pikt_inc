from __future__ import annotations

from typing import Any

import frappe

from ...contracts.common import clean_str
from ..errors import CustomerPortalNotFoundError
from . import repo
from .models import ChecklistSessionItemRecord, ChecklistSessionRecord


def require_session(session_name: str) -> ChecklistSessionRecord:
    session = repo.get_session(session_name)
    if not session:
        raise CustomerPortalNotFoundError("That checklist session is not available.")
    return session


def require_session_item(session_name: str, item_key: str) -> ChecklistSessionItemRecord:
    item_key = clean_str(item_key)
    item = next(
        (
            row
            for row in repo.get_session_items(session_name)
            if row.item_key == item_key or row.name == item_key
        ),
        None,
    )
    if not item:
        raise CustomerPortalNotFoundError("Checklist session item not found.")
    return item


def ensure_active_session(building_name: str, service_date) -> ChecklistSessionRecord:
    existing = repo.get_active_session(building_name, service_date)
    if existing:
        return existing
    return repo.create_session(building_name, service_date)


def update_session_item(
    session_name: str,
    item_key: str,
    *,
    completed: bool | None = None,
    note: str | None = None,
    proof_image: str | None = None,
) -> tuple[ChecklistSessionRecord, ChecklistSessionItemRecord]:
    require_session(session_name)
    updated = repo.update_session_item(
        session_name,
        item_key,
        completed=completed,
        note=note,
        proof_image=proof_image,
    )
    if not updated:
        raise CustomerPortalNotFoundError("Checklist session item not found.")
    return updated


def complete_session(session_name: str) -> ChecklistSessionRecord:
    require_session(session_name)
    completed = repo.complete_session(session_name)
    if not completed:
        raise CustomerPortalNotFoundError("That checklist session is not available.")
    return completed


def upload_session_item_proof(session_name: str, item_key: str, uploaded=None) -> tuple[ChecklistSessionRecord, ChecklistSessionItemRecord]:
    uploaded = uploaded or (
        frappe.request.files.get("file")
        if getattr(frappe, "request", None) and getattr(frappe.request, "files", None)
        else None
    )
    if uploaded is None:
        raise CustomerPortalNotFoundError("A file upload is required.")

    require_session(session_name)
    require_session_item(session_name, item_key)

    file_name = clean_str(getattr(uploaded, "filename", "")) or "checklist-proof-upload"
    content = uploaded.read()
    if not content:
        raise CustomerPortalNotFoundError("Uploaded file was empty. Please choose the file again.")

    file_doc = frappe.get_doc(
        {
            "doctype": "File",
            "file_name": file_name,
            "is_private": 1,
            "attached_to_doctype": "Checklist Session",
            "attached_to_name": clean_str(session_name),
            "content": content,
        }
    )
    file_doc.save(ignore_permissions=True)

    return update_session_item(
        session_name,
        item_key,
        completed=True,
        proof_image=clean_str(file_doc.file_url),
    )
