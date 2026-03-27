from __future__ import annotations

from pikt_inc.services import contact_request as contact_request_service
from pikt_inc.views.public import PublicPageView


class ContactPageView(PublicPageView):
    """Public contact page backed by the shared page-view abstraction."""

    sitemap = 1
    page_title = "Contact Pikt"
    meta_description = (
        "Contact Pikt about recurring commercial cleaning, walkthrough requests, and scope questions for your facility."
    )

    def get_page_data(self) -> dict[str, object]:
        """Build the contact page payload.

        :returns: Page payload containing the contact-form request type options.
        """
        return {
            "request_type_options": list(contact_request_service.CONTACT_REQUEST_TYPE_OPTIONS),
        }
