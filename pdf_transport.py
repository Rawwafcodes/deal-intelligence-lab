"""How a request's PDFs reach Claude: inline base64, or the Files API when
they are too large to send inline.

Task 18.3 follow-up (M18 Track B failure mode): the scanned 54 MB technical
offer in the الكعكية bid could not be analysed at all, because every PDF was
sent inline and the combined inline payload is capped just under Anthropic's
32 MB request limit (`pdf_inspection.MAX_PDF_SOURCE_BYTES`).

Inline base64 stays the default, for the reason `pdf_inspection`'s docstring
gives: it creates no persistent copy on Anthropic's side. Only when a
request's PDFs together exceed the inline cap are they uploaded to the Files
API and referenced by `file_id` instead - and, exactly like the Excel
workbooks `cross_format_analysis` already uploads, every uploaded copy is
deleted again on every exit path (the callers' existing cleanup runs on
success and on each failure). Citations work the same way for both sources.

A request is all-inline or all-uploaded, never mixed, so block order and the
"PDF document blocks come first, in selection order" assumption callers rely
on are unchanged.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path

from anthropic.types import DocumentBlockParam

import pdf_inspection
import xlsx_inspection

# The existing inline ceiling (derived from the 32 MB request limit).
MAX_INLINE_PDF_SOURCE_BYTES = pdf_inspection.MAX_PDF_SOURCE_BYTES

# Hard ceilings once the Files API is used: Anthropic's per-file limit, and
# the same figure as a total so one request can't balloon without bound. The
# real per-request limits beyond this (600 pages, the model's context window)
# are reported by the API itself.
MAX_UPLOADED_PDF_FILE_BYTES = int(os.environ.get("DEAL_LAB_MAX_UPLOADED_PDF_FILE_BYTES", 500 * 1024 * 1024))
MAX_TOTAL_UPLOADED_PDF_BYTES = int(os.environ.get("DEAL_LAB_MAX_TOTAL_UPLOADED_PDF_BYTES", 500 * 1024 * 1024))


def use_files_api(total_pdf_bytes: int) -> bool:
    return total_pdf_bytes > MAX_INLINE_PDF_SOURCE_BYTES


def oversized(total_pdf_bytes: int, largest_pdf_bytes: int) -> bool:
    """Too large even for the Files API path."""
    return total_pdf_bytes > MAX_TOTAL_UPLOADED_PDF_BYTES or largest_pdf_bytes > MAX_UPLOADED_PDF_FILE_BYTES


def inline_block(path: Path, title: str) -> DocumentBlockParam:
    return {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": base64.standard_b64encode(path.read_bytes()).decode("ascii")},
        "title": title,
        "citations": {"enabled": True},
    }


def file_block(file_id: str, title: str) -> DocumentBlockParam:
    return {
        "type": "document",
        "source": {"type": "file", "file_id": file_id},
        "title": title,
        "citations": {"enabled": True},
    }


def upload(client, path: Path, filename: str) -> str:
    """Uploads one PDF to the Files API and returns its file_id. SDK errors
    propagate so the caller maps them exactly as it maps Excel uploads."""
    with open(path, "rb") as fh:
        return client.files.upload(file=(xlsx_inspection._files_api_safe_filename(filename), fh, "application/pdf")).id
