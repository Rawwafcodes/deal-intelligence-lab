"""End-to-end tests for Task 15.1's staleness propagation across the
real mandate capabilities and version-creation call sites - proving the
roadmap's own M15.1 completion-gate scenario for real:

1. An approved submission depends on source version 1.
2. Source version 2 is uploaded.
3. The submission and dependent conclusion become potentially stale
   without an AI call.

(15.2's targeted reassessment and 15.3's trigger policy are separate,
not-yet-authorized tasks - this file proves 15.1's own scope only.)

Provider calls are mocked (integrity_review.run_integrity_review,
decision_package.run_decision_package_draft) exactly as their own
dedicated test suites already do; nothing about staleness propagation
itself involves a mock, since version_dependencies.py makes no external
call at all.
"""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import cross_format_analyses
import deal_briefs
import decision_package
import deliverables
import documents
import integrity_review
import integrity_reviews
import mandates
import reviews
import store
import tasks
import triggers
import version_dependencies
import work_products
import workspaces
import workstreams

PDF_BYTES = b"%PDF-1.4\n%Staleness propagation test bytes\n%%EOF"


def _fake_integrity_outcome():
    return integrity_review.IntegrityReviewOutcome(
        success=True, transmitted=True, analysis_seconds=1.0, model="claude-opus-5", stop_reason="end_turn",
        usage={"input_tokens": 500, "output_tokens": 200},
        candidates=[integrity_review.IntegrityCandidateOutcome(
            index=0, title="Net debt figure differs", classification="numerical conflict", severity="high",
            assertion="the memo states $2.0m", conflicting_or_missing_evidence="the term sheet states $2.5m",
            why_it_matters="affects the price bridge", uncertainty="fully supported by citations",
            recommended_resolution="reconcile the two figures", deterministic_or_judgment="deterministic",
        )],
        materials_reviewed_text="Submission Under Review: memo.pdf",
    )


