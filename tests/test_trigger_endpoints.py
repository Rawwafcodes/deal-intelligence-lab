"""Integration tests for Task 15.3's real HTTP surface: trigger CRUD
(`GET/POST .../triggers[/<id>[/disable]]`), role enforcement, and both
real event hooks end to end - uploading a new document version actually
firing a configured `document_version_changed` trigger, and a real
(mocked-provider) decision-package run actually firing a configured
`decision_package_prepared` trigger.
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
import triggers
import version_dependencies
import workspaces

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


class TriggerEndpointTests(unittest.TestCase):
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
        triggers.init_triggers_db()
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
        self.project = store.create_project("Trigger Endpoint Tests", "")
        self.other_project = store.create_project("Other Deal", "")

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

    def _triggers_url(self, suffix: str = "") -> str:
        return f"/api/projects/{self.project.id}/triggers{suffix}"

    # -- CRUD -----------------------------------------------------------------

    def test_create_list_get_trigger(self):
        status, trigger = self._post(
            self._triggers_url(),
            {
                "name": "Readiness on source change", "event_type": "document_version_changed",
                "template_key": "readiness", "reason": "Keep readiness current as sources evolve.",
            },
        )
        self.assertEqual(status, 201)
        self.assertEqual(trigger["status"], "active")

        status, listed = self._get(self._triggers_url())
        self.assertEqual(status, 200)
        self.assertEqual(len(listed), 1)

        status, fetched = self._get(self._triggers_url(f"/{trigger['id']}"))
        self.assertEqual(status, 200)
        self.assertEqual(fetched["firings"], [])

    def test_create_rejects_incompatible_template(self):
        status, _ = self._post(
            self._triggers_url(),
            {"name": "x", "event_type": "decision_package_prepared", "template_key": "reassessment"},
        )
        self.assertEqual(status, 400)

    def test_disable_trigger(self):
        _, trigger = self._post(
            self._triggers_url(), {"name": "x", "event_type": "document_version_changed", "template_key": "readiness"},
        )
        status, disabled = self._post(self._triggers_url(f"/{trigger['id']}/disable"))
        self.assertEqual(status, 200)
        self.assertEqual(disabled["status"], "disabled")

    def test_unknown_trigger_404s(self):
        status, _ = self._get(self._triggers_url("/does-not-exist"))
        self.assertEqual(status, 404)

    def test_trigger_from_another_project_not_found(self):
        _, trigger = self._post(
            self._triggers_url(), {"name": "x", "event_type": "document_version_changed", "template_key": "readiness"},
        )
        status, _ = self._get(f"/api/projects/{self.other_project.id}/triggers/{trigger['id']}")
        self.assertEqual(status, 404)

    # -- role enforcement -------------------------------------------------------

    def test_analyst_cannot_create_a_trigger(self):
        analyst = identity.create_user(f"analyst-{uuid.uuid4().hex}@example.com", "Analyst")
        identity.add_deal_membership(self.project.id, analyst.id, "analyst")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": analyst.id})

        status, _ = client.post(
            self._triggers_url(), {"name": "x", "event_type": "document_version_changed", "template_key": "readiness"},
        )
        self.assertEqual(status, 403)

    def test_reviewer_can_create_a_trigger(self):
        reviewer = identity.create_user(f"reviewer-{uuid.uuid4().hex}@example.com", "Reviewer")
        identity.add_deal_membership(self.project.id, reviewer.id, "reviewer")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": reviewer.id})

        status, trigger = client.post(
            self._triggers_url(), {"name": "x", "event_type": "document_version_changed", "template_key": "readiness"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(trigger["owner_user_id"], reviewer.id)

    # -- real event hooks, end to end ---------------------------------------

    def test_document_version_upload_fires_a_real_configured_trigger(self):
        pdf_doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", b"%PDF-1.4\n%x\n%%EOF").document
        xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-bytes"
        ).document
        analysis = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id, pdf_document_ids=[pdf_doc.id], pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[pdf_doc.sha256], excel_document_ids=[xlsx_doc.id],
            excel_document_filenames=["model.xlsx"], excel_document_checksums=[xlsx_doc.sha256],
            status="success", transmitted=True, analysis_seconds=5.0, model="claude-opus-5", mandate_version="1",
            stop_reason="end_turn", input_tokens=100, output_tokens=50, code_execution_requests=0,
            error_type=None, error_message=None, segments=[_text_segment(SAMPLE_FINDINGS_TEXT)], tool_trace=None,
            excel_cleanup=None, excel_verification=None,
        )
        workspace, _ = workspaces.get_or_create_workspace(self.project.id, analysis)
        version_dependencies.record_dependency(
            "workspace", workspace.id, "document", pdf_doc.id, pdf_doc.current_version_id,
        )

        status, trigger = self._post(
            self._triggers_url(),
            {"name": "Readiness watch", "event_type": "document_version_changed", "template_key": "readiness"},
        )
        self.assertEqual(status, 201)

        # A real, plain HTTP multipart upload of a new document version -
        # no mandate call from the test itself.
        req = urllib.request.Request(
            self._url(f"/api/projects/{self.project.id}/documents/{pdf_doc.id}/versions"),
            data=(
                b"--BOUNDARY\r\nContent-Disposition: form-data; name=\"file\"; filename=\"im.pdf\"\r\n"
                b"Content-Type: application/pdf\r\n\r\n%PDF-1.4\n%revised\n%%EOF\r\n--BOUNDARY--\r\n"
            ),
            headers={"Content-Type": "multipart/form-data; boundary=BOUNDARY"}, method="POST",
        )
        res = urllib.request.urlopen(req)
        self.assertEqual(res.status, 201)

        status, fetched = self._get(self._triggers_url(f"/{trigger['id']}"))
        self.assertEqual(status, 200)
        self.assertEqual(len(fetched["firings"]), 1)
        self.assertEqual(fetched["firings"][0]["status"], "proposed")
        self.assertEqual(fetched["firings"][0]["workspace_id"], workspace.id)

        mandate_id = fetched["firings"][0]["mandate_id"]
        status, mandate = self._get(f"/api/projects/{self.project.id}/mandates/{mandate_id}")
        self.assertEqual(status, 200)
        self.assertEqual(mandate["status"], "awaiting_approval")

    def test_decision_package_creation_fires_a_real_configured_trigger(self):
        pdf_doc = documents.save_uploaded_file(self.project.id, "im2.pdf", "", b"%PDF-1.4\n%y\n%%EOF").document
        xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model2.xlsx", "", b"PK\x03\x04more-bytes"
        ).document
        analysis = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id, pdf_document_ids=[pdf_doc.id], pdf_document_filenames=["im2.pdf"],
            pdf_document_checksums=[pdf_doc.sha256], excel_document_ids=[xlsx_doc.id],
            excel_document_filenames=["model2.xlsx"], excel_document_checksums=[xlsx_doc.sha256],
            status="success", transmitted=True, analysis_seconds=5.0, model="claude-opus-5", mandate_version="1",
            stop_reason="end_turn", input_tokens=100, output_tokens=50, code_execution_requests=0,
            error_type=None, error_message=None, segments=[_text_segment(SAMPLE_FINDINGS_TEXT)], tool_trace=None,
            excel_cleanup=None, excel_verification=None,
        )
        workspace, _ = workspaces.get_or_create_workspace(self.project.id, analysis)
        finding = workspaces.list_findings(workspace)[0]
        workspaces.update_finding_workflow(workspace.id, finding["id"], {"review_status": "accepted"})

        status, trigger = self._post(
            self._triggers_url(),
            {"name": "Readiness after package", "event_type": "decision_package_prepared", "template_key": "readiness"},
        )
        self.assertEqual(status, 201)

        _, mandate = self._post(f"/api/projects/{self.project.id}/mandates", {"objective": "Prepare a package"})
        mandate_id = mandate["id"]
        status, plan = self._post(
            f"/api/projects/{self.project.id}/mandates/{mandate_id}/plan",
            {"template_key": "decision-package", "stage_inputs": {"draft": {"workspace_id": workspace.id}}},
        )
        self.assertEqual(status, 201)
        self._post(f"/api/projects/{self.project.id}/mandates/{mandate_id}/plan/approve", {"plan_id": plan["id"]})

        with patch(
            "mandates.decision_package.run_decision_package_draft",
            return_value=decision_package.DecisionPackageOutcome(
                success=True, transmitted=True, analysis_seconds=0.5, model="claude-opus-5", stop_reason="end_turn",
                usage={"input_tokens": 100, "output_tokens": 50}, executive_summary="s", recommendation="r",
                key_evidence_and_findings="k", outstanding_and_unresolved_matters="o", risks_and_limitations="l",
            ),
        ):
            status, run = self._post(f"/api/projects/{self.project.id}/mandates/{mandate_id}/runs")
            self.assertEqual(status, 202)
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                status, run_state = self._get(f"/api/projects/{self.project.id}/mandates/{mandate_id}/runs/{run['id']}")
                if run_state["status"] in ("waiting_for_input", "succeeded", "failed"):
                    break
                time.sleep(0.02)

        status, fetched = self._get(self._triggers_url(f"/{trigger['id']}"))
        self.assertEqual(status, 200)
        self.assertEqual(len(fetched["firings"]), 1)
        self.assertEqual(fetched["firings"][0]["status"], "proposed")
        self.assertEqual(fetched["firings"][0]["workspace_id"], workspace.id)


if __name__ == "__main__":
    unittest.main()
