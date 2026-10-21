"""Task 20.1 (Path B, multi-firm-per-deal): deal_parties widen Task 19.5's
tenant-isolation grant check from "member of the deal's one owning
organization" to "member of the owning organization, or of an organization
explicitly added as a party to this specific deal" - a deliberate,
per-deal, explicit allowlist, not a general cross-org relaxation. See
docs/workspace-shift/tasks/path-b-multi-firm-architecture-decision-report.md.
"""

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


class DealPartiesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        server.init_databases()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

        cls.lead_id = next(u for u in identity.list_users() if u.email == "lead@local.dev").id
        cls.reviewer_id = next(u for u in identity.list_users() if u.email == "reviewer@local.dev").id

        cls.lead = _Client(cls.port)
        cls.lead.post("/api/dev/session", {"user_id": cls.lead_id})
        status, project = cls.lead.post("/api/projects", {"name": "Path B Deal", "description": ""})
        assert status == 201, project
        cls.project_id = project["id"]
        cls.own_org_id = identity.get_project_organization_id(cls.project_id)

        status, _ = cls.lead.post(
            f"/api/projects/{cls.project_id}/memberships", {"user_id": cls.reviewer_id, "role": "reviewer"}
        )
        assert status == 201

        # A second, wholly separate organization and a member of it - not
        # a party to the deal yet.
        cls.other_org = identity.create_organization("Counterparty LLP")
        cls.outsider = identity.create_user(f"outsider-{uuid.uuid4().hex[:6]}@counterparty.example", "Outsider")
        identity.add_organization_membership(cls.other_org.id, cls.outsider.id, "member")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def test_granting_access_to_a_non_party_outside_org_is_still_refused(self):
        """Task 19.5's original behavior must survive unchanged for any
        organization never added as a party - no blanket cross-org
        relaxation."""
        status, body = self.lead.post(
            f"/api/projects/{self.project_id}/memberships", {"user_id": self.outsider.id, "role": "reviewer"}
        )
        self.assertEqual(status, 400)
        self.assertIn("organization", body["error"])

    def test_only_a_deal_lead_may_add_a_party(self):
        reviewer = _Client(self.port)
        reviewer.post("/api/dev/session", {"user_id": self.reviewer_id})
        status, body = reviewer.post(
            f"/api/projects/{self.project_id}/parties",
            {"organization_id": self.other_org.id, "party_role": "counterparty"},
        )
        self.assertEqual(status, 403)

    def test_adding_the_owning_organization_as_its_own_party_is_rejected(self):
        status, body = self.lead.post(
            f"/api/projects/{self.project_id}/parties",
            {"organization_id": self.own_org_id, "party_role": "counterparty"},
        )
        self.assertEqual(status, 400)

    def test_invalid_party_role_is_rejected(self):
        status, body = self.lead.post(
            f"/api/projects/{self.project_id}/parties",
            {"organization_id": self.other_org.id, "party_role": "not_a_real_role"},
        )
        self.assertEqual(status, 400)

    def test_deal_lead_adds_a_party_then_its_members_can_be_granted_access(self):
        status, parties = self.lead.post(
            f"/api/projects/{self.project_id}/parties",
            {"organization_id": self.other_org.id, "party_role": "counterparty"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(len(parties), 1)
        self.assertEqual(parties[0]["organization_id"], self.other_org.id)
        self.assertEqual(parties[0]["party_role"], "counterparty")

        status, listed = self.lead.get(f"/api/projects/{self.project_id}/parties")
        self.assertEqual(status, 200)
        self.assertEqual({p["organization_id"] for p in listed}, {self.other_org.id})

        # A broader role is refused for a party-org grant (Task 20.2,
        # Phase 2's safe default) even though the organization is now a
        # recognized party.
        status, body = self.lead.post(
            f"/api/projects/{self.project_id}/memberships", {"user_id": self.outsider.id, "role": "reviewer"}
        )
        self.assertEqual(status, 400)
        self.assertIn("external_executive", body["error"])

        # Only external_executive succeeds, and the grant records which
        # organization the member was granted access through.
        status, memberships = self.lead.post(
            f"/api/projects/{self.project_id}/memberships",
            {"user_id": self.outsider.id, "role": "external_executive"},
        )
        self.assertEqual(status, 201)
        granted = next(m for m in memberships if m["user_id"] == self.outsider.id)
        self.assertEqual(granted["organization_id"], self.other_org.id)
        self.assertEqual(granted["role"], "external_executive")

        # Removing the party does not retroactively revoke the grant
        # already made through it.
        status, _ = self.lead.delete(f"/api/projects/{self.project_id}/parties/{self.other_org.id}")
        self.assertEqual(status, 200)
        status, listed_after = self.lead.get(f"/api/projects/{self.project_id}/parties")
        self.assertEqual(listed_after, [])
        self.assertIsNotNone(identity.get_deal_role(self.project_id, self.outsider.id))

    def test_removing_a_nonexistent_party_is_404(self):
        status, _ = self.lead.delete(f"/api/projects/{self.project_id}/parties/{uuid.uuid4().hex}")
        self.assertEqual(status, 404)

    def test_a_party_org_member_can_never_be_granted_deal_lead(self):
        status, _ = self.lead.post(
            f"/api/projects/{self.project_id}/parties",
            {"organization_id": self.other_org.id, "party_role": "lender"},
        )
        self.assertEqual(status, 201)
        status, body = self.lead.post(
            f"/api/projects/{self.project_id}/memberships", {"user_id": self.outsider.id, "role": "deal_lead"}
        )
        self.assertEqual(status, 400)
        self.lead.delete(f"/api/projects/{self.project_id}/parties/{self.other_org.id}")


class ResolveGrantableOrganizationTests(unittest.TestCase):
    """Pure identity.py-level coverage, independent of the HTTP layer."""

    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()
        cls.owning_org = identity.create_organization("Owning Org")
        cls.party_org = identity.create_organization("Party Org")
        cls.stranger_org = identity.create_organization("Stranger Org")

        cls.lead = identity.create_user("lead@owning.example", "Lead")
        identity.add_organization_membership(cls.owning_org.id, cls.lead.id, "admin")

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def _make_project(self):
        project = store.create_project(f"Resolve Deal {uuid.uuid4().hex[:6]}", "")
        identity.assign_project_organization(project.id, self.owning_org.id)
        return project.id

    def test_resolves_to_owning_org_for_an_owning_org_member(self):
        project_id = self._make_project()
        self.assertEqual(identity.resolve_grantable_organization_for(project_id, self.lead.id), self.owning_org.id)

    def test_resolves_to_party_org_for_a_party_org_member(self):
        project_id = self._make_project()
        member = identity.create_user(f"party-{uuid.uuid4().hex[:6]}@party.example", "Party Member")
        identity.add_organization_membership(self.party_org.id, member.id, "member")
        self.assertIsNone(identity.resolve_grantable_organization_for(project_id, member.id))
        identity.add_deal_party(project_id, self.party_org.id, "legal_counsel")
        self.assertEqual(identity.resolve_grantable_organization_for(project_id, member.id), self.party_org.id)

    def test_returns_none_for_a_stranger_org_member(self):
        project_id = self._make_project()
        stranger = identity.create_user(f"stranger-{uuid.uuid4().hex[:6]}@stranger.example", "Stranger")
        identity.add_organization_membership(self.stranger_org.id, stranger.id, "member")
        self.assertIsNone(identity.resolve_grantable_organization_for(project_id, stranger.id))

    def test_owning_org_takes_priority_when_member_of_both(self):
        project_id = self._make_project()
        identity.add_deal_party(project_id, self.party_org.id, "lender")
        both = identity.create_user(f"both-{uuid.uuid4().hex[:6]}@both.example", "Both")
        identity.add_organization_membership(self.owning_org.id, both.id, "member")
        identity.add_organization_membership(self.party_org.id, both.id, "member")
        self.assertEqual(identity.resolve_grantable_organization_for(project_id, both.id), self.owning_org.id)


if __name__ == "__main__":
    unittest.main()
