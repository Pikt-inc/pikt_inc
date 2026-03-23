from __future__ import annotations

import frappe

from . import shared


ROUTE_SIGNATURE_BUILDING_FIELDS = [
    "building_name",
    "address_line_1",
    "address_line_2",
    "city",
    "state",
    "postal_code",
    "site_notes",
    "access_notes",
    "alarm_notes",
    "site_supervisor_name",
    "site_supervisor_phone",
]


def acquire_route_lock(employee: str, service_date):
    lock_key = f"dispatch_route::{employee}::{service_date}"
    try:
        rows = frappe.db.sql("SELECT GET_LOCK(%s, 0) AS acquired", (lock_key,), as_dict=True)
        acquired = bool(rows and shared.as_int(rows[0].get("acquired"), 0) == 1)
    except Exception:
        acquired = True
    return {"lock_key": lock_key, "acquired": acquired}


def release_route_lock(lock_key: str | None):
    if not lock_key:
        return
    try:
        frappe.db.sql("SELECT RELEASE_LOCK(%s)", (lock_key,))
    except Exception:
        pass


def determine_ordered_requirement_names(existing_index_map: dict, assigned_rows: list[dict], membership_changed: bool) -> list[str]:
    if membership_changed:
        return [row["name"] for row in assigned_rows if row.get("name")]

    sortable = []
    for row in assigned_rows:
        requirement_name = row.get("name")
        if not requirement_name:
            continue
        stop_index = existing_index_map.get(requirement_name, 9999) or 9999
        sortable.append(
            [
                stop_index,
                str(row.get("arrival_window_start") or row.get("arrival_window_end") or ""),
                str(row.get("creation") or ""),
                requirement_name,
            ]
        )
    sortable.sort()
    return [row[3] for row in sortable]


def compute_route_window(stop_rows: list[dict]):
    route_start = None
    route_end = None
    earliest_start = None
    latest_end = None

    for stop in stop_rows:
        stop_start = stop.get("arrival_window_start") or stop.get("arrival_window_end")
        stop_end = stop.get("arrival_window_end") or stop.get("arrival_window_start")
        stop_start_dt = shared.to_datetime(stop_start)
        stop_end_dt = shared.to_datetime(stop_end)

        if stop_start_dt and (not earliest_start or stop_start_dt < earliest_start):
            earliest_start = stop_start_dt
            route_start = stop_start
        if stop_end_dt and (not latest_end or stop_end_dt > latest_end):
            latest_end = stop_end_dt
            route_end = stop_end

    notify_at = frappe.utils.add_to_date(route_start, hours=-2, as_string=True) if route_start else None
    return route_start, route_end, notify_at


def build_route_signature(stop_rows: list[dict], building_rows: dict[str, dict]) -> str:
    signature_parts = []
    for stop in stop_rows:
        building_name = shared.clean(stop.get("building"))
        building_row = building_rows.get(building_name) or {}
        stop_index = shared.as_int(stop.get("stop_index"), 0)
        signature_parts.append(
            "||".join(
                [
                    str(stop_index),
                    shared.clean(stop.get("site_shift_requirement")),
                    building_name,
                    str(stop.get("arrival_window_start") or ""),
                    str(stop.get("arrival_window_end") or ""),
                    shared.clean(building_row.get("building_name")),
                    shared.clean(building_row.get("address_line_1")),
                    shared.clean(building_row.get("address_line_2")),
                    shared.clean(building_row.get("city")),
                    shared.clean(building_row.get("state")),
                    shared.clean(building_row.get("postal_code")),
                    shared.clean(building_row.get("site_notes")),
                    shared.clean(building_row.get("access_notes")),
                    shared.clean(building_row.get("alarm_notes")),
                    shared.clean(building_row.get("site_supervisor_name")),
                    shared.clean(building_row.get("site_supervisor_phone")),
                ]
            )
        )
    return "\n".join(signature_parts)


def get_building_signature_rows(building_names: list[str]) -> dict[str, dict]:
    rows = {}
    for building_name in building_names:
        building_name = shared.clean(building_name)
        if not building_name or building_name in rows:
            continue
        rows[building_name] = shared.get_building_fields(building_name, ROUTE_SIGNATURE_BUILDING_FIELDS) or {}
    return rows


