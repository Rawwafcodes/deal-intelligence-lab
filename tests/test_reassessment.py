"""Tests for Task 15.2's targeted reassessment: the pure adapter
(reassessment.py), its persistence (reassessments.py), and the
`reassessment.compare_versions` mandate capability/template
(mandates.py). No real network call anywhere - every provider call is
mocked, mirroring tests/test_integrity_review.py's own convention.
"""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import cross_format_analyses
import cross_format_analysis
import documents
import mandates
import reassessment
import reassessments
import store
import version_dependencies
import workspaces

PDF_BYTES = b"%PDF-1.4\n%Reassessment test bytes\n%%EOF"

ITEMS_TEXT = (
    "## Executive Summary\n"
    "One finding is materially affected by the new version.\n\n"
    "## What Changed\n"
    "The net debt figure was revised upward in the superseding version.\n\n"
    "## Reassessment Items\n"
    "- **Finding:** Net Debt at Closing differs by USD 500,000\n"
    "**Status:** materially_changed\n"
    "**Explanation:** the superseding version now states a still-different figure.\n"
    "**Evidence of change:** the new version restates net debt as USD 2,750,000.\n\n"
    "- **Finding:** Enterprise Value agrees across both sources\n"
    "**Status:** still_valid\n"
    "**Explanation:** the enterprise value figure did not change.\n"
    "**Evidence of change:** No relevant change located\n\n"
)


def _text_segment(text: str) -> dict:
    return {"parts": [{"type": "text", "text": text}], "pdf_citations": []}


class ParseSectionsAndItemsTests(unittest.TestCase):
    """Module-level, no database: the parser."""

    def test_parses_executive_summary_what_changed_and_two_items(self):
        segments = [cross_format_analysis.AnalysisSegment(
            parts=[cross_format_analysis.Part(type="text", text=ITEMS_TEXT)]
        )]
        exec_summary, what_changed, items = reassessment._parse_sections_and_items(segments)
        self.assertIn("materially affected", exec_summary)
        self.assertIn("revised upward", what_changed)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0].finding_title, "Net Debt at Closing differs by USD 500,000")
        self.assertEqual(items[0].status, "materially_changed")
        self.assertIn("2,750,000", items[0].evidence_of_change)
        self.assertEqual(items[1].finding_title, "Enterprise Value agrees across both sources")
        self.assertEqual(items[1].status, "still_valid")

    def test_no_items_section_returns_empty_list(self):
        segments = [cross_format_analysis.AnalysisSegment(
            parts=[cross_format_analysis.Part(type="text", text="## Executive Summary\nAll clear.\n")]
        )]
        _, _, items = reassessment._parse_sections_and_items(segments)
        self.assertEqual(items, [])


class ValidateDigestTests(unittest.TestCase):
    def test_no_findings_rejected(self):
        digest = reassessment.build_digest("memo.pdf", "t1", "t2", [])
        error = reassessment.validate_digest(digest)
        self.assertEqual(error[0], "no_findings")

    def test_with_findings_passes(self):
        finding = {"id": "f1", "title": "x", "classification": "c", "effective_severity": "high", "explanation": "e"}
        digest = reassessment.build_digest("memo.pdf", "t1", "t2", [finding])
        self.assertIsNone(reassessment.validate_digest(digest))


class ReassessmentPersistenceTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        reassessments.init_reassessments_db()
        self.project = store.create_project("Reassessment Persistence Tests", "")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def _create(self):
        return reassessments.create_reassessment(
            project_id=self.project.id, workspace_id="ws-1", mandate_id=None, run_id=None, attempt_id=None,
            document_id="doc-1", old_version_id="v1", new_version_id="v2", status="success", transmitted=True,
            analysis_seconds=1.0, model="claude-opus-5", reassessment_template_version="1", stop_reason="end_turn",
            input_tokens=100, output_tokens=50, error_type=None, error_message=None,
            executive_summary="summary", what_changed="changed",
        )

    def test_create_and_get_and_list(self):
        record = self._create()
        self.assertEqual(reassessments.get_reassessment(self.project.id, record.id).id, record.id)
        self.assertEqual(len(reassessments.list_reassessments(self.project.id)), 1)
        self.assertEqual(len(reassessments.list_reassessments(self.project.id, workspace_id="ws-1")), 1)
        self.assertEqual(len(reassessments.list_reassessments(self.project.id, workspace_id="ws-2")), 0)

    def test_items_start_pending_and_acknowledge_updates_in_place(self):
        record = self._create()
        items = reassessments.create_items(record.id, [
            {"index": 0, "finding_title": "x", "finding_id": "f1", "status": "still_valid", "explanation": "e",
             "evidence_of_change": "ev", "raw_text": "raw", "pdf_citations": []},
        ])
        self.assertEqual(items[0].decision, "pending")
        self.assertFalse(reassessments.all_items_acknowledged(record.id))

        updated = reassessments.acknowledge_item(record.id, items[0].id, decided_by="lead-1", decision_notes="ok")
        self.assertEqual(updated.decision, "acknowledged")
        self.assertEqual(updated.decided_by, "lead-1")
        self.assertTrue(reassessments.all_items_acknowledged(record.id))

    def test_all_items_acknowledged_false_with_no_items(self):
        record = self._create()
        self.assertFalse(reassessments.all_items_acknowledged(record.id))

    def test_all_items_acknowledged_requires_every_item(self):
        record = self._create()
        items = reassessments.create_items(record.id, [
            {"index": 0, "finding_title": "a", "finding_id": None, "status": "still_valid", "explanation": "",
             "evidence_of_change": "", "raw_text": "", "pdf_citations": []},
            {"index": 1, "finding_title": "b", "finding_id": None, "status": "still_valid", "explanation": "",
             "evidence_of_change": "", "raw_text": "", "pdf_citations": []},
        ])
        reassessments.acknowledge_item(record.id, items[0].id, decided_by="lead-1")
        self.assertFalse(reassessments.all_items_acknowledged(record.id))
        reassessments.acknowledge_item(record.id, items[1].id, decided_by="lead-1")
        self.assertTrue(reassessments.all_items_acknowledged(record.id))

    def test_acknowledge_unknown_item_raises(self):
        record = self._create()
        with self.assertRaises(reassessments.ReassessmentItemDecisionError):
            reassessments.acknowledge_item(record.id, "does-not-exist", decided_by="lead-1")


def _fake_outcome(success=True):
    if not success:
        return reassessment.ReassessmentOutcome(
            success=False, transmitted=True, analysis_seconds=1.0, model="claude-opus-5",
            error_type="rate_limit", error_message="slow down",
        )
    return reassessment.ReassessmentOutcome(
        success=True, transmitted=True, analysis_seconds=1.0, model="claude-opus-5", stop_reason="end_turn",
        usage={"input_tokens": 400, "output_tokens": 150},
        executive_summary="One finding materially affected.", what_changed="Net debt revised.",
        items=[
            reassessment.ReassessmentItemOutcome(
                index=0, finding_title="Term-sheet price gap", status="materially_changed",
                explanation="revised figure", evidence_of_change="new value cited",
            ),
            reassessment.ReassessmentItemOutcome(
                index=1, finding_title="Unmatched Finding Title", status="still_valid",
                explanation="n/a", evidence_of_change="No relevant change located",
            ),
        ],
    )


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


