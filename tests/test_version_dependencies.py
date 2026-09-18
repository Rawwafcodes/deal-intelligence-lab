"""Tests for Task 15.1's version dependency tracking and staleness
propagation (version_dependencies.py). No mocking - this module makes no
external call of any kind, deterministic by design.
"""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import store
import version_dependencies as vd


class VersionDependenciesTestBase(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        vd.init_version_dependencies_db()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)


class RecordDependencyTests(VersionDependenciesTestBase):
    def test_no_staleness_recorded_initially(self):
        vd.record_dependency("workspace", "ws-1", "document", "doc-1", "v1")
        self.assertIsNone(vd.get_staleness("workspace", "ws-1"))

    def test_recording_the_same_edge_twice_is_a_no_op(self):
        vd.record_dependency("workspace", "ws-1", "document", "doc-1", "v1")
        vd.record_dependency("workspace", "ws-1", "document", "doc-1", "v1")  # should not raise
        vd.mark_superseded("document", "doc-1", "v2")
        flag = vd.get_staleness("workspace", "ws-1")
        self.assertIsNotNone(flag)


class MarkSupersededTests(VersionDependenciesTestBase):
    def test_leaf_dependent_flagged_on_version_mismatch(self):
        vd.record_dependency("workspace", "ws-1", "document", "doc-1", "v1")
        results = vd.mark_superseded("document", "doc-1", "v2")
        self.assertEqual(len(results), 1)
        flag = vd.get_staleness("workspace", "ws-1")
        self.assertIsNotNone(flag)
        self.assertIn("doc-1", flag.reason)
        self.assertIn("v1", flag.reason)
        self.assertIn("v2", flag.reason)
        self.assertEqual(flag.superseded_version_id, "v2")

    def test_no_flag_if_new_version_matches_pinned(self):
        vd.record_dependency("workspace", "ws-1", "document", "doc-1", "v1")
        vd.mark_superseded("document", "doc-1", "v1")  # same version - no real change
        self.assertIsNone(vd.get_staleness("workspace", "ws-1"))

    def test_unrelated_dependent_is_not_flagged(self):
        vd.record_dependency("workspace", "ws-1", "document", "doc-1", "v1")
        vd.record_dependency("workspace", "ws-2", "document", "doc-2", "v1")
        vd.mark_superseded("document", "doc-1", "v2")
        self.assertIsNotNone(vd.get_staleness("workspace", "ws-1"))
        self.assertIsNone(vd.get_staleness("workspace", "ws-2"))

    def test_cascade_propagates_through_an_intermediate_dependent(self):
        """workspace depends on document; deliverable depends on
        workspace (a cascade edge, no version of its own) - superseding
        the document must flag both, not only the direct dependent."""
        vd.record_dependency("workspace", "ws-1", "document", "doc-1", "v1")
        vd.record_dependency("deliverable_version", "dv-1", "workspace", "ws-1")  # cascade edge
        vd.mark_superseded("document", "doc-1", "v2")

        ws_flag = vd.get_staleness("workspace", "ws-1")
        dv_flag = vd.get_staleness("deliverable_version", "dv-1")
        self.assertIsNotNone(ws_flag)
        self.assertIsNotNone(dv_flag)
        self.assertIn("ws-1", dv_flag.reason)
        self.assertIn("doc-1", dv_flag.reason)  # the root cause is named in the cascade reason too

    def test_cascade_does_not_propagate_through_a_leaf_edge_with_matching_version(self):
        """A second, unrelated leaf edge on the same dependent must not
        be treated as a cascade trigger just because the dependent
        shares a table row with a cascade edge elsewhere."""
        vd.record_dependency("workspace", "ws-1", "document", "doc-1", "v1")
        vd.record_dependency("workspace", "ws-1", "document", "doc-2", "vX")
        vd.mark_superseded("document", "doc-1", "v2")
        flag = vd.get_staleness("workspace", "ws-1")
        self.assertIsNotNone(flag)
        self.assertIn("doc-1", flag.reason)
        self.assertNotIn("doc-2", flag.reason)

    def test_repeated_supersession_updates_reason_without_duplicating(self):
        vd.record_dependency("workspace", "ws-1", "document", "doc-1", "v1")
        vd.mark_superseded("document", "doc-1", "v2")
        first = vd.get_staleness("workspace", "ws-1")
        vd.mark_superseded("document", "doc-1", "v3")
        second = vd.get_staleness("workspace", "ws-1")
        self.assertIn("v3", second.reason)
        self.assertEqual(second.superseded_version_id, "v3")
        self.assertEqual(first.first_marked_at, second.first_marked_at)  # history preserved, not reset

    def test_self_healing_new_edge_onto_an_already_stale_source(self):
        """Recording a brand-new edge onto a source that is already
        stale must immediately flag the new dependent too - the
        invariant holds at every point in time, not only at the instant
        a version first changes."""
        vd.record_dependency("workspace", "ws-1", "document", "doc-1", "v1")
        vd.mark_superseded("document", "doc-1", "v2")
        self.assertIsNone(vd.get_staleness("deliverable_version", "dv-new"))

        vd.record_dependency("deliverable_version", "dv-new", "workspace", "ws-1")  # created after the fact
        flag = vd.get_staleness("deliverable_version", "dv-new")
        self.assertIsNotNone(flag)
        self.assertIn("ws-1", flag.reason)

    def test_marking_never_touches_unrelated_containers(self):
        vd.record_dependency("workspace", "ws-1", "work_product", "wp-1", "sv-1")
        vd.mark_superseded("work_product", "wp-1", "sv-2")
        self.assertIsNotNone(vd.get_staleness("workspace", "ws-1"))
        # A same-named document id is a completely different container -
        # source_type is part of the identity, not just source_id.
        self.assertIsNone(vd.get_staleness("document", "wp-1"))


if __name__ == "__main__":
    unittest.main()
