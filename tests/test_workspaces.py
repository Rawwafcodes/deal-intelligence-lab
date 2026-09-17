"""Tests for workspaces.py: workspace creation/idempotency, finding
extraction/immutability, human review workflow, human-added findings,
duplicate lineage, information requests, the executive memo lifecycle,
the dashboard summary, and the audit trail. No Anthropic client is ever
used here - every analysis record is constructed directly with
cross_format_analyses.create_cross_format_analysis, exactly like the
existing validation-lab tests.
"""

import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import cross_format_analyses
import documents
import evaluations
import store
import workspaces


def _text_segment(text: str, pdf_citations=None) -> dict:
    return {"parts": [{"type": "text", "text": text}], "pdf_citations": pdf_citations or []}


def _finding_ids_by_title(workspace, analysis) -> dict:
    """Task 11.2: AI finding ids are minted UUIDs (`ai-<uuid>`), not
    `ai-<index>`, so tests look a finding up by its known (deterministic)
    title instead of assuming a literal id string."""
    return {f["title"]: f["id"] for f in workspaces.list_findings(workspace, analysis)}


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
    "- **Title:** No evidence located for churn assumption\n"
    "**Classification:** missing evidence\n"
    "**Severity:** medium\n"
    "**Explanation:** churn is assumed at 5% with no source.\n"
    "**PDF evidence:** No PDF evidence located\n"
    "**Workbook evidence:** No workbook evidence located\n"
    "**Commercial or financial relevance:** affects retention forecasts.\n"
    "**Uncertainty:** uncited\n"
    "**Recommended action:** request the churn analysis.\n\n"
    "- **Title:** Headcount figures agree across sources\n"
    "**Classification:** confirmed consistency\n"
    "**Severity:** low\n"
    "**Explanation:** headcount matches in both the IM and the model.\n"
    "**PDF evidence:** the IM lists 42 employees.\n"
    "**Workbook evidence:** the model lists 42 employees.\n"
    "**Commercial or financial relevance:** confirms opex basis.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended action:** none required.\n\n"
)


class WorkspaceTestBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        cls._original_data_dir = documents.DATA_DIR
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        store.init_db()
        documents.init_documents_db()
        cross_format_analyses.init_cross_format_analyses_db()
        workspaces.init_workspaces_db()

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    def setUp(self):
        self.project = store.create_project(f"Project {self.id()}", "workspace tests")
        self.pdf_doc = documents.save_uploaded_file(
            self.project.id, "im.pdf", "", f"%PDF-1.4\n%{self.id()}\n%%EOF".encode()
        ).document
        self.xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-bytes"
        ).document
        self.analysis = self._make_analysis()

    def _make_analysis(self, status="success", segments=None):
        if segments is None:
            segments = [_text_segment(SAMPLE_FINDINGS_TEXT)]
        return cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id,
            pdf_document_ids=[self.pdf_doc.id],
            pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[self.pdf_doc.sha256],
            excel_document_ids=[self.xlsx_doc.id],
            excel_document_filenames=["model.xlsx"],
            excel_document_checksums=[self.xlsx_doc.sha256],
            status=status,
            transmitted=True,
            analysis_seconds=12.5,
            model="claude-opus-5",
            mandate_version="1",
            stop_reason="end_turn",
            input_tokens=5000,
            output_tokens=1200,
            code_execution_requests=2,
            error_type=None,
            error_message=None,
            segments=segments if status == "success" else None,
            tool_trace=None,
            excel_cleanup=None,
            excel_verification=None,
        )


class WorkspaceCreationTests(WorkspaceTestBase):
    def test_creates_workspace_and_materializes_every_finding(self):
        workspace, created = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        self.assertTrue(created)
        self.assertEqual(workspace.cross_format_analysis_id, self.analysis.id)
        findings = workspaces.list_findings(workspace, self.analysis)
        self.assertEqual(len(findings), 4)
        self.assertEqual(
            {f["title"] for f in findings},
            {
                "Term-sheet price gap",
                "Unsupported growth rate",
                "No evidence located for churn assumption",
                "Headcount figures agree across sources",
            },
        )
        ids = {f["id"] for f in findings}
        self.assertEqual(len(ids), 4)  # every id distinct
        self.assertTrue(all(finding_id.startswith("ai-") for finding_id in ids))

    def test_reopening_is_idempotent_and_does_not_duplicate_findings(self):
        workspace1, created1 = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        workspace2, created2 = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        self.assertTrue(created1)
        self.assertFalse(created2)
        self.assertEqual(workspace1.id, workspace2.id)
        findings = workspaces.list_findings(workspace2, self.analysis)
        self.assertEqual(len(findings), 4)

    def test_extraction_loses_no_findings_across_a_larger_set(self):
        text = SAMPLE_FINDINGS_TEXT * 8  # 32 findings, mirrors the real 33-finding deal in shape
        analysis = self._make_analysis(segments=[_text_segment(text)])
        expected = len(evaluations.extract_findings(analysis.segments))
        workspace, _ = workspaces.get_or_create_workspace(self.project.id, analysis)
        findings = workspaces.list_findings(workspace, analysis)
        self.assertEqual(len(findings), expected)
        self.assertEqual(len({f["id"] for f in findings}), expected)  # every id unique

    def test_workspace_creation_logs_audit_event(self):
        workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        events = workspaces.list_audit_log(workspace.id)
        self.assertEqual(events[0].event_type, "workspace_created")
        self.assertEqual(events[0].detail["finding_count"], 4)


