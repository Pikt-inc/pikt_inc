from __future__ import annotations

import json
from pathlib import Path
import unittest

from pikt_inc import hooks as app_hooks


BUILDER_PAGE_FIXTURE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "builder_page.json"


class TestWebsiteFixtures(unittest.TestCase):
    def test_home_page_is_explicit(self):
        self.assertEqual(app_hooks.home_page, "home")

    def test_home_alias_redirects_to_root(self):
        self.assertIn(
            {"source": "/home", "target": "/", "redirect_http_status": "301"},
            app_hooks.website_redirects,
        )

    def test_builder_page_fixture_contains_home_route(self):
        builder_pages = json.loads(BUILDER_PAGE_FIXTURE_PATH.read_text(encoding="utf-8"))
        home_page = next(doc for doc in builder_pages if doc["name"] == "page-c6c8b9f1")

        self.assertEqual(home_page["route"], "home")
        self.assertEqual(home_page["page_name"], "page-c6c8b9f1")
        self.assertEqual(home_page["page_title"], "Home")
