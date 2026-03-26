from __future__ import annotations

from pikt_inc.services import contact_request as contact_request_service


sitemap = 1


def get_context(context):
    context.no_cache = 1
    context.body_class = "no-web-page-sections"
    context.page_title = "Contact Pikt"
    context.meta_description = (
        "Contact Pikt about recurring commercial cleaning, walkthrough requests, and scope questions for your facility."
    )
    context.description = context.meta_description
    context.request_type_options = list(contact_request_service.CONTACT_REQUEST_TYPE_OPTIONS)
    return context
