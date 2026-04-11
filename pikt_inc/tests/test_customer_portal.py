from __future__ import annotations

import importlib
from datetime import date, datetime
from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch
import types

from pydantic import ValidationError

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()


APP_ROOT = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

if "frappe" not in sys.modules:
    fake_frappe = types.ModuleType("frappe")
    fake_utils = types.ModuleType("frappe.utils")
    fake_utils.get_url = lambda path="": f"https://example.test{path}"
    fake_frappe.db = types.SimpleNamespace(sql=lambda *args, **kwargs: [], get_value=lambda *args, **kwargs: None)
    fake_frappe.get_all = lambda *args, **kwargs: []
    fake_frappe.get_roles = lambda _user=None: []
    fake_frappe.local = types.SimpleNamespace(response={}, request=types.SimpleNamespace(get_json=lambda silent=True: None))
    fake_frappe.request = types.SimpleNamespace(data=None)
    fake_frappe.form_dict = {}
    fake_frappe.session = types.SimpleNamespace(user="Guest")
    fake_frappe.throw = lambda message, **_kwargs: (_ for _ in ()).throw(Exception(message))
    fake_frappe.whitelist = lambda **_kwargs: (lambda fn: fn)
    fake_frappe.utils = fake_utils
    sys.modules["frappe"] = fake_frappe
    sys.modules["frappe.utils"] = fake_utils


try:
    app_hooks = importlib.import_module("pikt_inc.hooks")
    portal = importlib.import_module("pikt_inc.services.customer_portal")
    portal_account = importlib.import_module("pikt_inc.services.customer_portal.account")
    portal_account_service = importlib.import_module("pikt_inc.services.customer_portal.account.service")
    portal_api = importlib.import_module("pikt_inc.api.customer_portal")
    portal_api_contracts = importlib.import_module("pikt_inc.api.customer_portal_contracts")
    portal_api_serializers = importlib.import_module("pikt_inc.api.customer_portal_serializers")
    portal_building = importlib.import_module("pikt_inc.services.customer_portal.building")
    portal_checklist = importlib.import_module("pikt_inc.services.customer_portal.checklist")
    portal_client = importlib.import_module("pikt_inc.services.customer_portal.client")
    retire_legacy_customer_portal_role = importlib.import_module(
        "pikt_inc.patches.post_model_sync.retire_legacy_customer_portal_role"
    )
except ModuleNotFoundError:
    app_hooks = importlib.import_module("pikt_inc.pikt_inc.hooks")
    portal = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal")
    portal_account = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal.account")
    portal_account_service = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal.account.service")
    portal_api = importlib.import_module("pikt_inc.pikt_inc.api.customer_portal")
    portal_api_contracts = importlib.import_module("pikt_inc.pikt_inc.api.customer_portal_contracts")
    portal_api_serializers = importlib.import_module("pikt_inc.pikt_inc.api.customer_portal_serializers")
    portal_building = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal.building")
    portal_checklist = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal.checklist")
    portal_client = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal.client")
    retire_legacy_customer_portal_role = importlib.import_module(
        "pikt_inc.pikt_inc.patches.post_model_sync.retire_legacy_customer_portal_role"
    )


PATCHES_PATH = Path(__file__).resolve().parents[1] / "patches.txt"


class FakeDB:
    def __init__(self, dataset):
        self.dataset = dataset

    def sql(self, _query, params=None, as_dict=False):
        params = list(params or [])
        if len(params) >= 2:
            customer_name = params[0]
            email_id = str(params[1] or "").strip().lower()
            rows = []
            for row in self.dataset.get("contact_links", []):
                if row.get("customer_name") != customer_name:
                    continue
                if str(row.get("email_id") or "").strip().lower() != email_id:
                    continue
                rows.append({"name": row.get("contact_name")})
            return rows
        return []

    def get_value(self, doctype, name, fields, as_dict=False):
        source = self.dataset.get(doctype, {})
        row = source.get(name)
        if row is None:
            return None
        if isinstance(fields, list):
            result = {field: row.get(field) for field in fields}
            return result if as_dict else result
        return row.get(fields)

    def exists(self, doctype, name):
        return name in self.dataset.get(doctype, {})


