"""Integration tests for Task 14.4's real HTTP surface: the readiness
capability's mandate lifecycle end to end (a single-stage template, no
human_checkpoint, no mocking needed anywhere - this capability makes no
external call) and the new `GET .../workspaces/<id>/readiness[/<id>]`
read routes.
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

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_identity_endpoints import _Client

import cross_format_analyses
import deal_briefs
import deliverables
import documents
import identity
import mandates
import readiness_assessments
import server
import store
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


class ReadinessEndpointTests(unittest.TestCase):
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
        deal_briefs.init_deal_briefs_db()
        deliverables.init_deliverables_db()
        readiness_assessments.init_readiness_assessments_db()
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
        self.project = store.create_project("Readiness Endpoint Tests", "")
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

    def _run_readiness(self, workspace_id=None):
        """Proposes, approves, and executes a readiness mandate to
        completion (no mocking, no checkpoint - a single-stage template
        that reaches 'succeeded' directly); returns (mandate_id,
        assessment_id, run_id)."""
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess readiness"})
        mandate_id = mandate["id"]
        status, plan = self._post(
            self._mandates_url(f"/{mandate_id}/plan"),
            {"template_key": "readiness", "stage_inputs": {"assess": {"workspace_id": workspace_id or self.workspace.id}}},
        )
        self.assertEqual(status, 201)
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})

        status, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))
        self.assertEqual(status, 202)
        final = self._wait_for_terminal_run(mandate_id, run["id"])

        self.assertEqual(final["status"], "succeeded")
        assessment_id = final["attempts"][0]["output"]["assessment_id"]
        return mandate_id, assessment_id, run["id"]

    # -- template listing and propose contract -------------------------------

    def test_list_templates_includes_readiness(self):
        status, templates = self._get("/api/mandate-templates")
        keys = {t["key"] for t in templates}
        self.assertIn("readiness", keys)

    def test_propose_readiness_plan_requires_workspace_id(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess readiness"})
        status, _ = self._post(
            self._mandates_url(f"/{mandate['id']}/plan"),
            {"template_key": "readiness", "stage_inputs": {"assess": {}}},
        )
        self.assertEqual(status, 400)

    # -- full lifecycle over HTTP --------------------------------------------

    def test_full_readiness_lifecycle_over_http(self):
        mandate_id, assessment_id, run_id = self._run_readiness()

        status, listed = self._get(f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/readiness")
        self.assertEqual(status, 200)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], assessment_id)
        self.assertFalse(listed[0]["ready"])  # nothing has been reviewed on this fresh workspace

        status, assessment = self._get(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/readiness/{assessment_id}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(assessment["mandate_id"], mandate_id)
        self.assertEqual(assessment["run_id"], run_id)
        unmet_keys = {i["key"] for i in assessment["items"] if not i["met"]}
        self.assertIn("no_unreviewed_findings", unmet_keys)
        self.assertIn("has_brief", unmet_keys)
        self.assertIn("position_approved", unmet_keys)

    def test_revoked_member_is_denied(self):
        """Required test #3: revoked member denied."""
        mandate_id, assessment_id, run_id = self._run_readiness()

        member = identity.create_user(f"member-{uuid.uuid4().hex}@example.com", "Temp Analyst")
        identity.add_deal_membership(self.project.id, member.id, "analyst")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": member.id})
        status, _ = client.get(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/readiness/{assessment_id}"
        )
        self.assertEqual(status, 200)

        identity.revoke_deal_membership(self.project.id, member.id)
        status, _ = client.get(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/readiness/{assessment_id}"
        )
        self.assertEqual(status, 404)

    # -- project isolation ----------------------------------------------------

    def test_readiness_from_another_project_workspace_not_found(self):
        status, _ = self._get(f"/api/projects/{self.other_project.id}/workspaces/{self.workspace.id}/readiness")
        self.assertEqual(status, 404)

    def test_unknown_assessment_404s(self):
        status, _ = self._get(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}/readiness/does-not-exist"
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
