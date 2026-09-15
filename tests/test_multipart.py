"""Unit tests for the hand-rolled multipart/form-data parser."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import multipart


def build_body(boundary: str, parts: list[dict]) -> bytes:
    """Build a multipart body from a list of {name, filename?, content_type?, data} dicts."""
    chunks = []
    b = boundary.encode()
    for part in parts:
        chunks.append(b"--" + b + b"\r\n")
        disposition = f'Content-Disposition: form-data; name="{part["name"]}"'
        if "filename" in part:
            disposition += f'; filename="{part["filename"]}"'
        chunks.append(disposition.encode("utf-8") + b"\r\n")
        if "content_type" in part:
            chunks.append(f"Content-Type: {part['content_type']}\r\n".encode())
        chunks.append(b"\r\n")
        data = part["data"]
        chunks.append(data if isinstance(data, bytes) else data.encode("utf-8"))
        chunks.append(b"\r\n")
    chunks.append(b"--" + b + b"--\r\n")
    return b"".join(chunks)


class MultipartTests(unittest.TestCase):
    def test_parse_boundary_from_content_type_header(self):
        boundary = multipart.parse_boundary('multipart/form-data; boundary=abc123')
        self.assertEqual(boundary, b"abc123")

    def test_parse_boundary_quoted(self):
        boundary = multipart.parse_boundary('multipart/form-data; boundary="abc 123"')
        self.assertEqual(boundary, b"abc 123")

    def test_parse_boundary_missing_raises(self):
        with self.assertRaises(multipart.MultipartError):
            multipart.parse_boundary("multipart/form-data")

    def test_single_text_field(self):
        body = build_body("BOUNDARY", [{"name": "project_id", "data": "abc123"}])
        parts = multipart.parse_multipart(body, b"BOUNDARY")
        self.assertEqual(len(parts), 1)
        self.assertEqual(parts[0].name, "project_id")
        self.assertIsNone(parts[0].filename)
        self.assertEqual(parts[0].data, b"abc123")

    def test_file_part_with_content_type(self):
        body = build_body(
            "BOUNDARY",
            [{"name": "files", "filename": "report.pdf", "content_type": "application/pdf", "data": b"%PDF-1.4 fake"}],
        )
        parts = multipart.parse_multipart(body, b"BOUNDARY")
        self.assertEqual(len(parts), 1)
        part = parts[0]
        self.assertEqual(part.name, "files")
        self.assertEqual(part.filename, "report.pdf")
        self.assertEqual(part.content_type, "application/pdf")
        self.assertEqual(part.data, b"%PDF-1.4 fake")

    def test_multiple_parts_preserve_order(self):
        body = build_body(
            "BOUNDARY",
            [
                {"name": "files", "filename": "a.txt", "data": "AAA"},
                {"name": "relative_paths", "data": "folder/a.txt"},
                {"name": "files", "filename": "b.txt", "data": "BBB"},
                {"name": "relative_paths", "data": ""},
            ],
        )
        parts = multipart.parse_multipart(body, b"BOUNDARY")
        self.assertEqual([p.filename for p in parts if p.name == "files"], ["a.txt", "b.txt"])
        self.assertEqual([p.data for p in parts if p.name == "relative_paths"], [b"folder/a.txt", b""])

    def test_binary_data_with_embedded_boundary_like_bytes(self):
        binary_data = bytes(range(256)) * 4
        body = build_body("BOUNDARY", [{"name": "files", "filename": "blob.bin", "data": binary_data}])
        parts = multipart.parse_multipart(body, b"BOUNDARY")
        self.assertEqual(parts[0].data, binary_data)

    def test_filename_with_escaped_quote(self):
        body = build_body("BOUNDARY", [{"name": "files", "filename": 'weird \\"name\\".txt', "data": "x"}])
        parts = multipart.parse_multipart(body, b"BOUNDARY")
        self.assertEqual(parts[0].filename, 'weird "name".txt')

    def test_missing_boundary_in_body_raises(self):
        with self.assertRaises(multipart.MultipartError):
            multipart.parse_multipart(b"not a multipart body", b"BOUNDARY")

    def test_part_without_name_raises(self):
        malformed = b'--BOUNDARY\r\nContent-Disposition: form-data\r\n\r\ndata\r\n--BOUNDARY--\r\n'
        with self.assertRaises(multipart.MultipartError):
            multipart.parse_multipart(malformed, b"BOUNDARY")

    def test_empty_file_part(self):
        body = build_body("BOUNDARY", [{"name": "files", "filename": "empty.txt", "data": b""}])
        parts = multipart.parse_multipart(body, b"BOUNDARY")
        self.assertEqual(parts[0].data, b"")


if __name__ == "__main__":
    unittest.main()
