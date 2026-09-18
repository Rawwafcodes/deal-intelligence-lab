"""Tests for Task 14.4's readiness checklist: the pure assessment logic
(readiness.py), its persistence (readiness_assessments.py), and the
`readiness.assess_scope` mandate capability/template (mandates.py). No
mocking anywhere in this module - this capability makes no external call
of any kind, so its full real execution can be exercised directly,
unlike every paid capability's own test suite.
"""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cross_format_analyses
import deal_briefs
import deliverables
import documents
import mandates
import readiness
import readiness_assessments
import store
import workspaces


def _text_segment(text: str) -> dict:
    return {"parts": [{"type": "text", "text": text}], "pdf_citations": []}


SAMPLE_FINDINGS_TEXT = (
    "## Reconciliation Findings\n"
    "- **Title:** Term-sheet price gap\n"
    "**Classification:** cross-source conflict\n"
    "**Severity:** critical\n"
    "**Explanation:** the price differs across sources.\n"
    "**PDF evidence:** the IM says $12m.\n"
    "**Workbook evidence:** the model says $10m.\n"
    "**Commercial or financial relevance:** determines the offer price.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended action:** ask the seller to reconcile.\n\n"
)


def _finding(review_status="unreviewed", effective_severity="high", resolution_status="open", title="x"):
    return {
        "id": uuid.uuid4().hex, "title": title, "effective_severity": effective_severity,
        "review_status": review_status, "resolution_status": resolution_status,
    }


class AssessReadinessTests(unittest.TestCase):
    """Module-level, no database: the pure checklist function."""

    def test_all_items_met_is_ready(self):
        assessment = readiness.assess_readiness(
            has_brief=True, has_documents=True, findings=[_finding(review_status="accepted", effective_severity="low")],
            open_request_count=0, memo_approved=True, deliverable_approved=False,
        )
        self.assertTrue(assessment.ready)
        self.assertEqual(assessment.unmet_items, [])
        self.assertEqual(len(assessment.items), 6)

    def test_missing_brief_fails_that_item_only(self):
        assessment = readiness.assess_readiness(
            has_brief=False, has_documents=True, findings=[], open_request_count=0,
            memo_approved=True, deliverable_approved=False,
        )
        self.assertFalse(assessment.ready)
        unmet_keys = {i.key for i in assessment.unmet_items}
        self.assertEqual(unmet_keys, {"has_brief"})

    def test_open_critical_finding_fails_readiness(self):
        assessment = readiness.assess_readiness(
            has_brief=True, has_documents=True,
            findings=[_finding(review_status="accepted", effective_severity="critical", resolution_status="open")],
            open_request_count=0, memo_approved=True, deliverable_approved=False,
        )
        self.assertFalse(assessment.ready)
        self.assertIn("no_open_critical_or_high_findings", {i.key for i in assessment.unmet_items})

    def test_resolved_critical_finding_does_not_fail_readiness(self):
        assessment = readiness.assess_readiness(
            has_brief=True, has_documents=True,
            findings=[_finding(review_status="accepted", effective_severity="critical", resolution_status="resolved")],
            open_request_count=0, memo_approved=True, deliverable_approved=False,
        )
        self.assertNotIn("no_open_critical_or_high_findings", {i.key for i in assessment.unmet_items})

    def test_unreviewed_finding_fails_readiness(self):
        assessment = readiness.assess_readiness(
            has_brief=True, has_documents=True,
            findings=[_finding(review_status="unreviewed", effective_severity="low")],
            open_request_count=0, memo_approved=True, deliverable_approved=False,
        )
        self.assertIn("no_unreviewed_findings", {i.key for i in assessment.unmet_items})

    def test_open_information_request_fails_readiness(self):
        assessment = readiness.assess_readiness(
            has_brief=True, has_documents=True, findings=[], open_request_count=1,
            memo_approved=True, deliverable_approved=False,
        )
        self.assertIn("no_open_information_requests", {i.key for i in assessment.unmet_items})

    def test_deliverable_approval_alone_satisfies_position_approved(self):
        assessment = readiness.assess_readiness(
            has_brief=True, has_documents=True, findings=[], open_request_count=0,
            memo_approved=False, deliverable_approved=True,
        )
        self.assertNotIn("position_approved", {i.key for i in assessment.unmet_items})

    def test_neither_memo_nor_deliverable_approved_fails_readiness(self):
        assessment = readiness.assess_readiness(
            has_brief=True, has_documents=True, findings=[], open_request_count=0,
            memo_approved=False, deliverable_approved=False,
        )
        self.assertIn("position_approved", {i.key for i in assessment.unmet_items})

    def test_scope_description_carried_on_every_assessment(self):
        assessment = readiness.assess_readiness(
            has_brief=True, has_documents=True, findings=[], open_request_count=0,
            memo_approved=True, deliverable_approved=False,
        )
        self.assertEqual(assessment.scope_description, readiness.SCOPE_DESCRIPTION)
        self.assertIn("not a claim", assessment.scope_description.lower())


class ReadinessAssessmentPersistenceTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        readiness_assessments.init_readiness_assessments_db()
        self.project = store.create_project("Readiness Persistence Tests", "")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def test_create_and_list_and_get(self):
        assessment = readiness.assess_readiness(
            has_brief=True, has_documents=True, findings=[], open_request_count=0,
            memo_approved=True, deliverable_approved=False,
        )
        record = readiness_assessments.create_readiness_assessment(
            project_id=self.project.id, workspace_id="ws-1", mandate_id="m1", run_id="r1", attempt_id="a1",
            assessment=assessment,
        )
        self.assertTrue(record.ready)
        self.assertEqual(record.mandate_id, "m1")

        listed = readiness_assessments.list_readiness_assessments("ws-1")
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0].id, record.id)

        fetched = readiness_assessments.get_readiness_assessment("ws-1", record.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.scope_description, readiness.SCOPE_DESCRIPTION)
        self.assertEqual(len(fetched.items), 6)

    def test_multiple_assessments_are_all_preserved(self):
        not_ready = readiness.assess_readiness(
            has_brief=False, has_documents=True, findings=[], open_request_count=0,
            memo_approved=False, deliverable_approved=False,
        )
        ready = readiness.assess_readiness(
            has_brief=True, has_documents=True, findings=[], open_request_count=0,
            memo_approved=True, deliverable_approved=False,
        )
        readiness_assessments.create_readiness_assessment(
            project_id=self.project.id, workspace_id="ws-2", mandate_id=None, run_id=None, attempt_id=None,
            assessment=not_ready,
        )
        readiness_assessments.create_readiness_assessment(
            project_id=self.project.id, workspace_id="ws-2", mandate_id=None, run_id=None, attempt_id=None,
            assessment=ready,
        )
        listed = readiness_assessments.list_readiness_assessments("ws-2")
        self.assertEqual(len(listed), 2)
        self.assertFalse(listed[0].ready)
        self.assertTrue(listed[1].ready)