class StalenessPropagationTests(unittest.TestCase):
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
        deliverables.init_deliverables_db()
        reviews.init_reviews_db()
        version_dependencies.init_version_dependencies_db()
        triggers.init_triggers_db()
        mandates.init_mandates_db()

        self.project = store.create_project("Staleness Propagation Tests", "")
        self.task = tasks.create_task(self.project.id, "Draft the valuation memo")
        self.submission = work_products.create_work_product(
            self.project.id, self.task.id, "Valuation memo", "memo.pdf", PDF_BYTES, created_by="analyst-1"
        ).work_product
        self.source_doc = documents.save_uploaded_file(self.project.id, "term_sheet.pdf", "", PDF_BYTES).document
        self.worker = mandates.Worker()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def _run_integrity_review_to_completion(self):
        mandate = mandates.create_mandate(self.project.id, "Integrity review the memo", created_by="lead-1")
        stage_input = {
            "target": {"work_product_id": self.submission.id, "version_id": self.submission.current_version_id},
            "documents": [{"document_id": self.source_doc.id, "version_id": self.source_doc.current_version_id}],
        }
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "integrity-review", stage_inputs={"review": stage_input},
        )
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead-1")
        run = mandates.execute_run(self.project.id, mandate.id)
        with patch("mandates.integrity_review.run_integrity_review", return_value=_fake_integrity_outcome()):
            self.worker.poll_once()
        return mandates.get_run(mandate.id, run.id)

    # -- the roadmap's own completion-gate scenario, steps 1-3 -----------

    def test_completion_gate_scenario_source_version_change_stales_the_workspace(self):
        run = self._run_integrity_review_to_completion()
        self.assertEqual(run.status, "waiting_for_input")
        review_id = mandates.list_attempts(run.id)[0].output["integrity_review_id"]
        review = integrity_reviews.get_integrity_review(self.project.id, review_id)
        workspace = workspaces.get_workspace_for_integrity_review(self.project.id, review_id)
        self.assertIsNotNone(workspace)

        # Step 1 (already true by construction): the review depends on
        # source_doc at its version-1 id.
        self.assertEqual(review.source_version_ids, [self.source_doc.current_version_id])
        old_version_id = self.source_doc.current_version_id
        self.assertIsNone(version_dependencies.get_staleness("workspace", workspace.id))

        # Publish the candidate as a real shared finding (the "conclusion").
        candidate = integrity_reviews.list_candidates(review_id)[0]
        finding = workspaces.publish_integrity_candidate_as_finding(
            workspace.id, candidate.candidate_index, candidate.effective_content(),
            review.review_template_version, {"integrity_review_id": review.id},
        )
        original_finding_content = dict(finding)

        # Step 2: source version 2 is uploaded - no mandate, no AI call,
        # a plain document upload.
        result = documents.add_version(self.project.id, self.source_doc.id, PDF_BYTES + b"\nrevised terms\n")
        self.assertEqual(result.status, "new_version")
        new_version_id = result.document.current_version_id
        self.assertNotEqual(old_version_id, new_version_id)

        # Step 3: the workspace (and, by extension, its published
        # conclusion) is now potentially stale - no AI call anywhere in
        # this test, and the finding's own content is untouched.
        flag = version_dependencies.get_staleness("workspace", workspace.id)
        self.assertIsNotNone(flag)
        self.assertIn(self.source_doc.id, flag.reason)
        self.assertIn(old_version_id, flag.reason)
        self.assertIn(new_version_id, flag.reason)

        unchanged_finding = workspaces.get_finding(workspace, None, finding["id"])
        self.assertEqual(unchanged_finding["title"], original_finding_content["title"])
        self.assertEqual(unchanged_finding["assertion"], original_finding_content["assertion"])

        # MandateRun -> every version it consumed (a required relationship
        # in its own right, independent of the workspace).
        mandate_run_flag_source = version_dependencies.get_staleness("mandate_run", run.id)
        self.assertIsNotNone(mandate_run_flag_source)

    def test_deliverable_built_from_a_stale_workspace_inherits_staleness_immediately(self):
        run = self._run_integrity_review_to_completion()
        review_id = mandates.list_attempts(run.id)[0].output["integrity_review_id"]
        review = integrity_reviews.get_integrity_review(self.project.id, review_id)
        workspace = workspaces.get_workspace_for_integrity_review(self.project.id, review_id)
        candidate = integrity_reviews.list_candidates(review_id)[0]
        workspaces.publish_integrity_candidate_as_finding(
            workspace.id, candidate.candidate_index, candidate.effective_content(),
            review.review_template_version, {"integrity_review_id": review.id},
        )
        workspaces.update_finding_workflow(
            workspace.id, workspaces.list_findings(workspace)[0]["id"], {"review_status": "accepted"},
        )

        # Source changes first, staling the workspace...
        documents.add_version(self.project.id, self.source_doc.id, PDF_BYTES + b"\nrevised again\n")
        self.assertIsNotNone(version_dependencies.get_staleness("workspace", workspace.id))

        # ...then a decision package is drafted from that already-stale
        # workspace. The new deliverable must inherit staleness at the
        # moment of its own creation, not only via a future propagation.
        dp_mandate = mandates.create_mandate(self.project.id, "Draft a package anyway", created_by="lead-1")
        dp_plan = mandates.propose_plan(
            self.project.id, dp_mandate.id, "decision-package",
            stage_inputs={"draft": {"workspace_id": workspace.id}},
        )
        mandates.approve_plan(self.project.id, dp_mandate.id, dp_plan.id, approved_by="lead-1")
        dp_run = mandates.execute_run(self.project.id, dp_mandate.id)
        with patch(
            "mandates.decision_package.run_decision_package_draft",
            return_value=decision_package.DecisionPackageOutcome(
                success=True, transmitted=True, analysis_seconds=0.5, model="claude-opus-5", stop_reason="end_turn",
                usage={"input_tokens": 100, "output_tokens": 50}, executive_summary="x", recommendation="y",
                key_evidence_and_findings="z", outstanding_and_unresolved_matters="a", risks_and_limitations="b",
            ),
        ):
            self.worker.poll_once()

        deliverable_id = mandates.list_attempts(dp_run.id)[0].output["deliverable_id"]
        flag = version_dependencies.get_staleness("deliverable_version", deliverable_id)
        self.assertIsNotNone(flag)
        self.assertIn(workspace.id, flag.reason)

    def test_review_decision_becomes_stale_when_the_submission_gets_a_new_version(self):
        """SubmissionVersion -> approval decision, the other required
        relationship - independent of the source-document chain above."""
        decision = reviews.record_decision(
            self.task.id, self.submission.id, self.submission.current_version_id, reviewer_id="lead-1",
            decision="approved",
        )
        self.assertIsNone(version_dependencies.get_staleness("review_decision", decision.id))

        old_version_id = self.submission.current_version_id
        result = work_products.add_version(
            self.project.id, self.submission.id, PDF_BYTES + b"\nrevised submission\n", uploaded_by="analyst-1",
        )
        self.assertEqual(result.status, "new_version")

        flag = version_dependencies.get_staleness("review_decision", decision.id)
        self.assertIsNotNone(flag)
        self.assertIn(self.submission.id, flag.reason)
        self.assertIn(old_version_id, flag.reason)
        # The append-only decision itself is never mutated - staleness
        # lives entirely in the side table, not on the ReviewDecision row.
        self.assertEqual(reviews.latest_decision_for_work_product(self.submission.id).id, decision.id)
        self.assertEqual(reviews.latest_decision_for_work_product(self.submission.id).decision, "approved")


if __name__ == "__main__":
    unittest.main()
