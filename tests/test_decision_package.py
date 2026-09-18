"""Tests for Task 14.3's decision-package drafting: the pure adapter
(decision_package.py), its persistence (deliverables.py), and the
`decision_package.produce_draft` mandate capability/template
(mandates.py). No real network call anywhere in this module - every
provider call is mocked, mirroring tests/test_integrity_review.py's own
convention exactly.
"""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import cross_format_analyses
import decision_package
import deliverables
import documents
import mandates
import store
import version_dependencies
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
    "- **Title:** Unsupported growth rate\n"
    "**Classification:** unsupported model assumption\n"
    "**Severity:** high\n"
    "**Explanation:** no support found for the 18% growth rate.\n"
    "**PDF evidence:** No PDF evidence located\n"
    "**Workbook evidence:** hardcoded 18% in the model.\n"
    "**Commercial or financial relevance:** inflates the forecast.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended action:** ask for the derivation.\n\n"
)

DRAFT_TEXT = (
    "## Executive Summary\n"
    "Two findings on record; one is critical and unresolved.\n\n"
    "## Recommendation\n"
    "Draft only, for the deal lead to adopt, amend, or reject: proceed "
    "subject to resolving the price gap.\n\n"
    "## Key Evidence And Findings\n"
    "- Term-sheet price gap: a critical cross-source conflict.\n\n"
    "## Outstanding And Unresolved Matters\n"
    "- Term-sheet price gap remains open.\n\n"
    "## Risks And Limitations\n"
    "- Unsupported growth rate is not yet reviewed.\n"
)


def _fake_outcome(success=True, error_type=None, error_message=None):
    if not success:
        return decision_package.DecisionPackageOutcome(
            success=False, transmitted=True, analysis_seconds=1.2, model="claude-opus-5",
            error_type=error_type, error_message=error_message,
        )
    return decision_package.DecisionPackageOutcome(
        success=True, transmitted=True, analysis_seconds=1.2, model="claude-opus-5", stop_reason="end_turn",
        usage={"input_tokens": 800, "output_tokens": 250},
        executive_summary="Two findings on record; one is critical and unresolved.",
        recommendation="Draft only, for the deal lead to adopt, amend, or reject: proceed subject to resolving the price gap.",
        key_evidence_and_findings="- Term-sheet price gap: a critical cross-source conflict.",
        outstanding_and_unresolved_matters="- Term-sheet price gap remains open.",
        risks_and_limitations="- Unsupported growth rate is not yet reviewed.",
    )


class ParseSectionsTests(unittest.TestCase):
    """Module-level, no database: the plain heading-split parser."""

    def test_parses_all_five_sections(self):
        sections = decision_package._parse_sections(DRAFT_TEXT)
        self.assertIn("critical and unresolved", sections["executive_summary"])
        self.assertIn("deal lead to adopt", sections["recommendation"])
        self.assertIn("Term-sheet price gap", sections["key_evidence_and_findings"])
        self.assertIn("remains open", sections["outstanding_and_unresolved_matters"])
        self.assertIn("not yet reviewed", sections["risks_and_limitations"])

    def test_missing_sections_are_simply_absent(self):
        sections = decision_package._parse_sections("## Executive Summary\nOnly this one.\n")
        self.assertEqual(sections, {"executive_summary": "Only this one."})

    def test_no_headings_returns_empty_dict(self):
        self.assertEqual(decision_package._parse_sections("plain text, no headings"), {})


class ValidateSelectionTests(unittest.TestCase):
    """Module-level, no database: the digest/validate_selection gate."""

    def _finding(self, review_status="unreviewed"):
        return {
            "id": uuid.uuid4().hex, "title": "x", "classification": "cross-source conflict",
            "effective_severity": "high", "review_status": review_status, "resolution_status": "open",
            "recommended_action": "", "commercial_relevance": "", "uncertainty": "",
        }

    def test_no_findings_rejected(self):
        digest = decision_package.build_digest("ws", [], [])
        error = decision_package.validate_selection(digest)
        self.assertEqual(error[0], "no_findings")

    def test_all_unreviewed_rejected(self):
        digest = decision_package.build_digest("ws", [self._finding(), self._finding()], [])
        error = decision_package.validate_selection(digest)
        self.assertEqual(error[0], "no_reviewed_findings")

    def test_one_reviewed_finding_passes(self):
        digest = decision_package.build_digest("ws", [self._finding(), self._finding(review_status="accepted")], [])
        self.assertIsNone(decision_package.validate_selection(digest))


