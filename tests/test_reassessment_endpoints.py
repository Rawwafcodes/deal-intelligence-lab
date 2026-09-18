"""Integration tests for Task 15.2's real HTTP surface: the reassessment
capability's mandate lifecycle end to end, the new `GET/POST
.../reassessments[/<id>[/items/<id>/decision]]` routes, and the
staleness-clearing behavior once every item is acknowledged.
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
import documents
import identity
import mandates
import reassessment
import reassessments
import server
import store
import version_dependencies
import workspaces

_TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled", "outcome_unknown", "waiting_for_input"}

PDF_BYTES = b"%PDF-1.4\n%Reassessment endpoint test bytes\n%%EOF"

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


def _text_segment(text: str) -> dict:
    return {"parts": [{"type": "text", "text": text}], "pdf_citations": []}


def _fake_outcome():
    return reassessment.ReassessmentOutcome(
        success=True, transmitted=True, analysis_seconds=1.0, model="claude-opus-5", stop_reason="end_turn",
        usage={"input_tokens": 300, "output_tokens": 100}, executive_summary="One finding affected.",
        what_changed="The price figure was revised.",
        items=[
            reassessment.ReassessmentItemOutcome(
                index=0, finding_title="Term-sheet price gap", status="materially_changed",
                explanation="revised figure", evidence_of_change="new value cited",
            ),
        ],
    )


class ReassessmentEndpointTests(unittest.TestCase):
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
        version_dependencies.init_version_dependencies_db()
        reassessments.init_reassessments_db()
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
        self.project = store.create_project("Reassessment Endpoint Tests", "")
        self.other_project = store.create_project("Other Deal", "")
        self.pdf_doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF_BYTES).document
        self.old_version_id = self.pdf_doc.current_version_id
        self.xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-bytes"
        ).document
        analysis = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id, pdf_document_ids=[self.pdf_doc.id], pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[self.pdf_doc.sha256], excel_document_ids=[self.xlsx_doc.id],
            excel_document_filenames=["model.xlsx"], excel_document_checksums=[self.xlsx_doc.sha256],
            pdf_document_version_ids=[self.old_version_id],
            excel_document_version_ids=[self.xlsx_doc.current_version_id],
            status="success", transmitted=True, analysis_seconds=5.0, model="claude-opus-5", mandate_version="1",
            stop_reason="end_turn", input_tokens=1000, output_tokens=300, code_execution_requests=1,
            error_type=None, error_message=None, segments=[_text_segment(SAMPLE_FINDINGS_TEXT)], tool_trace=None,
            excel_cleanup=None, excel_verification=None,
        )
        self.workspace, _ = workspaces.get_or_create_workspace(self.project.id, analysis)
        version_dependencies.record_dependency(
            "workspace", self.workspace.id, "document", self.pdf_doc.id, self.old_version_id,
        )
        documents.add_version(self.project.id, self.pdf_doc.id, PDF_BYTES + b"\nrevised\n")

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

    def _run_to_waiting_checkpoint(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reassess after source change"})
        mandate_id = mandate["id"]
        status, plan = self._post(
            self._mandates_url(f"/{mandate_id}/plan"),
            {"template_key": "reassessment", "stage_inputs": {"reassess": {"workspace_id": self.workspace.id}}},
        )
        self.assertEqual(status, 201)
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})

        with patch("mandates.reassessment.run_reassessment", return_value=_fake_outcome()):
            status, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))
            self.assertEqual(status, 202)
            final = self._wait_for_terminal_run(mandate_id, run["id"])

        self.assertEqual(final["status"], "waiting_for_input")
        reassessment_id = final["attempts"][0]["output"]["reassessment_id"]
        return mandate_id, reassessment_id, run["id"]

    # -- template listing and propose contract -------------------------------

    def test_list_templates_includes_reassessment(self):
        status, templates = self._get("/api/mandate-templates")
        keys = {t["key"] for t in templates}
        self.assertIn("reassessment", keys)

    def test_propose_reassessment_requires_workspace_id(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reassess"})
        status, _ = self._post(
            self._mandates_url(f"/{mandate['id']}/plan"),
            {"template_key": "reassessment", "stage_inputs": {"reassess": {}}},
        )
        self.assertEqual(status, 400)

    # -- full lifecycle over HTTP --------------------------------------------

    def test_full_reassessment_lifecycle_over_http(self):
        mandate_id, reassessment_id, run_id = self._run_to_waiting_checkpoint()

        status, listed = self._get(f"/api/projects/{self.project.id}/reassessments")
        self.assertEqual(status, 200)
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], reassessment_id)

        status, record = self._get(f"/api/projects/{self.project.id}/reassessments/{reassessment_id}")
        self.assertEqual(status, 200)
        self.assertEqual(len(record["items"]), 1)
        self.assertEqual(record["items"][0]["status"], "materially_changed")
        self.assertIsNotNone(record["workspace_staleness"])  # still stale - nothing acknowledged yet

        item_id = record["items"][0]["id"]
        status, updated = self._post(
            f"/api/projects/{self.project.id}/reassessments/{reassessment_id}/items/{item_id}/decision",
            {"decision_notes": "Confirmed, will update the finding separately."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["decision"], "acknowledged")

        # Every item acknowledged -> staleness cleared automatically.
        status, record_after = self._get(f"/api/projects/{self.project.id}/reassessments/{reassessment_id}")
        self.assertIsNone(record_after["workspace_staleness"])
        status, workspace_after = self._get(
            f"/api/projects/{self.project.id}/workspaces/{self.workspace.id}"
        )
        self.assertIsNone(workspace_after["staleness"])

        # The underlying finding is untouched by acknowledgment.
        finding = next(f for f in workspace_after["findings"] if f["title"] == "Term-sheet price gap")
        self.assertEqual(finding["review_status"], "unreviewed")

        status, _ = self._post(
            self._mandates_url(f"/{mandate_id}/runs/{run_id}/resume"),
            {"stage_id": "checkpoint", "decision": "reviewed"},
        )
        self.assertEqual(status, 200)
        final = self._wait_for_terminal_run(mandate_id, run_id)
        self.assertEqual(final["status"], "succeeded")

    # -- role enforcement -----------------------------------------------------

    def test_external_executive_cannot_decide_a_reassessment_item(self):
        mandate_id, reassessment_id, run_id = self._run_to_waiting_checkpoint()
        status, record = self._get(f"/api/projects/{self.project.id}/reassessments/{reassessment_id}")
        item_id = record["items"][0]["id"]

        external = identity.create_user(f"external-{uuid.uuid4().hex}@example.com", "External Reviewer")
        identity.add_deal_membership(self.project.id, external.id, "external_executive")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": external.id})

        status, _ = client.post(
            f"/api/projects/{self.project.id}/reassessments/{reassessment_id}/items/{item_id}/decision", {},
        )
        self.assertEqual(status, 403)

    def test_analyst_can_decide_a_reassessment_item(self):
        mandate_id, reassessment_id, run_id = self._run_to_waiting_checkpoint()
        status, record = self._get(f"/api/projects/{self.project.id}/reassessments/{reassessment_id}")
        item_id = record["items"][0]["id"]

        analyst = identity.create_user(f"analyst-{uuid.uuid4().hex}@example.com", "Analyst")
        identity.add_deal_membership(self.project.id, analyst.id, "analyst")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": analyst.id})

        status, updated = client.post(
            f"/api/projects/{self.project.id}/reassessments/{reassessment_id}/items/{item_id}/decision", {},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["decision"], "acknowledged")

    def test_revoked_member_is_denied(self):
        """Required test #3: revoked member denied."""
        mandate_id, reassessment_id, run_id = self._run_to_waiting_checkpoint()

        member = identity.create_user(f"member-{uuid.uuid4().hex}@example.com", "Temp Analyst")
        identity.add_deal_membership(self.project.id, member.id, "analyst")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": member.id})
        status, _ = client.get(f"/api/projects/{self.project.id}/reassessments/{reassessment_id}")
        self.assertEqual(status, 200)

        identity.revoke_deal_membership(self.project.id, member.id)
        status, _ = client.get(f"/api/projects/{self.project.id}/reassessments/{reassessment_id}")
        self.assertEqual(status, 404)

    # -- project isolation ----------------------------------------------------

    def test_reassessment_from_another_project_is_not_found(self):
        mandate_id, reassessment_id, run_id = self._run_to_waiting_checkpoint()
        status, _ = self._get(f"/api/projects/{self.other_project.id}/reassessments/{reassessment_id}")
        self.assertEqual(status, 404)

    def test_unknown_reassessment_404s(self):
        status, _ = self._get(f"/api/projects/{self.project.id}/reassessments/does-not-exist")
        self.assertEqual(status, 404)

    def test_unknown_item_404s(self):
        mandate_id, reassessment_id, run_id = self._run_to_waiting_checkpoint()
        status, _ = self._post(
            f"/api/projects/{self.project.id}/reassessments/{reassessment_id}/items/does-not-exist/decision", {},
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
