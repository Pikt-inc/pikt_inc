from __future__ import annotations

import json
import importlib
import sys
from datetime import datetime
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch
import types

from pikt_inc.tests._frappe_harness import install_test_frappe

install_test_frappe()

APP_ROOT = Path(__file__).resolve().parents[2]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

if "frappe" not in sys.modules:
    fake_frappe = types.ModuleType("frappe")
    fake_utils = types.ModuleType("frappe.utils")
    fake_utils.get_url = lambda path="": f"https://example.test{path}"
    fake_utils.now_datetime = lambda: datetime(2026, 3, 25, 12, 0, 0)
    fake_utils.get_datetime = lambda value: value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    fake_frappe.db = types.SimpleNamespace(
        get_value=lambda *args, **kwargs: None,
        count=lambda *args, **kwargs: 0,
        exists=lambda *args, **kwargs: False,
    )
    fake_frappe.get_all = lambda *args, **kwargs: []
    fake_frappe.get_roles = lambda _user=None: []
    fake_frappe.local = types.SimpleNamespace(response={})
    fake_frappe.form_dict = {}
    fake_frappe.session = types.SimpleNamespace(user="Guest")
    fake_frappe.delete_doc = lambda *args, **kwargs: None
    fake_frappe.clear_cache = lambda: None
    fake_frappe.throw = lambda message, **_kwargs: (_ for _ in ()).throw(Exception(message))
    fake_frappe.utils = fake_utils
    sys.modules["frappe"] = fake_frappe
    sys.modules["frappe.utils"] = fake_utils

if "frappe.model" not in sys.modules:
    sys.modules["frappe.model"] = types.SimpleNamespace(document=types.SimpleNamespace(Document=object))
if "frappe.model.document" not in sys.modules:
    sys.modules["frappe.model.document"] = types.SimpleNamespace(Document=object)

try:
    app_hooks = importlib.import_module("pikt_inc.hooks")
    blog = importlib.import_module("pikt_inc.services.blog")
    blog_home = importlib.import_module("pikt_inc.www.blog_home")
    blog_post = importlib.import_module("pikt_inc.www.blog_post")
    blog_rss = importlib.import_module("pikt_inc.www.blog_rss")
    blog_sitemap = importlib.import_module("pikt_inc.www.blog_sitemap")
    ensure_starter_blog_content = importlib.import_module(
        "pikt_inc.patches.post_model_sync.ensure_starter_blog_content"
    )
    remove_legacy_blog_builder_pages = importlib.import_module(
        "pikt_inc.patches.post_model_sync.remove_legacy_blog_builder_pages"
    )
except ModuleNotFoundError:
    app_hooks = importlib.import_module("pikt_inc.pikt_inc.hooks")
    blog = importlib.import_module("pikt_inc.pikt_inc.services.blog")
    blog_home = importlib.import_module("pikt_inc.www.blog_home")
    blog_post = importlib.import_module("pikt_inc.www.blog_post")
    blog_rss = importlib.import_module("pikt_inc.www.blog_rss")
    blog_sitemap = importlib.import_module("pikt_inc.www.blog_sitemap")
    ensure_starter_blog_content = importlib.import_module(
        "pikt_inc.patches.post_model_sync.ensure_starter_blog_content"
    )
    remove_legacy_blog_builder_pages = importlib.import_module(
        "pikt_inc.patches.post_model_sync.remove_legacy_blog_builder_pages"
    )


APP_PATH = Path(__file__).resolve().parents[1]
WORKSPACE_FIXTURE_PATH = APP_PATH / "fixtures" / "workspace.json"
PATCHES_PATH = APP_PATH / "patches.txt"
BLOG_BUILDER_FIXTURE_PATH = APP_PATH / "fixtures" / "blog_builder_page.json"
BLOG_HOME_TEMPLATE_PATH = APP_PATH / "www" / "blog-home.html"
BLOG_POST_TEMPLATE_PATH = APP_PATH / "www" / "blog-post.html"
BLOG_RSS_TEMPLATE_PATH = APP_PATH / "www" / "blog-rss.xml"
STARTER_CONTENT_PATCH_PATH = APP_PATH / "patches" / "post_model_sync" / "ensure_starter_blog_content.py"
LEGACY_RSS_CONTROLLER_PATH = APP_PATH / "www" / "blog" / "rss.py"
LEGACY_RSS_TEMPLATE_PATH = APP_PATH / "www" / "blog" / "rss.xml"


