from __future__ import annotations

import importlib
import sys
import types
from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import call, patch

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
    fake_utils.now_datetime = lambda: "2026-04-02 10:00:00"
    fake_frappe.db = types.SimpleNamespace(get_value=lambda *args, **kwargs: None)
    fake_frappe.get_all = lambda *args, **kwargs: []
    fake_frappe.get_doc = lambda *args, **kwargs: None
    fake_frappe.get_roles = lambda _user=None: []
    fake_frappe.local = types.SimpleNamespace(response={}, request=types.SimpleNamespace(get_json=lambda silent=True: None))
    fake_frappe.request = types.SimpleNamespace(data=None, files={})
    fake_frappe.form_dict = {}
    fake_frappe.session = types.SimpleNamespace(user="cleaner@example.com")
    fake_frappe.throw = lambda message, **_kwargs: (_ for _ in ()).throw(Exception(message))
    fake_frappe.whitelist = lambda **_kwargs: (lambda fn: fn)
    fake_frappe.utils = fake_utils
    sys.modules["frappe"] = fake_frappe
    sys.modules["frappe.utils"] = fake_utils


try:
    portal = importlib.import_module("pikt_inc.services.customer_portal")
    cleaner = importlib.import_module("pikt_inc.services.customer_portal.cleaner")
    checklist_api = importlib.import_module("pikt_inc.api.checklist_portal")
    checklist_api_contracts = importlib.import_module("pikt_inc.api.checklist_portal_contracts")
    checklist_api_serializers = importlib.import_module("pikt_inc.api.checklist_portal_serializers")
    portal_building = importlib.import_module("pikt_inc.services.customer_portal.building")
    portal_checklist = importlib.import_module("pikt_inc.services.customer_portal.checklist")
except ModuleNotFoundError:
    portal = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal")
    cleaner = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal.cleaner")
    checklist_api = importlib.import_module("pikt_inc.pikt_inc.api.checklist_portal")
    checklist_api_contracts = importlib.import_module("pikt_inc.pikt_inc.api.checklist_portal_contracts")
    checklist_api_serializers = importlib.import_module("pikt_inc.pikt_inc.api.checklist_portal_serializers")
    portal_building = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal.building")
    portal_checklist = importlib.import_module("pikt_inc.pikt_inc.services.customer_portal.checklist")


class FakeDB:
    def __init__(self, dataset):
        self.dataset = dataset

    def get_value(self, doctype, name, fields, as_dict=False):
        source = self.dataset.get(doctype, {})
        row = source.get(name)
        if row is None:
            return None
        if isinstance(fields, list):
            result = {field: row.get(field) for field in fields}
            return result if as_dict else result
        return row.get(fields)


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


