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

from tests.test_identity_endpoints import _Client
from tests.test_multipart import build_body

import documents
import identity
import reviews
import server
import store
import tasks
import version_dependencies
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
        reviews.init_reviews_db()
        version_dependencies.init_version_dependencies_db()

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

    # -- review decisions (Task 13.2) ---------------------------------------

    def _review(self, work_product_id: str, decision: str, rationale: str = "", related_comment_id=None):
        payload = {"decision": decision, "rationale": rationale}
        if related_comment_id is not None:
            payload["related_comment_id"] = related_comment_id
        return self._post(f"/api/projects/{self.project.id}/work-products/{work_product_id}/review", payload)

    def _submitted_task_and_work_product(self):
        _, task = self._post(self._tasks_url(), {"title": "Reconcile the two sources"})
        _, result = self._upload_work_product(task["id"], "Reconciliation memo", "memo.txt", b"v1 content")
        return task, result["work_product"]

    def test_approve_marks_task_approved_and_targets_current_version(self):
        task, wp = self._submitted_task_and_work_product()
        status, updated_task = self._review(wp["id"], "approved", rationale="Looks correct.")
        self.assertEqual(status, 201)
        self.assertEqual(updated_task["status"], "approved")
        reviewed_wp = updated_task["work_products"][0]
        self.assertEqual(len(reviewed_wp["review_decisions"]), 1)
        self.assertEqual(reviewed_wp["review_decisions"][0]["decision"], "approved")
        self.assertEqual(reviewed_wp["review_decisions"][0]["submission_version_id"], wp["current_version_id"])
        self.assertTrue(reviewed_wp["current_version_approved"])

    def test_return_requires_rationale(self):
        task, wp = self._submitted_task_and_work_product()
        status, _ = self._review(wp["id"], "returned", rationale="")
        self.assertEqual(status, 400)

    def test_return_marks_task_returned(self):
        task, wp = self._submitted_task_and_work_product()
        status, updated_task = self._review(wp["id"], "returned", rationale="Numbers don't tie out.")
        self.assertEqual(status, 201)
        self.assertEqual(updated_task["status"], "returned")
        reviewed_wp = updated_task["work_products"][0]
        self.assertFalse(reviewed_wp["current_version_approved"])

    def test_cannot_review_a_task_that_is_not_submitted(self):
        _, task = self._post(self._tasks_url(), {"title": "x"})
        # No work product exists yet, so there is nothing to review -
        # simulate by creating one, approving it, then trying to review
        # again while the task sits "approved" (not "submitted").
        _, result = self._upload_work_product(task["id"], "Model", "model.xlsx", b"v1")
        wp = result["work_product"]
        self._review(wp["id"], "approved")
        status, _ = self._review(wp["id"], "approved")
        self.assertEqual(status, 400)

    def test_resubmission_after_return_re_enters_review(self):
        task, wp = self._submitted_task_and_work_product()
        self._review(wp["id"], "returned", rationale="Please redo the calculation.")
        status, add_result = self._add_work_product_version(wp["id"], "memo.txt", b"v2 content")
        self.assertEqual(status, 201)
        status, fetched = self._get(self._tasks_url(f"/{task['id']}"))
        self.assertEqual(fetched["status"], "submitted")
        # The old return decision is still there - append-only history.
        self.assertEqual(len(fetched["work_products"][0]["review_decisions"]), 1)

    def test_approval_does_not_transfer_to_a_new_version(self):
        task, wp = self._submitted_task_and_work_product()
        self._review(wp["id"], "approved")
        self._add_work_product_version(wp["id"], "memo.txt", b"v2 content")
        status, fetched = self._get(self._tasks_url(f"/{task['id']}"))
        # New content means the task is unreviewed again, and the old
        # approval no longer applies to the new current version.
        self.assertEqual(fetched["status"], "submitted")
        self.assertFalse(fetched["work_products"][0]["current_version_approved"])
        self.assertEqual(len(fetched["work_products"][0]["review_decisions"]), 1)

    def test_related_comment_id_must_belong_to_the_same_task(self):
        task, wp = self._submitted_task_and_work_product()
        _, comments = self._post(self._tasks_url(f"/{task['id']}/comments"), {"body": "Heads up."})
        comment_id = comments[0]["id"]
        status, updated_task = self._review(
            wp["id"], "returned", rationale="See comment.", related_comment_id=comment_id
        )
        self.assertEqual(status, 201)
        self.assertEqual(
            updated_task["work_products"][0]["review_decisions"][0]["related_comment_id"], comment_id
        )

    def test_unknown_related_comment_id_is_rejected(self):
        task, wp = self._submitted_task_and_work_product()
        status, _ = self._review(wp["id"], "returned", rationale="x", related_comment_id="not-a-real-comment")
        self.assertEqual(status, 400)

    def test_review_unknown_work_product_is_not_found(self):
        status, _ = self._review("not-a-real-work-product", "approved")
        self.assertEqual(status, 404)

    def test_invalid_decision_value_is_rejected(self):
        task, wp = self._submitted_task_and_work_product()
        status, _ = self._review(wp["id"], "maybe")
        self.assertEqual(status, 400)

    def test_list_review_decisions_for_a_work_product(self):
        task, wp = self._submitted_task_and_work_product()
        self._review(wp["id"], "returned", rationale="Redo it.")
        status, decisions = self._get(f"/api/projects/{self.project.id}/work-products/{wp['id']}/review")
        self.assertEqual(status, 200)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0]["decision"], "returned")

    # -- review role enforcement (Task 13.4 / docs/09-acceptance.md T04) ---

    def test_analyst_cannot_record_a_review_decision(self):
        task, wp = self._submitted_task_and_work_product()
        analyst = next(u for u in identity.list_users() if u.email == "analyst@local.dev")
        identity.add_deal_membership(self.project.id, analyst.id, "analyst")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": analyst.id})
        status, _ = client.post(
            f"/api/projects/{self.project.id}/work-products/{wp['id']}/review",
            {"decision": "approved", "rationale": "Looks fine."},
        )
        self.assertEqual(status, 403)

    def test_reviewer_can_record_a_review_decision(self):
        task, wp = self._submitted_task_and_work_product()
        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        identity.add_deal_membership(self.project.id, reviewer.id, "reviewer")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": reviewer.id})
        status, updated_task = client.post(
            f"/api/projects/{self.project.id}/work-products/{wp['id']}/review",
            {"decision": "approved", "rationale": "Looks fine."},
        )
        self.assertEqual(status, 201)
        self.assertEqual(updated_task["status"], "approved")

    def test_deal_lead_can_record_a_review_decision(self):
        task, wp = self._submitted_task_and_work_product()
        lead = next(u for u in identity.list_users() if u.email == "lead@local.dev")
        identity.add_deal_membership(self.project.id, lead.id, "deal_lead")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": lead.id})
        status, _ = client.post(
            f"/api/projects/{self.project.id}/work-products/{wp['id']}/review",
            {"decision": "approved", "rationale": "Looks fine."},
        )
        self.assertEqual(status, 201)

    def test_caller_with_no_deal_membership_cannot_record_a_review_decision(self):
        task, wp = self._submitted_task_and_work_product()
        outsider = identity.create_user("outsider@example.com", "Outsider")
        identity.add_deal_membership(self.project.id, outsider.id, "analyst")
        # Even though this grants access to the project at all (analyst),
        # a caller with no reviewer/deal_lead role is still denied - this
        # assertion mirrors test_analyst_cannot_record_a_review_decision
        # but via a freshly created user rather than a seeded dev identity.
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": outsider.id})
        status, _ = client.post(
            f"/api/projects/{self.project.id}/work-products/{wp['id']}/review",
            {"decision": "approved", "rationale": "Looks fine."},
        )
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
