"""Tests for Task 11.4's document versioning: a stable Document parent
with immutable, individually-addressable DocumentVersion children.
"""

import hashlib
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import documents
import identity
import server
import store
import version_dependencies
from tests.test_multipart import build_body


class DocumentVersionsModuleTests(unittest.TestCase):
    """Exercises documents.py directly - no HTTP server needed."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(self._tmpdir.name) / "DealLabData"
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        documents.init_documents_db()
        version_dependencies.init_version_dependencies_db()
        self.project = store.create_project("Acme Merger", "")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def test_first_upload_creates_one_version(self):
        result = documents.save_uploaded_file(self.project.id, "model.xlsx", "", b"v1 bytes")
        self.assertEqual(result.status, "success")
        doc = result.document
        self.assertEqual(doc.version_number, 1)
        versions = documents.list_versions(doc.id)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].version_number, 1)
        self.assertEqual(versions[0].sha256, hashlib.sha256(b"v1 bytes").hexdigest())

    def test_same_named_different_content_upload_creates_a_second_independent_document(self):
        """docs' own design note: an ordinary upload never infers 'this
        is a new version' from a filename collision - that would have
        silently changed behavior for existing same-named-but-unrelated
        uploads. Only add_version (a caller explicitly targeting one
        known document) creates a new version."""
        first = documents.save_uploaded_file(self.project.id, "model.xlsx", "", b"v1 bytes")
        second = documents.save_uploaded_file(self.project.id, "model.xlsx", "", b"different bytes entirely")
        self.assertEqual(first.status, "success")
        self.assertEqual(second.status, "success")
        self.assertNotEqual(first.document.id, second.document.id)

    def test_add_version_replaces_current_and_preserves_the_old_one(self):
        created = documents.save_uploaded_file(self.project.id, "model.xlsx", "", b"v1 bytes")
        doc_id = created.document.id

        result = documents.add_version(self.project.id, doc_id, b"v2 bytes")
        self.assertEqual(result.status, "new_version")
        updated = result.document
        self.assertEqual(updated.id, doc_id)  # same stable parent
        self.assertEqual(updated.version_number, 2)
        self.assertEqual(updated.sha256, hashlib.sha256(b"v2 bytes").hexdigest())

        versions = documents.list_versions(doc_id)
        self.assertEqual([v.version_number for v in versions], [1, 2])

        # Old version's bytes are still there, untouched, independently.
        v1 = versions[0]
        v1_path = documents.version_file_path(updated, v1)
        self.assertEqual(v1_path.read_bytes(), b"v1 bytes")

        # Current-version convenience fields on the Document track v2.
        current = documents.get_document(self.project.id, doc_id)
        self.assertEqual(current.sha256, hashlib.sha256(b"v2 bytes").hexdigest())
        self.assertEqual(current.size_bytes, len(b"v2 bytes"))

    def test_add_version_does_not_touch_the_documents_identity(self):
        created = documents.save_uploaded_file(self.project.id, "model.xlsx", "Contracts", b"v1 bytes")
        doc_id = created.document.id
        result = documents.add_version(self.project.id, doc_id, b"v2 bytes")
        self.assertEqual(result.document.original_filename, "model.xlsx")
        self.assertEqual(result.document.relative_path, "Contracts")
        self.assertEqual(result.document.id, doc_id)

    def test_add_version_with_identical_content_is_rejected_as_duplicate(self):
        created = documents.save_uploaded_file(self.project.id, "model.xlsx", "", b"v1 bytes")
        result = documents.add_version(self.project.id, created.document.id, b"v1 bytes")
        self.assertEqual(result.status, "duplicate")
        self.assertEqual(len(documents.list_versions(created.document.id)), 1)

    def test_add_version_on_unknown_document_fails(self):
        result = documents.add_version(self.project.id, "does-not-exist", b"data")
        self.assertEqual(result.status, "failed")

    def test_stored_file_path_resolves_to_current_version(self):
        created = documents.save_uploaded_file(self.project.id, "model.xlsx", "", b"v1 bytes")
        doc_id = created.document.id
        documents.add_version(self.project.id, doc_id, b"v2 bytes")
        current = documents.get_document(self.project.id, doc_id)
        self.assertEqual(documents.stored_file_path(current).read_bytes(), b"v2 bytes")

    def test_get_version_is_scoped_to_its_own_document(self):
        doc_a = documents.save_uploaded_file(self.project.id, "a.xlsx", "", b"a bytes").document
        doc_b = documents.save_uploaded_file(self.project.id, "b.xlsx", "", b"b bytes").document
        version_of_a = documents.list_versions(doc_a.id)[0]
        # Asking for A's version id but scoped under B's document id finds nothing.
        self.assertIsNone(documents.get_version(doc_b.id, version_of_a.id))
        self.assertIsNotNone(documents.get_version(doc_a.id, version_of_a.id))

    def test_deleting_a_document_removes_every_version_file(self):
        created = documents.save_uploaded_file(self.project.id, "model.xlsx", "", b"v1 bytes")
        doc_id = created.document.id
        result = documents.add_version(self.project.id, doc_id, b"v2 bytes")
        v1_path = documents.version_file_path(result.document, documents.list_versions(doc_id)[0])
        v2_path = documents.stored_file_path(result.document)
        self.assertTrue(v1_path.is_file())
        self.assertTrue(v2_path.is_file())

        self.assertTrue(documents.delete_document(self.project.id, doc_id))
        self.assertFalse(v1_path.is_file())
        self.assertFalse(v2_path.is_file())
        self.assertEqual(documents.list_versions(doc_id), [])

    def test_legacy_backfill_gives_pre_versioning_rows_a_version_one_without_moving_files(self):
        """Simulates a document created before this task existed: insert
        the row by hand with no current_version_id/version row, matching
        what every real pre-11.4 document looks like, then confirm
        init_documents_db()'s backfill adopts it without moving its file."""
        legacy_id = uuid.uuid4().hex
        conn = store.get_connection()
        try:
            conn.execute(
                """
                INSERT INTO documents (id, project_id, original_filename, relative_path, extension,
                                        size_bytes, sha256, uploaded_at)
                VALUES (%s, %s, 'legacy.txt', '', '.txt', 5, %s, '2020-01-01T00:00:00+00:00')
                """,
                (legacy_id, self.project.id, hashlib.sha256(b"hello").hexdigest()),
            )
            conn.commit()
        finally:
            conn.close()
        documents.originals_dir_for(self.project.id)
        legacy_path = documents.DATA_DIR / "projects" / self.project.id / "originals" / f"{legacy_id}.txt"
        legacy_path.write_bytes(b"hello")

        documents.init_documents_db()  # re-runs the additive backfill

        doc = documents.get_document(self.project.id, legacy_id)
        self.assertEqual(doc.current_version_id, legacy_id)
        self.assertEqual(doc.version_number, 1)
        self.assertEqual(documents.stored_file_path(doc), legacy_path)
        self.assertTrue(legacy_path.is_file())  # never moved
        versions = documents.list_versions(legacy_id)
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].id, legacy_id)


