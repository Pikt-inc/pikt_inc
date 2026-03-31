from __future__ import annotations

import frappe


STARTER_CATEGORY = {
    "title": "Operations",
    "slug": "operations",
    "description": "Practical guidance for recurring service accounts and facility operators.",
}

STARTER_POST = {
    "title": "How PIKT Plans the First Service Walkthrough",
    "slug": "how-pikt-plans-the-first-service-walkthrough",
    "published": 1,
    "featured": 1,
    "author_name": "Pikt Team",
    "excerpt": "A quick look at how we confirm scope, note access details, and set the service routine before recurring cleaning begins.",
    "body_html": """
<p>The first walkthrough is where the operating details get locked in. Before recurring service starts, we verify access instructions, confirm scope, and note the surfaces that need extra attention during the opening visits.</p>
<h2>What we confirm on the walkthrough</h2>
<p>We review the agreed scope, document room priorities, identify supply or trash expectations, and confirm any lockup or alarm details that affect the cleaning crew. That reduces ambiguity once service begins.</p>
<h2>How it helps the ongoing schedule</h2>
<p>When the walkthrough is documented well, recurring service becomes more consistent. Supervisors know what was promised, technicians know what matters most on the site, and the client has a cleaner handoff from quoting into active service.</p>
<p>That operating discipline is what keeps routine service dependable after the first week.</p>
""".strip(),
    "seo_title": "How PIKT Plans the First Service Walkthrough",
    "seo_description": "See how Pikt uses the first service walkthrough to confirm scope, access details, and recurring cleaning priorities.",
}


def execute():
    if not frappe.db.exists("DocType", "Marketing Blog Category") or not frappe.db.exists(
        "DocType", "Marketing Blog Post"
    ):
        return {"status": "missing-doctype", "created": []}

    if frappe.db.count("Marketing Blog Post"):
        return {"status": "noop", "created": []}

    created = []
    category_name = frappe.db.get_value(
        "Marketing Blog Category",
        {"slug": STARTER_CATEGORY["slug"]},
        "name",
    )

    if not category_name:
        category = frappe.get_doc({"doctype": "Marketing Blog Category", **STARTER_CATEGORY})
        category.insert(ignore_permissions=True)
        category_name = category.name
        created.append(category_name)

    post = frappe.get_doc(
        {
            "doctype": "Marketing Blog Post",
            "category": category_name,
            **STARTER_POST,
        }
    )
    post.insert(ignore_permissions=True)
    created.append(post.name)
    frappe.clear_cache()

    return {"status": "created", "created": created}
