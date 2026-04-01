from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import sys
import types
import unittest
from unittest.mock import patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

if "frappe" not in sys.modules:
    fake_frappe = types.SimpleNamespace(
        utils=types.SimpleNamespace(
            now=lambda: "2026-03-31 12:00:00",
            nowdate=lambda: "2026-03-31",
            now_datetime=lambda: datetime(2026, 3, 31, 12, 0, 0),
            get_datetime=lambda value=None: value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace(" ", "T")),
            getdate=lambda value: datetime.fromisoformat(str(value)).date() if isinstance(value, str) else value,
        ),
        db=types.SimpleNamespace(exists=lambda *args, **kwargs: False, get_value=lambda *args, **kwargs: None, set_value=lambda *args, **kwargs: None),
        get_all=lambda *args, **kwargs: [],
        get_doc=lambda *args, **kwargs: None,
        log_error=lambda *args, **kwargs: None,
        throw=lambda message: (_ for _ in ()).throw(Exception(message)),
    )
    sys.modules["frappe"] = fake_frappe

from pikt_inc.services import building_sop


class FakeDoc(dict):
    doctype = "Building SOP"

    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value

    def is_new(self):
        return not bool(self.get("name"))

    def set(self, key, value):
        self[key] = value

    def append(self, key, value):
        self.setdefault(key, [])
        self[key].append(value)

    def save(self, **_kwargs):
        self["saved"] = True


class FakeChildRow:
    def __init__(self, **values):
        self.__dict__.update(values)

    def get(self, fieldname, default=None):
        return getattr(self, fieldname, default)


