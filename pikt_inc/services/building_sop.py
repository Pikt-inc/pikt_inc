from __future__ import annotations

import mimetypes
import uuid
from typing import Any

import frappe


BUILDING_SOP_DOCTYPE = "Building SOP"
BUILDING_SOP_ITEM_DOCTYPE = "Building SOP Item"
SSR_CHECKLIST_ITEM_DOCTYPE = "Site Shift Requirement Checklist Item"
SSR_CHECKLIST_PROOF_DOCTYPE = "Site Shift Requirement Checklist Proof"

BUILDING_CURRENT_SOP_FIELD = "current_sop"
SSR_SOP_FIELD = "custom_building_sop"
SSR_CHECKLIST_FIELD = "custom_checklist_items"
SSR_PROOF_FIELD = "custom_checklist_proofs"

SSR_CHECKLIST_STATUS_PENDING = "Pending"
SSR_CHECKLIST_STATUS_COMPLETED = "Completed"
SSR_CHECKLIST_STATUS_EXCEPTION = "Exception"
SSR_CHECKLIST_FINAL_STATES = {SSR_CHECKLIST_STATUS_COMPLETED, SSR_CHECKLIST_STATUS_EXCEPTION}
TERMINAL_REQUIREMENT_STATES = {"Completed", "Completed With Exception", "Unfilled Closed", "Cancelled"}


def clean(value: Any) -> str:
    return str(value or "").strip()


def truthy(value: Any) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "on"}


def _now_datetime():
    try:
        return frappe.utils.now_datetime()
    except Exception:
        return frappe.utils.get_datetime(frappe.utils.now())


def _to_datetime(value):
    if not value:
        return None
    try:
        return frappe.utils.get_datetime(value)
    except Exception:
        return None


def _today():
    try:
        return frappe.utils.getdate(frappe.utils.nowdate())
    except Exception:
        return _now_datetime().date()


def _safe_temporal_string(value: Any) -> str:
    raw = clean(value)
    if not raw:
        return ""
    if raw.startswith("0000-00-00") or "-00-" in raw:
        return ""
    return raw


def _copy_item_rows(item_rows: list[Any]) -> list[Any]:
    return list(item_rows or [])


def _field_value(doc, fieldname: str, default=None):
    if hasattr(doc, "get"):
        try:
            return doc.get(fieldname, default)
        except Exception:
            pass
    return getattr(doc, fieldname, default)


def _item_row_value(row: Any, fieldname: str, default=None):
    if row is None:
        return default
    if isinstance(row, dict):
        return row.get(fieldname, default)
    if hasattr(row, "get"):
        try:
            value = row.get(fieldname)
        except Exception:
            value = default
        if value is not None:
            return value
    return getattr(row, fieldname, default)


def normalize_sop_items(items: list[Any] | None) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in items or []:
        title = clean(_item_row_value(raw, "title") or _item_row_value(raw, "item_title"))
        description = clean(_item_row_value(raw, "description") or _item_row_value(raw, "item_description"))
        if not title:
            continue
        item_id = clean(_item_row_value(raw, "item_id") or _item_row_value(raw, "sop_item_id")) or uuid.uuid4().hex[:12]
        requires_photo_proof = _item_row_value(raw, "requires_photo_proof", 0)
        active = _item_row_value(raw, "active", 1)
        normalized.append(
            {
                "sop_item_id": item_id,
                "item_title": title,
                "item_description": description,
                "requires_photo_proof": 1 if truthy(requires_photo_proof) else 0,
                "active": 1 if active not in (0, "0", False) else 0,
            }
        )
    return normalized


def _load_building_row(building_name: str) -> dict[str, Any]:
    return frappe.db.get_value(
        "Building",
        clean(building_name),
        ["name", "customer", BUILDING_CURRENT_SOP_FIELD],
        as_dict=True,
    ) or {}


def _next_sop_version(building_name: str) -> int:
    rows = frappe.get_all(
        BUILDING_SOP_DOCTYPE,
        filters={"building": clean(building_name)},
        fields=["version_number"],
        order_by="version_number desc, creation desc",
        limit=1,
    )
    if not rows:
        return 1
    try:
        return int(rows[0].get("version_number") or 0) + 1
    except Exception:
        return 1


