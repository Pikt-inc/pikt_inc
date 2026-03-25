from __future__ import annotations

import json
import math
import re
import unicodedata
from calendar import month_name
from typing import Any
from urllib.parse import urlencode

import frappe
from frappe.utils import now_datetime


BLOG_PAGE_SIZE = 9
BLOG_PREVIEW_ROLES = {"System Manager", "Website Manager"}
DEFAULT_BLOG_TITLE = "Commercial Cleaning Blog"
DEFAULT_BLOG_DESCRIPTION = (
    "Commercial cleaning insights, facility care guidance, and recurring service ideas "
    "for teams that run real buildings."
)


def clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def truthy(value: Any) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "on"}


def strip_html(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", clean(value))
    return re.sub(r"\s+", " ", text).strip()


def slugify(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", clean(value))
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    normalized = re.sub(r"-{2,}", "-", normalized)
    return normalized


def truncate(value: Any, limit: int) -> str:
    text = clean(value)
    if len(text) <= limit:
        return text
    return text[:limit].rstrip(" -")


def make_excerpt(value: Any, limit: int = 190) -> str:
    text = strip_html(value)
    if len(text) <= limit:
        return text
    shortened = text[:limit].rsplit(" ", 1)[0]
    return (shortened or text[:limit]).rstrip(" .,;:") + "..."


def fail(message: str):
    frappe.throw(message)


def _get_roles() -> set[str]:
    get_roles = getattr(frappe, "get_roles", None)
    session_user = clean(getattr(getattr(frappe, "session", None), "user", None))
    if callable(get_roles):
        try:
            return {clean(role) for role in (get_roles(session_user) or []) if clean(role)}
        except Exception:
            return set()
    return set()


def has_blog_preview_access() -> bool:
    session_user = clean(getattr(getattr(frappe, "session", None), "user", None))
    if not session_user or session_user == "Guest":
        return False
    return bool(_get_roles() & BLOG_PREVIEW_ROLES)


def _get_existing_value(doctype: str, name: str, fields: list[str]) -> dict[str, Any]:
    name = clean(name)
    if not name:
        return {}
    get_value = getattr(frappe.db, "get_value", None)
    if callable(get_value):
        result = get_value(doctype, name, fields, as_dict=True)
        if result:
            if isinstance(result, dict):
                return result
            return dict(result)
    return {}


def _slug_exists(doctype: str, slug: str, current_name: str = "") -> bool:
    slug = clean(slug)
    if not slug:
        return False
    rows = frappe.get_all(doctype, filters={"slug": slug}, fields=["name"], limit=2)
    return any(clean(row.get("name")) != clean(current_name) for row in rows)


def _make_unique_slug(doctype: str, seed: str, current_name: str = "") -> str:
    base_slug = slugify(seed)
    if not base_slug:
        fail("Enter a title that can be converted into a URL slug.")
    candidate = base_slug
    suffix = 2
    while _slug_exists(doctype, candidate, current_name):
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    return candidate


def _current_user_author_name() -> str:
    session_user = clean(getattr(getattr(frappe, "session", None), "user", None))
    if not session_user or session_user == "Guest":
        return "Pikt Team"
    get_value = getattr(frappe.db, "get_value", None)
    if callable(get_value):
        full_name = clean(get_value("User", session_user, "full_name"))
        if full_name:
            return full_name
    return session_user


def _normalize_slug_input(slug_value: Any, title_value: Any) -> tuple[str, bool]:
    raw_slug = clean(slug_value)
    if raw_slug:
        return slugify(raw_slug), True
    return slugify(title_value), False


def prepare_blog_category_for_save(doc):
    doc.title = truncate(clean(getattr(doc, "title", None)), 140)
    if not doc.title:
        fail("Title is required.")

    requested_slug = clean(getattr(doc, "slug", None))
    doc.slug = slugify(requested_slug or doc.title)
    if not doc.slug:
        fail("Enter a category title that can be converted into a slug.")

    if _slug_exists("Marketing Blog Category", doc.slug, clean(getattr(doc, "name", None))):
        fail(f"Category slug '{doc.slug}' is already in use.")

    doc.description = truncate(clean(getattr(doc, "description", None)), 280)

    return {"status": "prepared", "slug": doc.slug}


def prepare_blog_post_for_save(doc):
    doc.title = truncate(clean(getattr(doc, "title", None)), 140)
    if not doc.title:
        fail("Title is required.")

    if not clean(getattr(doc, "category", None)):
        fail("Category is required.")

    if not clean(getattr(doc, "body_html", None)):
        fail("Body is required.")

    existing = _get_existing_value(
        "Marketing Blog Post",
        clean(getattr(doc, "name", None)),
        ["name", "slug", "published", "published_on"],
    )
    requested_slug, user_provided_slug = _normalize_slug_input(getattr(doc, "slug", None), doc.title)
    if not requested_slug:
        fail("Enter a title that can be converted into a URL slug.")

    if existing and clean(existing.get("published_on")) and requested_slug != clean(existing.get("slug")):
        fail("Slug cannot be changed after the post has been published.")

    if user_provided_slug and _slug_exists("Marketing Blog Post", requested_slug, clean(getattr(doc, "name", None))):
        fail(f"Slug '{requested_slug}' is already in use.")

    doc.slug = requested_slug if user_provided_slug else _make_unique_slug(
        "Marketing Blog Post",
        requested_slug or doc.title,
        clean(getattr(doc, "name", None)),
    )

    if not clean(getattr(doc, "author_name", None)):
        doc.author_name = _current_user_author_name()

    excerpt = clean(getattr(doc, "excerpt", None))
    if not excerpt:
        doc.excerpt = make_excerpt(getattr(doc, "body_html", None))
    else:
        doc.excerpt = truncate(excerpt, 220)

    if truthy(getattr(doc, "published", None)) and not getattr(doc, "published_on", None):
        doc.published_on = now_datetime()

    return {"status": "prepared", "slug": doc.slug}


def _format_public_date(value: Any) -> str:
    if not value:
        return ""
    dt = value if hasattr(value, "strftime") else now_datetime()
    try:
        dt = value if hasattr(value, "year") else frappe.utils.get_datetime(value)
    except Exception:
        return clean(value)
    return f"{month_name[dt.month]} {dt.day}, {dt.year}"


def _format_rss_date(value: Any) -> str:
    if not value:
        return ""
    try:
        dt = value if hasattr(value, "strftime") else frappe.utils.get_datetime(value)
    except Exception:
        return ""
    return dt.strftime("%a, %d %b %Y %H:%M:%S +0000")


def _site_url(path: str = "") -> str:
    path = clean(path)
    if not path.startswith("/") and path:
        path = "/" + path
    get_url = getattr(frappe.utils, "get_url", None)
    if callable(get_url):
        return get_url(path or "/")
    return path or "/"


def _blog_post_path(slug: str) -> str:
    return f"/blog/{clean(slug)}"


def _blog_index_path(page: int = 1, category_slug: str = "") -> str:
    params = {}
    if clean(category_slug):
        params["category"] = clean(category_slug)
    if int(page or 1) > 1:
        params["page"] = int(page)
    query = urlencode(params)
    return "/blog" if not query else f"/blog?{query}"


def _sanitize_page_number(value: Any) -> int:
    try:
        page = int(clean(value) or "1")
    except Exception:
        page = 1
    return max(page, 1)


def _get_category_map() -> dict[str, dict[str, Any]]:
    rows = frappe.get_all(
        "Marketing Blog Category",
        fields=["name", "title", "slug", "description"],
        order_by="title asc",
    )
    return {clean(row.get("name")): row for row in rows}


def _get_category_by_slug(slug: Any) -> dict[str, Any]:
    slug = clean(slug)
    if not slug:
        return {}
    rows = frappe.get_all(
        "Marketing Blog Category",
        filters={"slug": slug},
        fields=["name", "title", "slug", "description"],
        limit=1,
    )
    return (rows or [{}])[0]


def _build_post_summary(row: dict[str, Any], category_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    category = category_map.get(clean(row.get("category")), {})
    slug = clean(row.get("slug"))
    return {
        "name": clean(row.get("name")),
        "title": clean(row.get("title")),
        "slug": slug,
        "url": _blog_post_path(slug),
        "excerpt": clean(row.get("excerpt")) or make_excerpt(row.get("body_html")),
        "cover_image": clean(row.get("cover_image")) or clean(row.get("og_image")),
        "author_name": clean(row.get("author_name")) or "Pikt Team",
        "published_on": row.get("published_on"),
        "published_label": _format_public_date(row.get("published_on")),
        "featured": int(truthy(row.get("featured"))),
        "category_title": clean(category.get("title")),
        "category_slug": clean(category.get("slug")),
        "category_url": _blog_index_path(category_slug=clean(category.get("slug"))),
    }


def _build_pagination(page: int, total_count: int, category_slug: str = "") -> dict[str, Any]:
    page_count = max(1, math.ceil((total_count or 0) / BLOG_PAGE_SIZE)) if total_count else 1
    page = min(max(page, 1), page_count)
    pages = [
        {
            "number": number,
            "label": str(number),
            "url": _blog_index_path(page=number, category_slug=category_slug),
            "is_current": int(number == page),
        }
        for number in range(1, page_count + 1)
    ]
    return {
        "page": page,
        "page_count": page_count,
        "total_count": total_count,
        "has_prev": int(page > 1),
        "has_next": int(page < page_count),
        "prev_url": _blog_index_path(page=page - 1, category_slug=category_slug) if page > 1 else "",
        "next_url": _blog_index_path(page=page + 1, category_slug=category_slug) if page < page_count else "",
        "pages": pages,
    }


def _collection_json_ld(posts: list[dict[str, Any]], page_title: str, page_url: str) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": page_title,
        "url": page_url,
        "description": DEFAULT_BLOG_DESCRIPTION,
        "mainEntity": {
            "@type": "ItemList",
            "itemListElement": [
                {
                    "@type": "ListItem",
                    "position": index + 1,
                    "url": _site_url(post["url"]),
                    "name": post["title"],
                }
                for index, post in enumerate(posts)
            ],
        },
    }
    return json.dumps(payload, separators=(",", ":"))


def _article_json_ld(post: dict[str, Any]) -> str:
    payload = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post["title"],
        "description": post["seo_description"] or post["excerpt"],
        "url": post["canonical_url"],
        "datePublished": clean(post.get("published_on")),
        "dateModified": clean(post.get("modified")),
        "author": {"@type": "Person", "name": post["author_name"] or "Pikt Team"},
    }
    image = post.get("og_image") or post.get("cover_image")
    if image:
        payload["image"] = _site_url(image)
    return json.dumps(payload, separators=(",", ":"))


def _blog_meta(title: str, description: str, image: str = "") -> dict[str, Any]:
    meta = {"title": title, "description": description}
    if clean(image):
        meta["image"] = clean(image)
    return meta


def _resolve_public_post(slug: str, include_unpublished: bool = False) -> dict[str, Any]:
    filters = {"slug": clean(slug)}
    if not include_unpublished:
        filters["published"] = 1
    rows = frappe.get_all(
        "Marketing Blog Post",
        filters=filters,
        fields=[
            "name",
            "title",
            "slug",
            "published",
            "published_on",
            "category",
            "author_name",
            "excerpt",
            "cover_image",
            "body_html",
            "seo_title",
            "seo_description",
            "canonical_url",
            "og_image",
            "no_index",
            "featured",
            "modified",
        ],
        limit=1,
    )
    return (rows or [{}])[0]


def _mark_not_found() -> None:
    local = getattr(frappe, "local", None)
    response = getattr(local, "response", None)
    if isinstance(response, dict):
        response["http_status_code"] = 404


def get_blog_index_data(page: Any = None, category: Any = None) -> dict[str, Any]:
    page_number = _sanitize_page_number(page)
    active_category = _get_category_by_slug(category)
    active_category_slug = clean(active_category.get("slug"))

    filters = {"published": 1}
    if active_category:
        filters["category"] = clean(active_category.get("name"))

    total_count = int(getattr(frappe.db, "count")("Marketing Blog Post", filters=filters) or 0)
    pagination = _build_pagination(page_number, total_count, active_category_slug)
    offset = (pagination["page"] - 1) * BLOG_PAGE_SIZE
    rows = frappe.get_all(
        "Marketing Blog Post",
        filters=filters,
        fields=[
            "name",
            "title",
            "slug",
            "published_on",
            "category",
            "author_name",
            "excerpt",
            "body_html",
            "cover_image",
            "og_image",
            "featured",
        ],
        order_by="featured desc, published_on desc, modified desc",
        limit_start=offset,
        limit_page_length=BLOG_PAGE_SIZE,
    )
    category_map = _get_category_map()
    posts = [_build_post_summary(row, category_map) for row in rows]

    categories = [
        {
            "title": clean(row.get("title")),
            "slug": clean(row.get("slug")),
            "url": _blog_index_path(category_slug=clean(row.get("slug"))),
            "is_active": int(clean(row.get("slug")) == active_category_slug),
        }
        for row in category_map.values()
    ]

    page_title = DEFAULT_BLOG_TITLE
    if clean(active_category.get("title")):
        page_title = f"{clean(active_category.get('title'))} | {DEFAULT_BLOG_TITLE}"

    canonical_url = _site_url(_blog_index_path(page=pagination["page"], category_slug=active_category_slug))
    return {
        "title": page_title,
        "page_title": page_title,
        "canonical_url": canonical_url,
        "metatags": _blog_meta(page_title, DEFAULT_BLOG_DESCRIPTION),
        "structured_data_json": _collection_json_ld(posts, page_title, canonical_url),
        "rss_url": _site_url("/blog/rss.xml"),
        "blog_sitemap_url": _site_url("/blog-sitemap.xml"),
        "noindex_meta": 0,
        "posts": posts,
        "categories": categories,
        "active_category_title": clean(active_category.get("title")),
        "active_category_slug": active_category_slug,
        "pagination": pagination,
        "empty_state_title": "No blog posts match this filter yet.",
        "empty_state_copy": "Try another category or check back after the next article is published.",
    }


def get_blog_post_data(slug: Any, preview: Any = None) -> dict[str, Any]:
    slug = clean(slug)
    allow_preview = truthy(preview) and has_blog_preview_access()
    row = _resolve_public_post(slug, include_unpublished=allow_preview)
    if not row:
        _mark_not_found()
        return {
            "title": "Article Not Found",
            "page_title": "Article Not Found",
            "canonical_url": _site_url("/blog"),
            "metatags": _blog_meta("Article Not Found", "The requested article could not be found."),
            "structured_data_json": "",
            "rss_url": _site_url("/blog/rss.xml"),
            "blog_sitemap_url": _site_url("/blog-sitemap.xml"),
            "noindex_meta": 1,
            "not_found": 1,
            "post": None,
            "related_posts": [],
            "previous_post": None,
            "next_post": None,
        }

    category_map = _get_category_map()
    post = _build_post_summary(row, category_map)
    post.update(
        {
            "body_html": clean(row.get("body_html")),
            "seo_title": clean(row.get("seo_title")) or post["title"],
            "seo_description": clean(row.get("seo_description")) or post["excerpt"],
            "canonical_url": clean(row.get("canonical_url")) or _site_url(post["url"]),
            "og_image": clean(row.get("og_image")) or clean(row.get("cover_image")),
            "no_index": int(truthy(row.get("no_index"))),
            "modified": row.get("modified"),
        }
    )

    related_rows = frappe.get_all(
        "Marketing Blog Post",
        filters={
            "published": 1,
            "category": clean(row.get("category")),
            "name": ["!=", clean(row.get("name"))],
        },
        fields=[
            "name",
            "title",
            "slug",
            "published_on",
            "category",
            "author_name",
            "excerpt",
            "body_html",
            "cover_image",
            "og_image",
            "featured",
        ],
        order_by="featured desc, published_on desc, modified desc",
        limit_page_length=3,
    )
    related_posts = [_build_post_summary(item, category_map) for item in related_rows]

    ordered_rows = frappe.get_all(
        "Marketing Blog Post",
        filters={"published": 1},
        fields=["name", "title", "slug", "published_on", "category", "author_name", "excerpt", "body_html", "cover_image", "og_image", "featured"],
        order_by="published_on desc, modified desc",
    )
    ordered_posts = [_build_post_summary(item, category_map) for item in ordered_rows]
    current_index = next(
        (index for index, item in enumerate(ordered_posts) if clean(item.get("name")) == clean(row.get("name"))),
        -1,
    )
    previous_post = ordered_posts[current_index - 1] if current_index > 0 else None
    next_post = ordered_posts[current_index + 1] if current_index != -1 and current_index + 1 < len(ordered_posts) else None

    title = post["seo_title"]
    description = post["seo_description"]
    return {
        "title": title,
        "page_title": title,
        "canonical_url": post["canonical_url"],
        "metatags": _blog_meta(title, description, post["og_image"]),
        "structured_data_json": _article_json_ld(post),
        "rss_url": _site_url("/blog/rss.xml"),
        "blog_sitemap_url": _site_url("/blog-sitemap.xml"),
        "noindex_meta": int(post["no_index"]),
        "not_found": 0,
        "post": post,
        "related_posts": related_posts,
        "previous_post": previous_post,
        "next_post": next_post,
    }


def get_rss_feed_data() -> dict[str, Any]:
    rows = frappe.get_all(
        "Marketing Blog Post",
        filters={"published": 1, "no_index": 0},
        fields=[
            "title",
            "slug",
            "excerpt",
            "published_on",
            "modified",
            "author_name",
            "body_html",
        ],
        order_by="published_on desc, modified desc",
        limit_page_length=25,
    )
    posts = []
    for row in rows:
        url = _site_url(_blog_post_path(clean(row.get("slug"))))
        posts.append(
            {
                "title": clean(row.get("title")),
                "url": url,
                "guid": url,
                "description": clean(row.get("excerpt")) or make_excerpt(row.get("body_html")),
                "published_label": _format_rss_date(row.get("published_on")),
                "author_name": clean(row.get("author_name")) or "Pikt Team",
                "modified": row.get("modified") or row.get("published_on"),
            }
        )
    last_modified = posts[0]["published_label"] if posts else _format_rss_date(now_datetime())
    return {
        "channel_title": DEFAULT_BLOG_TITLE,
        "channel_link": _site_url("/blog"),
        "channel_description": DEFAULT_BLOG_DESCRIPTION,
        "channel_language": "en-us",
        "last_build_date": last_modified,
        "posts": posts,
    }


def get_blog_sitemap_data() -> dict[str, Any]:
    rows = frappe.get_all(
        "Marketing Blog Post",
        filters={"published": 1, "no_index": 0},
        fields=["slug", "modified"],
        order_by="published_on desc, modified desc",
    )
    return {
        "links": [
            {
                "loc": _site_url(_blog_post_path(clean(row.get("slug")))),
                "lastmod": clean(getattr(row.get("modified"), "date", lambda: row.get("modified"))()),
            }
            if hasattr(row.get("modified"), "date")
            else {
                "loc": _site_url(_blog_post_path(clean(row.get("slug")))),
                "lastmod": clean(row.get("modified")),
            }
            for row in rows
        ]
    }