class ImmutableAiContentTests(WorkspaceTestBase):
    def setUp(self):
        super().setUp()
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        self.finding_id = _finding_ids_by_title(self.workspace, self.analysis)["Term-sheet price gap"]

    def test_ai_content_matches_extract_findings_exactly(self):
        expected = evaluations.extract_findings(self.analysis.segments)
        findings = workspaces.list_findings(self.workspace, self.analysis)
        by_title = {f["title"]: f for f in findings}
        for exp in expected:
            got = by_title[exp["title"]]
            self.assertEqual(got["title"], exp["title"])
            self.assertEqual(got["classification"], exp["classification"])
            self.assertEqual(got["severity"], exp["severity"])
            self.assertEqual(got["explanation"], exp["explanation"])
            self.assertEqual(got["pdf_evidence"], exp["pdf_evidence"])
            self.assertEqual(got["workbook_evidence"], exp["workbook_evidence"])

    def test_workflow_update_never_changes_ai_content_fields(self):
        before = workspaces.get_finding(self.workspace, self.analysis, self.finding_id)
        workspaces.update_finding_workflow(
            self.workspace.id, self.finding_id, {"review_status": "accepted", "adjusted_severity": "low"}
        )
        after = workspaces.get_finding(self.workspace, self.analysis, self.finding_id)
        self.assertEqual(before["title"], after["title"])
        self.assertEqual(before["severity"], after["severity"])  # original AI severity untouched
        self.assertEqual(after["adjusted_severity"], "low")
        self.assertEqual(after["effective_severity"], "low")  # adjusted overrides only the *effective* view


class HumanReviewWorkflowTests(WorkspaceTestBase):
    def setUp(self):
        super().setUp()
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        self.finding_id = _finding_ids_by_title(self.workspace, self.analysis)["Term-sheet price gap"]

    def test_updates_review_and_resolution_fields(self):
        updated = workspaces.update_finding_workflow(
            self.workspace.id,
            self.finding_id,
            {
                "review_status": "accepted",
                "resolution_status": "awaiting_information",
                "assigned_owner": "J. Rivera",
                "reviewer_notes": "Escalate to management",
                "due_date_text": "2026-09-30",
            },
        )
        self.assertEqual(updated["review_status"], "accepted")
        self.assertEqual(updated["resolution_status"], "awaiting_information")
        self.assertEqual(updated["assigned_owner"], "J. Rivera")

    def test_rejects_invalid_review_status(self):
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.update_finding_workflow(self.workspace.id, self.finding_id, {"review_status": "bogus"})

    def test_rejects_invalid_adjusted_severity(self):
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.update_finding_workflow(self.workspace.id, self.finding_id, {"adjusted_severity": "extreme"})

    def test_rejects_invalid_resolution_status(self):
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.update_finding_workflow(self.workspace.id, self.finding_id, {"resolution_status": "bogus"})

    def test_updating_unknown_finding_raises_value_error(self):
        with self.assertRaises(ValueError):
            workspaces.update_finding_workflow(self.workspace.id, "ai-999", {"review_status": "accepted"})

    def test_severity_change_and_assignment_are_audited(self):
        workspaces.update_finding_workflow(self.workspace.id, self.finding_id, {"adjusted_severity": "medium"})
        workspaces.update_finding_workflow(self.workspace.id, self.finding_id, {"assigned_owner": "A. Chen"})
        events = [e.event_type for e in workspaces.list_audit_log(self.workspace.id)]
        self.assertIn("severity_changed", events)
        self.assertIn("assignment", events)

    # -- revision conflicts (Task 11.5) ---------------------------------

    def test_a_fresh_finding_starts_at_revision_one(self):
        finding = workspaces.get_finding(self.workspace, self.analysis, self.finding_id)
        self.assertEqual(finding["revision"], 1)

    def test_matching_expected_revision_succeeds_and_increments(self):
        updated = workspaces.update_finding_workflow(
            self.workspace.id, self.finding_id, {"assigned_owner": "J. Rivera"}, expected_revision=1
        )
        self.assertEqual(updated["revision"], 2)

    def test_stale_expected_revision_raises_conflict_without_writing(self):
        workspaces.update_finding_workflow(self.workspace.id, self.finding_id, {"assigned_owner": "J. Rivera"})
        with self.assertRaises(workspaces.FindingRevisionConflictError) as ctx:
            workspaces.update_finding_workflow(
                self.workspace.id, self.finding_id, {"assigned_owner": "M. Chen"}, expected_revision=1
            )
        # The conflict carries the finding's real current state...
        self.assertEqual(ctx.exception.current["assigned_owner"], "J. Rivera")
        self.assertEqual(ctx.exception.current["revision"], 2)
        # ...and nothing was overwritten by the losing, stale-revision call.
        after = workspaces.get_finding(self.workspace, self.analysis, self.finding_id)
        self.assertEqual(after["assigned_owner"], "J. Rivera")

    def test_no_expected_revision_supplied_never_conflicts(self):
        workspaces.update_finding_workflow(self.workspace.id, self.finding_id, {"assigned_owner": "J. Rivera"})
        updated = workspaces.update_finding_workflow(
            self.workspace.id, self.finding_id, {"assigned_owner": "M. Chen"}
        )
        self.assertEqual(updated["assigned_owner"], "M. Chen")