def _load_sop_rows(sop_name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sop_name = clean(sop_name)
    if not sop_name:
        return {}, []
    sop_row = frappe.db.get_value(
        BUILDING_SOP_DOCTYPE,
        sop_name,
        ["name", "building", "customer", "version_number", "supersedes", "modified", "owner"],
        as_dict=True,
    ) or {}
    item_rows = frappe.get_all(
        BUILDING_SOP_ITEM_DOCTYPE,
        filters={"parent": sop_name, "parenttype": BUILDING_SOP_DOCTYPE, "parentfield": "items"},
        fields=["name", "idx", "sop_item_id", "item_title", "item_description", "requires_photo_proof", "active"],
        order_by="idx asc",
        limit=500,
    )
    return sop_row, list(item_rows or [])


def get_current_building_sop(building_name: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    building_row = _load_building_row(building_name)
    current_sop = clean(building_row.get(BUILDING_CURRENT_SOP_FIELD))
    if current_sop:
        return _load_sop_rows(current_sop)

    rows = frappe.get_all(
        BUILDING_SOP_DOCTYPE,
        filters={"building": clean(building_name)},
        fields=["name"],
        order_by="version_number desc, creation desc",
        limit=1,
    )
    if not rows:
        return {}, []
    return _load_sop_rows(clean(rows[0].get("name")))


def shape_portal_sop_payload(building_name: str) -> dict[str, Any]:
    sop_row, item_rows = get_current_building_sop(building_name)
    return {
        "version": {
            "name": clean(sop_row.get("name")),
            "version_number": int(sop_row.get("version_number") or 0),
            "updated_on": sop_row.get("modified"),
            "updated_by": clean(sop_row.get("owner")),
            "item_count": len([row for row in item_rows if truthy(row.get("active") or 1)]),
        }
        if sop_row
        else None,
        "items": [
            {
                "item_id": clean(row.get("sop_item_id")),
                "title": clean(row.get("item_title")),
                "description": clean(row.get("item_description")),
                "requires_photo_proof": truthy(row.get("requires_photo_proof")),
                "active": truthy(row.get("active") or 1),
                "sort_order": int(row.get("idx") or 0),
            }
            for row in item_rows
            if truthy(row.get("active") or 1)
        ],
    }


def prepare_building_sop_for_insert(doc) -> None:
    building_name = clean(getattr(doc, "building", None))
    if not building_name:
        frappe.throw("Building is required.")

    building_row = _load_building_row(building_name)
    if not building_row:
        frappe.throw("Building is required.")

    if not clean(getattr(doc, "customer", None)):
        doc.customer = clean(building_row.get("customer"))

    if not getattr(doc, "version_number", None):
        doc.version_number = _next_sop_version(building_name)

    if not clean(getattr(doc, "supersedes", None)):
        doc.supersedes = clean(building_row.get(BUILDING_CURRENT_SOP_FIELD))

    normalized_items = normalize_sop_items(_copy_item_rows(_field_value(doc, "items", []) or []))
    doc.set("items", [])
    for row in normalized_items:
        doc.append("items", row)


def prevent_sop_mutation(doc) -> None:
    if getattr(doc, "flags", None) and getattr(doc.flags, "allow_sop_update", False):
        return
    if getattr(doc, "is_new", None):
        try:
            if doc.is_new():
                return
        except Exception:
            pass
    if doc.name and frappe.db.exists(BUILDING_SOP_DOCTYPE, doc.name):
        frappe.throw("Building SOP versions are immutable. Create a new version instead.")


def activate_building_sop(doc) -> None:
    building_name = clean(getattr(doc, "building", None))
    if not building_name:
        return
    frappe.db.set_value("Building", building_name, BUILDING_CURRENT_SOP_FIELD, doc.name)
    refresh_future_requirement_snapshots(building_name)


def create_building_sop_version(building_name: str, items: list[dict[str, Any]], *, source: str = "Portal") -> tuple[dict[str, Any], list[dict[str, Any]]]:
    building_row = _load_building_row(building_name)
    if not building_row:
        frappe.throw("That service location is not available.")

    doc = frappe.get_doc(
        {
            "doctype": BUILDING_SOP_DOCTYPE,
            "building": clean(building_name),
            "customer": clean(building_row.get("customer")),
            "source": clean(source) or "Portal",
            "items": normalize_sop_items(items),
        }
    )
    doc.insert(ignore_permissions=True)
    return _load_sop_rows(doc.name)


def build_requirement_checklist_rows_from_sop(building_name: str) -> tuple[str, list[dict[str, Any]]]:
    sop_row, item_rows = get_current_building_sop(building_name)
    sop_name = clean(sop_row.get("name"))
    normalized_rows = []
    for row in item_rows:
        if not truthy(row.get("active") or 1):
            continue
        normalized_rows.append(
            {
                "doctype": SSR_CHECKLIST_ITEM_DOCTYPE,
                "sop_item_id": clean(row.get("sop_item_id")),
                "item_title": clean(row.get("item_title")),
                "item_description": clean(row.get("item_description")),
                "requires_photo_proof": 1 if truthy(row.get("requires_photo_proof")) else 0,
                "item_status": SSR_CHECKLIST_STATUS_PENDING,
                "exception_note": "",
            }
        )
    return sop_name, normalized_rows


def sync_checklist_snapshot_for_requirement(requirement_doc_or_name, *, allow_started: bool = False) -> bool:
    requirement_doc = requirement_doc_or_name
    if not getattr(requirement_doc_or_name, "doctype", None):
        requirement_doc = frappe.get_doc("Site Shift Requirement", requirement_doc_or_name)

    if not requirement_doc:
        return False

    if not allow_started:
        arrival_start = _to_datetime(getattr(requirement_doc, "arrival_window_start", None))
        if arrival_start and arrival_start <= _now_datetime():
            return False
        if clean(getattr(requirement_doc, "status", None)) in TERMINAL_REQUIREMENT_STATES:
            return False
        if getattr(requirement_doc, "checked_in_at", None):
            return False

    sop_name, checklist_rows = build_requirement_checklist_rows_from_sop(clean(getattr(requirement_doc, "building", None)))
    existing_rows = list(_field_value(requirement_doc, SSR_CHECKLIST_FIELD, []) or [])
    existing_signature = _checklist_signature_from_rows(existing_rows)
    desired_signature = _checklist_signature_from_rows(checklist_rows)
    current_sop_name = clean(getattr(requirement_doc, SSR_SOP_FIELD, None))
    if current_sop_name == sop_name and existing_signature == desired_signature:
        return False

    requirement_doc.set(SSR_CHECKLIST_FIELD, [])
    for row in checklist_rows:
        requirement_doc.append(SSR_CHECKLIST_FIELD, row)
    requirement_doc.set(SSR_PROOF_FIELD, [])
    setattr(requirement_doc, SSR_SOP_FIELD, sop_name or None)
    requirement_doc.flags.ignore_permissions = True
    requirement_doc.save(ignore_permissions=True)
    return True


def refresh_future_requirement_snapshots(building_name: str) -> dict[str, int]:
    building_name = clean(building_name)
    if not building_name:
        return {"visited": 0, "updated": 0}

    rows = frappe.get_all(
        "Site Shift Requirement",
        filters={"building": building_name, "service_date": [">=", _today()]},
        fields=["name"],
        order_by="service_date asc, arrival_window_start asc, creation asc",
        limit=5000,
    )
    updated = 0
    for row in rows or []:
        try:
            if sync_checklist_snapshot_for_requirement(clean(row.get("name"))):
                updated += 1
        except Exception as exc:
            frappe.log_error(str(exc), f"Building SOP snapshot refresh {clean(row.get('name'))}")
    try:
        from .dispatch import routing as dispatch_routing

        dispatch_routing.mark_routes_dirty_for_building(building_name)
    except Exception:
        pass
    return {"visited": len(rows or []), "updated": updated}


def _get_requirement_history_rows(building_name: str, *, start: int, page_size: int) -> list[dict[str, Any]]:
    fields = [
        "name",
        "service_date",
        "arrival_window_start",
        "arrival_window_end",
        "status",
        "completion_status",
        "current_employee",
        SSR_SOP_FIELD,
        "modified",
    ]
    try:
        rows = frappe.get_all(
            "Site Shift Requirement",
            filters={"building": building_name},
            fields=fields,
            order_by="service_date desc, arrival_window_start desc, creation desc",
            start=start,
            limit=page_size + 1,
        )
        return list(rows or [])
    except Exception as exc:
        if hasattr(frappe, "log_error"):
            frappe.log_error(str(exc), f"Building SOP history fallback {building_name}")
        rows = frappe.db.sql(
            f"""
            select
                name,
                cast(service_date as char) as service_date,
                cast(arrival_window_start as char) as arrival_window_start,
                cast(arrival_window_end as char) as arrival_window_end,
                status,
                completion_status,
                current_employee,
                {SSR_SOP_FIELD},
                cast(modified as char) as modified
            from `tabSite Shift Requirement`
            where building = %s
            order by service_date desc, arrival_window_start desc, creation desc
            limit %s, %s
            """,
            (building_name, int(start or 0), int(page_size or 0) + 1),
            as_dict=True,
        )
        return list(rows or [])


def _get_requirement_checklist_rows(requirement_name: str) -> list[dict[str, Any]]:
    requirement_name = clean(requirement_name)
    if not requirement_name:
        return []
    rows = frappe.get_all(
        SSR_CHECKLIST_ITEM_DOCTYPE,
        filters={"parent": requirement_name, "parenttype": "Site Shift Requirement", "parentfield": SSR_CHECKLIST_FIELD},
        fields=["name", "idx", "sop_item_id", "item_title", "item_description", "requires_photo_proof", "item_status", "exception_note"],
        order_by="idx asc",
        limit=500,
    )
    return list(rows or [])


def _get_requirement_proof_rows(requirement_name: str) -> list[dict[str, Any]]:
    requirement_name = clean(requirement_name)
    if not requirement_name:
        return []
    rows = frappe.get_all(
        SSR_CHECKLIST_PROOF_DOCTYPE,
        filters={"parent": requirement_name, "parenttype": "Site Shift Requirement", "parentfield": SSR_PROOF_FIELD},
        fields=["name", "idx", "checklist_item_id", "proof_file", "proof_caption", "modified"],
        order_by="idx asc",
        limit=500,
    )
    return list(rows or [])


def _group_proofs_by_item(proof_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in proof_rows or []:
        grouped.setdefault(clean(row.get("checklist_item_id")), []).append(dict(row))
    return grouped


def shape_requirement_checklist(requirement_name: str, *, include_proofs: bool = False, proof_url_builder=None) -> list[dict[str, Any]]:
    checklist_rows = _get_requirement_checklist_rows(requirement_name)
    proof_rows = _get_requirement_proof_rows(requirement_name) if include_proofs else []
    proofs_by_item = _group_proofs_by_item(proof_rows)
    shaped = []
    for row in checklist_rows:
        item_id = clean(row.get("sop_item_id"))
        proof_items = []
        for proof in proofs_by_item.get(item_id, []):
            proof_name = clean(proof.get("name"))
            file_url = clean(proof.get("proof_file"))
            proof_items.append(
                {
                    "name": proof_name,
                    "label": clean(proof.get("proof_caption")) or file_url.rsplit("/", 1)[-1] or "Proof photo",
                    "url": proof_url_builder(proof_name) if callable(proof_url_builder) else "",
                }
            )
        shaped.append(
            {
                "item_id": item_id,
                "title": clean(row.get("item_title")),
                "description": clean(row.get("item_description")),
                "requires_photo_proof": truthy(row.get("requires_photo_proof")),
                "status": clean(row.get("item_status")) or SSR_CHECKLIST_STATUS_PENDING,
                "exception_note": clean(row.get("exception_note")),
                "sort_order": int(row.get("idx") or 0),
                "proofs": proof_items,
            }
        )
    return shaped


def _checklist_signature_from_rows(rows: list[dict[str, Any]]) -> str:
    parts = []
    for row in rows or []:
        parts.append(
            "||".join(
                [
                    clean(row.get("sop_item_id")),
                    clean(row.get("item_title")),
                    clean(row.get("item_description")),
                    "1" if truthy(row.get("requires_photo_proof")) else "0",
                ]
            )
        )
    return "\n".join(parts)


def build_requirement_checklist_signature(requirement_name: str) -> str:
    return _checklist_signature_from_rows(_get_requirement_checklist_rows(requirement_name))


def build_requirement_checklist_route_lines(requirement_name: str) -> list[str]:
    lines = []
    for row in _get_requirement_checklist_rows(requirement_name):
        title = clean(row.get("item_title"))
        description = clean(row.get("item_description"))
        label = title
        if description:
            label = f"{label}: {description}"
        if truthy(row.get("requires_photo_proof")):
            label = f"{label} [Photo proof required]"
        if label:
            lines.append(label)
    return lines


def validate_requirement_checklist(doc) -> None:
    checklist_rows = list(_field_value(doc, SSR_CHECKLIST_FIELD, []) or [])
    proof_rows = list(_field_value(doc, SSR_PROOF_FIELD, []) or [])
    proofs_by_item = _group_proofs_by_item(proof_rows)
    for row in checklist_rows:
        item_id = clean(getattr(row, "sop_item_id", None) or row.get("sop_item_id"))
        title = clean(getattr(row, "item_title", None) or row.get("item_title")) or "Checklist item"
        status = clean(getattr(row, "item_status", None) or row.get("item_status")) or SSR_CHECKLIST_STATUS_PENDING
        exception_note = clean(getattr(row, "exception_note", None) or row.get("exception_note"))
        requires_photo = truthy(getattr(row, "requires_photo_proof", None) or row.get("requires_photo_proof"))

        if status == SSR_CHECKLIST_STATUS_EXCEPTION and not exception_note:
            frappe.throw(f"{title} requires an exception note.")
        if status == SSR_CHECKLIST_STATUS_COMPLETED and requires_photo and not proofs_by_item.get(item_id):
            frappe.throw(f"{title} requires at least one proof photo before completion.")


def requirement_checklist_state(doc_or_name) -> dict[str, Any]:
    if getattr(doc_or_name, "doctype", None):
        checklist_rows = list(_field_value(doc_or_name, SSR_CHECKLIST_FIELD, []) or [])
        proof_rows = list(_field_value(doc_or_name, SSR_PROOF_FIELD, []) or [])
    else:
        checklist_rows = _get_requirement_checklist_rows(clean(doc_or_name))
        proof_rows = _get_requirement_proof_rows(clean(doc_or_name))

    if not checklist_rows:
        return {"enabled": False, "resolved": True, "final_state": "Completed", "has_exception": False}

    proofs_by_item = _group_proofs_by_item(proof_rows)
    has_exception = False
    for row in checklist_rows:
        item_id = clean(getattr(row, "sop_item_id", None) or row.get("sop_item_id"))
        status = clean(getattr(row, "item_status", None) or row.get("item_status")) or SSR_CHECKLIST_STATUS_PENDING
        requires_photo = truthy(getattr(row, "requires_photo_proof", None) or row.get("requires_photo_proof"))
        exception_note = clean(getattr(row, "exception_note", None) or row.get("exception_note"))

        if status == SSR_CHECKLIST_STATUS_EXCEPTION:
            if not exception_note:
                return {"enabled": True, "resolved": False, "final_state": "Completed With Exception", "has_exception": True}
            has_exception = True
            continue
        if status != SSR_CHECKLIST_STATUS_COMPLETED:
            return {"enabled": True, "resolved": False, "final_state": "Completed", "has_exception": has_exception}
        if requires_photo and not proofs_by_item.get(item_id):
            return {"enabled": True, "resolved": False, "final_state": "Completed", "has_exception": has_exception}

    return {
        "enabled": True,
        "resolved": True,
        "final_state": "Completed With Exception" if has_exception else "Completed",
        "has_exception": has_exception,
    }


def apply_requirement_completion_state(doc) -> str | None:
    state = requirement_checklist_state(doc)
    if not state.get("enabled"):
        return None
    final_state = clean(state.get("final_state")) or "Completed"
    doc.completion_status = final_state
    if clean(getattr(doc, "status", None)) in {"Completed", "Completed With Exception"}:
        doc.status = final_state
    return final_state


def get_building_service_history(building_name: str, *, page: int = 1, page_size: int = 5) -> dict[str, Any]:
    building_name = clean(building_name)
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 5), 20))
    start = (page - 1) * page_size

    rows = _get_requirement_history_rows(building_name, start=start, page_size=page_size)
    has_more = len(rows or []) > page_size
    rows = list(rows or [])[:page_size]

    visits = []
    for row in rows:
        checklist = shape_requirement_checklist(clean(row.get("name")), include_proofs=True)
        visits.append(
            {
                "name": clean(row.get("name")),
                "service_date": _safe_temporal_string(row.get("service_date")),
                "arrival_window_start": _safe_temporal_string(row.get("arrival_window_start")),
                "arrival_window_end": _safe_temporal_string(row.get("arrival_window_end")),
                "status": clean(row.get("completion_status")) or clean(row.get("status")),
                "raw_status": clean(row.get("status")),
                "completion_status": clean(row.get("completion_status")),
                "employee_label": clean(row.get("current_employee")),
                "sop_name": clean(row.get(SSR_SOP_FIELD)),
                "checklist_items": checklist,
                "has_checklist": bool(checklist),
                "modified": _safe_temporal_string(row.get("modified")),
            }
        )

    return {"page": page, "page_size": page_size, "has_more": has_more, "visits": visits}


