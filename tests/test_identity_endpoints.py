"""Integration tests for Task 11.3b's HTTP surface: /api/session, the
dev-only identity-switch endpoints, and server-side authorization enforced
across the existing /api/projects/... routes.

Runs the real HTTP server against an isolated, disposable Postgres schema
(never `public`/Universal Logic - see this task's own file for why).
"""

import http.cookiejar
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import identity
import server
import store


class _Client:
    """A tiny per-identity HTTP client with its own cookie jar - the
    equivalent of a separate browser profile (docs/06: 'browser profiles
    test distinct sessions'). Two _Client instances against the same
    running server behave like two independent browser sessions."""

    def __init__(self, port: int):
        self._base = f"http://127.0.0.1:{port}"
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))

    def request(self, method: str, path: str, payload=None, origin: str | None = None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        if origin is not None:
            headers["Origin"] = origin
        req = urllib.request.Request(f"{self._base}{path}", data=data, headers=headers, method=method)
        try:
            res = self._opener.open(req)
            return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as exc:
            body = exc.read()
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, body

    def get(self, path: str):
        return self.request("GET", path)

    def post(self, path: str, payload=None, origin: str | None = None):
        return self.request("POST", path, payload, origin=origin)

    def delete(self, path: str, payload=None):
        return self.request("DELETE", path, payload)


class IdentityEndpointTests(unittest.TestCase):
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

    def _client(self) -> _Client:
        return _Client(self.port)

    # -- /api/session -----------------------------------------------------

    def test_session_without_a_cookie_gets_the_default_identity(self):
        status, body = self._client().get("/api/session")
        self.assertEqual(status, 200)
        self.assertEqual(body["user"]["id"], identity.get_default_user_id())
        self.assertEqual(len(body["organizations"]), 1)

    def test_two_clients_get_independent_sessions(self):
        # Neither has switched identity yet, so both resolve to the same
        # default identity - but each holds its OWN session token/cookie,
        # not a shared one (confirmed by clearing one and checking the
        # other is unaffected, below).
        a, b = self._client(), self._client()
        status_a, body_a = a.get("/api/session")
        status_b, body_b = b.get("/api/session")
        self.assertEqual((status_a, status_b), (200, 200))
        self.assertEqual(body_a["user"]["id"], body_b["user"]["id"])

        self.assertEqual(a.post("/api/dev/session/clear")[0], 200)
        # b's own session (and the identity it resolves to) is unaffected.
        status_b2, body_b2 = b.get("/api/session")
        self.assertEqual(status_b2, 200)
        self.assertEqual(body_b2["user"]["id"], body_a["user"]["id"])

    # -- dev identity switching --------------------------------------------

    def test_dev_identities_lists_seeded_users(self):
        status, body = self._client().get("/api/dev/identities")
        self.assertEqual(status, 200)
        emails = {row["user"]["email"] for row in body}
        # Task 13.4 added a 4th seeded identity for the external_executive
        # deal role, alongside the original analyst/reviewer/deal_lead.
        self.assertEqual(
            emails, {"lead@local.dev", "analyst@local.dev", "reviewer@local.dev", "external@local.dev"}
        )

    def test_switching_identity_changes_session(self):
        client = self._client()
        analyst = next(u for u in identity.list_users() if u.email == "analyst@local.dev")

        status, body = client.post("/api/dev/session", {"user_id": analyst.id})
        self.assertEqual(status, 200)
        self.assertEqual(body["user"]["id"], analyst.id)

        status, body = client.get("/api/session")
        self.assertEqual(status, 200)
        self.assertEqual(body["user"]["id"], analyst.id)

    def test_switching_to_unknown_user_id_is_rejected(self):
        status, body = self._client().post("/api/dev/session", {"user_id": "does-not-exist"})
        self.assertEqual(status, 400)

    def test_dev_routes_are_absent_when_dev_auth_is_disabled(self):
        """docs/06: dev identity switching must be 'disabled outside
        development... and absent from production routes' - absent means
        404, not merely unauthorized."""
        client = self._client()
        with patch.dict(os.environ, {"DEAL_LAB_DEV_AUTH": "0"}):
            status_list, _ = client.get("/api/dev/identities")
            status_login, _ = client.post("/api/dev/session", {"user_id": "anything"})
        self.assertEqual(status_list, 404)
        self.assertEqual(status_login, 404)
        # /api/session itself is not dev-only - it keeps working.
        status_session, _ = client.get("/api/session")
        self.assertEqual(status_session, 200)

    # -- server-side authorization on real project routes ------------------

    def test_default_identity_can_reach_its_own_project(self):
        client = self._client()
        status, project = client.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)
        status, _ = client.get(f"/api/projects/{project['id']}")
        self.assertEqual(status, 200)

    def test_unrelated_identity_gets_404_not_403_on_someone_elses_project(self):
        """docs/06: don't leak existence to a caller who isn't a member -
        a denied project looks exactly like a nonexistent one."""
        owner = self._client()
        status, project = owner.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)

        outsider = self._client()
        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        outsider.post("/api/dev/session", {"user_id": reviewer.id})

        status_real, body_real = outsider.get(f"/api/projects/{project['id']}")
        status_fake, body_fake = outsider.get("/api/projects/00000000000000000000000000000000")
        self.assertEqual(status_real, 404)
        self.assertEqual(status_fake, 404)
        self.assertEqual(body_real, body_fake)

    def test_project_list_is_scoped_to_the_caller(self):
        owner = self._client()
        owner.post("/api/projects", {"name": "Owner-only Deal", "description": ""})

        outsider = self._client()
        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        outsider.post("/api/dev/session", {"user_id": reviewer.id})
        status, projects = outsider.get("/api/projects")
        self.assertEqual(status, 200)
        self.assertNotIn("Owner-only Deal", [p["name"] for p in projects])

    def test_granting_membership_gives_real_access(self):
        owner = self._client()
        status, project = owner.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)

        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        reviewer_client = self._client()
        reviewer_client.post("/api/dev/session", {"user_id": reviewer.id})

        status, _ = reviewer_client.get(f"/api/projects/{project['id']}")
        self.assertEqual(status, 404)

        identity.add_deal_membership(project["id"], reviewer.id, "reviewer")
        status, _ = reviewer_client.get(f"/api/projects/{project['id']}")
        self.assertEqual(status, 200)

    def test_revocation_takes_effect_on_the_very_next_request(self):
        owner = self._client()
        status, project = owner.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)

        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        identity.add_deal_membership(project["id"], reviewer.id, "reviewer")
        reviewer_client = self._client()
        reviewer_client.post("/api/dev/session", {"user_id": reviewer.id})

        status, _ = reviewer_client.get(f"/api/projects/{project['id']}")
        self.assertEqual(status, 200)

        identity.revoke_deal_membership(project["id"], reviewer.id)
        status, _ = reviewer_client.get(f"/api/projects/{project['id']}")
        self.assertEqual(status, 404)

    def test_creating_a_project_grants_the_creator_deal_lead(self):
        client = self._client()
        status, project = client.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)
        session = client.get("/api/session")[1]
        memberships = identity.list_deal_memberships_for_project(project["id"])
        self.assertEqual(len(memberships), 1)
        self.assertEqual(memberships[0].user_id, session["user"]["id"])
        self.assertEqual(memberships[0].role, "deal_lead")

    # -- CSRF / origin check ------------------------------------------------

    def test_mutation_with_foreign_origin_is_rejected(self):
        client = self._client()
        status, _ = client.post(
            "/api/projects", {"name": "Acme Merger", "description": ""}, origin="http://evil.example"
        )
        self.assertEqual(status, 403)

    def test_mutation_with_known_dev_origin_is_accepted(self):
        # This test server binds an ephemeral port (unlike the real app's
        # fixed 8765), so the real allowlist can't already contain it -
        # add it for the duration of this one test rather than asserting
        # against a port that was never actually allowed.
        origin = f"http://127.0.0.1:{self.port}"
        server._ALLOWED_ORIGINS.add(origin)
        try:
            client = self._client()
            status, _ = client.post(
                "/api/projects", {"name": "Acme Merger", "description": ""}, origin=origin
            )
        finally:
            server._ALLOWED_ORIGINS.discard(origin)
        self.assertEqual(status, 201)

    def test_mutation_with_no_origin_header_is_accepted(self):
        client = self._client()
        status, _ = client.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)

    # -- deal membership management (Task 13.4) -----------------------------

    def test_deal_lead_can_grant_and_list_membership(self):
        owner = self._client()
        status, project = owner.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)

        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        status, memberships = owner.post(
            f"/api/projects/{project['id']}/memberships", {"user_id": reviewer.id, "role": "reviewer"}
        )
        self.assertEqual(status, 201)
        roles = {m["user_id"]: m["role"] for m in memberships}
        self.assertEqual(roles[reviewer.id], "reviewer")

        status, listed = owner.get(f"/api/projects/{project['id']}/memberships")
        self.assertEqual(status, 200)
        self.assertEqual({m["user_id"]: m["role"] for m in listed}, roles)

    def test_non_deal_lead_cannot_grant_membership(self):
        owner = self._client()
        status, project = owner.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)

        analyst = next(u for u in identity.list_users() if u.email == "analyst@local.dev")
        identity.add_deal_membership(project["id"], analyst.id, "analyst")
        analyst_client = self._client()
        analyst_client.post("/api/dev/session", {"user_id": analyst.id})

        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        status, _ = analyst_client.post(
            f"/api/projects/{project['id']}/memberships", {"user_id": reviewer.id, "role": "reviewer"}
        )
        self.assertEqual(status, 403)

    def test_grant_with_invalid_role_is_rejected(self):
        owner = self._client()
        status, project = owner.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)

        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        status, _ = owner.post(
            f"/api/projects/{project['id']}/memberships", {"user_id": reviewer.id, "role": "not-a-real-role"}
        )
        self.assertEqual(status, 400)

    def test_deal_lead_can_revoke_membership(self):
        owner = self._client()
        status, project = owner.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)

        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        owner.post(f"/api/projects/{project['id']}/memberships", {"user_id": reviewer.id, "role": "reviewer"})

        status, _ = owner.delete(f"/api/projects/{project['id']}/memberships/{reviewer.id}")
        self.assertEqual(status, 200)
        self.assertFalse(identity.has_deal_access(project["id"], reviewer.id))

    def test_non_deal_lead_cannot_revoke_membership(self):
        owner = self._client()
        status, project = owner.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)

        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        owner.post(f"/api/projects/{project['id']}/memberships", {"user_id": reviewer.id, "role": "reviewer"})

        reviewer_client = self._client()
        reviewer_client.post("/api/dev/session", {"user_id": reviewer.id})
        status, _ = reviewer_client.delete(f"/api/projects/{project['id']}/memberships/{reviewer.id}")
        self.assertEqual(status, 403)
        self.assertTrue(identity.has_deal_access(project["id"], reviewer.id))

    def test_revoking_nonexistent_membership_via_api_is_not_found(self):
        owner = self._client()
        status, project = owner.post("/api/projects", {"name": "Acme Merger", "description": ""})
        self.assertEqual(status, 201)
        reviewer = next(u for u in identity.list_users() if u.email == "reviewer@local.dev")
        status, _ = owner.delete(f"/api/projects/{project['id']}/memberships/{reviewer.id}")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