def fake_get_all_factory(dataset):
    def fake_get_all(doctype, filters=None, fields=None, order_by=None, limit=None, **_kwargs):
        rows = dataset.get(f"{doctype}_list")
        if rows is None:
            source = dataset.get(doctype, {})
            rows = list(source.values()) if isinstance(source, dict) else list(source)
        rows = [dict(row) for row in rows]
        filters = filters or {}

        def matches_operator(actual, operator, expected):
            if operator in {"=", "=="}:
                return actual == expected
            if operator == "!=":
                return actual != expected
            if operator == "in":
                return actual in {item for item in expected or []}
            raise AssertionError(f"Unsupported filter operator in test harness: {operator}")

        def matches(row):
            if isinstance(filters, list):
                for clause in filters:
                    if len(clause) == 3:
                        field, operator, expected = clause
                    elif len(clause) == 4:
                        _doctype, field, operator, expected = clause
                    else:
                        raise AssertionError(f"Unsupported filter clause in test harness: {clause}")
                    if not matches_operator(row.get(field), str(operator), expected):
                        return False
                return True

            for key, value in filters.items():
                if isinstance(value, list) and value:
                    operator = str(value[0])
                    expected = value[1] if len(value) > 1 else None
                    if not matches_operator(row.get(key), operator, expected):
                        return False
                    continue
                if row.get(key) != value:
                    return False
            return True

        filtered = [row for row in rows if matches(row)]
        if order_by:
            clauses = [clause.strip() for clause in order_by.split(",")]
            for clause in reversed(clauses):
                parts = clause.split()
                field = parts[0]
                direction = parts[1].lower() if len(parts) > 1 else "asc"
                filtered.sort(key=lambda row: str(row.get(field) or ""), reverse=(direction == "desc"))
        if limit is not None:
            filtered = filtered[: int(limit)]
        if fields:
            return [{field: row.get(field) for field in fields} for row in filtered]
        return filtered

    return fake_get_all