class FakeDoc(dict):
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError as exc:
            raise AttributeError(item) from exc

    def __setattr__(self, key, value):
        self[key] = value


class FakeDB:
    def __init__(self, dataset):
        self.dataset = dataset

    def get_value(self, doctype, name, fields, as_dict=False):
        if doctype == "User" and fields == "full_name":
            return self.dataset["users"].get(name, {}).get("full_name")

        rows = self.dataset["categories"] if doctype == "Marketing Blog Category" else self.dataset["posts"]
        for row in rows:
            if row["name"] == name:
                if isinstance(fields, list):
                    return {field: row.get(field) for field in fields}
                return row.get(fields)
        return None

    def count(self, doctype, filters=None):
        return len(fake_get_all_factory(self.dataset)(doctype, filters=filters))


def _match_filters(row, filters):
    if not filters:
        return True
    for key, value in filters.items():
        row_value = row.get(key)
        if isinstance(value, list) and value and value[0] == "!=":
            if row_value == value[1]:
                return False
            continue
        if row_value != value:
            return False
    return True


def _sort_rows(rows, order_by):
    def sort_key(value):
        if value is None:
            return ""
        if hasattr(value, "timestamp"):
            return value.timestamp()
        if isinstance(value, (int, float, bool)):
            return value
        return str(value)

    if not order_by:
        return list(rows)
    sorted_rows = list(rows)
    clauses = [clause.strip() for clause in order_by.split(",")]
    for clause in reversed(clauses):
        parts = clause.split()
        field = parts[0]
        direction = parts[1].lower() if len(parts) > 1 else "asc"
        sorted_rows.sort(key=lambda row: sort_key(row.get(field)), reverse=(direction == "desc"))
    return sorted_rows


def fake_get_all_factory(dataset):
    def fake_get_all(doctype, filters=None, fields=None, order_by=None, limit=0, limit_start=0, limit_page_length=0, **_kwargs):
        source = dataset["categories"] if doctype == "Marketing Blog Category" else dataset["posts"]
        rows = [row.copy() for row in source if _match_filters(row, filters or {})]
        rows = _sort_rows(rows, order_by)

        if limit:
            rows = rows[:limit]
        if limit_start:
            rows = rows[limit_start:]
        if limit_page_length:
            rows = rows[:limit_page_length]

        if fields:
            projected = []
            for row in rows:
                projected.append({field: row.get(field) for field in fields})
            return projected
        return rows

    return fake_get_all


