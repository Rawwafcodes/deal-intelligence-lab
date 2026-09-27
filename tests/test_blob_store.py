"""Task 19.3 (M19): document storage behind blob_store - local disk
(unchanged) and private object storage (S3-compatible, e.g. Cloudflare R2),
exercised end to end through documents.py with an in-memory fake bucket."""

import io
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import blob_store
import documents
import store
import version_dependencies

PDF = b"%PDF-1.4\n%blob-store-test\n%%EOF"


class NoSuchKey(Exception):
    response = {"Error": {"Code": "NoSuchKey"}}


class FakeBucket:
    """Minimal stand-in for a boto3 S3 client."""

    def __init__(self, fail_puts: bool = False):
        self.objects: dict[str, bytes] = {}
        self.fail_puts = fail_puts

    def put_object(self, Bucket, Key, Body):
        if self.fail_puts:
            raise RuntimeError("bucket unavailable")
        self.objects[Key] = bytes(Body)

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise NoSuchKey()
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)


class ObjectStorageDocumentTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        version_dependencies.init_version_dependencies_db()
        documents.init_documents_db()
        self._tmp = tempfile.TemporaryDirectory()
        self._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(self._tmp.name) / "local-data-must-stay-empty"
        self.bucket = FakeBucket()
        self.cache = Path(self._tmp.name) / "cache"
        blob_store.set_store(blob_store.ObjectBlobStore(self.bucket, "deal-lab", self.cache, prefix="staging"))
        self.project = store.create_project("Blob Store Tests", "")

    def tearDown(self):
        blob_store.set_store(None)
        documents.DATA_DIR = self._original_data_dir
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        self._tmp.cleanup()

    def _fresh_process_view(self):
        # A second process (e.g. the worker service) has its own empty cache.
        blob_store.set_store(blob_store.ObjectBlobStore(self.bucket, "deal-lab", Path(self._tmp.name) / "cache-2", prefix="staging"))

    def test_upload_lands_in_the_bucket_not_on_local_disk(self):
        doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF).document
        key = f"staging/projects/{self.project.id}/originals/{doc.current_version_id}.pdf"
        self.assertEqual(self.bucket.objects[key], PDF)
        self.assertFalse(documents.DATA_DIR.exists())

    def test_another_process_reads_the_same_bytes(self):
        doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF).document
        self._fresh_process_view()
        path = documents.stored_file_path(doc)
        self.assertTrue(path.is_file())
        self.assertEqual(path.read_bytes(), PDF)

    def test_new_version_and_delete_reach_the_bucket(self):
        doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF).document
        documents.add_version(self.project.id, doc.id, PDF + b"v2")
        self.assertEqual(len(self.bucket.objects), 2)
        self.assertTrue(documents.delete_document(self.project.id, doc.id))
        self.assertEqual(self.bucket.objects, {})

    def test_missing_object_behaves_like_a_missing_file(self):
        doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF).document
        self.bucket.objects.clear()
        self._fresh_process_view()
        self.assertFalse(documents.stored_file_path(doc).is_file())

    def test_bucket_failure_is_a_failed_upload_not_a_crash(self):
        self.bucket.fail_puts = True
        result = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF)
        self.assertEqual(result.status, "failed")


class CacheEvictionTests(unittest.TestCase):
    def test_least_recently_used_files_are_evicted_over_the_cap(self):
        with tempfile.TemporaryDirectory() as tmp:
            bucket = FakeBucket()
            store_ = blob_store.ObjectBlobStore(bucket, "b", Path(tmp), cache_max_bytes=25)
            for i in range(3):
                store_.put(f"k{i}", b"x" * 10, Path(tmp))
            cached = sorted(p.name for p in Path(tmp).rglob("*") if p.is_file())
            self.assertEqual(cached, ["k1", "k2"])  # oldest evicted, newest kept
            self.assertEqual(len(bucket.objects), 3)  # the bucket keeps everything
            self.assertEqual(store_.path_for("k0", Path(tmp)).read_bytes(), b"x" * 10)  # re-fetched on demand


class LocalStoreTests(unittest.TestCase):
    def test_default_backend_is_local_disk(self):
        blob_store.set_store(None)
        self.assertIsInstance(blob_store.get_store(), blob_store.LocalBlobStore)
        blob_store.set_store(None)


if __name__ == "__main__":
    unittest.main()