def should_mark_for_resend(last_emailed_hash: str, current_signature: str, route_start) -> bool:
    if not shared.clean(last_emailed_hash) or not route_start:
        return False
    route_start_dt = shared.to_datetime(route_start)
    if not route_start_dt or route_start_dt <= shared.now_datetime():
        return False
    return current_signature != last_emailed_hash


def normalize_dispatch_route(doc):
    prior_route = None
    if doc.name and frappe.db.exists("Dispatch Route", doc.name):
        prior_route = frappe.db.get_value(
            "Dispatch Route",
            doc.name,
            ["route_start", "status"],
            as_dict=True,
        ) or {}

    original_route_start = prior_route.get("route_start") if prior_route else doc.route_start
    original_status = shared.clean((prior_route or {}).get("status") or doc.status)

    sortable = []
    for row in doc.stops or []:
        requirement_name = shared.clean(row.site_shift_requirement)
        if not requirement_name:
            continue
        sortable.append([shared.as_int(row.stop_index, 9999), requirement_name])
    sortable.sort()

    rebuilt_rows = []
    for index, (_, requirement_name) in enumerate(sortable, start=1):
        ssr_row = frappe.db.get_value(
            "Site Shift Requirement",
            requirement_name,
            ["building", "arrival_window_start", "arrival_window_end"],
            as_dict=True,
        ) or {}
        rebuilt_rows.append(
            {
                "doctype": "Dispatch Route Stop",
                "site_shift_requirement": requirement_name,
                "stop_index": index,
                "building": ssr_row.get("building"),
                "arrival_window_start": ssr_row.get("arrival_window_start"),
                "arrival_window_end": ssr_row.get("arrival_window_end"),
            }
        )

    doc.set("stops", rebuilt_rows)

    if doc.stops:
        route_start, route_end, notify_at = compute_route_window(doc.stops)
        doc.route_start = route_start
        doc.route_end = route_end
        doc.notify_at = notify_at
        doc.status = "Ready"
    else:
        doc.route_start = None
        doc.route_end = None
        doc.notify_at = None
        original_start_dt = shared.to_datetime(original_route_start)
        if original_status == "Completed":
            doc.status = "Completed"
        elif original_start_dt and original_start_dt <= shared.now_datetime():
            doc.status = "Completed"
        else:
            doc.status = "Cancelled"

    building_rows = get_building_signature_rows([row.get("building") for row in doc.stops or []])
    current_signature = build_route_signature(doc.stops or [], building_rows)
    doc.needs_resend = 1 if should_mark_for_resend(doc.last_emailed_hash, current_signature, doc.route_start) else 0