class HumanAddedFindingTests(WorkspaceTestBase):
    def setUp(self):
        super().setUp()
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        self.finding_id = _finding_ids_by_title(self.workspace, self.analysis)["Term-sheet price gap"]

    def test_creates_human_finding_with_workflow_fields(self):
        created = workspaces.create_human_finding(
            self.workspace.id,
            {
                "title": "Undisclosed related-party lease",
                "severity": "high",
                "explanation": "Found in a side letter not covered by the reconciliation.",
                "evidence_notes": "See side letter dated 2026-01-01",
            },
        )
        self.assertTrue(created["id"].startswith("human-"))
        finding = workspaces.get_finding(self.workspace, self.analysis, created["id"])
        self.assertEqual(finding["origin"], "human")
        self.assertEqual(finding["title"], "Undisclosed related-party lease")
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(finding["review_status"], "unreviewed")  # same default workflow fields as AI findings

    def test_human_finding_never_labelled_as_ai(self):
        created = workspaces.create_human_finding(self.workspace.id, {"title": "Manual finding"})
        finding = workspaces.get_finding(self.workspace, self.analysis, created["id"])
        self.assertEqual(finding["origin"], "human")
        self.assertNotEqual(finding["origin"], "ai")

    def test_title_is_required(self):
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.create_human_finding(self.workspace.id, {"title": "   "})

    def test_invalid_severity_rejected(self):
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.create_human_finding(self.workspace.id, {"title": "X", "severity": "extreme"})

    def test_human_finding_is_editable_and_removable(self):
        created = workspaces.create_human_finding(self.workspace.id, {"title": "Temp finding"})
        workspaces.delete_human_finding(self.workspace.id, created["id"])
        self.assertIsNone(workspaces.get_finding(self.workspace, self.analysis, created["id"]))

    def test_ai_finding_cannot_be_deleted(self):
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.delete_human_finding(self.workspace.id, self.finding_id)

    def test_deleting_unknown_finding_raises_value_error(self):
        with self.assertRaises(ValueError):
            workspaces.delete_human_finding(self.workspace.id, "human-does-not-exist")

    def test_human_findings_counted_separately_in_summary(self):
        workspaces.create_human_finding(self.workspace.id, {"title": "Extra finding"})
        summary = workspaces.compute_summary(self.workspace, self.analysis, [])
        self.assertEqual(summary["by_origin"]["human"], 1)
        self.assertEqual(summary["by_origin"]["ai"], 4)
        self.assertEqual(summary["total_findings"], 5)