class FakeChecklistSessionDoc:
    def __init__(self, dataset, payload=None, name=None):
        self.dataset = dataset
        if payload is not None:
            self.doctype = payload.get("doctype")
            self.name = payload.get("name")
            self.building = payload.get("building")
            self.service_date = payload.get("service_date")
            self.checklist_template = payload.get("checklist_template") or dataset["Building"][self.building]["current_checklist_template"]
            self.status = payload.get("status", "in_progress")
            self.started_at = payload.get("started_at", "2026-04-02 10:00:00")
            self.completed_at = payload.get("completed_at")
            self.worker = payload.get("worker", "")
            self.session_notes = payload.get("session_notes", "")
            self.creation = payload.get("creation", "2026-04-02 10:00:00")
            self.modified = payload.get("modified", "2026-04-02 10:00:00")
            self.items = [types.SimpleNamespace(**item) for item in payload.get("items", [])]
        else:
            row = dict(dataset["Checklist Session"][name])
            self.doctype = "Checklist Session"
            self.name = row["name"]
            self.building = row["building"]
            self.service_date = row["service_date"]
            self.checklist_template = row["checklist_template"]
            self.status = row["status"]
            self.started_at = row["started_at"]
            self.completed_at = row.get("completed_at")
            self.worker = row.get("worker", "")
            self.session_notes = row.get("session_notes", "")
            self.creation = row.get("creation")
            self.modified = row.get("modified")
            self.items = [
                types.SimpleNamespace(**item)
                for item in dataset["Checklist Session Item_list"]
                if item.get("parent") == name
            ]

    def get(self, fieldname, default=None):
        return getattr(self, fieldname, default)

    def insert(self, ignore_permissions=False):
        self.name = self.name or "CS-NEW"
        if not list(self.items):
            template_items = [
                item for item in self.dataset["Checklist Template Item_list"]
                if item.get("parent") == self.checklist_template and item.get("active") == 1
            ]
            self.items = [
                types.SimpleNamespace(
                    name=f"CSI-{index}",
                    idx=index,
                    item_key=item["item_key"],
                    category=item["category"],
                    sort_order=item["sort_order"],
                    title_snapshot=item["title"],
                    description_snapshot=item["description"],
                    target_duration_seconds=item.get("target_duration_seconds"),
                    requires_image=item["requires_image"],
                    allow_notes=item["allow_notes"],
                    is_required=item["is_required"],
                    completed=0,
                    completed_at=None,
                    note="",
                    proof_image="",
                    training_media=item.get("training_media", ""),
                    training_media_kind=item.get("training_media_kind", ""),
                    parent=self.name,
                    parenttype="Checklist Session",
                    parentfield="items",
                )
                for index, item in enumerate(template_items, start=1)
            ]
        self.save(ignore_permissions=ignore_permissions)
        return self

    def save(self, ignore_permissions=False):
        session_row = {
            "name": self.name,
            "building": self.building,
            "service_date": self.service_date,
            "checklist_template": self.checklist_template,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "worker": self.worker,
            "session_notes": self.session_notes,
            "creation": self.creation,
            "modified": self.modified,
        }
        self.dataset["Checklist Session"][self.name] = dict(session_row)
        self.dataset["Checklist Session_list"] = [
            row for row in self.dataset["Checklist Session_list"] if row.get("name") != self.name
        ] + [dict(session_row)]
        self.dataset["Checklist Session Item_list"] = [
            row for row in self.dataset["Checklist Session Item_list"] if row.get("parent") != self.name
        ] + [
            {
                "name": item.name,
                "parent": self.name,
                "parenttype": "Checklist Session",
                "parentfield": "items",
                "idx": item.idx,
                "item_key": item.item_key,
                "category": item.category,
                "sort_order": item.sort_order,
                "title_snapshot": item.title_snapshot,
                "description_snapshot": item.description_snapshot,
                "target_duration_seconds": getattr(item, "target_duration_seconds", None),
                "requires_image": item.requires_image,
                "allow_notes": item.allow_notes,
                "is_required": item.is_required,
                "completed": item.completed,
                "completed_at": item.completed_at,
                "note": item.note,
                "proof_image": item.proof_image,
                "training_media": getattr(item, "training_media", ""),
                "training_media_kind": getattr(item, "training_media_kind", ""),
            }
            for item in self.items
        ]
        return self


class FakeFileDoc:
    def __init__(self, payload):
        self.payload = payload
        self.name = "FILE-1"
        self.file_name = payload.get("file_name")
        self.file_url = f"/private/files/{self.file_name}"

    def save(self, ignore_permissions=False):
        return self


class FakeUploadedFile:
    def __init__(self, filename: str, content: bytes):
        self.filename = filename
        self._content = content

    def read(self):
        return self._content


