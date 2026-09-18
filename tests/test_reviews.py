"""Tests for reviews.py (Task 13.2: ReviewDecision)."""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import reviews
import store
import version_dependencies


class ReviewDecisionTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        reviews.init_reviews_db()
        version_dependencies.init_version_dependencies_db()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    # -- recording -----------------------------------------------------

    def test_record_approval(self):
        decision = reviews.record_decision("task-1", "wp-1", "v1", "reviewer-1", "approved")
        self.assertEqual(decision.decision, "approved")
        self.assertEqual(decision.submission_version_id, "v1")
        self.assertEqual(decision.rationale, "")

    def test_record_return_requires_rationale(self):
        with self.assertRaises(reviews.ReviewValidationError):
            reviews.record_decision("task-1", "wp-1", "v1", "reviewer-1", "returned", rationale="   ")

    def test_record_return_with_rationale(self):
        decision = reviews.record_decision(
            "task-1", "wp-1", "v1", "reviewer-1", "returned", rationale="Numbers don't tie out."
        )
        self.assertEqual(decision.decision, "returned")
        self.assertEqual(decision.rationale, "Numbers don't tie out.")

    def test_invalid_decision_value_is_rejected(self):
        with self.assertRaises(reviews.ReviewValidationError):
            reviews.record_decision("task-1", "wp-1", "v1", "reviewer-1", "maybe")

    def test_related_comment_id_is_stored(self):
        decision = reviews.record_decision(
            "task-1", "wp-1", "v1", "reviewer-1", "returned",
            rationale="See my comment.", related_comment_id="comment-1",
        )
        self.assertEqual(decision.related_comment_id, "comment-1")

    # -- listing ---------------------------------------------------------

    def test_decisions_are_ordered_and_scoped_to_their_work_product(self):
        reviews.record_decision("task-1", "wp-1", "v1", "r1", "returned", rationale="First pass issues.")
        reviews.record_decision("task-1", "wp-1", "v2", "r1", "approved")
        reviews.record_decision("task-1", "wp-2", "v1", "r1", "approved")

        wp1_decisions = reviews.list_decisions_for_work_product("wp-1")
        self.assertEqual([d.decision for d in wp1_decisions], ["returned", "approved"])
        wp2_decisions = reviews.list_decisions_for_work_product("wp-2")
        self.assertEqual(len(wp2_decisions), 1)

        task_decisions = reviews.list_decisions_for_task("task-1")
        self.assertEqual(len(task_decisions), 3)

    def test_latest_decision_for_work_product(self):
        self.assertIsNone(reviews.latest_decision_for_work_product("wp-1"))
        reviews.record_decision("task-1", "wp-1", "v1", "r1", "returned", rationale="x")
        reviews.record_decision("task-1", "wp-1", "v2", "r1", "approved")
        latest = reviews.latest_decision_for_work_product("wp-1")
        assert latest is not None
        self.assertEqual(latest.decision, "approved")
        self.assertEqual(latest.submission_version_id, "v2")

    # -- version-specific approval (the literal M13.2 mechanism) --------

    def test_is_current_version_approved_true_when_latest_approval_matches_current(self):
        reviews.record_decision("task-1", "wp-1", "v1", "r1", "approved")
        self.assertTrue(reviews.is_current_version_approved("wp-1", "v1"))

    def test_is_current_version_approved_false_with_no_decisions(self):
        self.assertFalse(reviews.is_current_version_approved("wp-1", "v1"))

    def test_is_current_version_approved_false_after_a_newer_unreviewed_version(self):
        # The literal "approval is version-specific and cannot silently
        # transfer to a new version" requirement: v1 was approved, but the
        # work product has since moved to v2 - that approval does not
        # carry over.
        reviews.record_decision("task-1", "wp-1", "v1", "r1", "approved")
        self.assertFalse(reviews.is_current_version_approved("wp-1", "v2"))

    def test_is_current_version_approved_false_when_latest_decision_is_a_return(self):
        reviews.record_decision("task-1", "wp-1", "v1", "r1", "approved")
        reviews.record_decision("task-1", "wp-1", "v2", "r1", "returned", rationale="Needs more work.")
        self.assertFalse(reviews.is_current_version_approved("wp-1", "v2"))

    def test_approval_history_survives_a_later_return_on_a_new_version(self):
        # Append-only: the old approval decision is never edited or
        # deleted just because a later version was returned.
        reviews.record_decision("task-1", "wp-1", "v1", "r1", "approved")
        reviews.record_decision("task-1", "wp-1", "v2", "r1", "returned", rationale="New issue found.")
        history = reviews.list_decisions_for_work_product("wp-1")
        self.assertEqual([d.decision for d in history], ["approved", "returned"])
        self.assertEqual(history[0].submission_version_id, "v1")


if __name__ == "__main__":
    unittest.main()
