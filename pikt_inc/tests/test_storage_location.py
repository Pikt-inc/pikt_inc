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
except ModuleNotFoundError:
    storage_location_events = import_module("pikt_inc.pikt_inc.events.storage_location")


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


if __name__ == "__main__":
    unittest.main()