class DocumentVersionsEndpointTests(unittest.TestCase):
    """HTTP-level: the real server, the real routes."""

    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread
    project: store.Project

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()
        documents.init_documents_db()
        version_dependencies.init_version_dependencies_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.project = store.create_project("Acme Merger", "")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _upload(self, filename: str, data: bytes) -> dict:
        boundary = "BOUND-UP"
        body = build_body(boundary, [
            {"name": "files", "filename": filename, "data": data},
            {"name": "relative_paths", "data": ""},
        ])
        req = urllib.request.Request(
            self._url(f"/api/projects/{self.project.id}/documents"),
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read())["results"][0]["document"]

    def _add_version(self, document_id: str, data: bytes):
        boundary = "BOUND-VER"
        body = build_body(boundary, [{"name": "file", "filename": "replacement", "data": data}])
        req = urllib.request.Request(
            self._url(f"/api/projects/{self.project.id}/documents/{document_id}/versions"),
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_add_version_then_list_versions_then_download_each(self):
        doc = self._upload("model.xlsx", b"v1 bytes")

        status, body = self._add_version(doc["id"], b"v2 bytes")
        self.assertEqual(status, 201)
        self.assertEqual(body["document"]["version_number"], 2)

        with urllib.request.urlopen(
            self._url(f"/api/projects/{self.project.id}/documents/{doc['id']}/versions")
        ) as res:
            versions = json.loads(res.read())
        self.assertEqual([v["version_number"] for v in versions], [1, 2])

        with urllib.request.urlopen(
            self._url(
                f"/api/projects/{self.project.id}/documents/{doc['id']}/versions/{versions[0]['id']}/download"
            )
        ) as res:
            self.assertEqual(res.read(), b"v1 bytes")

        with urllib.request.urlopen(
            self._url(
                f"/api/projects/{self.project.id}/documents/{doc['id']}/versions/{versions[1]['id']}/download"
            )
        ) as res:
            self.assertEqual(res.read(), b"v2 bytes")

        # The document's own /download always returns the CURRENT version.
        with urllib.request.urlopen(
            self._url(f"/api/projects/{self.project.id}/documents/{doc['id']}/download")
        ) as res:
            self.assertEqual(res.read(), b"v2 bytes")

    def test_identical_content_new_version_is_rejected(self):
        doc = self._upload("report.pdf", b"same bytes")
        status, body = self._add_version(doc["id"], b"same bytes")
        self.assertEqual(status, 409)

    def test_version_from_a_different_document_is_not_found(self):
        doc_a = self._upload("a.pdf", b"a bytes")
        doc_b = self._upload("b.pdf", b"b bytes")
        with urllib.request.urlopen(
            self._url(f"/api/projects/{self.project.id}/documents/{doc_a['id']}/versions")
        ) as res:
            version_a_id = json.loads(res.read())[0]["id"]

        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(
                self._url(
                    f"/api/projects/{self.project.id}/documents/{doc_b['id']}/versions/{version_a_id}/download"
                )
            )
        self.assertEqual(ctx.exception.code, 404)

    def test_new_version_on_unknown_document_is_not_found(self):
        status, _ = self._add_version("does-not-exist", b"data")
        self.assertEqual(status, 404)

    def test_project_isolation_on_versions_list(self):
        other_project = store.create_project("Other Deal", "")
        doc = self._upload("shared-name.pdf", b"belongs to acme")
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(
                self._url(f"/api/projects/{other_project.id}/documents/{doc['id']}/versions")
            )
        self.assertEqual(ctx.exception.code, 404)


if __name__ == "__main__":
    unittest.main()
