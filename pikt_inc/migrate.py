from __future__ import annotations

import json

import frappe

from pikt_inc.services import customer_desk


_PERMISSION_FIELDS = (
	"select",
	"read",
	"write",
	"create",
	"delete",
	"submit",
	"cancel",
	"amend",
	"mask",
	"report",
	"export",
	"import",
	"share",
	"print",
	"email",
	"if_owner",
	"impersonate",
)

_BUILDING_CUSTOM_DOCPERMS = (
	{
		"role": "Accounts Manager",
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 0,
		"create": 0,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 1,
		"export": 1,
		"import": 0,
		"share": 0,
		"print": 1,
		"email": 1,
		"if_owner": 0,
		"impersonate": 0,
	},
	{
		"role": "Accounts User",
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 0,
		"create": 0,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 1,
		"export": 1,
		"import": 0,
		"share": 0,
		"print": 1,
		"email": 1,
		"if_owner": 0,
		"impersonate": 0,
	},
	{
		"role": "Digital Walkthrough Reviewer",
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 0,
		"create": 0,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 0,
		"export": 1,
		"import": 0,
		"share": 0,
		"print": 0,
		"email": 0,
		"if_owner": 0,
		"impersonate": 0,
	},
	{
		"role": "HR Manager",
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 1,
		"export": 1,
		"import": 0,
		"share": 1,
		"print": 1,
		"email": 1,
		"if_owner": 0,
		"impersonate": 0,
	},
	{
		"role": "HR User",
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 1,
		"export": 1,
		"import": 0,
		"share": 1,
		"print": 1,
		"email": 1,
		"if_owner": 0,
		"impersonate": 0,
	},
	{
		"role": "Maintenance Manager",
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 1,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 1,
		"export": 1,
		"import": 0,
		"share": 1,
		"print": 1,
		"email": 1,
		"if_owner": 0,
		"impersonate": 0,
	},
	{
		"role": "Maintenance User",
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 1,
		"export": 1,
		"import": 0,
		"share": 1,
		"print": 1,
		"email": 1,
		"if_owner": 0,
		"impersonate": 0,
	},
	{
		"role": "Sales Manager",
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 1,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 1,
		"export": 1,
		"import": 0,
		"share": 1,
		"print": 1,
		"email": 1,
		"if_owner": 0,
		"impersonate": 0,
	},
	{
		"role": "Sales User",
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 1,
		"export": 1,
		"import": 0,
		"share": 1,
		"print": 1,
		"email": 1,
		"if_owner": 0,
		"impersonate": 0,
	},
	{
		"role": "System Manager",
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 1,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 1,
		"export": 1,
		"import": 0,
		"share": 1,
		"print": 1,
		"email": 1,
		"if_owner": 0,
		"impersonate": 0,
	},
)

_CUSTOMER_DESK_BUILDING_DOCPERMS = (
	{
		"role": customer_desk.CUSTOMER_DESK_ROLE,
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": 1,
		"create": 1,
		"delete": 0,
		"submit": 0,
		"cancel": 0,
		"amend": 0,
		"mask": 0,
		"report": 0,
		"export": 0,
		"import": 0,
		"share": 0,
		"print": 0,
		"email": 0,
		"if_owner": 0,
		"impersonate": 0,
	},
)

_CUSTOMER_DESK_READONLY_DOCPERMS = {
	"Service Agreement": (
		{
			"role": customer_desk.CUSTOMER_DESK_ROLE,
			"permlevel": 0,
			"select": 1,
			"read": 1,
			"write": 0,
			"create": 0,
			"delete": 0,
			"submit": 0,
			"cancel": 0,
			"amend": 0,
			"mask": 0,
			"report": 0,
			"export": 0,
			"import": 0,
			"share": 0,
			"print": 0,
			"email": 0,
			"if_owner": 0,
			"impersonate": 0,
		},
	),
	"Service Agreement Addendum": (
		{
			"role": customer_desk.CUSTOMER_DESK_ROLE,
			"permlevel": 0,
			"select": 1,
			"read": 1,
			"write": 0,
			"create": 0,
			"delete": 0,
			"submit": 0,
			"cancel": 0,
			"amend": 0,
			"mask": 0,
			"report": 0,
			"export": 0,
			"import": 0,
			"share": 0,
			"print": 0,
			"email": 0,
			"if_owner": 0,
			"impersonate": 0,
		},
	),
}