def load_checklist_proof_for_download(proof_name: str) -> dict[str, Any]:
    proof_name = clean(proof_name)
    if not proof_name:
        return {}

    proof_row = frappe.db.get_value(
        SSR_CHECKLIST_PROOF_DOCTYPE,
        proof_name,
        ["name", "parent", "proof_file", "proof_caption"],
        as_dict=True,
    ) or {}
    if not proof_row:
        return {}

    parent_name = clean(proof_row.get("parent"))
    ssr_row = frappe.db.get_value("Site Shift Requirement", parent_name, ["name", "building"], as_dict=True) or {}
    building_row = frappe.db.get_value("Building", clean(ssr_row.get("building")), ["name", "customer"], as_dict=True) or {}
    return {
        "proof": proof_row,
        "requirement": ssr_row,
        "building": building_row,
    }


def get_proof_file_content(file_url: str) -> tuple[str, bytes, str]:
    file_url = clean(file_url)
    if not file_url:
        frappe.throw("No proof photo is attached to this checklist item.")

    file_rows = frappe.get_all(
        "File",
        filters={"file_url": file_url},
        fields=["name", "file_name"],
        limit=1,
    )
    file_name = clean(file_url)
    file_doc_name = ""
    if file_rows:
        file_doc_name = clean(file_rows[0].get("name"))
        file_name = clean(file_rows[0].get("file_name")) or file_name.rsplit("/", 1)[-1]
    elif frappe.db.exists("File", file_url):
        file_doc_name = file_url

    if not file_doc_name:
        frappe.throw("That proof photo file is not available.")

    file_doc = frappe.get_doc("File", file_doc_name)
    if hasattr(file_doc, "get_content"):
        content = file_doc.get_content()
    else:
        content = getattr(file_doc, "content", None) or getattr(file_doc, "filecontent", None)
    if content is None:
        frappe.throw("That proof photo file is not available.")
    if isinstance(content, str):
        content = content.encode("utf-8")
    content_type = mimetypes.guess_type(file_name)[0] or "application/octet-stream"
    return file_name, content, content_type
