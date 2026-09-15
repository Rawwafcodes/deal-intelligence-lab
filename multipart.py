"""Minimal multipart/form-data parser (RFC 7578), standard library only.

Python's `cgi` module traditionally handled this but is deprecated and
slated for removal, so this implements just enough of the spec for our
needs: form fields and file parts, parsed from an in-memory body.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_CONTENT_DISPOSITION_RE = re.compile(rb'Content-Disposition:\s*form-data;\s*(.*)', re.IGNORECASE)
_PARAM_RE = re.compile(r'(\w+)="((?:[^"\\]|\\.)*)"')
_CONTENT_TYPE_RE = re.compile(rb'Content-Type:\s*(.+)', re.IGNORECASE)


@dataclass
class Part:
    name: str
    filename: str | None
    content_type: str | None
    data: bytes


class MultipartError(ValueError):
    pass


def parse_boundary(content_type_header: str) -> bytes:
    """Extract the boundary token from a Content-Type header value."""
    match = re.search(r'boundary="?([^";]+)"?', content_type_header, re.IGNORECASE)
    if not match:
        raise MultipartError("no boundary found in Content-Type header")
    return match.group(1).encode("utf-8")


def _unescape(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _parse_headers(header_block: bytes) -> tuple[str, str | None, str | None]:
    name = ""
    filename: str | None = None
    content_type: str | None = None

    for line in header_block.split(b"\r\n"):
        if not line:
            continue
        disp_match = _CONTENT_DISPOSITION_RE.match(line)
        if disp_match:
            params_text = disp_match.group(1).decode("utf-8", errors="replace")
            for key, value in _PARAM_RE.findall(params_text):
                if key == "name":
                    name = _unescape(value)
                elif key == "filename":
                    filename = _unescape(value)
            continue
        type_match = _CONTENT_TYPE_RE.match(line)
        if type_match:
            content_type = type_match.group(1).decode("utf-8", errors="replace").strip()

    if not name:
        raise MultipartError("form-data part missing name")

    return name, filename, content_type


def parse_multipart(body: bytes, boundary: bytes) -> list[Part]:
    """Parse a multipart/form-data body into a list of Part objects."""
    delimiter = b"--" + boundary
    if delimiter not in body:
        raise MultipartError("boundary not found in body")

    # Split on the delimiter; drop the preamble (before the first delimiter)
    # and the epilogue (after the closing "--boundary--").
    segments = body.split(delimiter)
    parts: list[Part] = []

    for segment in segments[1:]:
        if segment.startswith(b"--"):
            break  # closing delimiter
        # Each segment looks like: \r\n<headers>\r\n\r\n<data>\r\n
        segment = segment[2:] if segment.startswith(b"\r\n") else segment
        header_end = segment.find(b"\r\n\r\n")
        if header_end == -1:
            continue
        header_block = segment[:header_end]
        data = segment[header_end + 4:]
        if data.endswith(b"\r\n"):
            data = data[:-2]

        name, filename, content_type = _parse_headers(header_block)
        parts.append(Part(name=name, filename=filename, content_type=content_type, data=data))

    return parts