class TestCustomerPortal(TestCase):
    def setUp(self):
        self.dataset = {
            "contact_links": [
                {
                    "customer_name": "CUST-1",
                    "email_id": "portal@example.com",
                    "contact_name": "CONTACT-1",
                }
            ],
            "User": {
                "portal@example.com": {
                    "name": "portal@example.com",
                    "email": "portal@example.com",
                    "custom_customer": "CUST-1",
                },
                "unlinked@example.com": {
                    "name": "unlinked@example.com",
                    "email": "unlinked@example.com",
                    "custom_customer": "",
                },
            },
            "Customer": {
                "CUST-1": {
                    "name": "CUST-1",
                    "customer_name": "Portal Customer LLC",
                    "customer_primary_contact": "CONTACT-BILLING",
                    "customer_primary_address": "ADDR-1",
                    "tax_id": "99-1234567",
                }
            },
            "Contact": {
                "CONTACT-1": {
                    "name": "CONTACT-1",
                    "first_name": "Pat",
                    "last_name": "Portal",
                    "email_id": "portal@example.com",
                    "phone": "512-555-0101",
                    "mobile_no": "",
                    "designation": "Office Manager",
                    "address": "ADDR-PORTAL",
                },
                "CONTACT-BILLING": {
                    "name": "CONTACT-BILLING",
                    "first_name": "Bill",
                    "last_name": "Payable",
                    "email_id": "billing@example.com",
                    "phone": "512-555-0133",
                    "mobile_no": "",
                    "designation": "Accounts Payable",
                    "address": "ADDR-1",
                },
            },
            "Building": {
                "BUILD-1": {
                    "name": "BUILD-1",
                    "customer": "CUST-1",
                    "building_name": "Headquarters",
                    "active": "1",
                    "current_checklist_template": "CHK-TPL-1",
                    "address_line_1": "123 Market St",
                    "address_line_2": "Suite 300",
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": "78701",
                    "site_notes": "Front entrance only.",
                    "creation": "2026-03-01 08:00:00",
                    "modified": "2026-03-06 12:00:00",
                },
                "BUILD-OTHER": {
                    "name": "BUILD-OTHER",
                    "customer": "CUST-2",
                    "building_name": "Other Site",
                    "active": "1",
                    "current_checklist_template": "CHK-TPL-2",
                    "address_line_1": "999 Elsewhere",
                    "address_line_2": "",
                    "city": "Dallas",
                    "state": "TX",
                    "postal_code": "75001",
                    "site_notes": "Out of scope.",
                    "creation": "2026-03-02 08:00:00",
                    "modified": "2026-03-07 12:00:00",
                },
            },
            "Building_list": [
                {
                    "name": "BUILD-1",
                    "customer": "CUST-1",
                    "building_name": "Headquarters",
                    "active": "1",
                    "current_checklist_template": "CHK-TPL-1",
                    "address_line_1": "123 Market St",
                    "address_line_2": "Suite 300",
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": "78701",
                    "site_notes": "Front entrance only.",
                    "creation": "2026-03-01 08:00:00",
                    "modified": "2026-03-06 12:00:00",
                },
                {
                    "name": "BUILD-OTHER",
                    "customer": "CUST-2",
                    "building_name": "Other Site",
                    "active": "1",
                    "current_checklist_template": "CHK-TPL-2",
                    "address_line_1": "999 Elsewhere",
                    "address_line_2": "",
                    "city": "Dallas",
                    "state": "TX",
                    "postal_code": "75001",
                    "site_notes": "Out of scope.",
                    "creation": "2026-03-02 08:00:00",
                    "modified": "2026-03-07 12:00:00",
                },
            ],
            "Checklist Session": {
                "CS-1": {
                    "name": "CS-1",
                    "building": "BUILD-1",
                    "service_date": "2026-03-09",
                    "checklist_template": "CHK-TPL-1",
                    "status": "completed",
                    "started_at": "2026-03-09 18:00:00",
                    "completed_at": "2026-03-09 19:15:00",
                    "worker": "Jordan Tech",
                    "session_notes": "Completed without issues.",
                    "creation": "2026-03-09 17:55:00",
                    "modified": "2026-03-09 19:15:00",
                },
                "CS-IN-PROGRESS": {
                    "name": "CS-IN-PROGRESS",
                    "building": "BUILD-1",
                    "service_date": "2026-03-10",
                    "checklist_template": "CHK-TPL-1",
                    "status": "in_progress",
                    "started_at": "2026-03-10 18:00:00",
                    "completed_at": None,
                    "worker": "Jordan Tech",
                    "session_notes": "Still open.",
                    "creation": "2026-03-10 17:55:00",
                    "modified": "2026-03-10 18:30:00",
                },
                "CS-OTHER": {
                    "name": "CS-OTHER",
                    "building": "BUILD-OTHER",
                    "service_date": "2026-03-11",
                    "checklist_template": "CHK-TPL-2",
                    "status": "completed",
                    "started_at": "2026-03-11 18:00:00",
                    "completed_at": "2026-03-11 19:15:00",
                    "worker": "Other Tech",
                    "session_notes": "Out of scope.",
                    "creation": "2026-03-11 17:55:00",
                    "modified": "2026-03-11 19:15:00",
                },
            },
            "Checklist Session_list": [
                {
                    "name": "CS-1",
                    "building": "BUILD-1",
                    "service_date": "2026-03-09",
                    "checklist_template": "CHK-TPL-1",
                    "status": "completed",
                    "started_at": "2026-03-09 18:00:00",
                    "completed_at": "2026-03-09 19:15:00",
                    "worker": "Jordan Tech",
                    "session_notes": "Completed without issues.",
                    "creation": "2026-03-09 17:55:00",
                    "modified": "2026-03-09 19:15:00",
                },
                {
                    "name": "CS-IN-PROGRESS",
                    "building": "BUILD-1",
                    "service_date": "2026-03-10",
                    "checklist_template": "CHK-TPL-1",
                    "status": "in_progress",
                    "started_at": "2026-03-10 18:00:00",
                    "completed_at": None,
                    "worker": "Jordan Tech",
                    "session_notes": "Still open.",
                    "creation": "2026-03-10 17:55:00",
                    "modified": "2026-03-10 18:30:00",
                },
                {
                    "name": "CS-OTHER",
                    "building": "BUILD-OTHER",
                    "service_date": "2026-03-11",
                    "checklist_template": "CHK-TPL-2",
                    "status": "completed",
                    "started_at": "2026-03-11 18:00:00",
                    "completed_at": "2026-03-11 19:15:00",
                    "worker": "Other Tech",
                    "session_notes": "Out of scope.",
                    "creation": "2026-03-11 17:55:00",
                    "modified": "2026-03-11 19:15:00",
                },
            ],
            "Checklist Session Item_list": [
                {
                    "name": "CSI-1",
                    "parent": "CS-1",
                    "parenttype": "Checklist Session",
                    "parentfield": "items",
                    "idx": "1",
                    "item_key": "restrooms",
                    "category": "job_completion",
                    "sort_order": "1",
                    "title_snapshot": "Restrooms sanitized",
                    "description_snapshot": "Disinfect restroom touchpoints.",
                    "requires_image": "1",
                    "allow_notes": "1",
                    "is_required": "1",
                    "completed": "1",
                    "completed_at": "2026-03-09 18:45:00",
                    "note": "Verification complete.",
                    "proof_image": "/private/files/restroom-proof.jpg",
                },
                {
                    "name": "CSI-2",
                    "parent": "CS-1",
                    "parenttype": "Checklist Session",
                    "parentfield": "items",
                    "idx": "2",
                    "item_key": "trash",
                    "category": "job_completion",
                    "sort_order": "2",
                    "title_snapshot": "Trash removed",
                    "description_snapshot": "Empty all cans and replace liners.",
                    "requires_image": "0",
                    "allow_notes": "1",
                    "is_required": "1",
                    "completed": "1",
                    "completed_at": "2026-03-09 19:00:00",
                    "note": "All clear.",
                    "proof_image": "",
                },
                {
                    "name": "CSI-OTHER",
                    "parent": "CS-OTHER",
                    "parenttype": "Checklist Session",
                    "parentfield": "items",
                    "idx": "1",
                    "item_key": "other",
                    "category": "job_completion",
                    "sort_order": "1",
                    "title_snapshot": "Other task",
                    "description_snapshot": "Out of scope.",
                    "requires_image": "1",
                    "allow_notes": "1",
                    "is_required": "1",
                    "completed": "1",
                    "completed_at": "2026-03-11 18:30:00",
                    "note": "Nope.",
                    "proof_image": "/private/files/other-proof.jpg",
                },
            ],
        }
        self.frappe = portal_account_service.frappe
        self.frappe.db = FakeDB(self.dataset)
        self.frappe.get_all = fake_get_all_factory(self.dataset)
        self.frappe.get_roles = lambda _user=None: ["Customer"]
        self.frappe.session = types.SimpleNamespace(user="portal@example.com")
        self.frappe.local = types.SimpleNamespace(response={}, request=types.SimpleNamespace(get_json=lambda silent=True: None))
        self.frappe.request = types.SimpleNamespace(data=None)
        self.frappe.form_dict = {}

    def _install_get_all_spy(self):
        self.get_all_calls = []

        def fake_get_all_with_spy(doctype, filters=None, fields=None, order_by=None, limit=None, **kwargs):
            self.get_all_calls.append(
                {
                    "doctype": doctype,
                    "filters": filters,
                    "fields": fields,
                    "order_by": order_by,
                    "limit": limit,
                }
            )
            return fake_get_all_factory(self.dataset)(
                doctype,
                filters=filters,
                fields=fields,
                order_by=order_by,
                limit=limit,
                **kwargs,
            )

        self.frappe.get_all = fake_get_all_with_spy

    def _session_query_calls(self):
        return [call for call in getattr(self, "get_all_calls", []) if call["doctype"] == "Checklist Session"]

    def test_package_surface_is_reduced_and_explicit(self):
        self.assertEqual(
            sorted(portal.__all__),
            sorted([
                "CustomerBuildingHistory",
                "CustomerJobDetail",
                "CustomerOverview",
                "CustomerPortalAccessError",
                "CustomerPortalNotFoundError",
                "ChecklistPortalBuildingDetail",
                "ChecklistSessionItemMutation",
                "ProofFileContent",
                "complete_checklist_session",
                "download_client_job_proof",
                "ensure_checklist_session",
                "get_checklist_building",
                "get_client_building",
                "get_client_job",
                "get_client_overview",
                "list_checklist_buildings",
                "update_checklist_session_item",
                "upload_checklist_session_item_proof",
            ]),
        )
        self.assertFalse(hasattr(portal, "CustomerPortalContext"))
        self.assertFalse(hasattr(portal, "CustomerPortalPrincipal"))
        self.assertFalse(hasattr(portal, "CustomerPortalBuilding"))
        self.assertFalse(hasattr(portal, "CustomerPortalSession"))
        self.assertFalse(hasattr(portal, "CustomerPortalSessionItem"))
        self.assertFalse(hasattr(portal, "ClientBuildingRequest"))
        self.assertFalse(hasattr(portal, "ClientBuildingResponse"))
        self.assertFalse(hasattr(portal, "FileDownload"))
        self.assertFalse(hasattr(portal, "list_customer_completed_sessions"))
        self.assertFalse(hasattr(portal, "ScopedJobDetailRead"))

    def test_resolve_context_returns_principal_only_for_linked_customer_user(self):
        context = portal_account.resolve_customer_principal()

        self.assertIsInstance(context, portal_account.CustomerPortalPrincipal)
        self.assertEqual(set(context.model_dump().keys()), {"session_user", "customer_name", "customer_display"})
        self.assertEqual(context.session_user, "portal@example.com")
        self.assertEqual(context.customer_name, "CUST-1")
        self.assertEqual(context.customer_display, "Portal Customer LLC")

    def test_resolve_context_rejects_invalid_portal_users(self):
        with self.assertRaisesRegex(portal.CustomerPortalAccessError, "Sign in to access your customer portal"):
            self.frappe.session = types.SimpleNamespace(user="Guest")
            portal_account.resolve_customer_principal()

        with self.assertRaisesRegex(portal.CustomerPortalAccessError, "does not have customer portal access"):
            self.frappe.session = types.SimpleNamespace(user="portal@example.com")
            self.frappe.get_roles = lambda _user=None: ["Employee"]
            portal_account.resolve_customer_principal()

        with self.assertRaisesRegex(portal.CustomerPortalAccessError, "missing a linked customer"):
            self.frappe.session = types.SimpleNamespace(user="unlinked@example.com")
            self.frappe.get_roles = lambda _user=None: ["Customer"]
            portal_account.resolve_customer_principal()

        with self.assertRaisesRegex(portal.CustomerPortalAccessError, "linked customer record could not be loaded"):
            self.dataset["User"]["portal@example.com"]["custom_customer"] = "MISSING"
            self.frappe.session = types.SimpleNamespace(user="portal@example.com")
            self.frappe.get_roles = lambda _user=None: ["Customer"]
            portal_account.resolve_customer_principal()

    def test_repo_records_normalize_flags_and_temporals(self):
        building = portal_building.get_building("BUILD-1")
        session = portal_checklist.get_session("CS-1")
        item = portal_checklist.get_session_items("CS-1")[0]

        self.assertIsNotNone(building)
        self.assertTrue(building.active)
        self.assertIsInstance(building.creation, datetime)
        self.assertIsInstance(building.modified, datetime)

        self.assertIsNotNone(session)
        self.assertIsInstance(session.service_date, date)
        self.assertIsInstance(session.started_at, datetime)
        self.assertIsInstance(session.completed_at, datetime)

        self.assertEqual(item.idx, 1)
        self.assertEqual(item.sort_order, 1)
        self.assertTrue(item.requires_image)
        self.assertTrue(item.allow_notes)
        self.assertTrue(item.is_required)
        self.assertTrue(item.completed)
        self.assertIsInstance(item.completed_at, datetime)

    def test_service_mappers_return_domain_models_with_temporal_values_and_raw_proof_paths(self):
        building = portal_building.get_building("BUILD-1")
        session = portal_checklist.get_session("CS-1")
        item = portal_checklist.get_session_items("CS-1")[0]

        building_summary = portal_building.map_portal_building(building)
        session_summary = portal_checklist.map_portal_session(session)
        session_item = portal_checklist.map_portal_session_item(item, "CS-1")
        fallback_item = portal_checklist.map_portal_session_item(
            item.model_copy(update={"category": "unexpected"}),
            "CS-1",
        )

        self.assertEqual(building_summary.address, "123 Market St, Suite 300, Austin, TX 78701")
        self.assertIsInstance(building_summary.created_at, datetime)
        self.assertIsInstance(session_summary.service_date, date)
        self.assertIsInstance(session_summary.started_at, datetime)
        self.assertEqual(session_item.proof_image_path, "/private/files/restroom-proof.jpg")
        self.assertIsInstance(session_item.completed_at, datetime)
        self.assertEqual(fallback_item.category, "job_completion")

    def test_get_client_overview_returns_only_scoped_completed_data(self):
        self.dataset["Building"]["BUILD-2"] = {
            "name": "BUILD-2",
            "customer": "CUST-1",
            "building_name": "Satellite Office",
            "active": "1",
            "current_checklist_template": "CHK-TPL-3",
            "address_line_1": "456 Congress Ave",
            "address_line_2": "",
            "city": "Austin",
            "state": "TX",
            "postal_code": "78702",
            "site_notes": "Second customer site.",
            "creation": "2026-03-03 08:00:00",
            "modified": "2026-03-08 09:00:00",
        }
        self.dataset["Building_list"].append(dict(self.dataset["Building"]["BUILD-2"]))
        self.dataset["Checklist Session"]["CS-2"] = {
            "name": "CS-2",
            "building": "BUILD-2",
            "service_date": "2026-03-12",
            "checklist_template": "CHK-TPL-3",
            "status": "completed",
            "started_at": "2026-03-12 18:00:00",
            "completed_at": "2026-03-12 19:00:00",
            "worker": "Taylor Tech",
            "session_notes": "Satellite complete.",
            "creation": "2026-03-12 17:55:00",
            "modified": "2026-03-12 19:00:00",
        }
        self.dataset["Checklist Session_list"].append(dict(self.dataset["Checklist Session"]["CS-2"]))
        self._install_get_all_spy()

        response = portal.get_client_overview()

        self.assertEqual([building.id for building in response.buildings], ["BUILD-1", "BUILD-2"])
        self.assertEqual([session.id for session in response.completed_sessions], ["CS-2", "CS-1"])
        self.assertIsInstance(response.buildings[0].created_at, datetime)
        self.assertIsInstance(response.completed_sessions[0].started_at, datetime)
        self.assertEqual(
            self._session_query_calls(),
            [
                {
                    "doctype": "Checklist Session",
                    "filters": [["building", "in", ["BUILD-1", "BUILD-2"]], ["status", "=", "completed"]],
                    "fields": portal_checklist.CHECKLIST_SESSION_FIELDS,
                    "order_by": "completed_at desc, started_at desc, creation desc",
                    "limit": 200,
                }
            ],
        )

    def test_get_client_building_returns_scoped_history_only(self):
        self._install_get_all_spy()
        response = portal.get_client_building("BUILD-1")

        self.assertEqual(response.building.id, "BUILD-1")
        self.assertEqual([session.id for session in response.completed_sessions], ["CS-1"])
        self.assertEqual(
            self._session_query_calls(),
            [
                {
                    "doctype": "Checklist Session",
                    "filters": [["building", "in", ["BUILD-1"]], ["status", "=", "completed"]],
                    "fields": portal_checklist.CHECKLIST_SESSION_FIELDS,
                    "order_by": "completed_at desc, started_at desc, creation desc",
                    "limit": 200,
                }
            ],
        )

    def test_get_client_job_returns_domain_job_detail_with_raw_proof_paths(self):
        response = portal.get_client_job("CS-1")

        self.assertEqual(response.building.id, "BUILD-1")
        self.assertEqual(response.session.id, "CS-1")
        self.assertEqual(len(response.session.items), 2)
        self.assertEqual(response.session.items[0].proof_image_path, "/private/files/restroom-proof.jpg")
        self.assertIsInstance(response.session.items[0].completed_at, datetime)

    def test_download_client_job_proof_returns_domain_file_content(self):
        with patch.object(
            portal_client.building_sop_service,
            "get_proof_file_content",
            return_value=("restroom-proof.jpg", b"IMG", "image/jpeg"),
        ):
            response = portal.download_client_job_proof("CS-1", "restrooms")

        self.assertEqual(response.filename, "restroom-proof.jpg")
        self.assertEqual(response.content, b"IMG")
        self.assertEqual(response.content_type, "image/jpeg")

    def test_download_client_job_proof_rejects_out_of_scope_job(self):
        with self.assertRaisesRegex(portal.CustomerPortalNotFoundError, "job report is not available"):
            portal.download_client_job_proof("CS-OTHER", "other")

    def test_get_client_job_rejects_unknown_out_of_scope_and_non_completed_sessions(self):
        with self.assertRaisesRegex(portal.CustomerPortalNotFoundError, "job report is not available"):
            portal.get_client_job("CS-MISSING")

        with self.assertRaisesRegex(portal.CustomerPortalNotFoundError, "job report is not available"):
            portal.get_client_job("CS-OTHER")

        with self.assertRaisesRegex(portal.CustomerPortalNotFoundError, "job report is not available"):
            portal.get_client_job("CS-IN-PROGRESS")

    def test_download_client_job_proof_rejects_missing_item_and_missing_image(self):
        with self.assertRaisesRegex(portal.CustomerPortalNotFoundError, "checklist proof is not available"):
            portal.download_client_job_proof("CS-1", "missing")

        with self.assertRaisesRegex(portal.CustomerPortalNotFoundError, "No proof photo is attached"):
            portal.download_client_job_proof("CS-1", "trash")

    def test_api_serializers_preserve_public_shape_and_current_formatting(self):
        overview = portal.get_client_overview()
        building_payload = portal_api_serializers.serialize_customer_portal_overview(overview)
        job_payload = portal_api_serializers.serialize_customer_portal_job_detail(portal.get_client_job("CS-1"))

        self.assertEqual(building_payload.buildings[0].created_at, "2026-03-01 08:00:00")
        self.assertEqual(building_payload.completed_sessions[0].service_date, "2026-03-09")
        self.assertEqual(job_payload.session.started_at, "2026-03-09 18:00:00")
        self.assertEqual(
            job_payload.session.items[0].proof_image,
            "/api/method/pikt_inc.api.customer_portal.download_customer_portal_client_job_proof?session=CS-1&item_key=restrooms",
        )

    def test_customer_job_serializer_treats_issue_reported_items_as_resolved_without_exposing_issue_fields(self):
        issue_item = portal_checklist.CustomerPortalSessionItem(
            id="CSI-ISSUE-1",
            job_session_id="CS-1",
            item_key="alarm_panel",
            category="rearm_security",
            step_order=1,
            title="Arm alarm panel",
            description="Set the alarm before leaving.",
            target_duration_seconds=90,
            requires_image=True,
            allow_notes=True,
            is_required=True,
            completed=False,
            completed_at=None,
            issue_reported=True,
            issue_reason="Panel displayed a fault code.",
            issue_reported_at=datetime(2026, 3, 9, 18, 50, 0),
            issue_image_path="/private/files/panel-fault.jpg",
            proof_image_path=None,
            note=None,
        )

        payload = portal_api_serializers.serialize_customer_portal_session_item(issue_item, "CS-1")
        dumped = payload.model_dump(mode="python")

        self.assertTrue(payload.completed)
        self.assertEqual(payload.completed_at, "2026-03-09 18:50:00")
        self.assertNotIn("issue_reported", dumped)
        self.assertNotIn("issue_reason", dumped)
        self.assertNotIn("issue_image", dumped)

    def test_api_wrappers_validate_request_models_and_preserve_shape(self):
        expected_building = portal.CustomerBuildingHistory(
            building=portal_building.CustomerPortalBuilding(
                id="BUILD-1",
                name="Headquarters",
                address="123 Market St",
                notes=None,
                active=True,
                current_checklist_template_id="CHK-TPL-1",
                created_at=datetime(2026, 3, 1, 8, 0, 0),
                updated_at=datetime(2026, 3, 6, 12, 0, 0),
            ),
            completed_sessions=[],
        )

        with patch.object(
            portal_api.customer_portal_service,
            "get_client_building",
            return_value=expected_building,
        ) as get_client_building:
            result = portal_api.get_customer_portal_client_building(building="BUILD-1")

        self.assertEqual(result["building"]["id"], "BUILD-1")
        self.assertEqual(result["building"]["created_at"], "2026-03-01 08:00:00")
        self.assertEqual(get_client_building.call_args.args, ("BUILD-1",))

        with self.assertRaisesRegex(Exception, "Field required"):
            portal_api.get_customer_portal_client_building()

    def test_download_wrapper_applies_inline_file_response(self):
        self.frappe.local.response = {}
        with patch.object(
            portal_api.customer_portal_service,
            "download_client_job_proof",
            return_value=portal.ProofFileContent(
                filename="restroom-proof.jpg",
                content=b"IMG",
                content_type="image/jpeg",
            ),
        ) as download_client_job_proof:
            result = portal_api.download_customer_portal_client_job_proof(session="CS-1", item_key="restrooms")

        self.assertIsNone(result)
        self.assertEqual(download_client_job_proof.call_args.args, ("CS-1", "restrooms"))
        self.assertEqual(self.frappe.local.response["filename"], "restroom-proof.jpg")
        self.assertEqual(self.frappe.local.response["type"], "binary")
        self.assertEqual(self.frappe.local.response["content_type"], "image/jpeg")

    def test_api_wrapper_surfaces_portal_errors(self):
        with patch.object(
            portal_api.customer_portal_service,
            "get_client_job",
            side_effect=portal.CustomerPortalNotFoundError("That job report is not available in this portal account."),
        ):
            with self.assertRaisesRegex(Exception, "That job report is not available in this portal account"):
                portal_api.get_customer_portal_client_job(session="CS-OTHER")

    def test_api_request_models_validate_required_fields(self):
        with self.assertRaises(ValidationError):
            portal_api_contracts.CustomerPortalClientBuildingRequestApi.model_validate({})

        with self.assertRaises(ValidationError):
            portal_api_contracts.CustomerPortalClientJobProofRequestApi.model_validate({"session": "CS-1"})

    def test_hooks_include_customer_portal_cleanup_patch(self):
        builder_fixture = next(fixture for fixture in app_hooks.fixtures if fixture["dt"] == "Builder Page")
        routes = builder_fixture["filters"][0][2]
        self.assertNotIn("portal", routes)
        self.assertNotIn("portal/agreements", routes)
        self.assertNotIn("portal/billing", routes)
        self.assertNotIn("portal/locations", routes)
        patches = PATCHES_PATH.read_text(encoding="utf-8")
        self.assertIn("pikt_inc.patches.post_model_sync.retire_legacy_customer_portal_role", patches)
        self.assertIn("pikt_inc.patches.post_model_sync.remove_legacy_customer_portal_builder_artifacts", patches)

    def test_retire_legacy_customer_portal_role_patch_migrates_linked_users_and_removes_stale_role(self):
        legacy_rows = [
            {"name": "ROLE-LEGACY-1", "parent": "linked@example.com"},
            {"name": "ROLE-LEGACY-2", "parent": "invalid@example.com"},
            {"name": "ROLE-LEGACY-3", "parent": "duplicate@example.com"},
        ]
        custom_customers = {
            "linked@example.com": "CUST-1",
            "invalid@example.com": "",
            "duplicate@example.com": "CUST-2",
        }
        existing_roles = {("duplicate@example.com", "Customer")}
        updated_rows = []
        deleted_docs = []
        cleared = []

        class PatchDB:
            def get_value(self, doctype, name, fieldname):
                if doctype == "User" and fieldname == "custom_customer":
                    return custom_customers.get(name)
                return None

            def exists(self, doctype, name):
                if doctype == "Has Role" and isinstance(name, dict):
                    return (name.get("parent"), name.get("role")) in existing_roles
                if doctype == "Role":
                    return name == "Customer Portal User"
                return False

            def set_value(self, doctype, name, fieldname, value, update_modified=False):
                updated_rows.append((doctype, name, fieldname, value, update_modified))

        fake_frappe = types.SimpleNamespace(
            db=PatchDB(),
            get_all=lambda doctype, filters=None, fields=None, limit=None: legacy_rows
            if doctype == "Has Role" and filters == {"role": "Customer Portal User"}
            else [],
            delete_doc=lambda doctype, name, **kwargs: deleted_docs.append((doctype, name, kwargs)),
            clear_cache=lambda: cleared.append(True),
        )

        with patch.object(retire_legacy_customer_portal_role, "frappe", fake_frappe):
            result = retire_legacy_customer_portal_role.execute()

        self.assertEqual(result["migrated_users"], ["linked@example.com"])
        self.assertEqual(result["removed_duplicate_assignments"], ["duplicate@example.com"])
        self.assertEqual(result["removed_invalid_assignments"], ["invalid@example.com"])
        self.assertTrue(result["role_removed"])
        self.assertEqual(updated_rows, [("Has Role", "ROLE-LEGACY-1", "role", "Customer", False)])
        self.assertEqual(
            deleted_docs,
            [
                ("Has Role", "ROLE-LEGACY-2", {"ignore_permissions": True, "force": True}),
                ("Has Role", "ROLE-LEGACY-3", {"ignore_permissions": True, "force": True}),
                ("Role", "Customer Portal User", {"ignore_permissions": True, "force": True}),
            ],
        )
        self.assertEqual(len(cleared), 1)