def _workspace_content() -> str:
	blocks = []
	for shortcut in customer_desk.CUSTOMER_DESK_WORKSPACE_SHORTCUTS:
		identifier = customer_desk.clean(shortcut["label"]).lower().replace(" ", "-")
		blocks.append(
			{
				"id": f"customer-desk-{identifier}",
				"type": "shortcut",
				"data": {"shortcut_name": shortcut["label"], "col": 4},
			}
		)
	return json.dumps(blocks, separators=(",", ":"))


def _permission_fields() -> tuple[str, ...]:
	meta = frappe.get_meta("Custom DocPerm")
	return tuple(field for field in _PERMISSION_FIELDS if meta.get_field(field))


def _permission_values(row: dict, permission_fields: tuple[str, ...]) -> dict:
	return {field: int(row.get(field) or 0) for field in permission_fields}


def _permission_key(row: dict) -> tuple[str, int]:
	return (row["role"], int(row.get("permlevel") or 0))


def _ensure_custom_docperms(doctype_name: str, desired_rows: tuple[dict, ...]) -> None:
	if not frappe.db.exists("DocType", doctype_name):
		return

	permission_fields = _permission_fields()
	desired_by_key = {_permission_key(row): row for row in desired_rows}
	existing_rows = frappe.get_all(
		"Custom DocPerm",
		filters={"parent": doctype_name},
		fields=["name", "role", "permlevel", *permission_fields],
		order_by="creation asc",
	)

	existing_by_key = {}
	rows_to_delete = []
	for row in existing_rows:
		key = _permission_key(row)
		if key not in desired_by_key or key in existing_by_key:
			rows_to_delete.append(row["name"])
			continue
		existing_by_key[key] = row

	for row_name in rows_to_delete:
		frappe.delete_doc("Custom DocPerm", row_name, force=1, ignore_permissions=True)

	for key, desired in desired_by_key.items():
		values = {
			"parent": doctype_name,
			"role": desired["role"],
			"permlevel": desired["permlevel"],
			**_permission_values(desired, permission_fields),
		}
		existing = existing_by_key.get(key)
		if not existing:
			frappe.get_doc({"doctype": "Custom DocPerm", **values}).insert(ignore_permissions=True)
			continue

		current_permissions = _permission_values(existing, permission_fields)
		if current_permissions == _permission_values(desired, permission_fields):
			continue

		doc = frappe.get_doc("Custom DocPerm", existing["name"])
		doc.update(values)
		doc.save(ignore_permissions=True)

	frappe.clear_cache(doctype=doctype_name)


def ensure_building_custom_docperms() -> None:
	ensure_customer_desk_role()
	_ensure_custom_docperms(
		"Building",
		_BUILDING_CUSTOM_DOCPERMS + _CUSTOMER_DESK_BUILDING_DOCPERMS,
	)


def ensure_customer_desk_role() -> None:
	existing = frappe.db.exists("Role", customer_desk.CUSTOMER_DESK_ROLE)
	if existing:
		role_doc = frappe.get_doc("Role", customer_desk.CUSTOMER_DESK_ROLE)
	else:
		role_doc = frappe.get_doc(
			{
				"doctype": "Role",
				"role_name": customer_desk.CUSTOMER_DESK_ROLE,
				"desk_access": 1,
				"home_page": customer_desk.CUSTOMER_DESK_HOME,
			}
		)
		role_doc.insert(ignore_permissions=True)
		return

	changed = False
	if int(getattr(role_doc, "desk_access", 0) or 0) != 1:
		role_doc.desk_access = 1
		changed = True
	if customer_desk.clean(getattr(role_doc, "home_page", None)) != customer_desk.CUSTOMER_DESK_HOME:
		role_doc.home_page = customer_desk.CUSTOMER_DESK_HOME
		changed = True
	if changed:
		role_doc.save(ignore_permissions=True)