class DecisionPackageCapabilityTests(unittest.TestCase):
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
        deliverables.init_deliverables_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()

        self.project = store.create_project("Decision Package Tests", "")
        self.other_project = store.create_project("Other Deal", "")
        self.pdf_doc = documents.save_uploaded_file(
            self.project.id, "im.pdf", "", b"%PDF-1.4\n%x\n%%EOF"
        ).document
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

    def _mark_one_finding_reviewed(self):
        finding = workspaces.list_findings(self.workspace)[0]
        workspaces.update_finding_workflow(self.workspace.id, finding["id"], {"review_status": "accepted"})

    def _run_to_checkpoint(self, workspace_id=None, emphasis=""):
        mandate = mandates.create_mandate(self.project.id, "Prepare a decision package", created_by="lead-1")
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "decision-package",
            stage_inputs={"draft": {"workspace_id": workspace_id or self.workspace.id, "emphasis": emphasis}},
        )
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="lead-1")
        run = mandates.execute_run(self.project.id, mandate.id)
        self.worker.poll_once()
        return mandates.get_mandate(self.project.id, mandate.id), mandates.get_run(mandate.id, run.id)

    def test_capability_and_template_registered(self):
        descriptor = mandates.get_capability("decision_package.produce_draft")
        self.assertIsNotNone(descriptor)
        self.assertEqual(descriptor.side_effect_class, "external_paid_call")
        template = mandates.get_template("decision-package")
        self.assertIsNotNone(template)
        self.assertIn("decision-package", mandates._TEMPLATES_EXCLUDED_FROM_LLM_PLANNING)

    def test_propose_rejects_unknown_workspace(self):
        mandate = mandates.create_mandate(self.project.id, "x", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "decision-package",
                stage_inputs={"draft": {"workspace_id": "does-not-exist"}},
            )

    def test_propose_rejects_workspace_from_another_project(self):
        mandate = mandates.create_mandate(self.other_project.id, "x", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.other_project.id, mandate.id, "decision-package",
                stage_inputs={"draft": {"workspace_id": self.workspace.id}},
            )

    def test_propose_rejects_workspace_with_no_reviewed_findings(self):
        mandate = mandates.create_mandate(self.project.id, "x", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(
                self.project.id, mandate.id, "decision-package",
                stage_inputs={"draft": {"workspace_id": self.workspace.id}},
            )

    def test_propose_missing_workspace_id_rejected_by_schema(self):
        mandate = mandates.create_mandate(self.project.id, "x", created_by="u1")
        with self.assertRaises(mandates.PlanValidationError):
            mandates.propose_plan(self.project.id, mandate.id, "decision-package", stage_inputs={"draft": {}})

    def test_successful_draft_persists_deliverable_version_and_pauses_at_checkpoint(self):
        self._mark_one_finding_reviewed()
        with patch("mandates.decision_package.run_decision_package_draft", return_value=_fake_outcome()):
            mandate, run = self._run_to_checkpoint(emphasis="focus on price")
        self.assertEqual(run.status, "waiting_for_input")
        self.assertEqual(mandate.status, "active")

        versions = deliverables.list_deliverable_versions(self.workspace.id)
        self.assertEqual(len(versions), 1)
        version = versions[0]
        self.assertEqual(version.status, "draft")
        self.assertEqual(version.version_number, 1)
        self.assertEqual(version.emphasis, "focus on price")
        self.assertIn("critical and unresolved", version.executive_summary)
        self.assertEqual(version.mandate_id, mandate.id)
        self.assertEqual(version.run_id, run.id)
        self.assertIsNotNone(version.attempt_id)

        attempts = mandates.list_attempts(run.id)
        draft_attempt = next(a for a in attempts if a.stage_id == "draft")
        self.assertEqual(draft_attempt.status, "succeeded")
        self.assertEqual(draft_attempt.output["deliverable_id"], version.id)
        self.assertEqual(draft_attempt.output["version"], 1)

    def test_failed_draft_leaves_no_deliverable_and_fails_the_run(self):
        self._mark_one_finding_reviewed()
        with patch(
            "mandates.decision_package.run_decision_package_draft",
            return_value=_fake_outcome(success=False, error_type="rate_limit", error_message="slow down"),
        ):
            mandate, run = self._run_to_checkpoint()
        self.assertEqual(run.status, "failed")
        self.assertEqual(mandate.status, "failed")
        self.assertEqual(deliverables.list_deliverable_versions(self.workspace.id), [])

    def test_budget_exceeded_blocks_the_paid_call(self):
        self._mark_one_finding_reviewed()
        mandate = mandates.create_mandate(self.project.id, "x", created_by="u1")
        plan = mandates.propose_plan(
            self.project.id, mandate.id, "decision-package",
            stage_inputs={"draft": {"workspace_id": self.workspace.id}},
        )
        mandates.approve_plan(self.project.id, mandate.id, plan.id, approved_by="u1")
        run = mandates.execute_run(self.project.id, mandate.id, budget_limit=0.5)
        with patch("mandates.decision_package.run_decision_package_draft") as mock_run:
            self.worker.poll_once()
            mock_run.assert_not_called()
        updated = mandates.get_run(mandate.id, run.id)
        self.assertEqual(updated.status, "failed")
        self.assertEqual(deliverables.list_deliverable_versions(self.workspace.id), [])

class DeliverableApprovalTests(unittest.TestCase):
    """Version-specific approval semantics (deliverables.py), mirroring
    reviews.py's own is_current_version_approved test shape."""

    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        deliverables.init_deliverables_db()
        self.project = store.create_project("Deliverable Approval Tests", "")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    def _create(self, workspace_id="ws-1"):
        return deliverables.create_deliverable_version(
            project_id=self.project.id, workspace_id=workspace_id, mandate_id=None, run_id=None, attempt_id=None,
            title="Decision package", executive_summary="es", recommendation="rec",
            key_evidence_and_findings="kf", outstanding_and_unresolved_matters="om",
            risks_and_limitations="rl", emphasis="", source_finding_ids=[], source_request_ids=[],
            model="claude-opus-5", draft_template_version="1", input_tokens=100, output_tokens=50,
        )

    def test_versions_increment_per_workspace(self):
        v1 = self._create()
        v2 = self._create()
        self.assertEqual(v1.version_number, 1)
        self.assertEqual(v2.version_number, 2)

    def test_approve_succeeds_on_latest_version(self):
        v1 = self._create()
        approved = deliverables.approve_deliverable_version(v1.workspace_id, v1.id, "lead-1")
        self.assertEqual(approved.status, "approved")
        self.assertEqual(approved.approved_by, "lead-1")
        self.assertTrue(deliverables.is_current_version_approved(v1.workspace_id, v1.id))

    def test_cannot_approve_a_superseded_version(self):
        v1 = self._create()
        v2 = self._create(workspace_id=v1.workspace_id)
        with self.assertRaises(deliverables.DeliverableValidationError):
            deliverables.approve_deliverable_version(v1.workspace_id, v1.id, "lead-1")
        # v2 remains approvable
        approved = deliverables.approve_deliverable_version(v2.workspace_id, v2.id, "lead-1")
        self.assertEqual(approved.status, "approved")

    def test_cannot_approve_twice(self):
        v1 = self._create()
        deliverables.approve_deliverable_version(v1.workspace_id, v1.id, "lead-1")
        with self.assertRaises(deliverables.DeliverableValidationError):
            deliverables.approve_deliverable_version(v1.workspace_id, v1.id, "lead-1")

    def test_a_newer_unapproved_draft_makes_older_approved_version_report_false(self):
        v1 = self._create()
        deliverables.approve_deliverable_version(v1.workspace_id, v1.id, "lead-1")
        self._create(workspace_id=v1.workspace_id)  # v2, unreviewed
        self.assertFalse(deliverables.is_current_version_approved(v1.workspace_id, v1.id))


if __name__ == "__main__":
    unittest.main()
