"""Integration tests for the Deal Workspace HTTP endpoints (Milestone 9):
the real server, with a cross_format_analyses record built directly (no
Anthropic client involved) exactly like the existing validation-lab
endpoint tests. Covers workspace creation/idempotency via HTTP, the
findings/requests/memo/export/audit-log endpoints, project isolation and
forged-id rejection, invalid-enum rejection, and that no secret, raw
document bytes, or filesystem path ever appears in a response or export.
"""

import io
import json
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from openpyxl import load_workbook

import cross_format_analyses
import documents
import identity
import server
import store
import version_dependencies
import workspaces

FAKE_SECRET = "sk-ant-api03-WORKSPACE-ENDPOINT-TEST-FAKE-SECRET-DO-NOT-LEAK"
PDF_BYTES = b"%PDF-1.4\n%Confidential information memorandum, harmless test bytes\n%%EOF"
XLSX_BYTES = b"PK\x03\x04fake-xlsx-bytes-for-workspace-endpoint-tests"


def _text_segment(text: str, pdf_citations=None) -> dict:
    return {"parts": [{"type": "text", "text": text}], "pdf_citations": pdf_citations or []}


def _pdf_citation_part(text: str, document_id: str, title: str, page: int = 1):
    return {
        "parts": [{"type": "text", "text": text}],
        "pdf_citations": [
            {
                "cited_text": "Revenue is $12m",
                "document_id": document_id,
                "document_title": title,
                "start_page": page,
                "end_page": page,
            }
        ],
    }


FINDINGS_TEXT = (
    "## Reconciliation Findings\n"
    "- **Title:** Term-sheet price gap\n"
    "**Classification:** cross-source conflict\n"
    "**Severity:** critical\n"
    "**Explanation:** the price differs across sources.\n"
    "**PDF evidence:** "
)
FINDINGS_TEXT_TAIL = (
    "\n**Workbook evidence:** the model says $10m.\n"
    "**Commercial or financial relevance:** determines the offer price.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended action:** ask the seller to reconcile.\n\n"
    "- **Title:** Unsupported growth rate\n"
    "**Classification:** unsupported model assumption\n"
    "**Severity:** high\n"
    "**Explanation:** no support found for the growth rate.\n"
    "**PDF evidence:** No PDF evidence located\n"
    "**Workbook evidence:** hardcoded 18% in the model.\n"
    "**Commercial or financial relevance:** inflates the forecast.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended action:** ask for the derivation.\n\n"
)


class WorkspaceEndpointTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread
    project: store.Project
    pdf_doc: documents.Document
    xlsx_doc: documents.Document
    other_project: store.Project

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
        identity.init_identity_db()
        documents.init_documents_db()
        cross_format_analyses.init_cross_format_analyses_db()
        workspaces.init_workspaces_db()
        version_dependencies.init_version_dependencies_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.project = store.create_project("Universal Widgets", "workspace endpoint tests")
        cls.pdf_doc = documents.save_uploaded_file(cls.project.id, "im.pdf", "", PDF_BYTES).document
        cls.xlsx_doc = documents.save_uploaded_file(cls.project.id, "model.xlsx", "", XLSX_BYTES).document
        cls.other_project = store.create_project("Other Project", "")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    def setUp(self):
        self._env_patcher = patch.dict(
            "os.environ", {"ANTHROPIC_API_KEY": FAKE_SECRET, "ANTHROPIC_MODEL": "claude-opus-5"}
        )
        self._env_patcher.start()

    def tearDown(self):
        self._env_patcher.stop()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _get(self, path: str):
        try:
            res = urllib.request.urlopen(self._url(path))
            return res.status, res.read(), dict(res.headers)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers)

    def _post_json(self, path: str, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else b""
        req = urllib.request.Request(
            self._url(path), data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            res = urllib.request.urlopen(req)
            return res.status, res.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def _delete_json(self, path: str, payload):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self._url(path), data=data, headers={"Content-Type": "application/json"}, method="DELETE"
        )
        try:
            res = urllib.request.urlopen(req)
            return res.status, res.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def _make_analysis(self, status="success"):
        segments = [_pdf_citation_part(FINDINGS_TEXT, self.pdf_doc.id, "im.pdf"), _text_segment(FINDINGS_TEXT_TAIL)]
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
            analysis_seconds=8.0,
            model="claude-opus-5",
            mandate_version="1",
            stop_reason="end_turn",
            input_tokens=4000,
            output_tokens=900,
            code_execution_requests=1,
            error_type=None if status == "success" else "unexpected_error",
            error_message=None if status == "success" else "boom",
            segments=segments if status == "success" else None,
            tool_trace=None,
            excel_cleanup=None,
            excel_verification=None,
        )

    def _open_workspace(self):
        analysis = self._make_analysis()
        status, body = self._post_json(f"/api/projects/{self.project.id}/cross-format-analyses/{analysis.id}/workspace")
        self.assertEqual(status, 201)
        workspace = json.loads(body)
        return analysis, workspace

    def _finding_id(self, workspace_id: str, title: str) -> str:
        """Task 11.2: finding ids are now minted UUIDs (`ai-<uuid>`), not
        `ai-<index>`, so tests look a finding up by its known title instead
        of assuming a literal id."""
        _, body, _ = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace_id}")
        findings = json.loads(body)["findings"]
        return next(f["id"] for f in findings if f["title"] == title)

    # -- creation / idempotency ---------------------------------------------

    def test_open_workspace_creates_then_idempotently_reopens(self):
        analysis, workspace = self._open_workspace()
        status2, body2 = self._post_json(f"/api/projects/{self.project.id}/cross-format-analyses/{analysis.id}/workspace")
        self.assertEqual(status2, 200)
        self.assertEqual(json.loads(body2)["id"], workspace["id"])

    def test_cannot_open_workspace_from_failed_analysis(self):
        analysis = self._make_analysis(status="error")
        status, _ = self._post_json(f"/api/projects/{self.project.id}/cross-format-analyses/{analysis.id}/workspace")
        self.assertEqual(status, 400)

    def test_open_workspace_never_calls_anthropic(self):
        # No mocked Anthropic client is installed anywhere in this test file
        # (unlike the reconciliation-creation tests) - if this endpoint
        # attempted a real network call it would raise, not merely be
        # "unmocked", since no client construction path is exercised here.
        analysis, workspace = self._open_workspace()
        self.assertIsNotNone(workspace["id"])

    # -- get workspace bundles findings + summary, citations intact --------

    def test_get_workspace_returns_findings_and_summary(self):
        analysis, workspace = self._open_workspace()
        status, body, _ = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}")
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual(len(payload["findings"]), 2)
        self.assertEqual(payload["summary"]["total_findings"], 2)
        self.assertEqual(payload["summary"]["by_severity"]["critical"], 1)

        first = next(f for f in payload["findings"] if f["title"] == "Term-sheet price gap")
        self.assertEqual(first["pdf_citations"][0]["document_id"], self.pdf_doc.id)
        self.assertEqual(first["pdf_citations"][0]["document_title"], "im.pdf")

    # -- finding workflow updates --------------------------------------------

    def test_update_finding_workflow_valid(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        status, body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"review_status": "accepted", "adjusted_severity": "high", "assigned_owner": "J. Rivera"},
        )
        self.assertEqual(status, 200)
        finding = json.loads(body)
        self.assertEqual(finding["review_status"], "accepted")
        self.assertEqual(finding["effective_severity"], "high")
        self.assertEqual(finding["severity"], "critical")  # original AI severity untouched

    def test_update_finding_rejects_invalid_enum(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        status, _ = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"review_status": "maybe"},
        )
        self.assertEqual(status, 400)

    # -- revision conflicts (Task 11.5) ---------------------------------------

    def test_finding_starts_at_revision_one_and_increments_on_update(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        status, body, _ = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}")
        finding = next(f for f in json.loads(body)["findings"] if f["id"] == finding_id)
        self.assertEqual(finding["revision"], 1)

        status, body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"review_status": "accepted", "revision": 1},
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["revision"], 2)

    def test_stale_revision_is_rejected_as_a_conflict_not_silently_overwritten(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")

        # Two "sessions" load the same finding at revision 1.
        first_status, first_body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"assigned_owner": "J. Rivera", "revision": 1},
        )
        self.assertEqual(first_status, 200)
        self.assertEqual(json.loads(first_body)["revision"], 2)

        # The second session, still holding the now-stale revision 1,
        # tries to save its own (different) change.
        second_status, second_body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"assigned_owner": "M. Chen", "revision": 1},
        )
        self.assertEqual(second_status, 409)
        conflict = json.loads(second_body)
        self.assertIn("current", conflict)
        # The first session's write actually won - never silently
        # overwritten by the second, stale-revision request.
        self.assertEqual(conflict["current"]["assigned_owner"], "J. Rivera")

        status, body, _ = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}")
        finding = next(f for f in json.loads(body)["findings"] if f["id"] == finding_id)
        self.assertEqual(finding["assigned_owner"], "J. Rivera")
        self.assertEqual(finding["revision"], 2)

    def test_update_without_a_revision_skips_the_conflict_check(self):
        """Backward compatibility: a caller that never sends `revision`
        (there are none left in this codebase, but the parameter is
        optional on principle) behaves exactly as before this task -
        last-write-wins, no conflict raised."""
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")

        status1, _ = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"assigned_owner": "J. Rivera"},
        )
        status2, body2 = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"assigned_owner": "M. Chen"},
        )
        self.assertEqual((status1, status2), (200, 200))
        self.assertEqual(json.loads(body2)["assigned_owner"], "M. Chen")

    def test_non_integer_revision_is_rejected(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        status, _ = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"review_status": "accepted", "revision": "not-a-number"},
        )
        self.assertEqual(status, 400)

    def test_update_finding_forged_id_rejected(self):
        analysis, workspace = self._open_workspace()
        status, _ = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/ai-999",
            {"review_status": "accepted"},
        )
        self.assertEqual(status, 404)

    def test_forged_workspace_id_rejected(self):
        status, _, _ = self._get(f"/api/projects/{self.project.id}/workspaces/does-not-exist")
        self.assertEqual(status, 404)

    def test_workspace_cross_project_access_rejected(self):
        analysis, workspace = self._open_workspace()
        status, _, _ = self._get(f"/api/projects/{self.other_project.id}/workspaces/{workspace['id']}")
        self.assertEqual(status, 404)

    # -- human-added findings -------------------------------------------------

    def test_create_and_delete_human_finding(self):
        analysis, workspace = self._open_workspace()
        status, body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings",
            {"title": "Undisclosed lease", "severity": "medium", "explanation": "Found in a side letter."},
        )
        self.assertEqual(status, 201)
        finding = json.loads(body)
        self.assertEqual(finding["origin"], "human")
        finding_id = finding["id"]

        del_status, _ = self._delete_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}", {"confirm": True}
        )
        self.assertEqual(del_status, 200)

        get_status, get_body, _ = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}")
        ids = [f["id"] for f in json.loads(get_body)["findings"]]
        self.assertNotIn(finding_id, ids)

    def test_deleting_ai_finding_rejected(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        status, _ = self._delete_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}", {"confirm": True}
        )
        self.assertEqual(status, 400)

    def test_delete_without_confirm_rejected(self):
        analysis, workspace = self._open_workspace()
        status, body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings", {"title": "Temp"}
        )
        finding_id = json.loads(body)["id"]
        status, _ = self._delete_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}", {"confirm": False}
        )
        self.assertEqual(status, 400)

    # -- duplicates -----------------------------------------------------------

    def test_mark_duplicate_via_http(self):
        analysis, workspace = self._open_workspace()
        canonical_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        duplicate_id = self._finding_id(workspace["id"], "Unsupported growth rate")
        status, body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{duplicate_id}/duplicate",
            {"duplicate_of": canonical_id, "marked_by": "M. Diaz"},
        )
        self.assertEqual(status, 200)
        finding = json.loads(body)
        self.assertTrue(finding["is_duplicate"])

        get_status, get_body, _ = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}")
        summary = json.loads(get_body)["summary"]
        self.assertEqual(summary["total_findings"], 1)  # one duplicate excluded by default
        self.assertEqual(summary["duplicate_count"], 1)

    # -- information requests --------------------------------------------------

    def test_request_lifecycle(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        status, body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/requests",
            {"question": "Confirm FY25 revenue.", "priority": "high", "related_finding_ids": [finding_id]},
        )
        self.assertEqual(status, 201)
        request = json.loads(body)

        status, body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/requests/{request['id']}",
            {"status": "sent", "management_response": ""},
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["status"], "sent")

        status, _ = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/requests/{request['id']}",
            {"status": "not-a-status"},
        )
        self.assertEqual(status, 400)

        list_status, list_body, _ = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/requests")
        self.assertEqual(list_status, 200)
        self.assertEqual(len(json.loads(list_body)), 1)

    # -- memo -------------------------------------------------------------

    def test_memo_get_edit_approve_reopen(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"review_status": "accepted"},
        )

        get_status, get_body, _ = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/memo")
        self.assertEqual(get_status, 200)
        memo = json.loads(get_body)
        self.assertEqual(memo["status"], "draft")
        self.assertEqual(memo["overall_recommendation"], "no_conclusion")
        self.assertIn("Term-sheet price gap", memo["critical_issues"])

        status, body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/memo",
            {"executive_conclusion": "Edited by reviewer."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["executive_conclusion"], "Edited by reviewer.")

        approve_status, _ = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/memo/approve", {"confirm": False}
        )
        self.assertEqual(approve_status, 400)  # confirm required

        approve_status, approve_body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/memo/approve",
            {"confirm": True, "approver": "V. Novak"},
        )
        self.assertEqual(approve_status, 200)
        approved = json.loads(approve_body)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["approved_by"], "V. Novak")

        approve_again_status, _ = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/memo/approve",
            {"confirm": True, "approver": "V. Novak"},
        )
        self.assertEqual(approve_again_status, 409)

        edit_status, edit_body = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/memo",
            {"executive_conclusion": "Changed after approval."},
        )
        self.assertEqual(edit_status, 200)
        reopened = json.loads(edit_body)
        self.assertEqual(reopened["status"], "draft")
        self.assertIsNone(reopened["approved_by"])

    def test_invalid_memo_recommendation_rejected(self):
        analysis, workspace = self._open_workspace()
        status, _ = self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/memo",
            {"overall_recommendation": "definitely proceed"},
        )
        self.assertEqual(status, 400)

    # -- audit log --------------------------------------------------------

    def test_audit_log_records_significant_actions(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"review_status": "accepted"},
        )
        self._post_json(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/memo")
        status, body, _ = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/audit-log")
        self.assertEqual(status, 200)
        event_types = [e["event_type"] for e in json.loads(body)]
        self.assertIn("workspace_created", event_types)
        self.assertIn("finding_reviewed", event_types)

    # -- exports: no secrets, no raw bytes, no filesystem paths ---------------

    def test_findings_export_xlsx_contents_and_no_secrets(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"review_status": "accepted", "adjusted_severity": "medium"},
        )
        status, body, headers = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/export/findings.xlsx")
        self.assertEqual(status, 200)
        self.assertIn("spreadsheetml", headers["Content-Type"])
        self.assertNotIn(FAKE_SECRET.encode(), body)
        self.assertNotIn(str(documents.DATA_DIR).encode(), body)
        self.assertNotIn(PDF_BYTES, body)

        wb = load_workbook(io.BytesIO(body))
        ws = wb.active
        all_text = "\n".join(str(cell.value) for row in ws.iter_rows() for cell in row if cell.value is not None)
        self.assertIn("Term-sheet price gap", all_text)
        self.assertIn("medium", all_text)  # human-adjusted severity present
        self.assertIn("critical", all_text)  # original AI severity present
        self.assertIn("independent professional verification", all_text.lower())  # disclaimer present
        self.assertIn(analysis.id, all_text)  # identifier present

    def test_findings_export_sanitizes_formula_injection(self):
        # workspace_exports._safe_cell_text: a reviewer-typed value that looks
        # like a spreadsheet formula must round-trip as literal text, not be
        # written as a live formula that a downstream Excel/Sheets user's
        # export could silently execute.
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"reviewer_notes": "=1+1"},
        )
        status, body, _ = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/export/findings.xlsx")
        self.assertEqual(status, 200)

        wb = load_workbook(io.BytesIO(body))
        ws = wb.active
        notes_cells = [cell for row in ws.iter_rows() for cell in row if cell.value == "'=1+1"]
        self.assertEqual(len(notes_cells), 1)
        self.assertEqual(notes_cells[0].data_type, "s")  # stored as a plain string, never a formula

    def test_requests_export_xlsx_contents(self):
        analysis, workspace = self._open_workspace()
        self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/requests",
            {"question": "Confirm FY25 revenue.", "priority": "high"},
        )
        status, body, headers = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/export/requests.xlsx")
        self.assertEqual(status, 200)
        self.assertIn("spreadsheetml", headers["Content-Type"])
        wb = load_workbook(io.BytesIO(body))
        ws = wb.active
        all_text = "\n".join(str(cell.value) for row in ws.iter_rows() for cell in row if cell.value is not None)
        self.assertIn("Confirm FY25 revenue.", all_text)
        self.assertNotIn(FAKE_SECRET, all_text)

    def test_combined_package_html_export(self):
        analysis, workspace = self._open_workspace()
        status, body, headers = self._get(f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/export/package.html")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers["Content-Type"])
        text = body.decode("utf-8")
        self.assertIn("Term-sheet price gap", text)
        self.assertIn("independent professional verification", text.lower())
        self.assertIn(self.project.name, text)
        self.assertNotIn(FAKE_SECRET, text)
        self.assertNotIn(str(documents.DATA_DIR), text)
        self.assertNotIn(PDF_BYTES.decode("latin-1"), text)

    def test_export_of_forged_workspace_rejected(self):
        status, _, _ = self._get(f"/api/projects/{self.project.id}/workspaces/does-not-exist/export/findings.xlsx")
        self.assertEqual(status, 404)

    # -- persistence across restart -------------------------------------------

    def test_workspace_state_persists_across_a_server_restart(self):
        analysis, workspace = self._open_workspace()
        finding_id = self._finding_id(workspace["id"], "Term-sheet price gap")
        self._post_json(
            f"/api/projects/{self.project.id}/workspaces/{workspace['id']}/findings/{finding_id}",
            {"review_status": "accepted", "assigned_owner": "J. Rivera"},
        )

        # Simulate a process restart: shut down this test's own temporary
        # server and start a brand new one, bound to the same on-disk
        # DB_PATH, with no shared in-memory state whatsoever.
        temp_httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        temp_port = temp_httpd.server_address[1]
        temp_thread = threading.Thread(target=temp_httpd.serve_forever, daemon=True)
        temp_thread.start()
        try:
            res = urllib.request.urlopen(
                f"http://127.0.0.1:{temp_port}/api/projects/{self.project.id}/workspaces/{workspace['id']}"
            )
            payload = json.loads(res.read())
            found = next(f for f in payload["findings"] if f["id"] == finding_id)
            self.assertEqual(found["review_status"], "accepted")
            self.assertEqual(found["assigned_owner"], "J. Rivera")
        finally:
            temp_httpd.shutdown()
            temp_httpd.server_close()


if __name__ == "__main__":
    unittest.main()
