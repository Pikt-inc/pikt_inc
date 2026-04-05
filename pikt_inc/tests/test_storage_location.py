from __future__ import annotations

import sys
import types
import unittest
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import Mock

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

if "frappe" not in sys.modules:
    fake_frappe = types.SimpleNamespace(
        db=types.SimpleNamespace(
            exists=lambda *args, **kwargs: False,
            set_value=lambda *args, **kwargs: None,
        ),
        get_all=lambda *args, **kwargs: [],
        get_doc=lambda *args, **kwargs: None,
        get_meta=lambda *args, **kwargs: SimpleNamespace(fields=[]),
        clear_cache=lambda: None,
        throw=lambda message, **_kwargs: (_ for _ in ()).throw(Exception(message)),
    )
    sys.modules["frappe"] = fake_frappe

try:
    storage_location_events = import_module("pikt_inc.events.storage_location")
    storage_location_patch = import_module(
        "pikt_inc.patches.post_model_sync.backfill_building_storage_locations"
    )
except ModuleNotFoundError:
    storage_location_events = import_module("pikt_inc.pikt_inc.events.storage_location")
    storage_location_patch = import_module(
        "pikt_inc.pikt_inc.patches.post_model_sync.backfill_building_storage_locations"
    )


class TestStorageLocationEvents(unittest.TestCase):
    def test_before_save_clears_other_primary_locations_for_building(self):
        set_value = Mock()
        storage_location_events.frappe.get_all = Mock(
            return_value=[{"name": "SL-1"}, {"name": "SL-2"}]
        )
        storage_location_events.frappe.db.set_value = set_value

        doc = SimpleNamespace(name="SL-2", building="BUILD-1", is_primary=1, active=1)

        storage_location_events.before_save(doc)

        self.assertEqual(storage_location_events.frappe.get_all.call_args.kwargs["filters"], {"building": "BUILD-1", "is_primary": 1})
        set_value.assert_called_once_with(
            "Storage Location",
            "SL-1",
            "is_primary",
            0,
            update_modified=False,
        )

    def test_before_save_rejects_inactive_primary_location(self):
        doc = SimpleNamespace(name="SL-1", building="BUILD-1", is_primary=1, active=0)

        with self.assertRaisesRegex(Exception, "Primary storage location must be active"):
            storage_location_events.before_save(doc)


class TestBackfillBuildingStorageLocations(unittest.TestCase):
    def test_build_legacy_storage_location_values_uses_expected_defaults(self):
        values = storage_location_patch.build_legacy_storage_location_values(
            building_name="BUILD-1",
            directions="Basement supply room",
        )

        self.assertEqual(values["doctype"], "Storage Location")
        self.assertEqual(values["building"], "BUILD-1")
        self.assertEqual(values["location_name"], "Primary Storage")
        self.assertEqual(values["location_type"], "other")
        self.assertEqual(values["directions"], "Basement supply room")
        self.assertEqual(values["active"], 1)
        self.assertEqual(values["is_primary"], 1)

    def test_execute_backfills_one_location_for_legacy_key_storage_value(self):
        inserted = []

        class FakeDoc:
            def __init__(self, payload):
                self.payload = payload

            def insert(self, ignore_permissions=False):
                inserted.append((self.payload, ignore_permissions))
                return self

        def fake_get_all(doctype, filters=None, fields=None, limit_page_length=None):
            if doctype == "Building":
                return [
                    {"name": "BUILD-1", "key_storage_location": "Janitor closet by dock"},
                    {"name": "BUILD-2", "key_storage_location": ""},
                ]
            if doctype == "Storage Location":
                return []
            raise AssertionError(f"Unexpected doctype lookup: {doctype}")

        storage_location_patch.frappe.db.exists = Mock(return_value=True)
        storage_location_patch.frappe.get_meta = Mock(
            return_value=SimpleNamespace(fields=[SimpleNamespace(fieldname="key_storage_location")])
        )
        storage_location_patch.frappe.get_all = fake_get_all
        storage_location_patch.frappe.get_doc = lambda payload: FakeDoc(payload)
        storage_location_patch.frappe.clear_cache = Mock()

        result = storage_location_patch.execute()

        self.assertEqual(result, {"status": "created", "created": 1})
        self.assertEqual(len(inserted), 1)
        self.assertEqual(inserted[0][0]["building"], "BUILD-1")
        self.assertEqual(inserted[0][0]["directions"], "Janitor closet by dock")
        self.assertTrue(inserted[0][1])
        storage_location_patch.frappe.clear_cache.assert_called_once_with()

    def test_execute_does_not_duplicate_when_storage_location_exists(self):
        storage_location_patch.frappe.db.exists = Mock(return_value=True)
        storage_location_patch.frappe.get_meta = Mock(
            return_value=SimpleNamespace(fields=[SimpleNamespace(fieldname="key_storage_location")])
        )

        def fake_get_all(doctype, filters=None, fields=None, limit_page_length=None):
            if doctype == "Building":
                return [{"name": "BUILD-1", "key_storage_location": "Hall closet"}]
            if doctype == "Storage Location":
                return [{"name": "SL-1"}]
            raise AssertionError(f"Unexpected doctype lookup: {doctype}")

        storage_location_patch.frappe.get_all = fake_get_all
        storage_location_patch.frappe.get_doc = Mock()
        storage_location_patch.frappe.clear_cache = Mock()

        result = storage_location_patch.execute()

        self.assertEqual(result, {"status": "noop", "created": 0})
        storage_location_patch.frappe.get_doc.assert_not_called()
        storage_location_patch.frappe.clear_cache.assert_not_called()


if __name__ == "__main__":
    unittest.main()