def ensure_customer_desk_module_profile() -> None:
	module_names = {
		customer_desk.clean(row.get("name"))
		for row in frappe.get_all("Module Def", fields=["name"], order_by="name asc")
		if customer_desk.clean(row.get("name"))
	}
	desired_modules = sorted(module_names - {customer_desk.CUSTOMER_DESK_MODULE})
	desired_rows = [{"module": module_name} for module_name in desired_modules]

	existing = frappe.db.exists("Module Profile", customer_desk.CUSTOMER_DESK_PROFILE)
	if existing:
		doc = frappe.get_doc("Module Profile", customer_desk.CUSTOMER_DESK_PROFILE)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Module Profile",
				"module_profile_name": customer_desk.CUSTOMER_DESK_PROFILE,
				"block_modules": desired_rows,
			}
		)
		doc.insert(ignore_permissions=True)
		return

	changed = False
	if customer_desk.clean(getattr(doc, "module_profile_name", None)) != customer_desk.CUSTOMER_DESK_PROFILE:
		doc.module_profile_name = customer_desk.CUSTOMER_DESK_PROFILE
		changed = True

	current_modules = sorted(
		customer_desk.clean(getattr(row, "module", None) if not isinstance(row, dict) else row.get("module"))
		for row in (getattr(doc, "block_modules", None) or [])
		if customer_desk.clean(getattr(row, "module", None) if not isinstance(row, dict) else row.get("module"))
	)
	if current_modules != desired_modules:
		doc.set("block_modules", desired_rows)
		changed = True

	if changed:
		doc.save(ignore_permissions=True)


def ensure_customer_desk_workspace() -> None:
	desired_shortcuts = [dict(row) for row in customer_desk.CUSTOMER_DESK_WORKSPACE_SHORTCUTS]
	desired_content = _workspace_content()
	desired_roles = [{"role": customer_desk.CUSTOMER_DESK_ROLE}]

	base_values = {
		"label": customer_desk.CUSTOMER_WORKSPACE,
		"title": customer_desk.CUSTOMER_WORKSPACE,
		"module": customer_desk.CUSTOMER_DESK_MODULE,
		"app": "pikt_inc",
		"type": "Workspace",
		"icon": "users",
		"public": 0,
		"is_hidden": 0,
		"hide_custom": 1,
		"content": desired_content,
	}

	existing = frappe.db.exists("Workspace", customer_desk.CUSTOMER_WORKSPACE)
	if existing:
		doc = frappe.get_doc("Workspace", customer_desk.CUSTOMER_WORKSPACE)
	else:
		doc = frappe.get_doc(
			{
				"doctype": "Workspace",
				**base_values,
				"shortcuts": desired_shortcuts,
				"roles": desired_roles,
			}
		)
		doc.insert(ignore_permissions=True)
		return

	changed = False
	for fieldname, value in base_values.items():
		if getattr(doc, fieldname, None) != value:
			setattr(doc, fieldname, value)
			changed = True

	current_shortcuts = [
		{
			"label": customer_desk.clean(getattr(row, "label", None) if not isinstance(row, dict) else row.get("label")),
			"link_to": customer_desk.clean(getattr(row, "link_to", None) if not isinstance(row, dict) else row.get("link_to")),
			"type": customer_desk.clean(getattr(row, "type", None) if not isinstance(row, dict) else row.get("type")),
			"doc_view": customer_desk.clean(getattr(row, "doc_view", None) if not isinstance(row, dict) else row.get("doc_view")),
			"color": customer_desk.clean(getattr(row, "color", None) if not isinstance(row, dict) else row.get("color")),
		}
		for row in (getattr(doc, "shortcuts", None) or [])
	]
	if current_shortcuts != desired_shortcuts:
		doc.set("shortcuts", desired_shortcuts)
		changed = True

	current_roles = sorted(
		customer_desk.clean(getattr(row, "role", None) if not isinstance(row, dict) else row.get("role"))
		for row in (getattr(doc, "roles", None) or [])
		if customer_desk.clean(getattr(row, "role", None) if not isinstance(row, dict) else row.get("role"))
	)
	if current_roles != [customer_desk.CUSTOMER_DESK_ROLE]:
		doc.set("roles", desired_roles)
		changed = True

	if changed:
		doc.save(ignore_permissions=True)


def ensure_customer_desk_title_fields() -> None:
	for doctype_name, fieldname in customer_desk.CUSTOMER_DESK_TITLE_FIELDS.items():
		if not frappe.db.exists("DocType", doctype_name):
			continue
		current = customer_desk.clean(frappe.db.get_value("DocType", doctype_name, "title_field"))
		if current == fieldname:
			continue
		frappe.db.set_value("DocType", doctype_name, "title_field", fieldname)
		frappe.clear_cache(doctype=doctype_name)


def ensure_customer_desk_custom_docperms() -> None:
	for doctype_name, rows in _CUSTOMER_DESK_READONLY_DOCPERMS.items():
		_ensure_custom_docperms(doctype_name, rows)


def ensure_customer_desk_records() -> None:
	ensure_customer_desk_role()
	ensure_customer_desk_module_profile()
	ensure_customer_desk_workspace()
	ensure_customer_desk_title_fields()
	ensure_customer_desk_custom_docperms()
