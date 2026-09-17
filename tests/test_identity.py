"""Tests for identity.py (Task 11.3b: Organization, User, DealMembership).

Runs entirely against an isolated, disposable Postgres schema per test -
never the real `public` schema (see docs/workspace-shift/tasks/
11.3b-organization-auth.md's "Data migration and recovery" section: real
data, Universal Logic included, stays untouched by this task's own tests).
"""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import identity
import store


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        identity.init_identity_db()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    # -- seeding ------------------------------------------------------

    def test_seeding_creates_one_org_and_four_users(self):
        # Task 13.4 added a 4th seeded identity for the external_executive
        # deal role, alongside the original analyst/reviewer/deal_lead.
        orgs = identity.list_organizations()
        users = identity.list_users()
        self.assertEqual(len(orgs), 1)
        self.assertEqual(len(users), 4)

    def test_external_executive_is_seeded_with_org_membership_but_no_deal_role(self):
        external = next(u for u in identity.list_users() if u.email == "external@local.dev")
        memberships = identity.list_organization_memberships_for_user(external.id)
        self.assertEqual(len(memberships), 1)
        project = store.create_project("Acme Merger", "")
        self.assertIsNone(identity.get_deal_role(project.id, external.id))

    def test_default_user_is_stable_across_calls(self):
        self.assertEqual(identity.get_default_user_id(), identity.get_default_user_id())

    def test_reinitializing_is_idempotent(self):
        before_orgs = {o.id for o in identity.list_organizations()}
        before_users = {u.id for u in identity.list_users()}
        identity.init_identity_db()
        identity.init_identity_db()
        after_orgs = {o.id for o in identity.list_organizations()}
        after_users = {u.id for u in identity.list_users()}
        self.assertEqual(before_orgs, after_orgs)
        self.assertEqual(before_users, after_users)

    # -- deal memberships -----------------------------------------------

    def test_membership_grants_access(self):
        project = store.create_project("Acme Merger", "")
        user = identity.create_user("a@example.com", "Analyst A")
        self.assertFalse(identity.has_deal_access(project.id, user.id))
        identity.add_deal_membership(project.id, user.id, "analyst")
        self.assertTrue(identity.has_deal_access(project.id, user.id))

    def test_revocation_removes_access_but_preserves_history(self):
        project = store.create_project("Acme Merger", "")
        user = identity.create_user("a@example.com", "Analyst A")
        identity.add_deal_membership(project.id, user.id, "analyst")
        self.assertTrue(identity.has_deal_access(project.id, user.id))

        revoked = identity.revoke_deal_membership(project.id, user.id)
        self.assertTrue(revoked)
        self.assertFalse(identity.has_deal_access(project.id, user.id))

        history = identity.list_deal_memberships_for_project(project.id)
        self.assertEqual(len(history), 1)
        self.assertIsNotNone(history[0].revoked_at)

    def test_revoking_nonexistent_membership_is_a_no_op(self):
        project = store.create_project("Acme Merger", "")
        user = identity.create_user("a@example.com", "Analyst A")
        self.assertFalse(identity.revoke_deal_membership(project.id, user.id))

    def test_regranting_after_revocation_creates_new_active_row_not_edits_old(self):
        project = store.create_project("Acme Merger", "")
        user = identity.create_user("a@example.com", "Analyst A")
        identity.add_deal_membership(project.id, user.id, "analyst")
        identity.revoke_deal_membership(project.id, user.id)
        identity.add_deal_membership(project.id, user.id, "reviewer")

        self.assertTrue(identity.has_deal_access(project.id, user.id))
        history = identity.list_deal_memberships_for_project(project.id)
        self.assertEqual(len(history), 2)
        active = [m for m in history if m.revoked_at is None]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].role, "reviewer")

    def test_get_deal_role_reflects_active_membership(self):
        project = store.create_project("Acme Merger", "")
        user = identity.create_user("a@example.com", "Analyst A")
        self.assertIsNone(identity.get_deal_role(project.id, user.id))
        identity.add_deal_membership(project.id, user.id, "analyst")
        self.assertEqual(identity.get_deal_role(project.id, user.id), "analyst")

    def test_get_deal_role_is_none_after_revocation(self):
        project = store.create_project("Acme Merger", "")
        user = identity.create_user("a@example.com", "Analyst A")
        identity.add_deal_membership(project.id, user.id, "reviewer")
        identity.revoke_deal_membership(project.id, user.id)
        self.assertIsNone(identity.get_deal_role(project.id, user.id))

    def test_org_admin_without_deal_membership_has_no_deal_access(self):
        """docs/06-security-and-collaboration.md: 'Organization admins do
        not automatically gain client-deal content rights merely by
        administering accounts.'"""
        org = identity.create_organization("Acme Advisory")
        admin = identity.create_user("admin@example.com", "Org Admin")
        identity.add_organization_membership(org.id, admin.id, "admin")
        project = store.create_project("Acme Merger", "")
        identity.assign_project_organization(project.id, org.id)

        self.assertFalse(identity.has_deal_access(project.id, admin.id))

    def test_cross_organization_project_is_not_accessible(self):
        org_a = identity.create_organization("Org A")
        org_b = identity.create_organization("Org B")
        user_b = identity.create_user("b@example.com", "User B")
        identity.add_organization_membership(org_b.id, user_b.id, "member")

        project = store.create_project("Org A's Deal", "")
        identity.assign_project_organization(project.id, org_a.id)

        self.assertFalse(identity.has_deal_access(project.id, user_b.id))

    def test_list_accessible_project_ids_is_scoped_per_user(self):
        analyst = identity.create_user("a@example.com", "Analyst A")
        reviewer = identity.create_user("r@example.com", "Reviewer R")
        shared = store.create_project("Shared Deal", "")
        only_analyst = store.create_project("Analyst-only Deal", "")
        identity.add_deal_membership(shared.id, analyst.id, "analyst")
        identity.add_deal_membership(shared.id, reviewer.id, "reviewer")
        identity.add_deal_membership(only_analyst.id, analyst.id, "analyst")

        self.assertEqual(
            identity.list_accessible_project_ids(analyst.id), {shared.id, only_analyst.id}
        )
        self.assertEqual(identity.list_accessible_project_ids(reviewer.id), {shared.id})

    # -- orphan / legacy projects ----------------------------------------

    def test_orphan_project_is_lazily_adopted_by_default_identity_only(self):
        """A project created directly via store.create_project(), bypassing
        POST /api/projects (this codebase's own test fixtures do this
        throughout), has no organization assignment yet. The default
        identity should still reach it (preserving pre-11.3b behavior);
        a different, unrelated seeded user should not."""
        project = store.create_project("Direct-created Deal", "")
        other_user = identity.create_user("other@example.com", "Someone Else")

        self.assertFalse(identity.has_deal_access(project.id, other_user.id))
        self.assertTrue(identity.has_deal_access(project.id, identity.get_default_user_id()))
        # Adoption is real, not a special-cased read: a second, unrelated
        # user still has no access after the project has been adopted.
        self.assertFalse(identity.has_deal_access(project.id, other_user.id))

    def test_orphan_project_appears_in_default_identity_list_without_prior_touch(self):
        project = store.create_project("Direct-created Deal", "")
        self.assertIn(project.id, identity.list_accessible_project_ids(identity.get_default_user_id()))

    # -- sessions ---------------------------------------------------------

    def test_session_round_trip(self):
        user = identity.create_user("a@example.com", "Analyst A")
        session = identity.create_session(user.id)
        fetched = identity.get_session(session.token)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.user_id, user.id)

    def test_unknown_session_token_returns_none(self):
        self.assertIsNone(identity.get_session("not-a-real-token"))

    def test_deleted_session_is_gone(self):
        user = identity.create_user("a@example.com", "Analyst A")
        session = identity.create_session(user.id)
        identity.delete_session(session.token)
        self.assertIsNone(identity.get_session(session.token))


if __name__ == "__main__":
    unittest.main()