def reconcile_routes(site_shift_requirement=None, trigger_source="manual"):
    stats = {
        "trigger_source": shared.clean(trigger_source) or "manual",
        "keys": 0,
        "created": 0,
        "updated": 0,
        "cancelled": 0,
        "completed": 0,
        "duplicates_cancelled": 0,
        "errors": 0,
        "skipped_locked": 0,
        "routes": [],
    }

    keys = {}
    site_shift_requirement = shared.clean(site_shift_requirement)
    if site_shift_requirement and frappe.db.exists("Site Shift Requirement", site_shift_requirement):
        ssr_row = frappe.db.get_value(
            "Site Shift Requirement",
            site_shift_requirement,
            ["current_employee", "service_date", "custom_dispatch_route"],
            as_dict=True,
        ) or {}
        if ssr_row.get("current_employee") and ssr_row.get("service_date"):
            keys[f"{ssr_row.get('current_employee')}::{ssr_row.get('service_date')}"] = {
                "employee": ssr_row.get("current_employee"),
                "service_date": ssr_row.get("service_date"),
            }
        if ssr_row.get("custom_dispatch_route") and frappe.db.exists("Dispatch Route", ssr_row.get("custom_dispatch_route")):
            route_row = frappe.db.get_value(
                "Dispatch Route",
                ssr_row.get("custom_dispatch_route"),
                ["employee", "service_date"],
                as_dict=True,
            ) or {}
            if route_row.get("employee") and route_row.get("service_date"):
                keys[f"{route_row.get('employee')}::{route_row.get('service_date')}"] = {
                    "employee": route_row.get("employee"),
                    "service_date": route_row.get("service_date"),
                }
    else:
        horizon_start = frappe.utils.add_days(frappe.utils.nowdate(), -1)
        assigned_rows = frappe.get_all(
            "Site Shift Requirement",
            filters={"status": "Assigned", "service_date": [">=", horizon_start]},
            fields=["current_employee", "service_date"],
            limit=5000,
        )
        for row in assigned_rows:
            if row.get("current_employee") and row.get("service_date"):
                keys[f"{row.get('current_employee')}::{row.get('service_date')}"] = {
                    "employee": row.get("current_employee"),
                    "service_date": row.get("service_date"),
                }

        route_rows = frappe.get_all(
            "Dispatch Route",
            filters={"service_date": [">=", horizon_start]},
            fields=["employee", "service_date"],
            limit=5000,
        )
        for row in route_rows:
            if row.get("employee") and row.get("service_date"):
                keys[f"{row.get('employee')}::{row.get('service_date')}"] = {
                    "employee": row.get("employee"),
                    "service_date": row.get("service_date"),
                }

    stats["keys"] = len(keys)

    for route_key in sorted(keys):
        payload = keys[route_key]
        employee = payload.get("employee")
        service_date = payload.get("service_date")
        if not employee or not service_date:
            continue

        lock = acquire_route_lock(employee, service_date)
        if not lock["acquired"]:
            stats["skipped_locked"] += 1
            continue

        try:
            existing_routes = frappe.get_all(
                "Dispatch Route",
                filters={"employee": employee, "service_date": service_date},
                fields=["name", "creation", "status", "route_start"],
                order_by="creation asc",
                limit=50,
            )
            assigned_rows = frappe.get_all(
                "Site Shift Requirement",
                filters={
                    "current_employee": employee,
                    "service_date": service_date,
                    "status": "Assigned",
                },
                fields=["name", "building", "arrival_window_start", "arrival_window_end", "creation"],
                order_by="arrival_window_start asc, creation asc",
                limit=5000,
            )

            if not existing_routes and not assigned_rows:
                continue

            if existing_routes:
                route_doc = frappe.get_doc("Dispatch Route", existing_routes[0]["name"])
            else:
                route_doc = frappe.get_doc(
                    {
                        "doctype": "Dispatch Route",
                        "employee": employee,
                        "service_date": service_date,
                        "status": "Ready",
                    }
                )

            original_route_start = route_doc.route_start
            previous_status = shared.clean(route_doc.status)
            previous_start = str(route_doc.route_start or "")
            previous_end = str(route_doc.route_end or "")
            previous_notify = str(route_doc.notify_at or "")

            existing_names = []
            existing_index_map = {}
            previous_stop_rows = []
            for stop in route_doc.stops or []:
                requirement_name = shared.clean(stop.site_shift_requirement)
                if not requirement_name:
                    continue
                existing_names.append(requirement_name)
                existing_index_map[requirement_name] = shared.as_int(stop.stop_index, 0)
                previous_stop_rows.append(
                    {
                        "site_shift_requirement": requirement_name,
                        "stop_index": shared.as_int(stop.stop_index, 0),
                        "building": stop.building,
                        "arrival_window_start": stop.arrival_window_start,
                        "arrival_window_end": stop.arrival_window_end,
                    }
                )

            row_map = {row.get("name"): row for row in assigned_rows if row.get("name")}
            desired_names = [name for name in row_map]
            membership_changed = sorted(existing_names) != sorted(desired_names)
            ordered_names = determine_ordered_requirement_names(existing_index_map, assigned_rows, membership_changed)

            stop_rows = []
            for index, requirement_name in enumerate(ordered_names, start=1):
                row = row_map.get(requirement_name) or {}
                stop_rows.append(
                    {
                        "site_shift_requirement": requirement_name,
                        "stop_index": index,
                        "building": row.get("building"),
                        "arrival_window_start": row.get("arrival_window_start"),
                        "arrival_window_end": row.get("arrival_window_end"),
                    }
                )

            previous_buildings = get_building_signature_rows([row.get("building") for row in previous_stop_rows])
            desired_buildings = get_building_signature_rows([row.get("building") for row in stop_rows])
            previous_signature = build_route_signature(previous_stop_rows, previous_buildings)
            desired_signature = build_route_signature(stop_rows, desired_buildings)

            route_doc.employee = employee
            route_doc.service_date = service_date
            route_doc.set("stops", [])
            for stop_row in stop_rows:
                route_doc.append("stops", stop_row)

            if stop_rows:
                route_start, route_end, notify_at = compute_route_window(stop_rows)
                next_status = "Ready"
            else:
                route_start = None
                route_end = None
                notify_at = None
                original_start_dt = shared.to_datetime(original_route_start)
                if original_start_dt and original_start_dt <= shared.now_datetime():
                    next_status = "Completed"
                else:
                    next_status = "Cancelled"

            route_doc.route_start = route_start
            route_doc.route_end = route_end
            route_doc.notify_at = notify_at
            route_doc.status = next_status

            if route_doc.is_new():
                route_doc.insert(ignore_permissions=True)
                stats["created"] += 1
            else:
                changed = any(
                    [
                        previous_signature != desired_signature,
                        previous_status != shared.clean(next_status),
                        previous_start != str(route_start or ""),
                        previous_end != str(route_end or ""),
                        previous_notify != str(notify_at or ""),
                    ]
                )
                if changed:
                    route_doc.save(ignore_permissions=True)
                    stats["updated"] += 1

            keep_names = {name: True for name in ordered_names}
            for requirement_name in ordered_names:
                current_link = frappe.db.get_value("Site Shift Requirement", requirement_name, "custom_dispatch_route")
                if current_link != route_doc.name:
                    frappe.db.set_value("Site Shift Requirement", requirement_name, "custom_dispatch_route", route_doc.name)

            linked_rows = frappe.get_all(
                "Site Shift Requirement",
                filters={"custom_dispatch_route": route_doc.name},
                fields=["name"],
                limit=5000,
            )
            for linked_row in linked_rows:
                requirement_name = linked_row.get("name")
                if requirement_name and not keep_names.get(requirement_name):
                    frappe.db.set_value("Site Shift Requirement", requirement_name, "custom_dispatch_route", None)

            if len(existing_routes) > 1:
                for duplicate_row in existing_routes[1:]:
                    duplicate_doc = frappe.get_doc("Dispatch Route", duplicate_row["name"])
                    duplicate_doc.set("stops", [])
                    duplicate_doc.route_start = None
                    duplicate_doc.route_end = None
                    duplicate_doc.notify_at = None
                    duplicate_doc.status = "Cancelled"
                    duplicate_doc.save(ignore_permissions=True)

                    duplicate_links = frappe.get_all(
                        "Site Shift Requirement",
                        filters={"custom_dispatch_route": duplicate_row["name"]},
                        fields=["name"],
                        limit=5000,
                    )
                    for linked_row in duplicate_links:
                        frappe.db.set_value("Site Shift Requirement", linked_row.get("name"), "custom_dispatch_route", None)
                    stats["duplicates_cancelled"] += 1

            if not ordered_names:
                if route_doc.status == "Cancelled":
                    stats["cancelled"] += 1
                elif route_doc.status == "Completed":
                    stats["completed"] += 1

            stats["routes"].append(route_doc.name)
        except Exception as exc:
            stats["errors"] += 1
            frappe.log_error(str(exc), "Dispatch Route reconcile")
        finally:
            release_route_lock(lock["lock_key"])

    return stats


