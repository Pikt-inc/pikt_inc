from __future__ import annotations

import frappe


_PORTAL_ROLE = "Customer Portal User"
_PORTAL_DOCTYPE_METADATA = {
	"Building": {
		"title_field": "building_name",
		"search_fields": "building_name,customer,city,state,postal_code",
		"show_title_field_in_link": 1,
	},
	"Building SOP": {
		"title_field": "building",
		"search_fields": "building,customer,version_number",
		"show_title_field_in_link": 1,
	},
	"Service Agreement": {
		"title_field": "agreement_name",
		"search_fields": "agreement_name,customer,template,signed_by_name,signed_by_email",
		"show_title_field_in_link": 1,
	},
	"Service Agreement Addendum": {
		"title_field": "addendum_name",
		"search_fields": "addendum_name,customer,service_agreement,quotation,sales_order,building",
		"show_title_field_in_link": 1,
	},
}

_PORTAL_MENU_TABLE_FIELDS = ("menu", "custom_menu")
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


def _clean(value) -> str:
	if value is None:
		return ""
	return str(value).strip()


def _portal_docperm_row(*, write: int = 0, print: int = 0) -> dict:
	return {
		"role": _PORTAL_ROLE,
		"permlevel": 0,
		"select": 1,
		"read": 1,
		"write": int(write),
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
		"print": int(print),
		"email": 0,
		"if_owner": 0,
		"impersonate": 0,
	}


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
	_portal_docperm_row(write=1),
)

_BUILDING_SOP_CUSTOM_DOCPERMS = (
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
	_portal_docperm_row(),
)

_SERVICE_AGREEMENT_CUSTOM_DOCPERMS = (_portal_docperm_row(print=1),)
_SERVICE_AGREEMENT_ADDENDUM_CUSTOM_DOCPERMS = (_portal_docperm_row(print=1),)


def _permission_fields() -> tuple[str, ...]:
	meta = frappe.get_meta("Custom DocPerm")
	return tuple(field for field in _PERMISSION_FIELDS if meta.get_field(field))


def _permission_values(row: dict, permission_fields: tuple[str, ...]) -> dict:
	return {field: int(row.get(field) or 0) for field in permission_fields}


def _permission_key(row: dict) -> tuple[str, int]:
	return (row["role"], int(row.get("permlevel") or 0))


def _ensure_doctype_metadata(doctype_name: str, updates: dict[str, object]) -> None:
	if not frappe.db.exists("DocType", doctype_name):
		return

	current = frappe.db.get_value("DocType", doctype_name, list(updates), as_dict=True) or {}
	changed_values = {}
	for fieldname, desired in updates.items():
		current_value = current.get(fieldname)
		if fieldname == "show_title_field_in_link":
			if int(current_value or 0) != int(desired or 0):
				changed_values[fieldname] = int(desired or 0)
			continue

		if _clean(current_value) != _clean(desired):
			changed_values[fieldname] = desired

	if not changed_values:
		return

	frappe.db.set_value("DocType", doctype_name, changed_values, update_modified=False)
	frappe.clear_cache(doctype=doctype_name)


def _prune_invalid_portal_menu_references() -> None:
	if not frappe.db.exists("DocType", "Portal Settings"):
		return

	settings = frappe.get_doc("Portal Settings")
	changed = False
	for fieldname in _PORTAL_MENU_TABLE_FIELDS:
		rows = list(getattr(settings, fieldname, None) or [])
		valid_rows = []
		for row in rows:
			reference_doctype = _clean(getattr(row, "reference_doctype", None))
			if reference_doctype and not frappe.db.exists("DocType", reference_doctype):
				changed = True
				continue
			valid_rows.append(row)
		if len(valid_rows) != len(rows):
			settings.set(fieldname, valid_rows)

	if not changed:
		return

	settings.save(ignore_permissions=True)
	frappe.clear_cache()


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
	_ensure_custom_docperms("Building", _BUILDING_CUSTOM_DOCPERMS)


def ensure_building_sop_custom_docperms() -> None:
	_ensure_custom_docperms("Building SOP", _BUILDING_SOP_CUSTOM_DOCPERMS)


def ensure_service_agreement_custom_docperms() -> None:
	_ensure_custom_docperms("Service Agreement", _SERVICE_AGREEMENT_CUSTOM_DOCPERMS)


def ensure_service_agreement_addendum_custom_docperms() -> None:
	_ensure_custom_docperms("Service Agreement Addendum", _SERVICE_AGREEMENT_ADDENDUM_CUSTOM_DOCPERMS)


def ensure_customer_portal_doctype_metadata() -> None:
	for doctype_name, updates in _PORTAL_DOCTYPE_METADATA.items():
		_ensure_doctype_metadata(doctype_name, updates)


def ensure_portal_settings_menu_references() -> None:
	_prune_invalid_portal_menu_references()