class TestBuildingSop(unittest.TestCase):
    def test_prepare_building_sop_for_insert_sets_customer_version_and_supersedes(self):
        doc = FakeDoc(
            {
                "building": "BUILD-1",
                "items": [
                    {
                        "title": "Restrooms sanitized",
                        "description": "Disinfect touchpoints.",
                        "requires_photo_proof": True,
                    }
                ],
            }
        )

        with patch.object(building_sop, "_load_building_row", return_value={"name": "BUILD-1", "customer": "CUST-1", "current_sop": "BSOP-1"}), patch.object(
            building_sop,
            "_next_sop_version",
            return_value=2,
        ):
            building_sop.prepare_building_sop_for_insert(doc)

        self.assertEqual(doc.customer, "CUST-1")
        self.assertEqual(doc.version_number, 2)
        self.assertEqual(doc.supersedes, "BSOP-1")
        self.assertEqual(doc["items"][0]["item_title"], "Restrooms sanitized")
        self.assertEqual(doc["items"][0]["requires_photo_proof"], 1)

    def test_prepare_building_sop_for_insert_accepts_materialized_child_rows(self):
        doc = FakeDoc(
            {
                "building": "BUILD-1",
                "items": [
                    FakeChildRow(
                        sop_item_id="restrooms",
                        item_title="Restrooms sanitized",
                        item_description="Disinfect touchpoints.",
                        requires_photo_proof=1,
                        active=1,
                    )
                ],
            }
        )

        with patch.object(building_sop, "_load_building_row", return_value={"name": "BUILD-1", "customer": "CUST-1", "current_sop": "BSOP-1"}), patch.object(
            building_sop,
            "_next_sop_version",
            return_value=2,
        ):
            building_sop.prepare_building_sop_for_insert(doc)

        self.assertEqual(doc["items"][0]["sop_item_id"], "restrooms")
        self.assertEqual(doc["items"][0]["item_title"], "Restrooms sanitized")
        self.assertEqual(doc["items"][0]["requires_photo_proof"], 1)

    def test_normalize_sop_items_preserves_explicit_ids_and_empty_list(self):
        normalized = building_sop.normalize_sop_items(
            [
                {
                    "item_id": "restrooms",
                    "title": "Restrooms sanitized",
                    "description": "Disinfect touchpoints.",
                    "requires_photo_proof": True,
                }
            ]
        )

        self.assertEqual(normalized[0]["sop_item_id"], "restrooms")
        self.assertEqual(normalized[0]["requires_photo_proof"], 1)
        self.assertEqual(building_sop.normalize_sop_items([]), [])

    def test_prevent_sop_mutation_blocks_existing_versions(self):
        doc = FakeDoc({"name": "BSOP-1"})

        with patch.object(building_sop.frappe.db, "exists", return_value=True):
            with self.assertRaisesRegex(Exception, "immutable"):
                building_sop.prevent_sop_mutation(doc)

    def test_activate_building_sop_sets_current_pointer_and_refreshes_future_requirements(self):
        doc = FakeDoc({"name": "BSOP-2", "building": "BUILD-1"})

        with patch.object(building_sop.frappe.db, "set_value") as set_value, patch.object(
            building_sop,
            "refresh_future_requirement_snapshots",
            return_value={"visited": 2, "updated": 2},
        ) as refresh_snapshots:
            building_sop.activate_building_sop(doc)

        set_value.assert_called_once_with("Building", "BUILD-1", "current_sop", "BSOP-2")
        refresh_snapshots.assert_called_once_with("BUILD-1")

    def test_requirement_checklist_state_requires_photo_proof_for_completed_items(self):
        checklist_rows = [
            {
                "sop_item_id": "restrooms",
                "item_title": "Restrooms sanitized",
                "requires_photo_proof": 1,
                "item_status": "Completed",
                "exception_note": "",
            }
        ]

        with patch.object(building_sop, "_get_requirement_checklist_rows", return_value=checklist_rows), patch.object(
            building_sop,
            "_get_requirement_proof_rows",
            return_value=[],
        ):
            state = building_sop.requirement_checklist_state("SSR-1")

        self.assertTrue(state["enabled"])
        self.assertFalse(state["resolved"])

    def test_sync_checklist_snapshot_for_requirement_copies_current_sop_rows(self):
        requirement_doc = FakeDoc(
            {
                "doctype": "Site Shift Requirement",
                "name": "SSR-1",
                "building": "BUILD-1",
                "status": "Assigned",
                "arrival_window_start": "2026-04-01 18:00:00",
                "checked_in_at": None,
                "custom_building_sop": "",
                "custom_checklist_items": [],
                "custom_checklist_proofs": [{"checklist_item_id": "old", "proof_file": "/old.jpg"}],
            }
        )
        requirement_doc.flags = SimpleNamespace(ignore_permissions=False)

        with patch.object(building_sop, "_now_datetime", return_value=datetime(2026, 3, 31, 12, 0, 0)), patch.object(
            building_sop,
            "build_requirement_checklist_rows_from_sop",
            return_value=(
                "BSOP-2",
                [
                    {
                        "doctype": "Site Shift Requirement Checklist Item",
                        "sop_item_id": "restrooms",
                        "item_title": "Restrooms sanitized",
                        "item_description": "Disinfect touchpoints.",
                        "requires_photo_proof": 1,
                        "item_status": "Pending",
                        "exception_note": "",
                    }
                ],
            ),
        ):
            updated = building_sop.sync_checklist_snapshot_for_requirement(requirement_doc)

        self.assertTrue(updated)
        self.assertEqual(requirement_doc.custom_building_sop, "BSOP-2")
        self.assertEqual(len(requirement_doc.custom_checklist_items), 1)
        self.assertEqual(requirement_doc.custom_checklist_items[0]["item_title"], "Restrooms sanitized")
        self.assertEqual(requirement_doc.custom_checklist_proofs, [])
        self.assertTrue(requirement_doc["saved"])

    def test_create_building_sop_version_accepts_materialized_insert_rows(self):
        inserted = {}

        class FakeInsertDoc(FakeDoc):
            def __init__(self, payload):
                super().__init__(payload)
                self.doctype = payload.get("doctype", "Building SOP")
                self["items"] = [
                    FakeChildRow(
                        sop_item_id=row["sop_item_id"],
                        item_title=row["item_title"],
                        item_description=row["item_description"],
                        requires_photo_proof=row["requires_photo_proof"],
                        active=row["active"],
                    )
                    for row in payload.get("items", [])
                ]

            def insert(self, **_kwargs):
                building_sop.prepare_building_sop_for_insert(self)
                self.name = "BSOP-NEW"
                inserted["items"] = list(self["items"])
                return self

        with patch.object(building_sop, "_load_building_row", return_value={"name": "BUILD-1", "customer": "CUST-1", "current_sop": "BSOP-1"}), patch.object(
            building_sop.frappe,
            "get_doc",
            side_effect=lambda payload: FakeInsertDoc(payload),
        ), patch.object(
            building_sop,
            "_load_sop_rows",
            return_value=({"name": "BSOP-NEW", "version_number": 2}, []),
        ):
            sop_row, _item_rows = building_sop.create_building_sop_version(
                "BUILD-1",
                [
                    {
                        "item_id": "restrooms",
                        "title": "Restrooms sanitized",
                        "description": "Disinfect touchpoints.",
                        "requires_photo_proof": True,
                    }
                ],
                source="Portal",
            )

        self.assertEqual(sop_row["name"], "BSOP-NEW")
        self.assertEqual(inserted["items"][0]["sop_item_id"], "restrooms")
        self.assertEqual(inserted["items"][0]["requires_photo_proof"], 1)


if __name__ == "__main__":
    unittest.main()
