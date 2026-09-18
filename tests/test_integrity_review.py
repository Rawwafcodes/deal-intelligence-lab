"""Tests for Task 14.2's Work-product Integrity Review: the pure adapter
(integrity_review.py), its persistence (integrity_reviews.py), the
`integrity.review_work_product` mandate capability/template
(mandates.py), and the generalized shared-findings-register plumbing in
workspaces.py. No real network call anywhere in this module - every
provider call is mocked, mirroring tests/test_mandates.py's own
ReconciliationCapabilityTests convention exactly.
"""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import deal_briefs
import documents
import integrity_review
import integrity_reviews
import mandates
import store
import tasks
import version_dependencies
import work_products
import workspaces
import workstreams

PDF_BYTES = b"%PDF-1.4\n%Integrity Review test bytes\n%%EOF"
XLSX_BYTES = b"PK\x03\x04fake-xlsx-bytes-for-integrity-review-tests"

CANDIDATES_TEXT = (
    "## Materials Reviewed\n"
    "- **Label:** Submission Under Review\n"
    "**Purpose:** valuation memo\n"
    "**Interpreted:** yes\n"
    "**Limitations:** none\n\n"
    "## Integrity Candidates\n"
    "- **Title:** Working capital double-counted\n"
    "**Classification:** calculation or derivation divergence\n"
    "**Severity:** high\n"
    "**Assertion:** the memo states net investment of $91.75m.\n"
    "**Conflicting or missing evidence:** the source term sheet states $102.358m all-in.\n"
    "**Why it matters:** changes the offer price analysis.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended resolution:** ask the analyst to reconcile the two figures.\n"
    "**Deterministic or judgment:** model_judgment\n\n"
)


def _fake_outcome(success=True, candidates=None, error_message=None):
    return integrity_review.IntegrityReviewOutcome(
        success=success,
        transmitted=True,
        analysis_seconds=3.1,
        model="claude-opus-5",
        stop_reason="end_turn" if success else None,
        usage={"input_tokens": 2000, "output_tokens": 500} if success else None,
        candidates=candidates,
        materials_reviewed_text="Submission Under Review: valuation memo" if success else None,
        error_type=None if success else "provider_error",
        error_message=error_message,
    )


def _one_candidate(**overrides) -> integrity_review.IntegrityCandidateOutcome:
    candidate = integrity_review.IntegrityCandidateOutcome(
        index=0, title="Working capital double-counted", classification="calculation or derivation divergence",
        severity="high", assertion="the memo states net investment of $91.75m.",
        conflicting_or_missing_evidence="the source term sheet states $102.358m all-in.",
        why_it_matters="changes the offer price analysis.", uncertainty="fully supported by citations",
        recommended_resolution="ask the analyst to reconcile the two figures.",
        deterministic_or_judgment="model_judgment",
    )
    for key, value in overrides.items():
        setattr(candidate, key, value)
    return candidate


class IntegrityReviewParsingTests(unittest.TestCase):
    """Module-level, no database: the "## Integrity Candidates" parser."""

    def test_parses_one_candidate_with_every_field(self):
        segments = [
            integrity_review.cross_format_analysis.AnalysisSegment(
                parts=[integrity_review.cross_format_analysis.Part(type="text", text=CANDIDATES_TEXT)]
            )
        ]
        candidates, materials_text = integrity_review._parse_candidates(segments)
        self.assertEqual(len(candidates), 1)
        c = candidates[0]
        self.assertEqual(c.title, "Working capital double-counted")
        self.assertEqual(c.classification, "calculation or derivation divergence")
        self.assertEqual(c.severity, "high")
        self.assertIn("91.75m", c.assertion)
        self.assertIn("102.358m", c.conflicting_or_missing_evidence)
        self.assertEqual(c.deterministic_or_judgment, "model_judgment")
        self.assertIn("Submission Under Review", materials_text)

    def test_no_candidates_section_returns_empty_list(self):
        segments = [
            integrity_review.cross_format_analysis.AnalysisSegment(
                parts=[integrity_review.cross_format_analysis.Part(type="text", text="## Executive Summary\nAll clear.\n")]
            )
        ]
        candidates, _ = integrity_review._parse_candidates(segments)
        self.assertEqual(candidates, [])


