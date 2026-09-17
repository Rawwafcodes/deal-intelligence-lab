"""Tests for workstreams.py (Task 11.4: Workstream / Assignment)."""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import identity
import store
import workstreams


class WorkstreamTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        identity.init_identity_db()
        workstreams.init_workstreams_db()
        self.project = store.create_project("Acme Merger", "")
        self.other_project = store.create_project("Other Deal", "")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def test_create_and_list_workstream(self):
        created = workstreams.create_workstream(self.project.id, "Financial diligence", "Model and reconciliation")
        listed = workstreams.list_workstreams(self.project.id)
        self.assertEqual([w.id for w in listed], [created.id])
        self.assertEqual(created.description, "Model and reconciliation")

    def test_workstreams_are_isolated_per_project(self):
        workstreams.create_workstream(self.project.id, "Legal", "")
        self.assertEqual(workstreams.list_workstreams(self.other_project.id), [])

    def test_blank_name_is_rejected(self):
        with self.assertRaises(workstreams.WorkstreamValidationError):
            workstreams.create_workstream(self.project.id, "   ", "")

    def test_get_workstream_is_scoped_to_its_own_project(self):
        created = workstreams.create_workstream(self.project.id, "Commercial", "")
        self.assertIsNotNone(workstreams.get_workstream(self.project.id, created.id))
        self.assertIsNone(workstreams.get_workstream(self.other_project.id, created.id))

    def test_assign_and_list_active_assignments(self):
        ws = workstreams.create_workstream(self.project.id, "Legal", "")
        user = identity.create_user("lead@example.com", "Legal Lead")
        workstreams.assign(ws.id, user.id, "Lead")
        active = workstreams.list_active_assignments(ws.id)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].user_id, user.id)
        self.assertEqual(active[0].role_label, "Lead")
        self.assertIsNone(active[0].revoked_at)

    def test_revoke_removes_from_active_but_preserves_history(self):
        ws = workstreams.create_workstream(self.project.id, "Legal", "")
        user = identity.create_user("lead@example.com", "Legal Lead")
        workstreams.assign(ws.id, user.id, "Lead")

        revoked = workstreams.revoke_assignment(ws.id, user.id)
        self.assertTrue(revoked)
        self.assertEqual(workstreams.list_active_assignments(ws.id), [])

        history = workstreams.list_assignments(ws.id)
        self.assertEqual(len(history), 1)
        self.assertIsNotNone(history[0].revoked_at)

    def test_revoking_a_never_assigned_user_is_a_no_op(self):
        ws = workstreams.create_workstream(self.project.id, "Legal", "")
        self.assertFalse(workstreams.revoke_assignment(ws.id, "no-such-user"))

    def test_reassigning_after_revocation_creates_a_new_active_row(self):
        ws = workstreams.create_workstream(self.project.id, "Legal", "")
        user = identity.create_user("lead@example.com", "Legal Lead")
        workstreams.assign(ws.id, user.id, "Lead")
        workstreams.revoke_assignment(ws.id, user.id)
        workstreams.assign(ws.id, user.id, "Contributor")

        active = workstreams.list_active_assignments(ws.id)
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].role_label, "Contributor")
        self.assertEqual(len(workstreams.list_assignments(ws.id)), 2)

    def test_assignment_does_not_grant_or_restrict_document_access(self):
        """docs/03-domain-model.md, verbatim: 'WorkstreamAssignment
        assigns responsibility; it does not silently grant or restrict
        document access.' This module has no access-control concept at
        all - confirmed here by simply asserting assign()/revoke() never
        touch identity.py's deal_memberships."""
        ws = workstreams.create_workstream(self.project.id, "Legal", "")
        user = identity.create_user("lead@example.com", "Legal Lead")
        self.assertFalse(identity.has_deal_access(self.project.id, user.id))
        workstreams.assign(ws.id, user.id, "Lead")
        self.assertFalse(identity.has_deal_access(self.project.id, user.id))

    def test_deleting_a_workstream_removes_its_assignments_too(self):
        ws = workstreams.create_workstream(self.project.id, "Legal", "")
        user = identity.create_user("lead@example.com", "Legal Lead")
        workstreams.assign(ws.id, user.id, "Lead")

        self.assertTrue(workstreams.delete_workstream(self.project.id, ws.id))
        self.assertIsNone(workstreams.get_workstream(self.project.id, ws.id))
        self.assertEqual(workstreams.list_assignments(ws.id), [])

    def test_deleting_unknown_workstream_returns_false(self):
        self.assertFalse(workstreams.delete_workstream(self.project.id, "does-not-exist"))


if __name__ == "__main__":
    unittest.main()
