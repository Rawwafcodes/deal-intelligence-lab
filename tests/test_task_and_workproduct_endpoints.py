"""Integration tests for Task 13.1's HTTP surface: tasks, comments, and
work-product submissions/versions. Mirrors tests/test_brief_and_
workstream_endpoints.py's structure and tests/test_document_versions.py's
multipart-upload helper pattern.
"""

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

from tests.test_multipart import build_body

import documents
import identity
import server
import store
import tasks
import work_products
import workstreams


class TaskAndWorkProductEndpointTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread

    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        work_products.DATA_DIR = documents.DATA_DIR
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()
        workstreams.init_workstreams_db()
        tasks.init_tasks_db()
        work_products.init_work_products_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    def setUp(self):
        self.project = store.create_project("Acme Merger", "")
        self.other_project = store.create_project("Other Deal", "")

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _get(self, path: str):
        try:
            res = urllib.request.urlopen(self._url(path))
            return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null")

    def _post(self, path: str, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else b""
        req = urllib.request.Request(
            self._url(path), data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            res = urllib.request.urlopen(req)
            return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null")

    def _upload_work_product(self, task_id: str, title: str, filename: str, data: bytes):
        boundary = "BOUND-WP"
        body = build_body(boundary, [
            {"name": "title", "data": title},
            {"name": "file", "filename": filename, "data": data},
        ])
        req = urllib.request.Request(
            self._url(f"/api/projects/{self.project.id}/tasks/{task_id}/work-products"),
            data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def _add_work_product_version(self, work_product_id: str, filename: str, data: bytes):
        boundary = "BOUND-WPV"
        body = build_body(boundary, [{"name": "file", "filename": filename, "data": data}])
        req = urllib.request.Request(
            self._url(f"/api/projects/{self.project.id}/work-products/{work_product_id}/versions"),
            data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}, method="POST",
        )
        try:
            with urllib.request.urlopen(req) as res:
                return res.status, json.loads(res.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def _tasks_url(self, suffix: str = "") -> str:
        return f"/api/projects/{self.project.id}/tasks{suffix}"

    # -- creation / listing -----------------------------------------------

    def test_create_and_list_task(self):
        status, task = self._post(self._tasks_url(), {"title": "Reconcile the two sources"})
        self.assertEqual(status, 201)
        self.assertEqual(task["status"], "open")
        self.assertEqual(task["comments"], [])
        self.assertEqual(task["work_products"], [])

        status, listed = self._get(self._tasks_url())
        self.assertEqual(status, 200)
        self.assertEqual([t["id"] for t in listed], [task["id"]])

    def test_blank_title_is_rejected(self):
        status, _ = self._post(self._tasks_url(), {"title": "   "})
        self.assertEqual(status, 400)

    def test_task_on_unknown_project_is_not_found(self):
        status, _ = self._get("/api/projects/does-not-exist/tasks")
        self.assertEqual(status, 404)

    def test_task_from_wrong_project_is_not_found(self):
        _, task = self._post(self._tasks_url(), {"title": "Acme only"})
        status, _ = self._get(f"/api/projects/{self.other_project.id}/tasks/{task['id']}")
        self.assertEqual(status, 404)

    def test_create_task_with_workstream_and_assignee(self):
        _, ws = self._post(f"/api/projects/{self.project.id}/workstreams", {"name": "Financial diligence"})
        _, identities = self._get("/api/dev/identities")
        user_id = identities[0]["user"]["id"]
        status, task = self._post(
            self._tasks_url(), {"title": "Reconcile", "workstream_id": ws["id"], "assigned_to": user_id}
        )
        self.assertEqual(status, 201)
        self.assertEqual(task["workstream_id"], ws["id"])
        self.assertEqual(task["workstream"]["id"], ws["id"])
        self.assertEqual(task["assigned_to"], user_id)
        self.assertEqual(task["assigned_user"]["id"], user_id)

    def test_create_task_with_unknown_workstream_is_rejected(self):
        status, _ = self._post(self._tasks_url(), {"title": "x", "workstream_id": "not-real"})
        self.assertEqual(status, 400)

    def test_create_task_with_unknown_assignee_is_rejected(self):
        status, _ = self._post(self._tasks_url(), {"title": "x", "assigned_to": "not-real"})
        self.assertEqual(status, 400)

    # -- status / assignment ------------------------------------------------

    def test_update_status(self):
        _, task = self._post(self._tasks_url(), {"title": "x"})
        status, updated = self._post(self._tasks_url(f"/{task['id']}/status"), {"status": "in_progress"})
        self.assertEqual(status, 200)
        self.assertEqual(updated["status"], "in_progress")

    def test_update_status_to_submitted_directly_is_rejected(self):
        _, task = self._post(self._tasks_url(), {"title": "x"})
        status, _ = self._post(self._tasks_url(f"/{task['id']}/status"), {"status": "submitted"})
        self.assertEqual(status, 400)

    def test_reassign_task(self):
        _, task = self._post(self._tasks_url(), {"title": "x"})
        _, identities = self._get("/api/dev/identities")
        user_id = identities[0]["user"]["id"]
        status, updated = self._post(self._tasks_url(f"/{task['id']}/assign"), {"assigned_to": user_id})
        self.assertEqual(status, 200)
        self.assertEqual(updated["assigned_to"], user_id)
        status, unassigned = self._post(self._tasks_url(f"/{task['id']}/assign"), {"assigned_to": None})
        self.assertEqual(status, 200)
        self.assertIsNone(unassigned["assigned_to"])

    # -- comments -----------------------------------------------------------

    def test_add_comment(self):
        _, task = self._post(self._tasks_url(), {"title": "x"})
        status, comments = self._post(self._tasks_url(f"/{task['id']}/comments"), {"body": "Started this."})
        self.assertEqual(status, 201)
        self.assertEqual(len(comments), 1)
        self.assertEqual(comments[0]["body"], "Started this.")

        status, fetched = self._get(self._tasks_url(f"/{task['id']}"))
        self.assertEqual(len(fetched["comments"]), 1)

    def test_comment_on_unknown_task_is_not_found(self):
        status, _ = self._post(self._tasks_url("/not-a-real-task/comments"), {"body": "x"})
        self.assertEqual(status, 404)

    # -- work-product submissions --------------------------------------------

    def test_submit_work_product_marks_task_submitted(self):
        _, task = self._post(self._tasks_url(), {"title": "Draft the model"})
        status, result = self._upload_work_product(task["id"], "Financial model", "model.xlsx", b"fake xlsx")
        self.assertEqual(status, 201)
        self.assertEqual(result["status"], "success")
        wp = result["work_product"]
        self.assertEqual(wp["title"], "Financial model")
        self.assertEqual(wp["version_number"], 1)

        status, fetched = self._get(self._tasks_url(f"/{task['id']}"))
        self.assertEqual(fetched["status"], "submitted")
        self.assertEqual(len(fetched["work_products"]), 1)
        self.assertEqual(len(fetched["work_products"][0]["versions"]), 1)

    def test_submit_unsupported_file_type_is_rejected(self):
        _, task = self._post(self._tasks_url(), {"title": "x"})
        status, result = self._upload_work_product(task["id"], "Bad", "malware.exe", b"x")
        self.assertEqual(status, 400)
        self.assertEqual(result["status"], "unsupported_type")

    def test_work_product_on_unknown_task_is_not_found(self):
        status, _ = self._upload_work_product("not-a-real-task", "x", "x.txt", b"x")
        self.assertEqual(status, 404)

    def test_add_version_then_download_each(self):
        _, task = self._post(self._tasks_url(), {"title": "Draft the model"})
        _, result = self._upload_work_product(task["id"], "Model", "model.xlsx", b"v1 bytes")
        wp = result["work_product"]

        status, versions = self._get(
            f"/api/projects/{self.project.id}/work-products/{wp['id']}/versions"
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(versions), 1)

        status, add_result = self._add_work_product_version(wp["id"], "model.xlsx", b"v2 bytes")
        self.assertEqual(status, 201)
        self.assertEqual(add_result["status"], "new_version")

        status, versions = self._get(
            f"/api/projects/{self.project.id}/work-products/{wp['id']}/versions"
        )
        self.assertEqual(len(versions), 2)

        v1_id, v2_id = versions[0]["id"], versions[1]["id"]
        res_v1 = urllib.request.urlopen(self._url(
            f"/api/projects/{self.project.id}/work-products/{wp['id']}/versions/{v1_id}/download"
        ))
        self.assertEqual(res_v1.read(), b"v1 bytes")
        res_v2 = urllib.request.urlopen(self._url(
            f"/api/projects/{self.project.id}/work-products/{wp['id']}/versions/{v2_id}/download"
        ))
        self.assertEqual(res_v2.read(), b"v2 bytes")

        # The task stayed "submitted" through the second version too.
        status, fetched = self._get(self._tasks_url(f"/{task['id']}"))
        self.assertEqual(fetched["status"], "submitted")

    def test_add_version_to_unknown_work_product_is_not_found(self):
        status, _ = self._add_work_product_version("not-a-real-wp", "x.txt", b"x")
        self.assertEqual(status, 404)

    def test_download_unknown_version_is_not_found(self):
        _, task = self._post(self._tasks_url(), {"title": "x"})
        _, result = self._upload_work_product(task["id"], "Model", "model.xlsx", b"v1 bytes")
        wp = result["work_product"]
        status, _ = self._get(
            f"/api/projects/{self.project.id}/work-products/{wp['id']}/versions/not-a-real-version/download"
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