class TestBlog(TestCase):
    def setUp(self):
        self.dataset = {
            "users": {"editor@example.com": {"full_name": "Editor User"}},
            "categories": [
                {
                    "name": "MBC-00001",
                    "title": "Office Cleaning",
                    "slug": "office-cleaning",
                    "description": "Office insights",
                },
                {
                    "name": "MBC-00002",
                    "title": "Medical Facilities",
                    "slug": "medical-facilities",
                    "description": "Medical insights",
                },
            ],
            "posts": [
                {
                    "name": "MBP-00001",
                    "title": "How to Keep a Lobby Presentation Ready",
                    "slug": "keep-a-lobby-presentation-ready",
                    "published": 1,
                    "published_on": datetime(2026, 3, 10, 9, 0, 0),
                    "category": "MBC-00001",
                    "author_name": "Editor User",
                    "excerpt": "Lobby routines that stop grime from showing up first.",
                    "body_html": "<p>Lobby body.</p>",
                    "cover_image": "/files/lobby.webp",
                    "og_image": "",
                    "seo_title": "Lobby Cleaning Checklist",
                    "seo_description": "A faster lobby checklist for shared spaces.",
                    "canonical_url": "",
                    "no_index": 0,
                    "featured": 1,
                    "modified": datetime(2026, 3, 11, 9, 0, 0),
                },
                {
                    "name": "MBP-00002",
                    "title": "Medical Waiting Room Turnover",
                    "slug": "medical-waiting-room-turnover",
                    "published": 1,
                    "published_on": datetime(2026, 3, 8, 10, 0, 0),
                    "category": "MBC-00002",
                    "author_name": "Editor User",
                    "excerpt": "Waiting room steps for tighter patient turnover.",
                    "body_html": "<p>Medical body.</p>",
                    "cover_image": "/files/medical.webp",
                    "og_image": "",
                    "seo_title": "",
                    "seo_description": "",
                    "canonical_url": "https://example.test/custom-medical",
                    "no_index": 0,
                    "featured": 0,
                    "modified": datetime(2026, 3, 9, 9, 0, 0),
                },
                {
                    "name": "MBP-00003",
                    "title": "Draft Post",
                    "slug": "draft-post",
                    "published": 0,
                    "published_on": None,
                    "category": "MBC-00001",
                    "author_name": "Editor User",
                    "excerpt": "Draft only.",
                    "body_html": "<p>Draft body.</p>",
                    "cover_image": "",
                    "og_image": "",
                    "seo_title": "",
                    "seo_description": "",
                    "canonical_url": "",
                    "no_index": 0,
                    "featured": 0,
                    "modified": datetime(2026, 3, 7, 9, 0, 0),
                },
                {
                    "name": "MBP-00004",
                    "title": "Internal Only Post",
                    "slug": "internal-only-post",
                    "published": 1,
                    "published_on": datetime(2026, 3, 5, 9, 0, 0),
                    "category": "MBC-00001",
                    "author_name": "Editor User",
                    "excerpt": "Visible but excluded from feeds.",
                    "body_html": "<p>Internal body.</p>",
                    "cover_image": "",
                    "og_image": "",
                    "seo_title": "",
                    "seo_description": "",
                    "canonical_url": "",
                    "no_index": 1,
                    "featured": 0,
                    "modified": datetime(2026, 3, 6, 9, 0, 0),
                },
            ],
        }
        blog.frappe.db = FakeDB(self.dataset)
        blog.frappe.get_all = fake_get_all_factory(self.dataset)
        blog.frappe.local.response = {}
        blog.frappe.form_dict = {}
        blog.frappe.session.user = "Guest"
        blog.frappe.get_roles = lambda _user=None: []
        blog.frappe.utils.get_url = lambda path="": f"https://example.test{path}"
        blog.frappe.utils.get_datetime = lambda value: value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
        blog.frappe.utils.now_datetime = lambda: datetime(2026, 3, 25, 12, 0, 0)
        blog.now_datetime = lambda: datetime(2026, 3, 25, 12, 0, 0)

    def test_prepare_blog_category_generates_slug(self):
        doc = FakeDoc({"name": "MBC-00010", "title": "  Healthcare Operations  ", "slug": "", "description": "  A desc  "})

        with patch.object(blog, "_slug_exists", return_value=False):
            result = blog.prepare_blog_category_for_save(doc)

        self.assertEqual(result["slug"], "healthcare-operations")
        self.assertEqual(doc.slug, "healthcare-operations")
        self.assertEqual(doc.title, "Healthcare Operations")

    def test_prepare_blog_post_sets_slug_excerpt_and_published_on(self):
        doc = FakeDoc(
            {
                "name": "MBP-00010",
                "title": "New Facility Checklist",
                "slug": "",
                "published": 1,
                "published_on": None,
                "category": "MBC-00001",
                "author_name": "",
                "excerpt": "",
                "body_html": "<p>Line one.</p><p>Line two.</p>",
            }
        )

        with patch.object(blog, "_get_existing_value", return_value={}), patch.object(
            blog, "_make_unique_slug", return_value="new-facility-checklist"
        ), patch.object(blog, "_current_user_author_name", return_value="Editor User"):
            result = blog.prepare_blog_post_for_save(doc)

        self.assertEqual(result["slug"], "new-facility-checklist")
        self.assertEqual(doc.slug, "new-facility-checklist")
        self.assertEqual(doc.author_name, "Editor User")
        self.assertIn("Line one", doc.excerpt)
        self.assertEqual(doc.published_on, datetime(2026, 3, 25, 12, 0, 0))

    def test_prepare_blog_post_rejects_slug_change_after_publish(self):
        doc = FakeDoc(
            {
                "name": "MBP-00001",
                "title": "How to Keep a Lobby Presentation Ready",
                "slug": "new-slug",
                "published": 1,
                "category": "MBC-00001",
                "body_html": "<p>Body.</p>",
            }
        )

        with patch.object(
            blog,
            "_get_existing_value",
            return_value={"name": "MBP-00001", "slug": "keep-a-lobby-presentation-ready", "published_on": "2026-03-10 09:00:00"},
        ):
            with self.assertRaisesRegex(Exception, "Slug cannot be changed"):
                blog.prepare_blog_post_for_save(doc)

    def test_get_blog_index_data_filters_and_paginates(self):
        data = blog.get_blog_index_data(page="1", category="office-cleaning")

        self.assertEqual(data["active_category_slug"], "office-cleaning")
        self.assertEqual([post["slug"] for post in data["posts"]], ["keep-a-lobby-presentation-ready", "internal-only-post"])
        self.assertEqual(data["pagination"]["page_count"], 1)
        self.assertEqual(data["metatags"]["title"], "Office Cleaning | Commercial Cleaning Blog")
        self.assertIn("structured_data_json", data)

    def test_get_blog_post_data_returns_404_for_unpublished_post(self):
        data = blog.get_blog_post_data("draft-post")

        self.assertTrue(data["not_found"])
        self.assertEqual(blog.frappe.local.response["http_status_code"], 404)
        self.assertEqual(data["metatags"]["title"], "Article Not Found")

    def test_get_blog_post_data_supports_preview_for_website_manager(self):
        blog.frappe.session.user = "editor@example.com"
        blog.frappe.get_roles = lambda _user=None: ["Website Manager"]
        data = blog.get_blog_post_data("draft-post", preview=1)

        self.assertFalse(data["not_found"])
        self.assertEqual(data["post"]["slug"], "draft-post")

    def test_get_blog_post_data_builds_metadata_and_related_posts(self):
        data = blog.get_blog_post_data("keep-a-lobby-presentation-ready")

        self.assertFalse(data["not_found"])
        self.assertEqual(data["post"]["canonical_url"], "https://example.test/blog/keep-a-lobby-presentation-ready")
        self.assertEqual(data["metatags"]["title"], "Lobby Cleaning Checklist")
        self.assertEqual(data["related_posts"][0]["slug"], "internal-only-post")
        self.assertEqual(data["next_post"]["slug"], "medical-waiting-room-turnover")

    def test_rss_and_sitemap_exclude_draft_and_noindex_posts(self):
        rss = blog.get_rss_feed_data()
        sitemap = blog.get_blog_sitemap_data()

        self.assertEqual([post["title"] for post in rss["posts"]], [
            "How to Keep a Lobby Presentation Ready",
            "Medical Waiting Room Turnover",
        ])
        self.assertEqual([entry["loc"] for entry in sitemap["links"]], [
            "https://example.test/blog/keep-a-lobby-presentation-ready",
            "https://example.test/blog/medical-waiting-room-turnover",
        ])

    def test_hooks_and_routes_include_blog_surface(self):
        builder_fixture = next(item for item in app_hooks.fixtures if item["dt"] == "Builder Page")
        workspace_fixture = next(item for item in app_hooks.fixtures if item["dt"] == "Workspace")
        route_rules = {(rule["from_route"], rule["to_route"]) for rule in app_hooks.website_route_rules}

        self.assertIn(("/blog", "blog-home"), route_rules)
        self.assertIn(("/blog/rss.xml", "blog-rss.xml"), route_rules)
        self.assertIn(("/blog/<slug>", "blog-post"), route_rules)
        self.assertNotIn("blog", builder_fixture["filters"][0][2])
        self.assertNotIn("blog/<slug>", builder_fixture["filters"][0][2])
        self.assertEqual(workspace_fixture["filters"][0][2], ["Marketing Blog"])

    def test_blog_home_context_delegates_to_service(self):
        context = types.SimpleNamespace(no_cache=0, body_class=None)
        blog.frappe.form_dict = {"page": "2", "category": "medical-facilities"}

        with patch("pikt_inc.views.pages.blog.home.blog.get_blog_index_data", return_value={"posts": []}) as get_blog_index_data:
            result = blog_home.get_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.no_cache, 1)
        self.assertEqual(context.body_class, "no-web-page-sections")
        self.assertEqual(context.posts, [])
        get_blog_index_data.assert_called_once_with(page="2", category="medical-facilities")

    def test_blog_post_context_delegates_to_service(self):
        context = types.SimpleNamespace(no_cache=0, body_class=None)
        blog.frappe.form_dict = {"slug": "keep-a-lobby-presentation-ready", "preview": "1"}

        with patch(
            "pikt_inc.views.pages.blog.post.blog.get_blog_post_data",
            return_value={
                "page_title": "Keep a Lobby Presentation Ready",
                "metatags": {"title": "Keep a Lobby Presentation Ready", "description": "Lobby routines."},
                "post": {"slug": "keep-a-lobby-presentation-ready"},
                "not_found": 0,
                "noindex_meta": 0,
            },
        ) as get_blog_post_data:
            result = blog_post.get_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.post["slug"], "keep-a-lobby-presentation-ready")
        self.assertEqual(context.no_cache, 1)
        self.assertEqual(context.body_class, "no-web-page-sections")
        get_blog_post_data.assert_called_once_with(slug="keep-a-lobby-presentation-ready", preview="1")

    def test_blog_post_context_sets_http_status_code_for_not_found(self):
        context = types.SimpleNamespace(no_cache=0, body_class=None)
        blog.frappe.form_dict = {"slug": "missing-post"}

        with patch(
            "pikt_inc.views.pages.blog.post.blog.get_blog_post_data",
            return_value={
                "page_title": "Article Not Found",
                "metatags": {"title": "Article Not Found", "description": "Missing."},
                "not_found": 1,
                "post": None,
                "noindex_meta": 1,
            },
        ) as get_blog_post_data:
            result = blog_post.get_context(context)

        self.assertIs(result, context)
        self.assertEqual(context.not_found, 1)
        self.assertEqual(context.http_status_code, 404)
        get_blog_post_data.assert_called_once_with(slug="missing-post", preview=None)

    def test_feed_and_sitemap_controllers_delegate_to_service(self):
        rss_context = types.SimpleNamespace(no_cache=0)
        sitemap_context = types.SimpleNamespace(no_cache=0)

        with patch("pikt_inc.views.pages.blog.rss.blog.get_rss_feed_data", return_value={"posts": []}) as get_rss_feed_data:
            rss_result = blog_rss.get_context(rss_context)
        with patch(
            "pikt_inc.views.pages.blog.sitemap.blog.get_blog_sitemap_data",
            return_value={"links": []},
        ) as get_blog_sitemap_data:
            sitemap_result = blog_sitemap.get_context(sitemap_context)

        self.assertEqual(blog_rss.base_template_path, "www/blog-rss.xml")
        self.assertEqual(blog_sitemap.base_template_path, "www/blog-sitemap.xml")
        self.assertIs(rss_result, rss_context)
        self.assertIs(sitemap_result, sitemap_context)
        self.assertEqual(rss_context.posts, [])
        self.assertEqual(sitemap_context.links, [])
        self.assertEqual(rss_context.no_cache, 1)
        self.assertEqual(sitemap_context.no_cache, 1)
        get_rss_feed_data.assert_called_once_with()
        get_blog_sitemap_data.assert_called_once_with()

    def test_remove_legacy_blog_builder_pages_patch_removes_existing_pages(self):
        existing_docs = {
            ("DocType", "Builder Page"),
            ("Builder Page", "page-blog-index"),
            ("Builder Page", "page-blog-detail"),
        }
        deleted = []
        cleared = []
        fake_frappe = types.SimpleNamespace(
            db=types.SimpleNamespace(exists=lambda doctype, name: (doctype, name) in existing_docs),
            delete_doc=lambda doctype, name, **kwargs: deleted.append((doctype, name, kwargs)),
            clear_cache=lambda: cleared.append(True),
        )

        with patch.object(remove_legacy_blog_builder_pages, "frappe", fake_frappe):
            result = remove_legacy_blog_builder_pages.execute()

        self.assertEqual(result["status"], "removed")
        self.assertEqual(result["removed"], ["page-blog-index", "page-blog-detail"])
        self.assertEqual([name for _doctype, name, _kwargs in deleted], ["page-blog-index", "page-blog-detail"])
        self.assertEqual(len(cleared), 1)

    def test_ensure_starter_blog_content_patch_seeds_empty_sites(self):
        created_docs = []
        cleared = []

        class FakeInsertedDoc:
            def __init__(self, payload):
                self.payload = payload
                self.doctype = payload["doctype"]
                self.name = payload.get("name") or ("MBC-STARTER" if self.doctype == "Marketing Blog Category" else "MBP-STARTER")

            def insert(self, ignore_permissions=False):
                created_docs.append((self.doctype, dict(self.payload), ignore_permissions))
                return self

        fake_frappe = types.SimpleNamespace(
            db=types.SimpleNamespace(
                exists=lambda doctype, name: (doctype, name) in {
                    ("DocType", "Marketing Blog Category"),
                    ("DocType", "Marketing Blog Post"),
                },
                count=lambda doctype: 0 if doctype == "Marketing Blog Post" else 0,
                get_value=lambda doctype, filters, fieldname: None,
            ),
            get_doc=lambda payload: FakeInsertedDoc(payload),
            clear_cache=lambda: cleared.append(True),
        )

        with patch.object(ensure_starter_blog_content, "frappe", fake_frappe):
            result = ensure_starter_blog_content.execute()

        self.assertEqual(result["status"], "created")
        self.assertEqual([doctype for doctype, _payload, _ignore in created_docs], ["Marketing Blog Category", "Marketing Blog Post"])
        self.assertEqual(created_docs[1][1]["category"], "MBC-STARTER")
        self.assertTrue(created_docs[1][1]["published"])
        self.assertEqual(len(cleared), 1)

    def test_ensure_starter_blog_content_patch_skips_when_posts_exist(self):
        fake_frappe = types.SimpleNamespace(
            db=types.SimpleNamespace(
                exists=lambda doctype, name: (doctype, name) in {
                    ("DocType", "Marketing Blog Category"),
                    ("DocType", "Marketing Blog Post"),
                },
                count=lambda doctype: 1 if doctype == "Marketing Blog Post" else 1,
                get_value=lambda doctype, filters, fieldname: "MBC-EXISTING",
            ),
            get_doc=lambda payload: (_ for _ in ()).throw(AssertionError("get_doc should not be called")),
            clear_cache=lambda: (_ for _ in ()).throw(AssertionError("clear_cache should not be called")),
        )

        with patch.object(ensure_starter_blog_content, "frappe", fake_frappe):
            result = ensure_starter_blog_content.execute()

        self.assertEqual(result["status"], "noop")
        self.assertEqual(result["created"], [])

    def test_ensure_starter_blog_content_uses_corrected_starter_title(self):
        self.assertEqual(
            ensure_starter_blog_content.STARTER_POST["title"],
            "How PIKT Plans the First Service Walkthrough",
        )
        self.assertEqual(
            ensure_starter_blog_content.STARTER_POST["seo_title"],
            "How PIKT Plans the First Service Walkthrough",
        )

    def test_blog_surface_files_and_patch_registration(self):
        self.assertFalse(BLOG_BUILDER_FIXTURE_PATH.exists())
        self.assertTrue(BLOG_HOME_TEMPLATE_PATH.exists())
        self.assertTrue(BLOG_POST_TEMPLATE_PATH.exists())
        self.assertTrue(BLOG_RSS_TEMPLATE_PATH.exists())
        self.assertTrue(STARTER_CONTENT_PATCH_PATH.exists())
        self.assertFalse(LEGACY_RSS_CONTROLLER_PATH.exists())
        self.assertFalse(LEGACY_RSS_TEMPLATE_PATH.exists())
        self.assertIn("remove_legacy_blog_builder_pages", PATCHES_PATH.read_text(encoding="utf-8"))
        self.assertIn("ensure_starter_blog_content", PATCHES_PATH.read_text(encoding="utf-8"))
        self.assertIn(
            "/files/PIKT_LOGO_OFFICIAL-2.webp",
            BLOG_HOME_TEMPLATE_PATH.read_text(encoding="utf-8")
            + (APP_PATH / "templates" / "includes" / "site_shell_macros.html").read_text(encoding="utf-8"),
        )
        self.assertEqual(json.loads(WORKSPACE_FIXTURE_PATH.read_text(encoding="utf-8"))[0]["name"], "Marketing Blog")


if __name__ == "__main__":
    import unittest

    unittest.main()