class ReadinessCapabilityTests(unittest.TestCase):
    """Real HTTP-free, real-database tests of the full mandate/
    capability/persistence pipeline - no mocking needed since this
    capability makes no external call."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(self._tmpdir.name) / "DealLabData"
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        documents.init_documents_db()
        cross_format_analyses.init_cross_format_analyses_db()
        workspaces.init_workspaces_db()
        deal_briefs.init_deal_briefs_db()
        deliverables.init_deliverables_db()
        readiness_assessments.init_readiness_assessments_db()
        mandates.init_mandates_db()

        self.project = store.create_project("Readiness Capability Tests", "")
        self.other_project = store.create_project("Other Deal", "")
        self.pdf_doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", b"%PDF-1.4\n%x\n%%EOF").document
        self.xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-bytes"
        ).document
        self.analysis = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id,
            pdf_document_ids=[self.pdf_doc.id], pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[self.pdf_doc.sha256],
            excel_document_ids=[self.xlsx_doc.id], excel_document_filenames=["model.xlsx"],
            excel_document_checksums=[self.xlsx_doc.sha256],
            status="success", transmitted=True, analysis_seconds=12.5, model="claude-opus-5", mandate_version="1",
            stop_reason="end_turn", input_tokens=5000, output_tokens=1200, code_execution_requests=2,
            error_type=None, error_message=None, segments=[_text_segment(SAMPLE_FINDINGS_TEXT)],
            tool_trace=None, excel_cleanup=None, excel_verification=None,
        )
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        self.worker = mandates.Worker()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def _run_to_completion(self, workspace_id=None):
        mandate = mandates.create_mandate(self.project.id, "Assess readiness", created_by="lead-1")
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "readiness",
            stage_inputs={"assess": {"workspace_id": workspace_id or self.workspace.id}},
        )
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead-1")
        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()
        return mandates.get_mandate(self.project.id, mandate.id), mandates.get_run(mandate.id, run.id)

    def test_capability_and_template_registered_no_checkpoint(self):
        descriptor = mandates.get_capability("readiness.assess_scope")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.side_effect_class, "read_only")
        self.assertEqual(descriptor.unit_cost, 0.0)
        template = mandates.get_template("readiness")
        self.assertIsNotNone(template)
        self.assertEqual(len(template.stages), 1)
        self.assertIn("readiness", mandates._TEMPLATES_EXCLUDED_FROM_LLM_PLANNING)

    def test_propose_rejects_unknown_workspace(self):
        mandate = mandates.create_mandate(self.project.id, "x", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "readiness", stage_inputs={"assess": {"workspace_id": "nope"}},
            )

    def test_propose_rejects_workspace_from_another_project(self):
        mandate = mandates.create_mandate(self.other_project.id, "x", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.other_project.id, mandate.id, "readiness",
                stage_inputs={"assess": {"workspace_id": self.workspace.id}},
            )

    def test_runs_immediately_even_when_nothing_is_reviewed_yet(self):
        """Unlike decision-package, readiness has no precondition on
        review activity - it must be runnable precisely when a workspace
        is NOT yet ready, to report that fact."""
        mandate, run = self._run_to_completion()
        self.assertEqual(run.status, "succeeded")
        self.assertEqual(mandate.status, "completed")

        attempts = mandates.list_attempts(run.id)
        assess_attempt = attempts[0]
        self.assertEqual(assess_attempt.status, "succeeded")
        self.assertFalse(assess_attempt.output["ready"])
        self.assertGreater(assess_attempt.output["unmet_count"], 0)

        records = readiness_assessments.list_readiness_assessments(self.workspace.id)
        self.assertEqual(len(records), 1)
        self.assertFalse(records[0].ready)
        self.assertEqual(records[0].mandate_id, mandate.id)
        self.assertEqual(records[0].run_id, run.id)

    def test_run_reports_ready_once_every_item_is_satisfied(self):
        finding = workspaces.list_findings(self.workspace)[0]
        workspaces.update_finding_workflow(
            self.workspace.id, finding["id"], {"review_status": "accepted", "resolution_status": "resolved"},
        )
        deal_briefs.create_version(self.project.id, {"objective": "Reconcile the deal"}, created_by="u1")
        memo = workspaces.get_or_create_memo(self.workspace, self.analysis)
        workspaces.approve_memo(self.workspace.id, "lead-1")

        mandate, run = self._run_to_completion()
        self.assertEqual(run.status, "succeeded")
        attempts = mandates.list_attempts(run.id)
        self.assertTrue(attempts[0].output["ready"])
        self.assertEqual(attempts[0].output["unmet_count"], 0)

    def test_budget_ledger_charges_nothing_for_a_read_only_capability(self):
        mandate, run = self._run_to_completion()
        self.assertEqual(run.budget_consumed, 0.0)


if __name__ == "__main__":
    unittest.main()
