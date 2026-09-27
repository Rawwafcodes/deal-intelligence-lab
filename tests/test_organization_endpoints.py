"""Task 19.5 (M19): minimal organization administration (surfaces #23-24):
view members, invite by email (admin only), rename (admin only)."""

import sys
import threading
import unittest
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.test_identity_endpoints import _Client

import identity
import server
import store


class OrganizationEndpointTests(unittest.TestCase):
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
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.org_id = identity.list_organizations()[0].id
        cls.admin_id = identity.get_default_user_id()  # seeded as org admin
        cls.member = next(u for u in identity.list_users() if u.email == "analyst@local.dev")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def _as(self, user_id):
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": user_id})
        return client

    def test_member_sees_organization_and_members(self):
        status, body = self._as(self.member.id).get("/api/organization")
        self.assertEqual(status, 200)
        self.assertEqual(body["role"], "member")
        self.assertIn(self.member.id, {m["user"]["id"] for m in body["members"]})

    def test_admin_invites_by_email_and_reinvite_reuses_the_user(self):
        email = f"pilot-{uuid.uuid4().hex[:6]}@Client.example"
        admin = self._as(self.admin_id)
        status, body = admin.post("/api/organization/members", {"email": email, "display_name": "Pilot User", "role": "member"})
        self.assertEqual(status, 201)
        invited = [m for m in body["members"] if m["user"]["email"].lower() == email.lower()]
        self.assertEqual(len(invited), 1)
        status, body = admin.post("/api/organization/members", {"email": email.upper(), "role": "admin"})
        self.assertEqual(status, 201)
        again = [m for m in body["members"] if m["user"]["email"].lower() == email.lower()]
        self.assertEqual(len(again), 1)  # same person, not a duplicate
        self.assertEqual(again[0]["role"], "admin")

    def test_non_admin_cannot_invite_or_rename(self):
        member = self._as(self.member.id)
        self.assertEqual(member.post("/api/organization/members", {"email": "x@y.z"})[0], 403)
        self.assertEqual(member.post("/api/organization", {"name": "Hijacked"})[0], 403)

    def test_invalid_invite_is_rejected(self):
        admin = self._as(self.admin_id)
        self.assertEqual(admin.post("/api/organization/members", {"email": "not-an-email"})[0], 400)
        self.assertEqual(admin.post("/api/organization/members", {"email": "a@b.c", "role": "owner"})[0], 400)

    def test_admin_renames_organization(self):
        status, body = self._as(self.admin_id).post("/api/organization", {"name": "Acme Advisory"})
        self.assertEqual(status, 200)
        self.assertEqual(body["organization"]["name"], "Acme Advisory")
        self.assertEqual(self._as(self.admin_id).post("/api/organization", {"name": "  "})[0], 400)


if __name__ == "__main__":
    unittest.main()
