from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import sys
import types
import unittest
from unittest.mock import call, patch

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

if "frappe" not in sys.modules:
    fake_frappe = types.SimpleNamespace(
        utils=types.SimpleNamespace(
            now=lambda: "2026-04-01 12:00:00",
            now_datetime=lambda: datetime(2026, 4, 1, 12, 0, 0),
            get_datetime=lambda value=None: value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace(" ", "T")),
        ),
        db=types.SimpleNamespace(get_value=lambda *args, **kwargs: None, set_value=lambda *args, **kwargs: None),
        get_all=lambda *args, **kwargs: [],
        throw=lambda message: (_ for _ in ()).throw(Exception(message)),
    )
    sys.modules["frappe"] = fake_frappe

from pikt_inc.services import checklist_model


class FakeDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value

    def set(self, key, value):
        self[key] = value

    def append(self, key, value):
        self.setdefault(key, [])
        self[key].append(value)


class FakeChildRow:
    def __init__(self, **values):
        self.__dict__.update(values)

    def get(self, fieldname, default=None):
        return getattr(self, fieldname, default)


class TestChecklistModel(unittest.TestCase):
    def test_prepare_checklist_template_sets_version_published_at_and_normalized_rows(self):
        doc = FakeDoc(
            {
                "building": "BUILD-1",
                "template_name": "Headquarters Checklist",
                "status": "Active",
                "items": [
                    {
                        "item_key": "north_entrance",
                        "category": "access",
                        "title": "Use north entrance",
                        "target_duration_seconds": 45,
                        "requires_image": False,
                        "training_media": "/private/files/north-entrance.jpg",
                        "training_media_kind": "image",
                    }
                ],
            }
        )

        with patch.object(checklist_model, "_next_template_version", return_value=3), patch.object(
            checklist_model, "_now_datetime", return_value=datetime(2026, 4, 1, 12, 0, 0)
        ):
            checklist_model.prepare_checklist_template(doc)

        self.assertEqual(doc.version_number, 3)
        self.assertEqual(doc.published_at, datetime(2026, 4, 1, 12, 0, 0))
        self.assertEqual(doc["items"][0]["item_key"], "north_entrance")
        self.assertEqual(doc["items"][0]["category"], "access")
        self.assertEqual(doc["items"][0]["sort_order"], 1)
        self.assertEqual(doc["items"][0]["allow_notes"], 1)
        self.assertEqual(doc["items"][0]["training_media"], "/private/files/north-entrance.jpg")
        self.assertEqual(doc["items"][0]["training_media_kind"], "image")

    def test_sync_active_checklist_template_archives_previous_active_and_updates_building_pointer(self):
        doc = FakeDoc({"name": "CHK-TPL-2", "building": "BUILD-1", "status": "Active"})

        with patch.object(
            checklist_model.frappe,
            "get_all",
            return_value=[{"name": "CHK-TPL-1"}, {"name": "CHK-TPL-2"}],
        ), patch.object(checklist_model.frappe.db, "set_value") as set_value:
            checklist_model.sync_active_checklist_template(doc)

        self.assertEqual(
            set_value.call_args_list,
            [
                call("Checklist Template", "CHK-TPL-1", "status", "Archived"),
                call("Building", "BUILD-1", "current_checklist_template", "CHK-TPL-2"),
            ],
        )

    def test_prepare_checklist_session_for_insert_uses_current_template_and_copies_active_items(self):
        doc = FakeDoc({"building": "BUILD-1", "service_date": "2026-04-02", "items": []})
        doc.flags = SimpleNamespace()

        with patch.object(checklist_model, "_active_session_exists", return_value=""), patch.object(
            checklist_model,
            "_load_building_row",
            return_value={"name": "BUILD-1", "current_checklist_template": "CHK-TPL-1"},
        ), patch.object(
            checklist_model,
            "_load_template_row",
            return_value={"name": "CHK-TPL-1", "building": "BUILD-1", "status": "Active"},
        ), patch.object(
            checklist_model,
            "_load_template_item_rows",
            return_value=[
                {
                    "item_key": "north_entrance",
                    "category": "access",
                    "sort_order": 1,
                    "title": "Use north entrance",
                    "description": "Enter through the loading bay.",
                    "target_duration_seconds": 45,
                    "requires_image": 0,
                    "allow_notes": 1,
                    "is_required": 1,
                    "active": 1,
                    "training_media": "/private/files/north-entrance.mp4",
                    "training_media_kind": "video",
                }
            ],
        ), patch.object(
            checklist_model, "_now_datetime", return_value=datetime(2026, 4, 1, 12, 0, 0)
        ):
            checklist_model.prepare_checklist_session_for_insert(doc)

        self.assertEqual(doc.checklist_template, "CHK-TPL-1")
        self.assertEqual(doc.status, "in_progress")
        self.assertEqual(doc.started_at, datetime(2026, 4, 1, 12, 0, 0))
        self.assertEqual(len(doc["items"]), 1)
        self.assertEqual(doc["items"][0]["title_snapshot"], "Use north entrance")
        self.assertEqual(doc["items"][0]["target_duration_seconds"], 45)
        self.assertEqual(doc["items"][0]["training_media"], "/private/files/north-entrance.mp4")
        self.assertEqual(doc["items"][0]["training_media_kind"], "video")
        self.assertEqual(doc["items"][0]["completed"], 0)
        self.assertEqual(doc["items"][0]["issue_reported"], 0)
        self.assertEqual(doc["items"][0]["issue_reason"], "")
        self.assertEqual(doc["items"][0]["issue_image"], "")

    def test_validate_checklist_session_blocks_duplicate_in_progress_session_for_same_day(self):
        doc = FakeDoc(
            {
                "name": "CHK-SES-2",
                "building": "BUILD-1",
                "service_date": "2026-04-02",
                "checklist_template": "CHK-TPL-1",
                "status": "in_progress",
                "items": [],
            }
        )

        with patch.object(checklist_model, "_active_session_exists", return_value="CHK-SES-1"):
            with self.assertRaisesRegex(Exception, "Only one in-progress Checklist Session"):
                checklist_model.validate_checklist_session(doc)

    def test_validate_checklist_session_allows_completed_same_day_run_when_another_session_is_active(self):
        doc = FakeDoc(
            {
                "name": "CHK-SES-2",
                "building": "BUILD-1",
                "service_date": "2026-04-02",
                "checklist_template": "CHK-TPL-1",
                "status": "completed",
                "items": [],
            }
        )

        with patch.object(checklist_model, "_active_session_exists", return_value="CHK-SES-1"), patch.object(
            checklist_model,
            "_load_building_row",
            return_value={"name": "BUILD-1", "current_checklist_template": "CHK-TPL-1"},
        ), patch.object(
            checklist_model,
            "_load_template_row",
            return_value={"name": "CHK-TPL-1", "building": "BUILD-1", "status": "Active"},
        ), patch.object(
            checklist_model, "_now_datetime", return_value=datetime(2026, 4, 1, 12, 0, 0)
        ):
            checklist_model.validate_checklist_session(doc)

        self.assertEqual(doc.completed_at, datetime(2026, 4, 1, 12, 0, 0))

    def test_validate_checklist_session_requires_completion_and_proof_image(self):
        doc = FakeDoc(
            {
                "name": "CHK-SES-1",
                "building": "BUILD-1",
                "service_date": "2026-04-02",
                "checklist_template": "CHK-TPL-1",
                "status": "completed",
                "items": [
                    FakeChildRow(
                        item_key="alarm_panel",
                        category="rearm_security",
                        title_snapshot="Arm alarm panel",
                        requires_image=1,
                        is_required=1,
                        completed=1,
                        proof_image="",
                    ),
                    FakeChildRow(
                        item_key="rear_door",
                        category="rearm_security",
                        title_snapshot="Close rear service door",
                        requires_image=0,
                        is_required=1,
                        completed=0,
                        proof_image="",
                    ),
                ],
            }
        )

        with patch.object(checklist_model, "_active_session_exists", return_value=""), patch.object(
            checklist_model,
            "_load_building_row",
            return_value={"name": "BUILD-1", "current_checklist_template": "CHK-TPL-1"},
        ), patch.object(
            checklist_model,
            "_load_template_row",
            return_value={"name": "CHK-TPL-1", "building": "BUILD-1", "status": "Active"},
        ):
            with self.assertRaisesRegex(Exception, "proof image"):
                checklist_model.validate_checklist_session(doc)

    def test_validate_checklist_session_rejects_out_of_order_completion(self):
        doc = FakeDoc(
            {
                "name": "CHK-SES-1",
                "building": "BUILD-1",
                "service_date": "2026-04-02",
                "checklist_template": "CHK-TPL-1",
                "status": "in_progress",
                "items": [
                    FakeChildRow(
                        item_key="access_code",
                        category="access",
                        sort_order=1,
                        title_snapshot="Enter building",
                        requires_image=0,
                        is_required=1,
                        completed=0,
                        proof_image="",
                    ),
                    FakeChildRow(
                        item_key="wipe_surfaces",
                        category="job_completion",
                        sort_order=2,
                        title_snapshot="Wipe surfaces",
                        requires_image=0,
                        is_required=1,
                        completed=1,
                        proof_image="",
                    ),
                ],
            }
        )

        with patch.object(checklist_model, "_active_session_exists", return_value=""), patch.object(
            checklist_model,
            "_load_building_row",
            return_value={"name": "BUILD-1", "current_checklist_template": "CHK-TPL-1"},
        ), patch.object(
            checklist_model,
            "_load_template_row",
            return_value={"name": "CHK-TPL-1", "building": "BUILD-1", "status": "Active"},
        ):
            with self.assertRaisesRegex(Exception, "previous checklist item"):
                checklist_model.validate_checklist_session(doc)

    def test_validate_checklist_session_rejects_issue_without_reason(self):
        doc = FakeDoc(
            {
                "name": "CHK-SES-1",
                "building": "BUILD-1",
                "service_date": "2026-04-02",
                "checklist_template": "CHK-TPL-1",
                "status": "in_progress",
                "items": [
                    FakeChildRow(
                        item_key="alarm_panel",
                        category="rearm_security",
                        sort_order=1,
                        title_snapshot="Arm alarm panel",
                        requires_image=0,
                        is_required=1,
                        completed=0,
                        issue_reported=1,
                        issue_reason="",
                        proof_image="",
                    )
                ],
            }
        )

        with patch.object(checklist_model, "_active_session_exists", return_value=""), patch.object(
            checklist_model,
            "_load_building_row",
            return_value={"name": "BUILD-1", "current_checklist_template": "CHK-TPL-1"},
        ), patch.object(
            checklist_model,
            "_load_template_row",
            return_value={"name": "CHK-TPL-1", "building": "BUILD-1", "status": "Active"},
        ):
            with self.assertRaisesRegex(Exception, "requires an issue reason"):
                checklist_model.validate_checklist_session(doc)

    def test_validate_checklist_session_completed_row_clears_issue_fields(self):
        doc = FakeDoc(
            {
                "name": "CHK-SES-1",
                "building": "BUILD-1",
                "service_date": "2026-04-02",
                "checklist_template": "CHK-TPL-1",
                "status": "in_progress",
                "items": [
                    FakeChildRow(
                        item_key="alarm_panel",
                        category="rearm_security",
                        sort_order=1,
                        title_snapshot="Arm alarm panel",
                        requires_image=0,
                        is_required=1,
                        completed=1,
                        completed_at=None,
                        issue_reported=1,
                        issue_reason="Panel jammed",
                        issue_reported_at=datetime(2026, 4, 1, 11, 0, 0),
                        issue_image="/private/files/issue.jpg",
                        proof_image="",
                    )
                ],
            }
        )

        with patch.object(checklist_model, "_active_session_exists", return_value=""), patch.object(
            checklist_model,
            "_load_building_row",
            return_value={"name": "BUILD-1", "current_checklist_template": "CHK-TPL-1"},
        ), patch.object(
            checklist_model,
            "_load_template_row",
            return_value={"name": "CHK-TPL-1", "building": "BUILD-1", "status": "Active"},
        ), patch.object(
            checklist_model, "_now_datetime", return_value=datetime(2026, 4, 1, 12, 0, 0)
        ):
            checklist_model.validate_checklist_session(doc)

        row = doc["items"][0]
        self.assertEqual(row.completed_at, datetime(2026, 4, 1, 12, 0, 0))
        self.assertEqual(row.issue_reported, 0)
        self.assertEqual(row.issue_reason, "")
        self.assertIsNone(row.issue_reported_at)
        self.assertEqual(row.issue_image, "")

    def test_validate_checklist_session_issue_reported_counts_as_resolved_for_completion(self):
        doc = FakeDoc(
            {
                "name": "CHK-SES-1",
                "building": "BUILD-1",
                "service_date": "2026-04-02",
                "checklist_template": "CHK-TPL-1",
                "status": "completed",
                "items": [
                    FakeChildRow(
                        item_key="alarm_panel",
                        category="rearm_security",
                        sort_order=1,
                        title_snapshot="Arm alarm panel",
                        requires_image=1,
                        is_required=1,
                        completed=0,
                        completed_at=None,
                        issue_reported=1,
                        issue_reason="Alarm panel would not arm",
                        issue_reported_at=None,
                        issue_image="",
                        proof_image="",
                    ),
                    FakeChildRow(
                        item_key="rear_door",
                        category="rearm_security",
                        sort_order=2,
                        title_snapshot="Close rear service door",
                        requires_image=0,
                        is_required=1,
                        completed=1,
                        completed_at=None,
                        issue_reported=0,
                        issue_reason="",
                        issue_reported_at=None,
                        issue_image="",
                        proof_image="",
                    ),
                ],
            }
        )

        with patch.object(checklist_model, "_active_session_exists", return_value=""), patch.object(
            checklist_model,
            "_load_building_row",
            return_value={"name": "BUILD-1", "current_checklist_template": "CHK-TPL-1"},
        ), patch.object(
            checklist_model,
            "_load_template_row",
            return_value={"name": "CHK-TPL-1", "building": "BUILD-1", "status": "Active"},
        ), patch.object(
            checklist_model, "_now_datetime", return_value=datetime(2026, 4, 1, 12, 0, 0)
        ):
            checklist_model.validate_checklist_session(doc)

        first_row = doc["items"][0]
        second_row = doc["items"][1]
        self.assertEqual(first_row.issue_reported, 1)
        self.assertEqual(first_row.issue_reason, "Alarm panel would not arm")
        self.assertEqual(first_row.issue_reported_at, datetime(2026, 4, 1, 12, 0, 0))
        self.assertEqual(second_row.completed_at, datetime(2026, 4, 1, 12, 0, 0))
        self.assertEqual(doc.completed_at, datetime(2026, 4, 1, 12, 0, 0))


if __name__ == "__main__":
    unittest.main()