class ReassessmentCapabilityTests(unittest.TestCase):
    """Real HTTP-free, real-database, mocked-provider tests of the full
    mandate/capability/persistence pipeline."""

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
        version_dependencies.init_version_dependencies_db()
        reassessments.init_reassessments_db()
        mandates.init_mandates_db()

        self.project = store.create_project("Reassessment Capability Tests", "")
        self.other_project = store.create_project("Other Deal", "")
        self.pdf_doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF_BYTES).document
        self.old_version_id = self.pdf_doc.current_version_id
        self.xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-bytes"
        ).document
        self.analysis = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id, pdf_document_ids=[self.pdf_doc.id], pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[self.pdf_doc.sha256], excel_document_ids=[self.xlsx_doc.id],
            excel_document_filenames=["model.xlsx"], excel_document_checksums=[self.xlsx_doc.sha256],
            pdf_document_version_ids=[self.old_version_id], excel_document_version_ids=[self.xlsx_doc.current_version_id],
            status="success", transmitted=True, analysis_seconds=5.0, model="claude-opus-5", mandate_version="1",
            stop_reason="end_turn", input_tokens=1000, output_tokens=300, code_execution_requests=1,
            error_type=None, error_message=None, segments=[_text_segment(SAMPLE_FINDINGS_TEXT)], tool_trace=None,
            excel_cleanup=None, excel_verification=None,
        )
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        version_dependencies.record_dependency("workspace", self.workspace.id, "document", self.pdf_doc.id, self.old_version_id)
        self.worker = mandates.Worker()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)
        documents.DATA_DIR = self._original_data_dir
        self._tmpdir.cleanup()

    def _make_stale(self):
        result = documents.add_version(self.project.id, self.pdf_doc.id, PDF_BYTES + b"\nrevised\n")
        return result.document.current_version_id

    def _run_to_checkpoint(self, workspace_id=None):
        mandate = mandates.create_mandate(self.project.id, "Reassess after source change", created_by="lead-1")
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "reassessment",
            stage_inputs={"reassess": {"workspace_id": workspace_id or self.workspace.id}},
        )
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead-1")
        run = mandates.execute_run(self.project.id, mandate.id)
        with patch("mandates.reassessment.run_reassessment", return_value=_fake_outcome()):
            self.worker.poll_once()
        return mandates.get_mandate(self.project.id, mandate.id), mandates.get_run(mandate.id, run.id)

    def test_capability_and_template_registered(self):
        descriptor = mandates.get_capability("reassessment.compare_versions")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.side_effect_class, "external_paid_call")
        template = mandates.get_template("reassessment")
        self.assertIsNotNone(template)
        self.assertEqual(len(template.stages), 2)
        self.assertIn("reassessment", mandates._TEMPLATES_EXCLUDED_FROM_LLM_PLANNING)

    def test_propose_rejects_a_workspace_that_is_not_stale(self):
        mandate = mandates.create_mandate(self.project.id, "x", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "reassessment",
                stage_inputs={"reassess": {"workspace_id": self.workspace.id}},
            )

    def test_propose_rejects_unknown_workspace(self):
        self._make_stale()
        mandate = mandates.create_mandate(self.project.id, "x", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "reassessment", stage_inputs={"reassess": {"workspace_id": "nope"}},
            )

    def test_propose_rejects_workspace_from_another_project(self):
        self._make_stale()
        mandate = mandates.create_mandate(self.other_project.id, "x", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.other_project.id, mandate.id, "reassessment",
                stage_inputs={"reassess": {"workspace_id": self.workspace.id}},
            )

    def test_successful_run_persists_items_with_matched_and_unmatched_finding_ids(self):
        new_version_id = self._make_stale()
        mandate, run = self._run_to_checkpoint()
        self.assertEqual(run.status, "waiting_for_input")
        self.assertEqual(mandate.status, "active")

        reassessment_id = mandates.list_attempts(run.id)[0].output["reassessment_id"]
        record = reassessments.get_reassessment(self.project.id, reassessment_id)
        self.assertEqual(record.document_id, self.pdf_doc.id)
        self.assertEqual(record.old_version_id, self.old_version_id)
        self.assertEqual(record.new_version_id, new_version_id)
        self.assertEqual(record.mandate_id, mandate.id)
        self.assertEqual(record.run_id, run.id)

        items = reassessments.list_items(reassessment_id)
        self.assertEqual(len(items), 2)
        real_finding_id = workspaces.list_findings(self.workspace)[0]["id"]
        matched = next(i for i in items if i.finding_title == "Term-sheet price gap")
        unmatched = next(i for i in items if i.finding_title == "Unmatched Finding Title")
        self.assertEqual(matched.finding_id, real_finding_id)
        self.assertIsNone(unmatched.finding_id)

        # The underlying finding is completely untouched.
        finding = workspaces.get_finding(self.workspace, None, real_finding_id)
        self.assertEqual(finding["title"], "Term-sheet price gap")

        # Staleness is not cleared just because the run completed - only
        # acknowledging every item clears it (see server.py's handler /
        # the endpoint test file for that path).
        self.assertIsNotNone(version_dependencies.get_staleness("workspace", self.workspace.id))

    def test_failed_reassessment_leaves_no_record_and_fails_the_run(self):
        self._make_stale()
        mandate = mandates.create_mandate(self.project.id, "x", created_by="u1")
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "reassessment",
            stage_inputs={"reassess": {"workspace_id": self.workspace.id}},
        )
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="u1")
        run = mandates.execute_run(self.project.id, mandate.id)
        with patch("mandates.reassessment.run_reassessment", return_value=_fake_outcome(success=False)):
            self.worker.poll_once()
        updated = mandates.get_run(mandate.id, run.id)
        self.assertEqual(updated.status, "failed")
        self.assertEqual(reassessments.list_reassessments(self.project.id), [])

    def test_budget_exceeded_blocks_the_paid_call(self):
        self._make_stale()
        mandate = mandates.create_mandate(self.project.id, "x", created_by="u1")
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "reassessment",
            stage_inputs={"reassess": {"workspace_id": self.workspace.id}},
        )
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="u1")
        run = mandates.execute_run(self.project.id, mandate.id, budget_limit=0.5)
        with patch("mandates.reassessment.run_reassessment") as mock_run:
            self.worker.poll_once()
            mock_run.assert_not_called()
        updated = mandates.get_run(mandate.id, run.id)
        self.assertEqual(updated.status, "failed")


if __name__ == "__main__":
    unittest.main()
