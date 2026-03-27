from __future__ import annotations

from pikt_inc.views.pages.contact import ContactPageView


sitemap = ContactPageView.sitemap


def get_context(context):
    """Build the contact page context through the shared contact page view.

    :param context: The mutable Frappe page context object.
    :returns: The populated contact page context.
    """
    return ContactPageView().build_context(context)