class IntegrityReviewValidateSelectionTests(unittest.TestCase):
    """Module-level, no database: format/count/size pre-flight checks."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(self._tmpdir.name) / "DealLabData"
        work_products.DATA_DIR = documents.DATA_DIR
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        documents.init_documents_db()
        tasks.init_tasks_db()
        work_products.init_work_products_db()
        self.project = store.create_project("Validate Selection Tests", "")
        self.task = tasks.create_task(self.project.id, "Draft memo")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def _wp(self, filename, data=PDF_BYTES):
        return work_products.create_work_product(
            self.project.id, self.task.id, "x", filename, data, created_by="u1"
        ).work_product

    def _doc(self, filename, data=PDF_BYTES):
        return documents.save_uploaded_file(self.project.id, filename, "", data).document

    def _target(self, wp):
        return integrity_review.TargetSelection(work_product=wp, version=work_products.get_version(wp.id, wp.current_version_id))

    def _source(self, doc):
        return integrity_review.SourceSelection(document=doc, version=documents.get_version(doc.id, doc.current_version_id))

    def test_target_must_be_pdf(self):
        target = self._target(self._wp("memo.txt"))
        error = integrity_review.validate_selection(target, [self._source(self._doc("im.pdf"))], [])
        self.assertEqual(error[0], "target_not_pdf")

    def test_requires_at_least_one_source(self):
        target = self._target(self._wp("memo.pdf"))
        error = integrity_review.validate_selection(target, [], [])
        self.assertEqual(error[0], "no_sources")

    def test_unsupported_source_type_rejected(self):
        target = self._target(self._wp("memo.pdf"))
        error = integrity_review.validate_selection(target, [self._source(self._doc("notes.txt"))], [])
        self.assertEqual(error[0], "unsupported_source_type")

    def test_peer_must_be_pdf(self):
        target = self._target(self._wp("memo.pdf"))
        peer_wp = self._wp("peer.txt")
        peer = integrity_review.PeerSelection(
            work_product=peer_wp, version=work_products.get_version(peer_wp.id, peer_wp.current_version_id)
        )
        error = integrity_review.validate_selection(target, [self._source(self._doc("im.pdf"))], [peer])
        self.assertEqual(error[0], "peer_not_pdf")

    def test_valid_selection_passes(self):
        target = self._target(self._wp("memo.pdf"))
        error = integrity_review.validate_selection(target, [self._source(self._doc("im.pdf"))], [])
        self.assertIsNone(error)

    def test_excel_source_is_supported(self):
        target = self._target(self._wp("memo.pdf"))
        error = integrity_review.validate_selection(target, [self._source(self._doc("model.xlsx", XLSX_BYTES))], [])
        self.assertIsNone(error)


class IntegrityReviewCapabilityTests(unittest.TestCase):
    """Real HTTP-free, real-database, mocked-provider tests of the full
    mandate/capability/persistence/publish pipeline."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(self._tmpdir.name) / "DealLabData"
        work_products.DATA_DIR = documents.DATA_DIR
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        documents.init_documents_db()
        tasks.init_tasks_db()
        work_products.init_work_products_db()
        workspaces.init_workspaces_db()
        deal_briefs.init_deal_briefs_db()
        workstreams.init_workstreams_db()
        integrity_reviews.init_integrity_reviews_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()

        self.project = store.create_project("Integrity Review Tests", "")
        self.other_project = store.create_project("Other Deal", "")
        self.task = tasks.create_task(self.project.id, "Draft the valuation memo")
        self.target_wp = work_products.create_work_product(
            self.project.id, self.task.id, "Valuation memo", "memo.pdf", PDF_BYTES, created_by="analyst-1"
        ).work_product
        self.source_doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF_BYTES).document
        self.worker = mandates.Worker()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def _stage_input(self, target_wp=None, target_version_id=None, documents_=None, peers=None, **extra):
        target_wp = target_wp or self.target_wp
        return {
            "target": {
                "work_product_id": target_wp.id,
                "version_id": target_version_id or target_wp.current_version_id,
            },
            "documents": documents_ or [{"document_id": self.source_doc.id, "version_id": self.source_doc.current_version_id}],
            **({"peers": peers} if peers is not None else {}),
            **extra,
        }

    def _propose_and_approve(self, stage_input=None):
        mandate = mandates.create_mandate(self.project.id, "Review the valuation memo", created_by="u1")
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "integrity-review",
            stage_inputs={"review": stage_input or self._stage_input()},
        )
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead")
        return mandate, plan

    # -- registration -------------------------------------------------------

    def test_capability_and_template_are_registered(self):
        descriptor = mandates.get_capability("integrity.review_work_product")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.side_effect_class, "external_paid_call")
        template = mandates.get_template("integrity-review")
        self.assertIsNotNone(template)
        self.assertEqual(template.stages[0]["capability"], "integrity.review_work_product")
        self.assertEqual(template.stages[1]["kind"], "human_checkpoint")

    def test_integrity_review_template_is_excluded_from_llm_planning(self):
        self.assertIn("integrity-review", mandates._TEMPLATES_EXCLUDED_FROM_LLM_PLANNING)

    # -- propose-time verification (required test #2: forged ids rejected) --

    def test_propose_plan_rejects_forged_target(self):
        mandate = mandates.create_mandate(self.project.id, "Review", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "integrity-review",
                stage_inputs={"review": {
                    "target": {"work_product_id": "does-not-exist", "version_id": "does-not-exist"},
                    "documents": [{"document_id": self.source_doc.id, "version_id": self.source_doc.current_version_id}],
                }},
            )

    def test_propose_plan_rejects_forged_source_version(self):
        mandate = mandates.create_mandate(self.project.id, "Review", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "integrity-review",
                stage_inputs={"review": {
                    "target": {"work_product_id": self.target_wp.id, "version_id": self.target_wp.current_version_id},
                    "documents": [{"document_id": self.source_doc.id, "version_id": "not-a-real-version"}],
                }},
            )

    def test_propose_plan_rejects_empty_documents_list(self):
        mandate = mandates.create_mandate(self.project.id, "Review", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "integrity-review",
                stage_inputs={"review": {
                    "target": {"work_product_id": self.target_wp.id, "version_id": self.target_wp.current_version_id},
                    "documents": [],
                }},
            )

    def test_propose_plan_rejects_peer_from_another_project(self):
        """Required test #5: peer submission from another project rejected."""
        other_task = tasks.create_task(self.other_project.id, "Other analyst's memo")
        other_wp = work_products.create_work_product(
            self.other_project.id, other_task.id, "Other memo", "other.pdf", PDF_BYTES, created_by="u2"
        ).work_product
        mandate = mandates.create_mandate(self.project.id, "Review", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "integrity-review",
                stage_inputs={"review": self._stage_input(peers=[
                    {"work_product_id": other_wp.id, "version_id": other_wp.current_version_id}
                ])},
            )

    def test_propose_plan_rejects_deleted_document_lookalike_cross_project(self):
        """A real document id from a different project must not resolve -
        documents.get_document is itself project-scoped."""
        other_doc = documents.save_uploaded_file(self.other_project.id, "im.pdf", "", PDF_BYTES).document
        mandate = mandates.create_mandate(self.project.id, "Review", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "integrity-review",
                stage_inputs={"review": self._stage_input(
                    documents_=[{"document_id": other_doc.id, "version_id": other_doc.current_version_id}]
                )},
            )

    def test_propose_plan_pins_the_exact_version_selected_not_current(self):
        """Required test #4 (exact bytes/versions transmitted): pinning an
        older version must not be silently upgraded to "current" the way
        reconciliation's own document_ids-only input is."""
        older_version_id = self.target_wp.current_version_id
        work_products.add_version(self.project.id, self.target_wp.id, PDF_BYTES + b"v2", uploaded_by="analyst-1")
        current_wp = work_products.get_work_product(self.project.id, self.target_wp.id)
        self.assertNotEqual(current_wp.current_version_id, older_version_id)

        mandate, plan = self._propose_and_approve(
            self._stage_input(target_version_id=older_version_id)
        )
        stage = plan.stages[0]
        self.assertEqual(stage["input"]["target"]["version_id"], older_version_id)

    # -- execution (mocked provider call) ------------------------------------

    def test_execute_run_persists_candidates_and_creates_workspace(self):
        mandate, plan = self._propose_and_approve()
        fake_outcome = _fake_outcome(candidates=[_one_candidate()])
        with patch("mandates.integrity_review.run_integrity_review", return_value=fake_outcome):
            run = mandates.execute_run(self.project.id, mandate.id)
            self.worker.poll_once()

        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "waiting_for_input")  # paused at the human_checkpoint
        attempts = mandates.list_attempts(run.id)
        output = attempts[0].output
        self.assertEqual(output["candidate_count"], 1)
        review = integrity_reviews.get_integrity_review(self.project.id, output["integrity_review_id"])
        self.assertIsNotNone(review)
        self.assertEqual(review.target_work_product_id, self.target_wp.id)
        self.assertEqual(review.source_document_ids, [self.source_doc.id])
        # Found live during this task's own real paid proof run (see
        # STATUS.md): the audit record must identify the exact mandate/
        # run/attempt that produced it - the M14.2 spec's own "Published
        # findings identify: Originating mandate/run/attempt" requirement.
        self.assertEqual(review.mandate_id, mandate.id)
        self.assertEqual(review.run_id, run.id)
        self.assertEqual(review.attempt_id, attempts[0].id)

        candidates = integrity_reviews.list_candidates(review.id)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].decision, "pending")

        workspace = workspaces.get_workspace_for_integrity_review(self.project.id, review.id)
        self.assertIsNotNone(workspace)
        # Required test #7 (human checkpoint required before publication):
        # a fresh candidate must not already be a shared finding.
        self.assertEqual(workspaces.list_findings(workspace), [])

    def test_a_failed_outcome_still_persists_the_audit_record_but_fails_the_run(self):
        mandate, plan = self._propose_and_approve()
        with patch(
            "mandates.integrity_review.run_integrity_review",
            return_value=_fake_outcome(success=False, error_message="the model returned an error"),
        ):
            run = mandates.execute_run(self.project.id, mandate.id)
            self.worker.poll_once()

        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "failed")
        reviews_list = integrity_reviews.list_integrity_reviews(self.project.id)
        self.assertEqual(len(reviews_list), 1)
        self.assertEqual(reviews_list[0].status, "error")
        self.assertEqual(integrity_reviews.list_candidates(reviews_list[0].id), [])

    def test_deleted_target_since_approval_fails_the_attempt(self):
        mandate, plan = self._propose_and_approve()
        # Work products have no delete route in this app, so simulate the
        # "deleted since approval" case the same way reconciliation's own
        # test does - by pointing the plan's pinned id at something that
        # no longer resolves.
        conn = store.get_connection()
        try:
            import json as _json
            row = conn.execute("SELECT stages_json FROM plan_revisions WHERE id = %s", (plan.id,)).fetchone()
            stages = _json.loads(row["stages_json"])
            stages[0]["input"]["target"]["work_product_id"] = "no-longer-exists"
            conn.execute("UPDATE plan_revisions SET stages_json = %s WHERE id = %s", (_json.dumps(stages), plan.id))
            conn.commit()
        finally:
            conn.close()

        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()
        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "failed")
        attempts = mandates.list_attempts(run.id)
        self.assertIn("target submission version not found", attempts[0].error)

    # -- budget ledger (required test #12) -----------------------------------

    def test_budget_exceeded_blocks_the_paid_call(self):
        mandate, plan = self._propose_and_approve()
        run = mandates.execute_run(self.project.id, mandate.id, budget_limit=0.5)  # unit_cost is 1.0
        with patch("mandates.integrity_review.run_integrity_review") as mock_run:
            self.worker.poll_once()
            mock_run.assert_not_called()
        run = mandates.get_run(mandate.id, run.id)
        self.assertEqual(run.status, "failed")
        attempts = mandates.list_attempts(run.id)
        self.assertIn("budget exceeded", attempts[0].error)

    # -- output schema self-consistency (Task 14.1's own pattern) -----------

    def test_real_output_matches_its_own_declared_output_schema(self):
        mandate, plan = self._propose_and_approve()
        descriptor = mandates.get_capability("integrity.review_work_product")
        with patch("mandates.integrity_review.run_integrity_review", return_value=_fake_outcome(candidates=[_one_candidate()])):
            run = mandates.execute_run(self.project.id, mandate.id)
            self.worker.poll_once()
        attempts = mandates.list_attempts(mandates.get_run(mandate.id, run.id).id)
        mandates._validate_against_schema(attempts[0].output, descriptor.output_schema, "test")  # must not raise

    # -- candidate decisions and shared-findings publication -----------------

    def _run_to_candidate(self):
        mandate, plan = self._propose_and_approve()
        with patch("mandates.integrity_review.run_integrity_review", return_value=_fake_outcome(candidates=[_one_candidate()])):
            run = mandates.execute_run(self.project.id, mandate.id)
            self.worker.poll_once()
        attempts = mandates.list_attempts(run.id)
        review_id = attempts[0].output["integrity_review_id"]
        candidate = integrity_reviews.list_candidates(review_id)[0]
        return review_id, candidate

    def test_rejected_candidate_never_becomes_a_shared_finding(self):
        """Required test #8."""
        review_id, candidate = self._run_to_candidate()
        integrity_reviews.record_candidate_decision(
            review_id, candidate.id, "rejected", decided_by="reviewer-1", decision_notes="not material",
        )
        workspace = workspaces.get_workspace_for_integrity_review(self.project.id, review_id)
        self.assertEqual(workspaces.list_findings(workspace), [])
        # But it stays fully auditable in the run - never deleted.
        refreshed = integrity_reviews.get_candidate(review_id, candidate.id)
        self.assertEqual(refreshed.decision, "rejected")
        self.assertEqual(refreshed.decision_notes, "not material")

    def test_accepted_candidate_publishes_with_complete_lineage(self):
        """Required test #9."""
        review_id, candidate = self._run_to_candidate()
        review = integrity_reviews.get_integrity_review(self.project.id, review_id)
        workspace, _ = workspaces.get_or_create_workspace_for_integrity_review(self.project.id, review_id)
        content = candidate.effective_content()
        lineage = {
            "integrity_review_id": review.id,
            "target": {"work_product_id": review.target_work_product_id, "version_id": review.target_version_id},
            "sources": [{"document_id": d, "version_id": v} for d, v in zip(review.source_document_ids, review.source_version_ids)],
            "peers": [],
            "review_template_version": review.review_template_version,
            "publication_decision": {"decided_by": "reviewer-1", "edited": False, "decision_notes": ""},
        }
        finding = workspaces.publish_integrity_candidate_as_finding(
            workspace.id, candidate.candidate_index, content, review.review_template_version, lineage,
        )
        self.assertEqual(finding["origin"], "integrity")
        self.assertEqual(finding["title"], candidate.title)
        self.assertEqual(finding["lineage"]["target"]["work_product_id"], self.target_wp.id)
        self.assertEqual(finding["lineage"]["sources"][0]["document_id"], self.source_doc.id)
        self.assertEqual(finding["lineage"]["review_template_version"], integrity_review.REVIEW_TEMPLATE_VERSION)
        self.assertEqual(finding["lineage"]["publication_decision"]["decided_by"], "reviewer-1")

        integrity_reviews.record_candidate_decision(
            review_id, candidate.id, "accepted", decided_by="reviewer-1", published_finding_id=finding["id"],
        )
        found = workspaces.list_findings(workspace)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["id"], finding["id"])

    def test_duplicate_linkage_preserves_both_histories(self):
        """Required test #10."""
        review_id, candidate = self._run_to_candidate()
        updated = integrity_reviews.record_candidate_decision(
            review_id, candidate.id, "duplicate", decided_by="reviewer-1",
            duplicate_of_finding_id="ai-some-existing-finding",
        )
        self.assertEqual(updated.decision, "duplicate")
        self.assertEqual(updated.duplicate_of_finding_id, "ai-some-existing-finding")
        # The candidate's own immutable parsed content is untouched.
        self.assertEqual(updated.title, candidate.title)
        self.assertEqual(updated.assertion, candidate.assertion)

    def test_duplicate_decision_requires_a_target_finding_id(self):
        review_id, candidate = self._run_to_candidate()
        with self.assertRaises(integrity_reviews.CandidateDecisionError):
            integrity_reviews.record_candidate_decision(review_id, candidate.id, "duplicate", decided_by="reviewer-1")

    def test_edit_may_only_touch_editable_fields(self):
        review_id, candidate = self._run_to_candidate()
        with self.assertRaises(integrity_reviews.CandidateDecisionError):
            integrity_reviews.record_candidate_decision(
                review_id, candidate.id, "accepted", decided_by="reviewer-1",
                edits={"assertion": "trying to rewrite the model's own evidence"},
            )

    def test_edit_overrides_only_the_edited_fields_on_publication(self):
        review_id, candidate = self._run_to_candidate()
        content = candidate.effective_content()
        content.update({"severity": "critical"})  # simulating a reviewer's edit, applied before publish
        review = integrity_reviews.get_integrity_review(self.project.id, review_id)
        workspace, _ = workspaces.get_or_create_workspace_for_integrity_review(self.project.id, review_id)
        finding = workspaces.publish_integrity_candidate_as_finding(
            workspace.id, candidate.candidate_index, content, review.review_template_version, {},
        )
        self.assertEqual(finding["severity"], "critical")
        self.assertEqual(finding["assertion"], candidate.assertion)  # untouched


