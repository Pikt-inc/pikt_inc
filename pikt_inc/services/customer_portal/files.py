from __future__ import annotations

import frappe

from ..contracts.common import clean_str
from .models import FileDownload


def apply_file_download(download: FileDownload) -> None:
    local = getattr(frappe, "local", None)
    if local is None:
        return

    response = getattr(local, "response", None)
    if response is None:
        local.response = {}
        response = local.response

    response["filename"] = clean_str(download.filename)
    response["filecontent"] = download.content
    response["type"] = "download" if download.as_attachment else "binary"
    response["content_type"] = clean_str(download.content_type) or "application/octet-stream"
