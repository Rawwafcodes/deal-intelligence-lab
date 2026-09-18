"""Integration tests for Task 14.3's real HTTP surface: the decision-
package capability's mandate lifecycle end to end, the new `GET/POST
.../workspaces/<id>/deliverables[/<id>[/approve]]` routes, and role
enforcement on approval. Same no-real-network-call convention as every
other mandate-capability endpoint test class - `decision_package.
run_decision_package_draft` is mocked; the point of this class is the
HTTP/authorization contract, not re-proving the adapter logic already
covered at the module level in tests/test_decision_package.py.
"""

import json
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_identity_endpoints import _Client

import cross_format_analyses
import decision_package
import deliverables
import documents
import identity
import mandates
import server
import store
import version_dependencies
import workspaces

_TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled", "outcome_unknown", "waiting_for_input"}


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


def _fake_outcome():
    return decision_package.DecisionPackageOutcome(
        success=True, transmitted=True, analysis_seconds=1.1, model="claude-opus-5", stop_reason="end_turn",
        usage={"input_tokens": 600, "output_tokens": 180},
        executive_summary="One critical finding remains open.",
        recommendation="Draft only: proceed subject to closing the price gap.",
        key_evidence_and_findings="- Term-sheet price gap: critical, accepted.",
        outstanding_and_unresolved_matters="- Term-sheet price gap remains open.",
        risks_and_limitations="- None beyond the open item above.",
    )


class DecisionPackageEndpointTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread
    worker: "mandates.Worker"

    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()
        documents.init_documents_db()
        cross_format_analyses.init_cross_format_analyses_db()
        workspaces.init_workspaces_db()
        deliverables.init_deliverables_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        cls.worker = mandates.Worker(poll_interval=0.02)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.worker.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    def setUp(self):
        self.project = store.create_project("Decision Package Endpoint Tests", "")
        self.other_project = store.create_project("Other Deal", "")
        self.pdf_doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", b"%PDF-1.4\n%x\n%%EOF").document
        self.xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-bytes"
        ).document
        analysis = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id,
            pdf_document_ids=[self.pdf_doc.id], pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[self.pdf_doc.sha256],
            excel_document_ids=[self.xlsx_doc.id], excel_document_filenames=["model.xlsx"],
            excel_document_checksums=[self.xlsx_doc.sha256],
            status="success", transmitted=True, analysis_seconds=5.0, model="claude-opus-5", mandate_version="1",
            stop_reason="end_turn", input_tokens=1000, output_tokens=300, code_execution_requests=1,
            error_type=None, error_message=None, segments=[_text_segment(SAMPLE_FINDINGS_TEXT)],
            tool_trace=None, excel_cleanup=None, excel_verification=None,
        )
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, analysis)
        finding = workspaces.list_findings(self.workspace)[0]
        workspaces.update_finding_workflow(self.workspace.id, finding["id"], {"review_status": "accepted"})

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _get(self, path: str):
        try:
            res = urllib.request.urlopen(self._url(path))
            return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null")

    def _post(self, path: str, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else b""
        req = urllib.request.Request(
            self._url(path), data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            res = urllib.request.urlopen(req)
            return res.status, json.loads(res.read() or b"null")
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"null")

    def _mandates_url(self, suffix: str = "") -> str:
        return f"/api/projects/{self.project.id}/mandates{suffix}"

    def _wait_for_terminal_run(self, mandate_id: str, run_id: str, timeout: float = 2.0) -> dict:
        deadline = time.monotonic() + timeout
        status, run = self._get(self._mandates_url(f"/{mandate_id}/runs/{run_id}"))
        while run.get("status") not in _TERMINAL_RUN_STATUSES and time.monotonic() < deadline:
            time.sleep(0.02)
            status, run = self._get(self._mandates_url(f"/{mandate_id}/runs/{run_id}"))
        self.assertIn(run.get("status"), _TERMINAL_RUN_STATUSES, f"run stuck at {run.get('status')!r}")
        return run

    def _run_to_waiting_checkpoint(self, workspace_id=None):
        """Proposes, approves, and executes a decision-package mandate
        (mocked provider call) through to its human_checkpoint pause;
        returns (mandate_id, deliverable_id, run_id)."""
        _, mandate = self._post(self._mandates_url(), {"objective": "Prepare a decision package"})
        mandate_id = mandate["id"]
        status, plan = self._post(
            self._mandates_url(f"/{mandate_id}/plan"),
            {
                "template_key": "decision-package",
                "stage_inputs": {"draft": {"workspace_id": workspace_id or self.workspace.id}},
            },
        )
        self.assertEqual(status, 201)
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})

        with patch("mandates.decision_package.run_decision_package_draft", return_value=_fake_outcome()):
            status, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))
            self.assertEqual(status, 202)
            final = self._wait_for_terminal_run(mandate_id, run["id"])

        self.assertEqual(final["status"], "waiting_for_input")
        deliverable_id = final["attempts"][0]["output"]["deliverable_id"]
        return mandate_id, deliverable_id, run["id"]

    # -- template listing and propose contract -------------------------------

    def test_list_templates_includes_decision_package(self):
        status, templates = self._get("/api/mandate-templates")
        keys = {t["key"] for t in templates}
        self.assertIn("decision-package", keys)

    def test_propose_decision_package_plan_requires_workspace_id(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Prepare a package"})
        status, _ = self._post(
            self._mandates_url(f"/{mandate['id']}/plan"),
            {"template_key": "decision-package", "stage_inputs": {"draft": {}}},
        )
        self.assertEqual(status, 400)

    def test_propose_rejects_workspace_with_no_reviewed_findings(self):
        # A second, unreviewed workspace on the same project.
        pdf2 = documents.save_uploaded_file(self.project.id, "im2.pdf", "", b"%PDF-1.4\n%y\n%%EOF").document
        xlsx2 = documents.save_uploaded_file(self.project.id, "model2.xlsx", "", b"PK\x03\x04more-bytes").document
        analysis2 = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id, pdf_document_ids=[pdf2.id], pdf_document_filenames=["im2.pdf"],
            pdf_document_checksums=[pdf2.sha256], excel_document_ids=[xlsx2.id],
            excel_document_filenames=["model2.xlsx"], excel_document_checksums=[xlsx2.sha256], status="success",
            transmitted=True, analysis_seconds=5.0, model="claude-opus-5", mandate_version="1", stop_reason="end_turn",
            input_tokens=100, output_tokens=50, code_execution_requests=0, error_type=None, error_message=None,
            segments=[_text_segment(SAMPLE_FINDINGS_TEXT)], tool_trace=None, excel_cleanup=None,
            excel_verification=None,
        )
        unreviewed_workspace, _ = workspaces.get_or_create_workspace(self.project.id, analysis2)

        _, mandate = self._post(self._mandates_url(), {"objective": "Prepare a package"})
        status, _ = self._post(
            self._mandates_url(f"/{mandate['id']}/plan"),
            {"template_key": "decision-package", "stage_inputs": {"draft": {"workspace_id": unreviewed_workspace.id}}},
        )
        self.assertEqual(status, 400)

    # -- full lifecycle over HTTP --------------------------------------------

    def test_full_decision_package_lifecycle_over_http(self):
        mandate_id, deliverable_id, run_id = self._run_to_waiting_checkpoint()

        status, listed = self._get(f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/deliverables")
        self.assertEqual(status, 200)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], deliverable_id)
        self.assertEqual(listed[0]["status"], "draft")

        status, deliverable = self._get(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/deliverables/{deliverable_id}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(deliverable["executive_summary"], "One critical finding remains open.")
        self.assertEqual(deliverable["mandate_id"], mandate_id)
        self.assertEqual(deliverable["run_id"], run_id)
        self.assertEqual(deliverable["version_number"], 1)

        lead = identity.create_user(f"lead-{uuid.uuid4().hex}@example.com", "Deal Lead")
        identity.add_deal_membership(self.project.id, lead.id, "deal_lead")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": lead.id})

        status, approved = client.post(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/deliverables/{deliverable_id}/approve",
            {"confirm": True},
        )
        self.assertEqual(status, 200)
        self.assertEqual(approved["status"], "approved")
        self.assertEqual(approved["approved_by"], lead.id)

        # Resuming the mandate's own human_checkpoint is a separate,
        # generic action from approving the deliverable itself - reuses
        # the same GET .../runs/<id>/resume mechanism every other
        # human_checkpoint template already exercises.
        status, _ = self._post(
            self._mandates_url(f"/{mandate_id}/runs/{run_id}/resume"),
            {"stage_id": "checkpoint", "decision": "reviewed"},
        )
        self.assertEqual(status, 200)
        final = self._wait_for_terminal_run(mandate_id, run_id)
        self.assertEqual(final["status"], "succeeded")

    # -- role enforcement -----------------------------------------------------

    def test_analyst_cannot_approve_a_decision_package(self):
        mandate_id, deliverable_id, run_id = self._run_to_waiting_checkpoint()

        analyst = identity.create_user(f"analyst-{uuid.uuid4().hex}@example.com", "Analyst")
        identity.add_deal_membership(self.project.id, analyst.id, "analyst")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": analyst.id})

        status, _ = client.post(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/deliverables/{deliverable_id}/approve",
            {"confirm": True},
        )
        self.assertEqual(status, 403)

    def test_reviewer_cannot_approve_a_decision_package(self):
        """docs/06's own table: reviewer only 'Recommends' a decision
        package approval, unlike deal_lead's outright 'Yes' - this v1 has
        no dedicated 'recommend' endpoint, so a reviewer is refused the
        same as an analyst (disclosed scope simplification)."""
        mandate_id, deliverable_id, run_id = self._run_to_waiting_checkpoint()

        reviewer = identity.create_user(f"reviewer-{uuid.uuid4().hex}@example.com", "Reviewer")
        identity.add_deal_membership(self.project.id, reviewer.id, "reviewer")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": reviewer.id})

        status, _ = client.post(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/deliverables/{deliverable_id}/approve",
            {"confirm": True},
        )
        self.assertEqual(status, 403)

    def test_approval_requires_confirm_true(self):
        mandate_id, deliverable_id, run_id = self._run_to_waiting_checkpoint()
        lead = identity.create_user(f"lead-{uuid.uuid4().hex}@example.com", "Deal Lead")
        identity.add_deal_membership(self.project.id, lead.id, "deal_lead")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": lead.id})

        status, _ = client.post(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/deliverables/{deliverable_id}/approve",
            {},
        )
        self.assertEqual(status, 400)

    def test_revoked_member_is_denied(self):
        """Required test #3: revoked member denied."""
        mandate_id, deliverable_id, run_id = self._run_to_waiting_checkpoint()

        member = identity.create_user(f"member-{uuid.uuid4().hex}@example.com", "Temp Analyst")
        identity.add_deal_membership(self.project.id, member.id, "analyst")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": member.id})
        status, _ = client.get(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/deliverables/{deliverable_id}"
        )
        self.assertEqual(status, 200)

        identity.revoke_deal_membership(self.project.id, member.id)
        status, _ = client.get(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/deliverables/{deliverable_id}"
        )
        self.assertEqual(status, 404)

    # -- project isolation ----------------------------------------------------

    def test_deliverables_from_another_project_workspace_not_found(self):
        status, _ = self._get(
            f"/api/projects/{self.other_project.id}/workspaces/{self.workspace.id}/deliverables"
        )
        self.assertEqual(status, 404)

    def test_unknown_deliverable_404s(self):
        status, _ = self._get(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/deliverables/does-not-exist"
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