class TestChecklistPortal(TestCase):
    def setUp(self):
        self.dataset = {
            "Building": {
                "BUILD-1": {
                    "name": "BUILD-1",
                    "customer": "CUST-1",
                    "building_name": "Headquarters",
                    "active": 1,
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
                "BUILD-2": {
                    "name": "BUILD-2",
                    "customer": "CUST-1",
                    "building_name": "Archive",
                    "active": 0,
                    "current_checklist_template": "CHK-TPL-2",
                    "address_line_1": "500 Old Rd",
                    "address_line_2": "",
                    "city": "Austin",
                    "state": "TX",
                    "postal_code": "78705",
                    "site_notes": "",
                    "creation": "2026-03-02 08:00:00",
                    "modified": "2026-03-06 12:00:00",
                },
            },
            "Building_list": [],
            "Checklist Template Item_list": [
                {
                    "name": "TPL-ITEM-1",
                    "parent": "CHK-TPL-1",
                    "parenttype": "Checklist Template",
                    "parentfield": "items",
                    "idx": 1,
                    "item_key": "access_code",
                    "category": "access",
                    "sort_order": 1,
                    "title": "Enter building",
                    "description": "Use the front code.",
                    "target_duration_seconds": 3,
                    "requires_image": 0,
                    "allow_notes": 1,
                    "is_required": 1,
                    "active": 1,
                    "training_media": "/files/access-training.jpg",
                    "training_media_kind": "image",
                }
            ],
            "Checklist Session": {
                "CS-1": {
                    "name": "CS-1",
                    "building": "BUILD-1",
                    "service_date": "2026-03-09",
                    "checklist_template": "CHK-TPL-1",
                    "status": "in_progress",
                    "started_at": "2026-03-09 18:00:00",
                    "completed_at": None,
                    "worker": "Jordan Tech",
                    "session_notes": "",
                    "creation": "2026-03-09 17:55:00",
                    "modified": "2026-03-09 18:00:00",
                }
            },
            "Checklist Session_list": [],
            "Checklist Session Item_list": [
                {
                    "name": "CSI-1",
                    "parent": "CS-1",
                    "parenttype": "Checklist Session",
                    "parentfield": "items",
                    "idx": 1,
                    "item_key": "access_code",
                    "category": "access",
                    "sort_order": 1,
                    "title_snapshot": "Enter building",
                    "description_snapshot": "Use the front code.",
                    "target_duration_seconds": 3,
                    "requires_image": 0,
                    "allow_notes": 1,
                    "is_required": 1,
                    "completed": 0,
                    "completed_at": None,
                    "note": "",
                    "proof_image": "",
                    "training_media": "/files/access-training.jpg",
                    "training_media_kind": "image",
                }
            ],
        }
        self.dataset["Building_list"] = [dict(row) for row in self.dataset["Building"].values()]
        self.dataset["Checklist Session_list"] = [dict(row) for row in self.dataset["Checklist Session"].values()]

        self.frappe = cleaner.require_portal_section.__globals__["frappe"]
        self.frappe.db = FakeDB(self.dataset)
        self.frappe.get_all = fake_get_all_factory(self.dataset)
        self.frappe.request = types.SimpleNamespace(data=None, files={})
        self.frappe.local = types.SimpleNamespace(response={}, request=types.SimpleNamespace(get_json=lambda silent=True: None))
        self.frappe.form_dict = {}

        def fake_get_doc(*args):
            if len(args) == 1 and isinstance(args[0], dict):
                payload = args[0]
                if payload.get("doctype") == "Checklist Session":
                    return FakeChecklistSessionDoc(self.dataset, payload=payload)
                if payload.get("doctype") == "File":
                    return FakeFileDoc(payload)
            if len(args) == 2 and args[0] == "Checklist Session":
                return FakeChecklistSessionDoc(self.dataset, name=args[1])
            raise AssertionError(f"Unsupported get_doc call: {args}")

        self.frappe.get_doc = fake_get_doc

    def test_list_checklist_buildings_returns_active_only_by_default(self):
        with patch.object(cleaner, "require_portal_section", return_value=None):
            buildings = cleaner.list_checklist_buildings(active_only=True)

        self.assertEqual([building.id for building in buildings], ["BUILD-1"])
        self.assertEqual(buildings[0].address, "123 Market St, Suite 300, Austin, TX 78701")

    def test_get_checklist_building_returns_steps_and_active_session(self):
        with patch.object(cleaner, "require_portal_section", return_value=None):
            detail = cleaner.get_checklist_building("BUILD-1", "2026-03-09")

        self.assertEqual(detail.building.id, "BUILD-1")
        self.assertEqual(detail.checklist_template_id, "CHK-TPL-1")
        self.assertEqual(len(detail.steps), 1)
        self.assertEqual(detail.steps[0].category, "access")
        self.assertEqual(detail.steps[0].target_duration_seconds, 3)
        self.assertEqual(detail.steps[0].training_media_path, "/files/access-training.jpg")
        self.assertEqual(detail.steps[0].training_media_kind, "image")
        self.assertEqual(detail.active_session.id, "CS-1")
        self.assertEqual(detail.active_session.items[0].item_key, "access_code")
        self.assertEqual(detail.active_session.items[0].target_duration_seconds, 3)
        self.assertEqual(detail.active_session.items[0].training_media_path, "/files/access-training.jpg")
        self.assertEqual(detail.active_session.items[0].training_media_kind, "image")

    def test_api_session_payloads_include_server_now(self):
        expected_server_now = checklist_api_serializers.checklist_server_now_string()

        with patch.object(cleaner, "require_portal_section", return_value=None), patch.object(
            cleaner, "require_checklist_work_access", return_value=None
        ):
            detail = checklist_api.get_checklist_portal_building(
                building="BUILD-1",
                serviceDate="2026-03-09",
            )
            self.assertEqual(detail["active_session"]["server_now"], expected_server_now)
            self.assertEqual(
                detail["steps"][0]["training_media"],
                "/api/method/pikt_inc.api.checklist_portal.download_checklist_portal_step_training_media?building=BUILD-1&item_key=access_code",
            )
            self.assertEqual(detail["steps"][0]["training_media_kind"], "image")
            self.assertEqual(
                detail["active_session"]["items"][0]["training_media"],
                "/api/method/pikt_inc.api.checklist_portal.download_checklist_portal_session_item_training_media?session=CS-1&item_key=access_code",
            )
            self.assertEqual(detail["active_session"]["items"][0]["training_media_kind"], "image")

            created = checklist_api.ensure_checklist_portal_session(
                building="BUILD-1",
                serviceDate="2026-04-02",
            )
            self.assertEqual(created["server_now"], expected_server_now)
            self.assertEqual(
                created["items"][0]["training_media"],
                "/api/method/pikt_inc.api.checklist_portal.download_checklist_portal_session_item_training_media?session=CS-NEW&item_key=access_code",
            )
            self.assertEqual(created["items"][0]["training_media_kind"], "image")

            updated = checklist_api.update_checklist_portal_session_item(
                session=created["id"],
                itemKey="access_code",
                completed=True,
            )
            self.assertEqual(updated["session"]["server_now"], expected_server_now)

            with patch.object(
                checklist_api,
                "_request_file",
                return_value=FakeUploadedFile("proof.jpg", b"IMG"),
            ):
                uploaded = checklist_api.upload_checklist_portal_session_item_proof(
                    session=created["id"],
                    itemKey="access_code",
                )
            self.assertEqual(uploaded["session"]["server_now"], expected_server_now)

            completed = checklist_api.complete_checklist_portal_session(session=created["id"])
            self.assertEqual(completed["server_now"], expected_server_now)

    def test_session_mutation_flow_runs_through_cleaner_service(self):
        with patch.object(cleaner, "require_portal_section", return_value=None), patch.object(
            cleaner, "require_checklist_work_access", return_value=None
        ):
            created = cleaner.ensure_checklist_session("BUILD-1", "2026-04-02")
            self.assertEqual(created.id, "CS-NEW")
            self.assertEqual(created.items[0].item_key, "access_code")
            self.assertEqual(created.items[0].target_duration_seconds, 3)
            self.assertEqual(created.items[0].training_media_path, "/files/access-training.jpg")
            self.assertEqual(created.items[0].training_media_kind, "image")

            updated = cleaner.update_checklist_session_item(
                created.id,
                "access_code",
                completed=True,
                note="Opened cleanly",
            )
            self.assertTrue(updated.item.completed)
            self.assertEqual(updated.item.note, "Opened cleanly")

            uploaded = cleaner.upload_checklist_session_item_proof(
                created.id,
                "access_code",
                uploaded=FakeUploadedFile("proof.jpg", b"IMG"),
            )
            self.assertTrue(uploaded.item.completed)
            self.assertEqual(uploaded.item.proof_image_path, "/private/files/proof.jpg")

            completed = cleaner.complete_checklist_session(created.id)
            self.assertEqual(completed.status, "completed")

    def test_training_media_download_service_uses_scoped_checklist_access(self):
        with patch.object(cleaner, "require_portal_section", return_value=None), patch.object(
            cleaner.building_sop_service,
            "get_proof_file_content",
            return_value=("training.jpg", b"IMG", "image/jpeg"),
        ) as get_proof_file_content:
            preview_download = cleaner.download_checklist_step_training_media("BUILD-1", "access_code")
            session_download = cleaner.download_checklist_session_item_training_media("CS-1", "access_code")

        self.assertEqual(preview_download.filename, "training.jpg")
        self.assertEqual(preview_download.content, b"IMG")
        self.assertEqual(session_download.filename, "training.jpg")
        self.assertEqual(session_download.content_type, "image/jpeg")
        self.assertEqual(
            get_proof_file_content.call_args_list,
            [
                call("/files/access-training.jpg"),
                call("/files/access-training.jpg"),
            ],
        )

    def test_api_serializers_and_wrappers_preserve_public_shape(self):
        detail = portal.ChecklistPortalBuildingDetail(
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
            checklist_template_id="CHK-TPL-1",
            steps=[
                portal_checklist.ChecklistStep(
                    id="access_code",
                    building_id="BUILD-1",
                    checklist_template_id="CHK-TPL-1",
                    category="access",
                    step_order=1,
                    title="Enter building",
                    description="Use the front code.",
                    target_duration_seconds=3,
                    requires_image=False,
                    allow_notes=True,
                    is_required=True,
                    active=True,
                    training_media_path="/files/access-training.mp4",
                    training_media_kind="video",
                )
            ],
            active_session=None,
        )
        payload = checklist_api_serializers.serialize_checklist_portal_building_detail(detail)
        self.assertEqual(payload.building.created_at, "2026-03-01 08:00:00")
        self.assertEqual(payload.steps[0].category, "access")
        self.assertEqual(payload.steps[0].target_duration_seconds, 3)
        self.assertEqual(
            payload.steps[0].training_media,
            "/api/method/pikt_inc.api.checklist_portal.download_checklist_portal_step_training_media?building=BUILD-1&item_key=access_code",
        )
        self.assertEqual(payload.steps[0].training_media_kind, "video")

        with patch.object(
            checklist_api.customer_portal_service,
            "get_checklist_building",
            return_value=detail,
        ) as get_checklist_building:
            result = checklist_api.get_checklist_portal_building(building="BUILD-1", serviceDate="2026-04-02")

        self.assertEqual(result["building"]["id"], "BUILD-1")
        self.assertEqual(
            result["steps"][0]["training_media"],
            "/api/method/pikt_inc.api.checklist_portal.download_checklist_portal_step_training_media?building=BUILD-1&item_key=access_code",
        )
        self.assertEqual(result["steps"][0]["training_media_kind"], "video")
        self.assertEqual(get_checklist_building.call_args.args, ("BUILD-1", "2026-04-02"))

        with self.assertRaises(ValidationError):
            checklist_api_contracts.ChecklistPortalBuildingRequestApi.model_validate({})

    def test_training_media_downloads_run_through_scoped_portal_methods(self):
        with patch.object(
            checklist_api.customer_portal_service,
            "download_checklist_step_training_media",
            return_value=portal.ProofFileContent(
                filename="training.jpg",
                content=b"IMG",
                content_type="image/jpeg",
            ),
        ) as download_step_training_media:
            result = checklist_api.download_checklist_portal_step_training_media(
                building="BUILD-1",
                item_key="access_code",
            )

        self.assertIsNone(result)
        self.assertEqual(download_step_training_media.call_args.args, ("BUILD-1", "access_code"))
        self.assertEqual(checklist_api.frappe.local.response["filename"], "training.jpg")

        with patch.object(
            checklist_api.customer_portal_service,
            "download_checklist_session_item_training_media",
            return_value=portal.ProofFileContent(
                filename="training.webm",
                content=b"VID",
                content_type="video/webm",
            ),
        ) as download_session_training_media:
            result = checklist_api.download_checklist_portal_session_item_training_media(
                session="CS-1",
                item_key="access_code",
            )

        self.assertIsNone(result)
        self.assertEqual(download_session_training_media.call_args.args, ("CS-1", "access_code"))
        self.assertEqual(checklist_api.frappe.local.response["filename"], "training.webm")


if __name__ == "__main__":
    import unittest

    unittest.main()
