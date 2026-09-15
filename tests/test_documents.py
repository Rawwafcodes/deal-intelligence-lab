"""Integration tests for document upload, inventory, download, and deletion."""

import hashlib
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import documents
import server
import store
from tests.test_multipart import build_body


def multipart_request(url: str, boundary: str, body: bytes, method: str = "POST"):
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method=method,
    )
    return urllib.request.urlopen(req)


def build_upload_body(boundary: str, files: list[tuple[str, str, bytes]]) -> bytes:
    """files: list of (filename, relative_path, data)."""
    parts = []
    for filename, relative_path, data in files:
        parts.append({"name": "files", "filename": filename, "data": data})
    for _, relative_path, _ in files:
        parts.append({"name": "relative_paths", "data": relative_path})
    return build_body(boundary, parts)


class DocumentsTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread
    project: store.Project

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_db_path = store.DB_PATH
        cls._original_data_dir = documents.DATA_DIR
        store.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        store.init_db()
        documents.init_documents_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.project = store.create_project("Project Falcon", "test project for document uploads")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.DB_PATH = cls._original_db_path
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def test_upload_single_file_appears_in_inventory(self):
        data = b"%PDF-1.4 fake pdf contents"
        body = build_upload_body("BOUND1", [("report.pdf", "", data)])
        with multipart_request(self._url(f"/api/projects/{self.project.id}/documents"), "BOUND1", body) as res:
            payload = json.loads(res.read())

        self.assertEqual(len(payload["results"]), 1)
        self.assertEqual(payload["results"][0]["status"], "success")
        doc = payload["results"][0]["document"]
        self.assertEqual(doc["original_filename"], "report.pdf")
        self.assertEqual(doc["sha256"], hashlib.sha256(data).hexdigest())
        self.assertEqual(doc["size_bytes"], len(data))

        with urllib.request.urlopen(self._url(f"/api/projects/{self.project.id}/documents")) as res:
            inventory = json.loads(res.read())
        self.assertTrue(any(d["id"] == doc["id"] for d in inventory))

    def test_upload_multiple_files_at_once(self):
        files = [
            ("a.txt", "", b"file A contents"),
            ("b.xlsx", "", b"PK fake xlsx contents"),
            ("c.docx", "", b"PK fake docx contents"),
        ]
        body = build_upload_body("BOUND2", files)
        with multipart_request(self._url(f"/api/projects/{self.project.id}/documents"), "BOUND2", body) as res:
            payload = json.loads(res.read())

        statuses = [r["status"] for r in payload["results"]]
        self.assertEqual(statuses, ["success", "success", "success"])

    def test_folder_relative_path_is_preserved(self):
        data = b"nested folder file"
        body = build_upload_body("BOUND3", [("nested.txt", "Contracts/Subfolder/nested.txt", data)])
        with multipart_request(self._url(f"/api/projects/{self.project.id}/documents"), "BOUND3", body) as res:
            payload = json.loads(res.read())

        doc = payload["results"][0]["document"]
        self.assertEqual(doc["relative_path"], "Contracts/Subfolder")
        self.assertEqual(doc["original_filename"], "nested.txt")

    def test_duplicate_upload_is_reported_and_not_duplicated_on_disk(self):
        data = b"identical bytes for dedup test"
        body1 = build_upload_body("BOUND4A", [("dup.txt", "", data)])
        with multipart_request(self._url(f"/api/projects/{self.project.id}/documents"), "BOUND4A", body1) as res:
            first = json.loads(res.read())
        self.assertEqual(first["results"][0]["status"], "success")

        body2 = build_upload_body("BOUND4B", [("dup-renamed.txt", "", data)])
        with multipart_request(self._url(f"/api/projects/{self.project.id}/documents"), "BOUND4B", body2) as res:
            second = json.loads(res.read())
        self.assertEqual(second["results"][0]["status"], "duplicate")

        with urllib.request.urlopen(self._url(f"/api/projects/{self.project.id}/documents")) as res:
            inventory = json.loads(res.read())
        matching = [d for d in inventory if d["sha256"] == hashlib.sha256(data).hexdigest()]
        self.assertEqual(len(matching), 1)

    def test_unsupported_extension_is_rejected(self):
        body = build_upload_body("BOUND5", [("virus.exe", "", b"MZ fake executable")])
        with multipart_request(self._url(f"/api/projects/{self.project.id}/documents"), "BOUND5", body) as res:
            payload = json.loads(res.read())

        self.assertEqual(payload["results"][0]["status"], "unsupported_type")

        with urllib.request.urlopen(self._url(f"/api/projects/{self.project.id}/documents")) as res:
            inventory = json.loads(res.read())
        self.assertFalse(any(d["original_filename"] == "virus.exe" for d in inventory))

    def test_download_returns_byte_for_byte_original(self):
        data = bytes(range(256)) * 100  # arbitrary binary content
        body = build_upload_body("BOUND6", [("binary.png", "", data)])
        with multipart_request(self._url(f"/api/projects/{self.project.id}/documents"), "BOUND6", body) as res:
            payload = json.loads(res.read())
        doc_id = payload["results"][0]["document"]["id"]

        with urllib.request.urlopen(
            self._url(f"/api/projects/{self.project.id}/documents/{doc_id}/download")
        ) as res:
            downloaded = res.read()
            content_disposition = res.headers.get("Content-Disposition", "")

        self.assertEqual(downloaded, data)
        self.assertEqual(hashlib.sha256(downloaded).hexdigest(), hashlib.sha256(data).hexdigest())
        self.assertIn("attachment", content_disposition)
        self.assertIn("binary.png", content_disposition)

    def test_delete_requires_confirmation(self):
        body = build_upload_body("BOUND7", [("to-delete.txt", "", b"delete me")])
        with multipart_request(self._url(f"/api/projects/{self.project.id}/documents"), "BOUND7", body) as res:
            payload = json.loads(res.read())
        doc_id = payload["results"][0]["document"]["id"]

        req = urllib.request.Request(
            self._url(f"/api/projects/{self.project.id}/documents/{doc_id}"),
            data=json.dumps({}).encode(),
            headers={"Content-Type": "application/json"},
            method="DELETE",
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

        req = urllib.request.Request(
            self._url(f"/api/projects/{self.project.id}/documents/{doc_id}"),
            data=json.dumps({"confirm": True}).encode(),
            headers={"Content-Type": "application/json"},
            method="DELETE",
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 200)

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self._url(f"/api/projects/{self.project.id}/documents/{doc_id}/download"))
        self.assertEqual(ctx.exception.code, 404)

    def test_document_from_wrong_project_is_not_found(self):
        other_project = store.create_project("Other Deal", "")
        body = build_upload_body("BOUND8", [("secret.txt", "", b"belongs to falcon")])
        with multipart_request(self._url(f"/api/projects/{self.project.id}/documents"), "BOUND8", body) as res:
            payload = json.loads(res.read())
        doc_id = payload["results"][0]["document"]["id"]

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(
                self._url(f"/api/projects/{other_project.id}/documents/{doc_id}/download")
            )
        self.assertEqual(ctx.exception.code, 404)

    def test_unknown_project_id_upload_is_not_found(self):
        body = build_upload_body("BOUND9", [("x.txt", "", b"x")])
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            multipart_request(self._url("/api/projects/does-not-exist/documents"), "BOUND9", body)
        self.assertEqual(ctx.exception.code, 404)

    def test_path_traversal_in_document_id_is_not_found(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(
                self._url(f"/api/projects/{self.project.id}/documents/..%2F..%2F..%2Fetc%2Fpasswd/download")
            )
        self.assertEqual(ctx.exception.code, 404)

    def test_path_traversal_in_project_id_is_not_found(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self._url("/api/projects/..%2F..%2Fetc/documents"))
        self.assertEqual(ctx.exception.code, 404)

    def test_default_data_dir_is_outside_the_repo_and_home_based(self):
        # Import documents.py in a clean subprocess (no DEAL_LAB_DATA_DIR override)
        # to check the real default, independent of this test class's override.
        import subprocess

        repo_root = Path(__file__).parent.parent.resolve()
        env = {k: v for k, v in __import__("os").environ.items() if k != "DEAL_LAB_DATA_DIR"}
        result = subprocess.run(
            ["python3", "-c", "import documents; print(documents.DATA_DIR)"],
            cwd=str(repo_root),
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        default_data_dir = Path(result.stdout.strip())
        self.assertEqual(default_data_dir, Path.home() / "DealLabData")
        self.assertNotEqual(default_data_dir.resolve(), repo_root)
        self.assertNotIn(repo_root, default_data_dir.resolve().parents)


if __name__ == "__main__":
    unittest.main()
