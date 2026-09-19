"""Tests for assertion_ledger.py (Task 16.2): promoting an already-accepted
M14.2 Integrity Review candidate into a versioned ledger entry.
"""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import assertion_ledger
import integrity_reviews
import store
import version_dependencies
from assertion_ledger import (
    AlreadyPromotedError,
    CandidateNotPromotableError,
    LedgerEntryNotFoundError,
)


class AssertionLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        integrity_reviews.init_integrity_reviews_db()
        assertion_ledger.init_assertion_ledger_db()
        version_dependencies.init_version_dependencies_db()
        cls.project = store.create_project("Project Falcon", "assertion ledger tests")

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def _make_review_and_candidate(
        self, *, decision="accepted", assertion_text="The purchase price is $50M.",
        source_document_ids=None, source_version_ids=None,
    ):
        source_document_ids = source_document_ids if source_document_ids is not None else ["doc-1", "doc-2"]
        source_version_ids = source_version_ids if source_version_ids is not None else ["docv-1", "docv-2"]
        review = integrity_reviews.create_integrity_review(
            project_id=self.project.id,
            target_work_product_id="wp-1",
            target_version_id="wpv-1",
            source_document_ids=source_document_ids,
            source_version_ids=source_version_ids,
            peer_work_product_ids=[],
            peer_version_ids=[],
            brief_version_id=None,
            workstream_id=None,
            review_scope="full",
            status="success",
            transmitted=True,
            analysis_seconds=1.5,
            model="claude-test-model",
            review_template_version="v1",
            stop_reason="end_turn",
            input_tokens=100,
            output_tokens=50,
            code_execution_requests=0,
            error_type=None,
            error_message=None,
            materials_reviewed_text="doc-1, doc-2",
            tool_trace=None,
            excel_cleanup=None,
            excel_verification=None,
        )
        [candidate] = integrity_reviews.create_candidates(
            review.id,
            [
                {
                    "index": 0,
                    "title": "Purchase price mismatch",
                    "classification": "numerical_conflict",
                    "severity": "high",
                    "assertion": assertion_text,
                    "conflicting_or_missing_evidence": "Term sheet says $50M, workbook says $52M.",
                    "why_it_matters": "Materially affects valuation.",
                    "uncertainty": "",
                    "recommended_resolution": "Confirm with deal team.",
                    "deterministic_or_judgment": "deterministic",
                    "raw_text": "raw model output",
                    "pdf_citations": [{"document_id": "doc-1", "page": 3}],
                    "excel_citations": [{"document_id": "doc-2", "cell": "B12"}],
                }
            ],
        )
        if decision != "pending":
            candidate = integrity_reviews.record_candidate_decision(
                review.id, candidate.id, decision, decided_by="reviewer@local.dev",
                published_finding_id="finding-1" if decision == "accepted" else None,
            )
        return review, candidate

    def test_promote_accepted_candidate(self):
        review, candidate = self._make_review_and_candidate()
        entry = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)

        self.assertEqual(entry.version_number, 1)
        self.assertEqual(entry.status, "active")
        self.assertEqual(entry.verification_status, "confirmed")
        self.assertEqual(entry.confirmed_by, "reviewer@local.dev")
        self.assertEqual(entry.assertion_text, "The purchase price is $50M.")
        self.assertEqual(entry.extraction_model, "claude-test-model")
        self.assertEqual(entry.extraction_prompt_version, "v1")
        self.assertEqual(entry.source_document_ids, ["doc-1", "doc-2"])
        self.assertEqual(entry.pdf_citations, [{"document_id": "doc-1", "page": 3}])
        self.assertEqual(entry.published_finding_id, "finding-1")
        self.assertEqual(entry.modality, "firm")
        self.assertIsNone(entry.normalized_fields)

    def test_promote_rejects_pending_candidate(self):
        review, candidate = self._make_review_and_candidate(decision="pending")
        with self.assertRaises(CandidateNotPromotableError):
            assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)

    def test_promote_rejects_rejected_candidate(self):
        review, candidate = self._make_review_and_candidate(decision="rejected")
        with self.assertRaises(CandidateNotPromotableError):
            assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)

    def test_promote_rejects_invalid_modality(self):
        review, candidate = self._make_review_and_candidate()
        with self.assertRaises(ValueError):
            assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id, modality="maybe")

    def test_promote_twice_raises_already_promoted(self):
        review, candidate = self._make_review_and_candidate()
        assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)
        with self.assertRaises(AlreadyPromotedError):
            assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)

    def test_get_entry_by_candidate(self):
        review, candidate = self._make_review_and_candidate()
        entry = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)
        fetched = assertion_ledger.get_entry_by_candidate(candidate.id)
        self.assertEqual(fetched.id, entry.id)

    def test_normalized_fields_and_language_are_optional_and_passthrough(self):
        review, candidate = self._make_review_and_candidate()
        entry = assertion_ledger.promote_candidate(
            self.project.id, review.id, candidate.id,
            modality="conditional", normalized_fields={"amount": 50_000_000, "currency": "USD"},
            language="fr",
        )
        self.assertEqual(entry.modality, "conditional")
        self.assertEqual(entry.normalized_fields, {"amount": 50_000_000, "currency": "USD"})
        self.assertEqual(entry.language, "fr")

    def test_dispute_creates_new_version_and_retires_old(self):
        review, candidate = self._make_review_and_candidate()
        original = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)

        disputed = assertion_ledger.dispute_entry(
            original.entry_key, disputed_by="lead@local.dev", reason="Superseded by term sheet v2."
        )

        self.assertEqual(disputed.version_number, 2)
        self.assertEqual(disputed.status, "active")
        self.assertEqual(disputed.verification_status, "disputed")
        self.assertEqual(disputed.disputed_by, "lead@local.dev")
        self.assertEqual(disputed.dispute_reason, "Superseded by term sheet v2.")
        # Content carried forward unchanged.
        self.assertEqual(disputed.assertion_text, original.assertion_text)

        current = assertion_ledger.get_entry(original.entry_key)
        self.assertEqual(current.id, disputed.id)

        history = assertion_ledger.get_entry_history(original.entry_key)
        self.assertEqual([e.version_number for e in history], [1, 2])
        self.assertEqual(history[0].status, "superseded")
        self.assertEqual(history[0].verification_status, "confirmed")  # untouched history
        self.assertEqual(history[1].status, "active")

    def test_dispute_requires_a_reason(self):
        review, candidate = self._make_review_and_candidate()
        entry = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)
        with self.assertRaises(assertion_ledger.AssertionLedgerError):
            assertion_ledger.dispute_entry(entry.entry_key, disputed_by="lead@local.dev", reason="   ")

    def test_dispute_unknown_entry_raises(self):
        with self.assertRaises(LedgerEntryNotFoundError):
            assertion_ledger.dispute_entry(uuid.uuid4().hex, disputed_by="x", reason="doesn't exist")

    def test_confirm_after_dispute_clears_dispute_fields_on_new_version(self):
        review, candidate = self._make_review_and_candidate()
        original = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)
        assertion_ledger.dispute_entry(original.entry_key, disputed_by="lead@local.dev", reason="Looked wrong.")

        reconfirmed = assertion_ledger.confirm_entry(original.entry_key, confirmed_by="lead@local.dev")

        self.assertEqual(reconfirmed.version_number, 3)
        self.assertEqual(reconfirmed.verification_status, "confirmed")
        self.assertIsNone(reconfirmed.disputed_by)
        self.assertIsNone(reconfirmed.disputed_at)
        self.assertEqual(reconfirmed.dispute_reason, "")

        history = assertion_ledger.get_entry_history(original.entry_key)
        self.assertEqual(len(history), 3)
        self.assertEqual(history[1].verification_status, "disputed")  # the disputed version stays on the record
        self.assertEqual(history[1].dispute_reason, "Looked wrong.")

    def test_list_entries_scoped_to_project_and_filters(self):
        review, candidate = self._make_review_and_candidate()
        entry = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)

        other_project = store.create_project("Project Osprey", "a different project")
        entries_for_other = assertion_ledger.list_entries(other_project.id)
        self.assertEqual(entries_for_other, [])

        entries = assertion_ledger.list_entries(self.project.id)
        self.assertIn(entry.id, [e.id for e in entries])

        by_work_product = assertion_ledger.list_entries(self.project.id, target_work_product_id="wp-1")
        self.assertIn(entry.id, [e.id for e in by_work_product])

        by_confirmed = assertion_ledger.list_entries(self.project.id, verification_status="confirmed")
        self.assertIn(entry.id, [e.id for e in by_confirmed])
        by_disputed = assertion_ledger.list_entries(self.project.id, verification_status="disputed")
        self.assertNotIn(entry.id, [e.id for e in by_disputed])

    def test_list_entries_excludes_superseded_by_default(self):
        review, candidate = self._make_review_and_candidate()
        original = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)
        assertion_ledger.dispute_entry(original.entry_key, disputed_by="lead@local.dev", reason="x")

        active_ids = {e.id for e in assertion_ledger.list_entries(self.project.id)}
        self.assertNotIn(original.id, active_ids)

        all_ids = {e.id for e in assertion_ledger.list_entries(self.project.id, include_superseded=True)}
        self.assertIn(original.id, all_ids)

    def test_promoted_entry_is_not_stale_until_a_source_version_changes(self):
        doc_id = f"doc-{uuid.uuid4().hex}"
        review, candidate = self._make_review_and_candidate(
            source_document_ids=[doc_id, "doc-peer"], source_version_ids=["v1", "v1"],
        )
        entry = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)

        self.assertFalse(assertion_ledger.is_stale(entry.entry_key))
        self.assertIsNone(assertion_ledger.get_staleness(entry.entry_key))

        # Simulate the source document getting a real new version - the
        # same real event documents.add_version fires in production.
        version_dependencies.mark_superseded("document", doc_id, "v2")

        self.assertTrue(assertion_ledger.is_stale(entry.entry_key))
        flag = assertion_ledger.get_staleness(entry.entry_key)
        self.assertIsNotNone(flag)
        self.assertEqual(flag.superseded_source_id, doc_id)
        self.assertEqual(flag.superseded_version_id, "v2")

    def test_staleness_persists_across_a_dispute_confirm_version_bump(self):
        doc_id = f"doc-{uuid.uuid4().hex}"
        review, candidate = self._make_review_and_candidate(
            source_document_ids=[doc_id], source_version_ids=["v1"],
        )
        entry = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)
        version_dependencies.mark_superseded("document", doc_id, "v2")
        self.assertTrue(assertion_ledger.is_stale(entry.entry_key))

        disputed = assertion_ledger.dispute_entry(entry.entry_key, disputed_by="lead@local.dev", reason="x")
        # A new version (new row id) of the SAME entry_key - staleness is
        # tracked by entry_key, so it must still show as stale.
        self.assertNotEqual(disputed.id, entry.id)
        self.assertTrue(assertion_ledger.is_stale(disputed.entry_key))

    def test_is_extraction_current_and_is_reusable(self):
        doc_id = f"doc-{uuid.uuid4().hex}"
        review, candidate = self._make_review_and_candidate(
            source_document_ids=[doc_id], source_version_ids=["v1"],
        )
        entry = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)
        # fixture's own review.model="claude-test-model", review_template_version="v1"

        self.assertTrue(
            assertion_ledger.is_extraction_current(
                entry, current_model="claude-test-model", current_prompt_version="v1"
            )
        )
        self.assertFalse(
            assertion_ledger.is_extraction_current(
                entry, current_model="claude-newer-model", current_prompt_version="v1"
            )
        )

        self.assertTrue(
            assertion_ledger.is_reusable(entry, current_model="claude-test-model", current_prompt_version="v1")
        )

        # A stale source makes it non-reusable even with a matching model/prompt.
        version_dependencies.mark_superseded("document", doc_id, "v2")
        self.assertFalse(
            assertion_ledger.is_reusable(entry, current_model="claude-test-model", current_prompt_version="v1")
        )

        # A second entry, on an entirely different (unaffected) source, is
        # still non-reusable when its own prompt/model is out of date -
        # independent of staleness.
        other_doc_id = f"doc-{uuid.uuid4().hex}"
        review2, candidate2 = self._make_review_and_candidate(
            assertion_text="A second, unrelated assertion.",
            source_document_ids=[other_doc_id], source_version_ids=["v1"],
        )
        entry2 = assertion_ledger.promote_candidate(self.project.id, review2.id, candidate2.id)
        self.assertFalse(assertion_ledger.is_stale(entry2.entry_key))
        self.assertFalse(
            assertion_ledger.is_reusable(entry2, current_model="claude-newer-model", current_prompt_version="v2")
        )

    def test_list_stale_entries_scoped_to_project(self):
        doc_id = f"doc-{uuid.uuid4().hex}"
        review, candidate = self._make_review_and_candidate(
            source_document_ids=[doc_id], source_version_ids=["v1"],
        )
        entry = assertion_ledger.promote_candidate(self.project.id, review.id, candidate.id)
        version_dependencies.mark_superseded("document", doc_id, "v2")

        stale = assertion_ledger.list_stale_entries(self.project.id)
        self.assertIn(entry.id, [e.id for e in stale])

        other_project = store.create_project("Project Osprey", "a different project")
        self.assertEqual(assertion_ledger.list_stale_entries(other_project.id), [])


if __name__ == "__main__":
    unittest.main()