def choose_route_recipient(employee_row: dict) -> str | None:
    user_id = shared.clean((employee_row or {}).get("user_id"))
    if user_id and frappe.db.exists("User", user_id):
        if frappe.db.get_value("User", user_id, "enabled"):
            return user_id

    company_email = shared.clean((employee_row or {}).get("company_email"))
    if company_email:
        return company_email

    personal_email = shared.clean((employee_row or {}).get("personal_email"))
    if personal_email:
        return personal_email

    return None


def build_route_context(route_name: str, now_value=None):
    now_dt = shared.to_datetime(now_value) if now_value else shared.now_datetime()
    route_doc = frappe.get_doc("Dispatch Route", route_name)
    if shared.clean(route_doc.status) != "Ready" or not route_doc.stops:
        return None

    route_start_dt = shared.to_datetime(route_doc.route_start)
    if not route_start_dt:
        frappe.db.set_value("Dispatch Route", route_doc.name, "delivery_error", "Route is missing route_start.")
        return None
    if route_start_dt <= now_dt:
        return None

    employee_row = frappe.db.get_value(
        "Employee",
        route_doc.employee,
        ["employee_name", "user_id", "company_email", "personal_email"],
        as_dict=True,
    ) if route_doc.employee else {}

    recipient = choose_route_recipient(employee_row or {})
    stop_rows = []
    stop_blocks = []

    for stop in route_doc.stops or []:
        ssr_row = frappe.db.get_value(
            "Site Shift Requirement",
            stop.site_shift_requirement,
            ["building", "arrival_window_start", "arrival_window_end"],
            as_dict=True,
        ) if stop.site_shift_requirement else {}

        building_name = shared.clean((ssr_row or {}).get("building") or stop.building)
        building_row = shared.get_building_fields(building_name, ROUTE_SIGNATURE_BUILDING_FIELDS) or {}

        stop_start = (ssr_row or {}).get("arrival_window_start") or stop.arrival_window_start
        stop_end = (ssr_row or {}).get("arrival_window_end") or stop.arrival_window_end
        stop_index = shared.as_int(stop.stop_index, 0)

        stop_rows.append(
            {
                "site_shift_requirement": stop.site_shift_requirement,
                "stop_index": stop_index,
                "building": building_name,
                "arrival_window_start": stop_start,
                "arrival_window_end": stop_end,
            }
        )

        stop_title = shared.clean(building_row.get("building_name")) or building_name or "Assigned Building"
        stop_start_label = str(stop_start or "TBD")
        stop_end_label = str(stop_end or "TBD")
        try:
            stop_start_label = frappe.utils.format_datetime(stop_start)
        except Exception:
            pass
        try:
            stop_end_label = frappe.utils.format_datetime(stop_end)
        except Exception:
            pass

        address_parts = []
        address_line_1 = shared.clean(building_row.get("address_line_1"))
        address_line_2 = shared.clean(building_row.get("address_line_2"))
        if address_line_1:
            address_parts.append(f"{address_line_1} {address_line_2}".strip())
        city_line = shared.clean(building_row.get("city"))
        state = shared.clean(building_row.get("state"))
        postal_code = shared.clean(building_row.get("postal_code"))
        if state:
            city_line = f"{city_line}, {state}".strip(", ") if city_line else state
        if postal_code:
            city_line = f"{city_line} {postal_code}".strip()
        if city_line:
            address_parts.append(city_line)

        lines = [f"<li><strong>Stop {stop_index}: {shared.escape_text(stop_title)}</strong></li>"]
        lines.append(
            f"<li>Arrival Window: {shared.escape_text(stop_start_label)} to {shared.escape_text(stop_end_label)}</li>"
        )
        for address_line in address_parts:
            lines.append(f"<li>Address: {shared.escape_text(address_line)}</li>")

        supervisor_name = shared.clean(building_row.get("site_supervisor_name"))
        supervisor_phone = shared.clean(building_row.get("site_supervisor_phone"))
        if supervisor_name:
            supervisor_line = f"{supervisor_name} ({supervisor_phone})" if supervisor_phone else supervisor_name
            lines.append(f"<li>Site Contact: {shared.escape_text(supervisor_line)}</li>")
        if building_row.get("site_notes"):
            lines.append(f"<li>Site Notes: {shared.escape_multiline(building_row.get('site_notes'))}</li>")
        if building_row.get("access_notes"):
            lines.append(f"<li>Access Notes: {shared.escape_multiline(building_row.get('access_notes'))}</li>")
        if building_row.get("alarm_notes"):
            lines.append(f"<li>Alarm Notes: {shared.escape_multiline(building_row.get('alarm_notes'))}</li>")
        stop_blocks.append("<ul>" + "".join(lines) + "</ul>")

    building_rows = get_building_signature_rows([row.get("building") for row in stop_rows])
    intro_name = shared.clean((employee_row or {}).get("employee_name")) or route_doc.employee
    return {
        "route_doc": route_doc,
        "route_start_dt": route_start_dt,
        "current_signature": build_route_signature(stop_rows, building_rows),
        "stop_blocks": stop_blocks,
        "recipient": recipient,
        "intro_name": intro_name,
    }


