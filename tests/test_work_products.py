"""Tests for work_products.py (Task 13.1: WorkProduct / SubmissionVersion).
Mirrors tests/test_document_versions.py's own structure closely, since
work_products.py's storage mechanics deliberately mirror documents.py's."""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import documents
import store
import tasks
import work_products


class WorkProductTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(self._tmpdir.name) / "DealLabData"
        work_products.DATA_DIR = documents.DATA_DIR
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        tasks.init_tasks_db()
        work_products.init_work_products_db()
        self.project = store.create_project("Acme Merger", "")
        self.task = tasks.create_task(self.project.id, "Draft the financial model")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    # -- creation -----------------------------------------------------------

    def test_create_work_product_success(self):
        result = work_products.create_work_product(
            self.project.id, self.task.id, "Financial model v1", "model.xlsx", b"fake xlsx bytes",
            created_by="u1",
        )
        self.assertEqual(result.status, "success")
        assert result.work_product is not None
        wp = result.work_product
        self.assertEqual(wp.title, "Financial model v1")
        self.assertEqual(wp.version_number, 1)
        self.assertEqual(wp.current_version_id, wp.id)
        self.assertTrue(work_products.stored_file_path(wp).is_file())
        self.assertEqual(work_products.stored_file_path(wp).read_bytes(), b"fake xlsx bytes")

    def test_unsupported_type_is_rejected(self):
        result = work_products.create_work_product(
            self.project.id, self.task.id, "Bad file", "malware.exe", b"x", created_by="u1"
        )
        self.assertEqual(result.status, "unsupported_type")
        self.assertIsNone(result.work_product)

    def test_title_defaults_to_filename_when_blank(self):
        result = work_products.create_work_product(
            self.project.id, self.task.id, "   ", "notes.txt", b"hello", created_by="u1"
        )
        self.assertEqual(result.status, "success")
        assert result.work_product is not None
        self.assertEqual(result.work_product.title, "notes.txt")

    def test_two_submissions_against_the_same_task_are_independent_work_products(self):
        # documents.save_uploaded_file's own "never infer versioning from a
        # name collision" rule, mirrored here.
        first = work_products.create_work_product(
            self.project.id, self.task.id, "Draft", "model.xlsx", b"version A", created_by="u1"
        )
        second = work_products.create_work_product(
            self.project.id, self.task.id, "Draft", "model.xlsx", b"version B", created_by="u1"
        )
        assert first.work_product is not None and second.work_product is not None
        self.assertNotEqual(first.work_product.id, second.work_product.id)
        self.assertEqual(len(work_products.list_work_products(self.task.id)), 2)

    def test_work_products_are_scoped_to_their_task(self):
        other_task = tasks.create_task(self.project.id, "A different task")
        work_products.create_work_product(
            self.project.id, self.task.id, "Model", "model.xlsx", b"bytes", created_by="u1"
        )
        self.assertEqual(work_products.list_work_products(other_task.id), [])

    # -- versioning -------------------------------------------------------

    def test_add_version_replaces_current_and_keeps_old_downloadable(self):
        result = work_products.create_work_product(
            self.project.id, self.task.id, "Model", "model.xlsx", b"v1 bytes", created_by="u1"
        )
        assert result.work_product is not None
        wp = result.work_product
        v1_path = work_products.stored_file_path(wp)

        add_result = work_products.add_version(self.project.id, wp.id, b"v2 bytes", uploaded_by="u2")
        self.assertEqual(add_result.status, "new_version")
        assert add_result.work_product is not None
        updated = add_result.work_product
        self.assertEqual(updated.version_number, 2)
        self.assertNotEqual(updated.current_version_id, wp.id)

        # The old version's own file is untouched and still readable.
        self.assertTrue(v1_path.is_file())
        self.assertEqual(v1_path.read_bytes(), b"v1 bytes")
        self.assertEqual(work_products.stored_file_path(updated).read_bytes(), b"v2 bytes")

        versions = work_products.list_versions(wp.id)
        self.assertEqual([v.version_number for v in versions], [1, 2])
        self.assertEqual(versions[1].uploaded_by, "u2")

    def test_add_version_identical_content_is_a_duplicate(self):
        result = work_products.create_work_product(
            self.project.id, self.task.id, "Model", "model.xlsx", b"same bytes", created_by="u1"
        )
        assert result.work_product is not None
        add_result = work_products.add_version(self.project.id, result.work_product.id, b"same bytes", uploaded_by="u1")
        self.assertEqual(add_result.status, "duplicate")

    def test_add_version_unknown_work_product(self):
        result = work_products.add_version(self.project.id, "not-a-real-work-product", b"x", uploaded_by="u1")
        self.assertEqual(result.status, "failed")

    def test_get_version_is_scoped_to_its_work_product(self):
        a = work_products.create_work_product(
            self.project.id, self.task.id, "A", "a.txt", b"a", created_by="u1"
        ).work_product
        b = work_products.create_work_product(
            self.project.id, self.task.id, "B", "b.txt", b"b", created_by="u1"
        ).work_product
        assert a is not None and b is not None
        # a's own version id must not resolve when looked up under b's id.
        self.assertIsNone(work_products.get_version(b.id, a.current_version_id))


if __name__ == "__main__":
    unittest.main()