class DuplicateFindingTests(WorkspaceTestBase):
    def setUp(self):
        super().setUp()
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        by_title = _finding_ids_by_title(self.workspace, self.analysis)
        self.id0 = by_title["Term-sheet price gap"]
        self.id1 = by_title["Unsupported growth rate"]
        self.id2 = by_title["No evidence located for churn assumption"]

    def test_marks_and_preserves_lineage(self):
        updated = workspaces.set_duplicate(self.workspace.id, self.id1, self.id0, "M. Diaz")
        self.assertTrue(updated["is_duplicate"])
        self.assertEqual(updated["duplicate_of"], self.id0)
        self.assertEqual(updated["duplicate_marked_by"], "M. Diaz")
        self.assertIsNotNone(updated["duplicate_marked_at"])

        canonical = workspaces.get_finding(self.workspace, self.analysis, self.id0)
        self.assertIn(self.id1, canonical["duplicate_finding_ids"])
        duplicate = workspaces.get_finding(self.workspace, self.analysis, self.id1)
        self.assertNotIn(self.id1, duplicate.get("duplicate_finding_ids", []))  # a duplicate isn't its own canonical

    def test_both_findings_remain_after_marking_no_destructive_merge(self):
        workspaces.set_duplicate(self.workspace.id, self.id1, self.id0, "M. Diaz")
        findings = workspaces.list_findings(self.workspace, self.analysis)
        self.assertEqual(len(findings), 4)  # nothing deleted or combined

    def test_duplicates_excluded_from_headline_counts_by_default(self):
        workspaces.set_duplicate(self.workspace.id, self.id1, self.id0, "M. Diaz")
        summary = workspaces.compute_summary(self.workspace, self.analysis, [])
        self.assertEqual(summary["total_findings"], 3)
        self.assertEqual(summary["total_findings_including_duplicates"], 4)
        self.assertEqual(summary["duplicate_count"], 1)

    def test_cannot_duplicate_a_finding_into_itself(self):
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.set_duplicate(self.workspace.id, self.id0, self.id0, "M. Diaz")

    def test_cannot_chain_duplicates(self):
        workspaces.set_duplicate(self.workspace.id, self.id1, self.id0, "M. Diaz")
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.set_duplicate(self.workspace.id, self.id2, self.id1, "M. Diaz")

    def test_unmarking_clears_fields(self):
        workspaces.set_duplicate(self.workspace.id, self.id1, self.id0, "M. Diaz")
        updated = workspaces.set_duplicate(self.workspace.id, self.id1, None, "")
        self.assertFalse(updated["is_duplicate"])
        self.assertIsNone(updated["duplicate_of"])

    def test_duplicate_marking_is_audited(self):
        workspaces.set_duplicate(self.workspace.id, self.id1, self.id0, "M. Diaz")
        events = [e for e in workspaces.list_audit_log(self.workspace.id) if e.event_type == "duplicate_marking"]
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].detail["marked_by"], "M. Diaz")


class InformationRequestTests(WorkspaceTestBase):
    def setUp(self):
        super().setUp()
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        self.finding_id = _finding_ids_by_title(self.workspace, self.analysis)["Term-sheet price gap"]

    def test_creates_and_lists_requests(self):
        request = workspaces.create_request(
            self.workspace.id,
            {
                "question": "Please confirm the FY25 revenue figure.",
                "priority": "high",
                "related_finding_ids": [self.finding_id],
            },
        )
        self.assertEqual(request.status, "draft")
        self.assertEqual(workspaces.list_requests(self.workspace.id), [request])

    def test_standalone_question_allowed(self):
        request = workspaces.create_request(self.workspace.id, {"question": "What is the closing date?"})
        self.assertEqual(request.related_finding_ids, [])

    def test_question_required(self):
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.create_request(self.workspace.id, {"question": "   "})

    def test_invalid_priority_rejected(self):
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.create_request(self.workspace.id, {"question": "Q?", "priority": "urgent!"})

    def test_updates_status_and_response(self):
        request = workspaces.create_request(self.workspace.id, {"question": "Q?"})
        updated = workspaces.update_request(
            self.workspace.id, request.id, {"status": "answered", "management_response": "Confirmed at $12m."}
        )
        self.assertEqual(updated.status, "answered")
        self.assertEqual(updated.management_response, "Confirmed at $12m.")

    def test_invalid_status_rejected(self):
        request = workspaces.create_request(self.workspace.id, {"question": "Q?"})
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.update_request(self.workspace.id, request.id, {"status": "bogus"})

    def test_updating_unknown_request_raises_value_error(self):
        with self.assertRaises(ValueError):
            workspaces.update_request(self.workspace.id, "does-not-exist", {"status": "sent"})