def send_due_route_emails(now_value=None):
    now_value = now_value or shared.now()
    now_dt = shared.to_datetime(now_value) or shared.now_datetime()
    horizon_start = frappe.utils.add_days(frappe.utils.nowdate(), -1)
    settings = shared.get_dispatch_settings()
    route_rows = frappe.get_all(
        "Dispatch Route",
        filters={
            "status": "Ready",
            "service_date": [">=", horizon_start],
            "notify_at": ["<=", now_value],
        },
        fields=["name"],
        order_by="notify_at asc",
        limit=5000,
    )

    stats = {"sent": 0, "skipped": 0, "errors": 0}
    for row in route_rows:
        route_name = row.get("name")
        route_header = frappe.db.get_value(
            "Dispatch Route",
            route_name,
            ["employee", "service_date"],
            as_dict=True,
        ) or {}
        if not route_header.get("employee") or not route_header.get("service_date"):
            stats["skipped"] += 1
            continue

        lock = acquire_route_lock(route_header.get("employee"), route_header.get("service_date"))
        if not lock["acquired"]:
            stats["skipped"] += 1
            continue

        try:
            context = build_route_context(route_name, now_value=now_value)
            if not context:
                stats["skipped"] += 1
                continue

            route_doc = context["route_doc"]
            sent_signature = context["current_signature"] or ""
            has_prior_email = bool(route_doc.last_emailed_hash)
            signature_changed = bool(has_prior_email and sent_signature != route_doc.last_emailed_hash)

            if route_doc.needs_resend and has_prior_email and not signature_changed:
                frappe.db.set_value("Dispatch Route", route_doc.name, "needs_resend", 0)
                route_doc.needs_resend = 0

            should_send = (not has_prior_email) or signature_changed
            if not should_send:
                stats["skipped"] += 1
                continue

            recipient = context.get("recipient")
            if not recipient:
                delivery_values = {
                    "delivery_error": "No user_id, company_email, or personal_email is available for this employee.",
                    "needs_resend": 1 if signature_changed and context["route_start_dt"] > now_dt else route_doc.needs_resend,
                }
                frappe.db.set_value("Dispatch Route", route_doc.name, delivery_values)
                stats["skipped"] += 1
                continue

            service_date_label = str(route_doc.service_date or "TBD")
            route_start_label = str(route_doc.route_start or "TBD")
            route_end_label = str(route_doc.route_end or "TBD")
            try:
                service_date_label = frappe.utils.format_date(route_doc.service_date)
            except Exception:
                pass
            try:
                route_start_label = frappe.utils.format_datetime(route_doc.route_start)
            except Exception:
                pass
            try:
                route_end_label = frappe.utils.format_datetime(route_doc.route_end)
            except Exception:
                pass

            subject_prefix = "Updated: " if route_doc.last_emailed_hash else ""
            subject = subject_prefix + "Cleaning Route for " + service_date_label
            message = "".join(
                [
                    "<p>Hello ",
                    shared.escape_text(context.get("intro_name") or "there"),
                    ",</p>",
                    "<p>Your cleaning route for <strong>",
                    shared.escape_text(service_date_label),
                    "</strong> is below.</p>",
                    "<p><strong>Route Window:</strong> ",
                    shared.escape_text(route_start_label),
                    " to ",
                    shared.escape_text(route_end_label),
                    "</p>",
                    "".join(context.get("stop_blocks") or []),
                    "<p>Please contact your supervisor if any stop details look incorrect.</p>",
                ]
            )

            frappe.sendmail(
                recipients=[recipient],
                subject=subject,
                message=message,
                sender=settings.get("sender_email") or shared.DEFAULT_SENDER_EMAIL,
                reference_doctype="Dispatch Route",
                reference_name=route_doc.name,
                now=True,
            )

            latest_context = build_route_context(route_name, now_value=now_value)
            resend_flag = 0
            if latest_context and latest_context.get("route_start_dt") and latest_context["route_start_dt"] > now_dt:
                latest_signature = latest_context.get("current_signature") or ""
                if latest_signature != sent_signature:
                    resend_flag = 1

            frappe.db.set_value(
                "Dispatch Route",
                route_doc.name,
                {
                    "last_emailed_on": shared.now(),
                    "last_emailed_hash": sent_signature,
                    "needs_resend": resend_flag,
                    "delivery_error": None,
                },
            )
            stats["sent"] += 1
        except Exception as exc:
            stats["errors"] += 1
            frappe.log_error(str(exc), "Dispatch Route Email Orchestrator route send")
            try:
                frappe.db.set_value("Dispatch Route", route_name, "delivery_error", str(exc))
            except Exception:
                pass
        finally:
            release_route_lock(lock["lock_key"])

    return stats


def handle_site_shift_requirement_after_save(doc):
    if not doc or not doc.name:
        return
    reconcile_routes(site_shift_requirement=doc.name, trigger_source="site_shift_requirement_save")