class IntegrityReviewWorkspaceGeneralizationTests(unittest.TestCase):
    """Confirms workspaces.py's generalization for a nullable
    cross_format_analysis_id / new integrity_review_id column did not
    disturb the pre-existing reconciliation-only shape."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        workspaces.init_workspaces_db()
        self.project = store.create_project("Workspace Generalization Tests", "")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def test_integrity_review_workspace_is_idempotent(self):
        review_id = uuid.uuid4().hex
        ws1, created1 = workspaces.get_or_create_workspace_for_integrity_review(self.project.id, review_id)
        ws2, created2 = workspaces.get_or_create_workspace_for_integrity_review(self.project.id, review_id)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(ws1.id, ws2.id)
        self.assertIsNone(ws1.cross_format_analysis_id)
        self.assertEqual(ws1.integrity_review_id, review_id)

    def test_integrity_review_workspace_starts_with_no_findings(self):
        review_id = uuid.uuid4().hex
        workspace, _ = workspaces.get_or_create_workspace_for_integrity_review(self.project.id, review_id)
        self.assertEqual(workspaces.list_findings(workspace), [])

    def test_two_kinds_of_workspace_do_not_collide(self):
        review_id = uuid.uuid4().hex
        analysis_id = uuid.uuid4().hex
        review_ws, _ = workspaces.get_or_create_workspace_for_integrity_review(self.project.id, review_id)
        self.assertIsNone(workspaces.get_workspace_for_analysis(self.project.id, analysis_id))
        self.assertIsNone(workspaces.get_workspace_for_integrity_review(self.project.id, analysis_id))
        found = workspaces.get_workspace_for_integrity_review(self.project.id, review_id)
        self.assertEqual(found.id, review_ws.id)


if __name__ == "__main__":
    unittest.main()