class MemoLifecycleTests(WorkspaceTestBase):
    def setUp(self):
        super().setUp()
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        for finding in workspaces.list_findings(self.workspace, self.analysis):
            workspaces.update_finding_workflow(self.workspace.id, finding["id"], {"review_status": "accepted"})

    def test_generates_initial_draft_deterministically(self):
        memo = workspaces.get_or_create_memo(self.workspace, self.analysis)
        self.assertEqual(memo.status, "draft")
        self.assertEqual(memo.overall_recommendation, "no_conclusion")
        self.assertIn("Term-sheet price gap", memo.critical_issues)
        self.assertIn("Unsupported growth rate", memo.high_priority_issues)
        self.assertIn("Headcount figures agree", memo.confirmed_consistencies)
        self.assertIn("churn", memo.missing_information.lower())

    def test_regenerating_never_overwrites_edits(self):
        workspaces.get_or_create_memo(self.workspace, self.analysis)
        workspaces.update_memo(self.workspace.id, {"executive_conclusion": "Human-written conclusion."})
        memo_again = workspaces.get_or_create_memo(self.workspace, self.analysis)
        self.assertEqual(memo_again.executive_conclusion, "Human-written conclusion.")

    def test_edit_then_approve_then_edit_reverts_to_draft(self):
        workspaces.get_or_create_memo(self.workspace, self.analysis)
        workspaces.update_memo(self.workspace.id, {"executive_conclusion": "Draft text."})
        approved = workspaces.approve_memo(self.workspace.id, "V. Novak")
        self.assertEqual(approved.status, "approved")
        self.assertEqual(approved.approved_by, "V. Novak")
        self.assertIsNotNone(approved.approved_at)

        edited = workspaces.update_memo(self.workspace.id, {"executive_conclusion": "Changed after approval."})
        self.assertEqual(edited.status, "draft")
        self.assertIsNone(edited.approved_by)
        self.assertIsNone(edited.approved_at)

    def test_cannot_approve_twice(self):
        workspaces.get_or_create_memo(self.workspace, self.analysis)
        workspaces.approve_memo(self.workspace.id, "V. Novak")
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.approve_memo(self.workspace.id, "V. Novak")

    def test_invalid_recommendation_rejected(self):
        workspaces.get_or_create_memo(self.workspace, self.analysis)
        with self.assertRaises(workspaces.WorkspaceValidationError):
            workspaces.update_memo(self.workspace.id, {"overall_recommendation": "definitely proceed"})

    def test_never_auto_sets_a_decisive_recommendation(self):
        memo = workspaces.get_or_create_memo(self.workspace, self.analysis)
        self.assertEqual(memo.overall_recommendation, "no_conclusion")

    def test_approval_is_audited(self):
        workspaces.get_or_create_memo(self.workspace, self.analysis)
        workspaces.approve_memo(self.workspace.id, "V. Novak")
        events = [e for e in workspaces.list_audit_log(self.workspace.id) if e.event_type == "memo_approved"]
        self.assertEqual(len(events), 1)


class ProjectIsolationTests(WorkspaceTestBase):
    def test_workspace_not_found_under_wrong_project(self):
        workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        other_project = store.create_project("Other Project", "")
        self.assertIsNone(workspaces.get_workspace(other_project.id, workspace.id))

    def test_get_workspace_for_analysis_is_scoped_to_project(self):
        workspaces.get_or_create_workspace(self.project.id, self.analysis)
        other_project = store.create_project("Other Project", "")
        self.assertIsNone(workspaces.get_workspace_for_analysis(other_project.id, self.analysis.id))


class PersistenceTests(WorkspaceTestBase):
    def test_findings_and_workflow_state_persist_across_reconnect(self):
        workspace, _ = workspaces.get_or_create_workspace(self.project.id, self.analysis)
        finding_id = _finding_ids_by_title(workspace, self.analysis)["Term-sheet price gap"]
        workspaces.update_finding_workflow(
            workspace.id, finding_id, {"review_status": "accepted", "assigned_owner": "J. Rivera"}
        )
        workspaces.create_human_finding(workspace.id, {"title": "Persisted human finding"})

        # Simulate a server restart: every module call below opens a brand
        # new sqlite3 connection to the same DB_PATH file - nothing is held
        # in memory between calls already, but re-reading here is the
        # actual proof that what was written is what comes back.
        reloaded_workspace = workspaces.get_workspace(self.project.id, workspace.id)
        self.assertIsNotNone(reloaded_workspace)
        findings = workspaces.list_findings(reloaded_workspace, self.analysis)
        by_id = {f["id"]: f for f in findings}
        self.assertEqual(by_id[finding_id]["review_status"], "accepted")
        self.assertEqual(by_id[finding_id]["assigned_owner"], "J. Rivera")
        self.assertTrue(any(f["origin"] == "human" and f["title"] == "Persisted human finding" for f in findings))


if __name__ == "__main__":
    unittest.main()
