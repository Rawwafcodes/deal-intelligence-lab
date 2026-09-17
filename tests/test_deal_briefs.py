"""Tests for deal_briefs.py (Task 11.4: the versioned Deal brief)."""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import deal_briefs
import store


class DealBriefTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        deal_briefs.init_deal_briefs_db()
        self.project = store.create_project("Acme Merger", "")
        self.other_project = store.create_project("Other Deal", "")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def test_no_version_yet_returns_none(self):
        self.assertIsNone(deal_briefs.get_current_version("no-brief-project"))
        self.assertEqual(deal_briefs.list_versions("no-brief-project"), [])

    def test_first_version_starts_at_one(self):
        version = deal_briefs.create_version(
            self.project.id, {"objective": "Acquire Acme Corp", "parties": "Buyer and Acme"}, created_by="u1"
        )
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.objective, "Acquire Acme Corp")
        self.assertEqual(version.parties, "Buyer and Acme")
        self.assertEqual(version.scope, "")  # never supplied, blank on the first version

    def test_editing_one_field_carries_the_others_forward_unchanged(self):
        deal_briefs.create_version(
            self.project.id, {"objective": "Acquire Acme", "parties": "Buyer and Acme"}, created_by="u1"
        )
        second = deal_briefs.create_version(self.project.id, {"scope": "Excludes the EU subsidiary"}, created_by="u1")
        self.assertEqual(second.version_number, 2)
        self.assertEqual(second.scope, "Excludes the EU subsidiary")
        # objective/parties carried forward from version 1, not blanked out.
        self.assertEqual(second.objective, "Acquire Acme")
        self.assertEqual(second.parties, "Buyer and Acme")

    def test_get_current_version_is_the_newest(self):
        deal_briefs.create_version(self.project.id, {"objective": "v1"}, created_by="u1")
        deal_briefs.create_version(self.project.id, {"objective": "v2"}, created_by="u1")
        current = deal_briefs.get_current_version(self.project.id)
        self.assertEqual(current.objective, "v2")
        self.assertEqual(current.version_number, 2)

    def test_list_versions_returns_full_immutable_history(self):
        deal_briefs.create_version(self.project.id, {"objective": "v1"}, created_by="u1")
        deal_briefs.create_version(self.project.id, {"objective": "v2"}, created_by="u1")
        deal_briefs.create_version(self.project.id, {"objective": "v3"}, created_by="u1")
        versions = deal_briefs.list_versions(self.project.id)
        self.assertEqual([v.objective for v in versions], ["v1", "v2", "v3"])
        # Editing again never rewrites an earlier version's own content.
        self.assertEqual(versions[0].objective, "v1")

    def test_get_version_is_scoped_to_its_own_project(self):
        version = deal_briefs.create_version(self.project.id, {"objective": "Acme's own brief"}, created_by="u1")
        self.assertIsNotNone(deal_briefs.get_version(self.project.id, version.id))
        self.assertIsNone(deal_briefs.get_version(self.other_project.id, version.id))

    def test_briefs_are_isolated_per_project(self):
        deal_briefs.create_version(self.project.id, {"objective": "Acme's objective"}, created_by="u1")
        self.assertIsNone(deal_briefs.get_current_version(self.other_project.id))


if __name__ == "__main__":
    unittest.main()
