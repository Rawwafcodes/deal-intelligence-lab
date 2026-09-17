"""Integration tests for Task 11.4's remaining two features exposed over
HTTP: the versioned deal brief and workstreams/assignments.
"""

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import deal_briefs
import identity
import server
import store
import workstreams


class BriefAndWorkstreamEndpointTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread

    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()
        deal_briefs.init_deal_briefs_db()
        workstreams.init_workstreams_db()

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

    def setUp(self):
        # A fresh project per test method - several tests create multiple
        # brief versions/workstreams and assert on absolute counts, which
        # would accumulate incorrectly against a project shared across the
        # whole class.
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

    def _delete(self, path: str, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else b""
        req = urllib.request.Request(
            self._url(path), data=data, headers={"Content-Type": "application/json"}, method="DELETE"
        )
        try:
            res = urllib.request.urlopen(req)
            return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null")

    # -- deal brief -------------------------------------------------------

    def test_brief_is_null_before_any_version_exists(self):
        status, body = self._get(f"/api/projects/{self.project.id}/brief")
        self.assertEqual(status, 200)
        self.assertIsNone(body)

    def test_create_version_then_get_current(self):
        status, body = self._post(
            f"/api/projects/{self.project.id}/brief",
            {"objective": "Acquire Acme Corp", "parties": "Buyer and Acme"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(body["version_number"], 1)

        status, current = self._get(f"/api/projects/{self.project.id}/brief")
        self.assertEqual(status, 200)
        self.assertEqual(current["objective"], "Acquire Acme Corp")

    def test_empty_body_is_rejected(self):
        status, _ = self._post(f"/api/projects/{self.project.id}/brief", {})
        self.assertEqual(status, 400)

    def test_version_history_and_version_item(self):
        self._post(f"/api/projects/{self.project.id}/brief", {"objective": "v1"})
        self._post(f"/api/projects/{self.project.id}/brief", {"objective": "v2"})
        status, versions = self._get(f"/api/projects/{self.project.id}/brief/versions")
        self.assertEqual(status, 200)
        self.assertEqual([v["objective"] for v in versions], ["v1", "v2"])

        status, first = self._get(f"/api/projects/{self.project.id}/brief/versions/{versions[0]['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(first["objective"], "v1")

    def test_brief_is_project_isolated(self):
        self._post(f"/api/projects/{self.project.id}/brief", {"objective": "belongs to Acme"})
        status, other = self._get(f"/api/projects/{self.other_project.id}/brief")
        self.assertEqual(status, 200)
        self.assertIsNone(other)

    def test_cross_project_version_lookup_is_not_found(self):
        status, version = self._post(f"/api/projects/{self.project.id}/brief", {"objective": "Acme only"})
        status, _ = self._get(f"/api/projects/{self.other_project.id}/brief/versions/{version['id']}")
        self.assertEqual(status, 404)

    def test_brief_on_unknown_project_is_not_found(self):
        status, _ = self._get("/api/projects/does-not-exist/brief")
        self.assertEqual(status, 404)

    # -- workstreams --------------------------------------------------------

    def test_create_and_list_workstream(self):
        status, workstream = self._post(
            f"/api/projects/{self.project.id}/workstreams",
            {"name": "Financial diligence", "description": "Model and reconciliation"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(workstream["assignments"], [])

        status, listed = self._get(f"/api/projects/{self.project.id}/workstreams")
        self.assertEqual(status, 200)
        self.assertEqual([w["id"] for w in listed], [workstream["id"]])

    def test_blank_workstream_name_is_rejected(self):
        status, _ = self._post(f"/api/projects/{self.project.id}/workstreams", {"name": "  "})
        self.assertEqual(status, 400)

    def test_assign_and_revoke_roundtrip(self):
        _, workstream = self._post(f"/api/projects/{self.project.id}/workstreams", {"name": "Legal"})
        lead = next(u for u in identity.list_users() if u.email == "lead@local.dev")

        status, assignments = self._post(
            f"/api/projects/{self.project.id}/workstreams/{workstream['id']}/assignments",
            {"user_id": lead.id, "role_label": "Workstream lead"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0]["role_label"], "Workstream lead")
        self.assertEqual(assignments[0]["user"]["email"], "lead@local.dev")

        status, fetched = self._get(f"/api/projects/{self.project.id}/workstreams/{workstream['id']}")
        self.assertEqual(len(fetched["assignments"]), 1)

        status, body = self._delete(
            f"/api/projects/{self.project.id}/workstreams/{workstream['id']}/assignments/{lead.id}"
        )
        self.assertEqual(status, 200)
        status, fetched_after = self._get(f"/api/projects/{self.project.id}/workstreams/{workstream['id']}")
        self.assertEqual(fetched_after["assignments"], [])

    def test_assigning_unknown_user_is_rejected(self):
        _, workstream = self._post(f"/api/projects/{self.project.id}/workstreams", {"name": "Legal"})
        status, _ = self._post(
            f"/api/projects/{self.project.id}/workstreams/{workstream['id']}/assignments",
            {"user_id": "does-not-exist", "role_label": "Lead"},
        )
        self.assertEqual(status, 400)

    def test_assignment_on_unknown_workstream_is_not_found(self):
        lead = next(u for u in identity.list_users() if u.email == "lead@local.dev")
        status, _ = self._post(
            f"/api/projects/{self.project.id}/workstreams/does-not-exist/assignments",
            {"user_id": lead.id, "role_label": "Lead"},
        )
        self.assertEqual(status, 404)

    def test_revoking_a_never_assigned_user_is_not_found(self):
        _, workstream = self._post(f"/api/projects/{self.project.id}/workstreams", {"name": "Legal"})
        lead = next(u for u in identity.list_users() if u.email == "lead@local.dev")
        status, _ = self._delete(
            f"/api/projects/{self.project.id}/workstreams/{workstream['id']}/assignments/{lead.id}"
        )
        self.assertEqual(status, 404)

    def test_delete_workstream_requires_confirmation(self):
        _, workstream = self._post(f"/api/projects/{self.project.id}/workstreams", {"name": "Legal"})
        status, _ = self._delete(f"/api/projects/{self.project.id}/workstreams/{workstream['id']}", {})
        self.assertEqual(status, 400)
        status, _ = self._delete(
            f"/api/projects/{self.project.id}/workstreams/{workstream['id']}", {"confirm": True}
        )
        self.assertEqual(status, 200)
        status, _ = self._get(f"/api/projects/{self.project.id}/workstreams/{workstream['id']}")
        self.assertEqual(status, 404)

    def test_workstream_from_wrong_project_is_not_found(self):
        _, workstream = self._post(f"/api/projects/{self.project.id}/workstreams", {"name": "Legal"})
        status, _ = self._get(f"/api/projects/{self.other_project.id}/workstreams/{workstream['id']}")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
