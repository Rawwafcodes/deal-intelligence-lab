"""Integration tests for Task 13.3's HTTP surface: the Deal Overview
(`GET /api/projects/<id>/overview`) and the Workspace Overview
(`GET /api/overview`). Reuses tests/test_workspace_endpoints.py's own
fixture-fabrication technique for a CrossFormatAnalysis/Workspace with
real findings, with no real network call.
"""

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

sys.path.insert(0, str(Path(__file__).parent.parent))

from tests.test_identity_endpoints import _Client

import cross_format_analyses
import deal_briefs
import documents
import identity
import mandates
import reviews
import server
import store
import tasks
import version_dependencies
import work_products
import workspaces
import workstreams


def _text_segment(text: str, pdf_citations=None) -> dict:
    return {"parts": [{"type": "text", "text": text}], "pdf_citations": pdf_citations or []}


FINDINGS_TEXT = (
    "## Reconciliation Findings\n"
    "- **Title:** Term-sheet price gap\n"
    "**Classification:** cross-source conflict\n"
    "**Severity:** critical\n"
    "**Explanation:** the price differs across sources.\n"
    "**PDF evidence:** No PDF evidence located\n"
    "**Workbook evidence:** the model says $10m.\n"
    "**Commercial or financial relevance:** determines the offer price.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended action:** ask the seller to reconcile.\n\n"
)


class OverviewEndpointTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread

    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        work_products.DATA_DIR = documents.DATA_DIR
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()
        deal_briefs.init_deal_briefs_db()
        workstreams.init_workstreams_db()
        tasks.init_tasks_db()
        work_products.init_work_products_db()
        reviews.init_reviews_db()
        documents.init_documents_db()
        cross_format_analyses.init_cross_format_analyses_db()
        workspaces.init_workspaces_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    def setUp(self):
        self.project = store.create_project("Acme Merger", "")
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

    def _seed_findings(self, project_id: str) -> None:
        pdf_doc = documents.save_uploaded_file(project_id, "im.pdf", "", b"%PDF-1.4\n%test\n%%EOF").document
        xlsx_doc = documents.save_uploaded_file(project_id, "model.xlsx", "", b"PK\x03\x04fake-xlsx").document
        assert pdf_doc is not None and xlsx_doc is not None
        analysis = cross_format_analyses.create_cross_format_analysis(
            project_id=project_id,
            pdf_document_ids=[pdf_doc.id], pdf_document_filenames=["im.pdf"], pdf_document_checksums=[pdf_doc.sha256],
            excel_document_ids=[xlsx_doc.id], excel_document_filenames=["model.xlsx"],
            excel_document_checksums=[xlsx_doc.sha256],
            status="success", transmitted=True, analysis_seconds=8.0, model="claude-opus-5",
            mandate_version="1", stop_reason="end_turn", input_tokens=4000, output_tokens=900,
            code_execution_requests=1, error_type=None, error_message=None,
            segments=[_text_segment(FINDINGS_TEXT)], tool_trace=None, excel_cleanup=None, excel_verification=None,
        )
        status, _ = self._post(f"/api/projects/{project_id}/cross-format-analyses/{analysis.id}/workspace")
        self.assertEqual(status, 201)

    def _seed_task_with_review(self, project_id: str, assigned_to=None):
        _, task = self._post(f"/api/projects/{project_id}/tasks", {"title": "Reconcile", "assigned_to": assigned_to})
        self._post(f"/api/projects/{project_id}/tasks/{task['id']}/comments", {"body": "Working on it."})
        return task

    # -- deal overview --------------------------------------------------

    def test_deal_overview_on_unknown_project_is_not_found(self):
        status, _ = self._get("/api/projects/does-not-exist/overview")
        self.assertEqual(status, 404)

    def test_deal_overview_with_no_activity_yet(self):
        status, body = self._get(f"/api/projects/{self.project.id}/overview")
        self.assertEqual(status, 200)
        self.assertEqual(body["project"]["id"], self.project.id)
        self.assertIsNone(body["brief"])
        self.assertEqual(body["workstreams"], [])
        self.assertEqual(body["tasks"]["counts"], {})
        self.assertEqual(body["tasks"]["needs_attention"], [])
        self.assertEqual(body["mandates"]["counts"], {})
        self.assertEqual(body["reconciliations"], {"count": 0, "findings": {"total": 0, "by_severity": {}, "open_by_severity": {}}})
        self.assertEqual(body["documents"], {"count": 0})
        self.assertEqual(body["activity"], [])

    def test_deal_overview_includes_real_brief_and_workstreams(self):
        deal_briefs.create_version(self.project.id, {"objective": "Assess the deal"}, created_by="u1")
        workstreams.create_workstream(self.project.id, "Financial diligence", "")
        status, body = self._get(f"/api/projects/{self.project.id}/overview")
        self.assertEqual(status, 200)
        self.assertEqual(body["brief"]["objective"], "Assess the deal")
        self.assertEqual(len(body["workstreams"]), 1)
        self.assertEqual(body["workstreams"][0]["name"], "Financial diligence")

    def test_deal_overview_task_counts_and_needs_attention(self):
        _, task_a = self._post(f"/api/projects/{self.project.id}/tasks", {"title": "A"})
        _, task_b = self._post(f"/api/projects/{self.project.id}/tasks", {"title": "B"})
        self._post(f"/api/projects/{self.project.id}/tasks/{task_b['id']}/status", {"status": "in_progress"})

        status, body = self._get(f"/api/projects/{self.project.id}/overview")
        self.assertEqual(status, 200)
        self.assertEqual(body["tasks"]["counts"], {"open": 1, "in_progress": 1})
        self.assertEqual(body["tasks"]["needs_attention"], [])

    def test_deal_overview_reconciliation_findings_summary(self):
        self._seed_findings(self.project.id)
        status, body = self._get(f"/api/projects/{self.project.id}/overview")
        self.assertEqual(status, 200)
        self.assertEqual(body["reconciliations"]["count"], 1)
        self.assertEqual(body["reconciliations"]["findings"]["total"], 1)
        self.assertEqual(body["reconciliations"]["findings"]["by_severity"], {"critical": 1})
        self.assertEqual(body["reconciliations"]["findings"]["open_by_severity"], {"critical": 1})

    def test_deal_overview_activity_feed_includes_comments(self):
        task = self._seed_task_with_review(self.project.id)
        status, body = self._get(f"/api/projects/{self.project.id}/overview")
        self.assertEqual(status, 200)
        self.assertEqual(len(body["activity"]), 1)
        self.assertEqual(body["activity"][0]["kind"], "comment")
        self.assertEqual(body["activity"][0]["task_id"], task["id"])

    def test_deal_overview_is_isolated_per_project(self):
        self._seed_task_with_review(self.project.id)
        status, body = self._get(f"/api/projects/{self.other_project.id}/overview")
        self.assertEqual(status, 200)
        self.assertEqual(body["tasks"]["counts"], {})
        self.assertEqual(body["activity"], [])

    # -- restricted external-executive deal overview (Task 13.4) -----------

    def test_external_executive_sees_restricted_overview_with_only_approved_deliverables(self):
        deal_briefs.create_version(self.project.id, {"objective": "Assess the deal"}, created_by="u1")

        _, approved_task = self._post(f"/api/projects/{self.project.id}/tasks", {"title": "Approved memo"})
        approved_wp = work_products.create_work_product(
            self.project.id, approved_task["id"], "Reconciliation memo", "memo.txt", b"v1", created_by="u1"
        ).work_product
        assert approved_wp is not None
        tasks.mark_submitted(self.project.id, approved_task["id"])
        assert approved_wp.current_version_id is not None
        reviews.record_decision(
            approved_task["id"], approved_wp.id, approved_wp.current_version_id, "reviewer-1",
            "approved", rationale="Looks correct.",
        )
        tasks.mark_approved(self.project.id, approved_task["id"])

        _, pending_task = self._post(f"/api/projects/{self.project.id}/tasks", {"title": "Still in review"})
        work_products.create_work_product(
            self.project.id, pending_task["id"], "Draft model", "model.xlsx", b"v1", created_by="u1"
        )
        tasks.mark_submitted(self.project.id, pending_task["id"])

        external = next(u for u in identity.list_users() if u.email == "external@local.dev")
        identity.add_deal_membership(self.project.id, external.id, "external_executive")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": external.id})

        status, body = client.get(f"/api/projects/{self.project.id}/overview")
        self.assertEqual(status, 200)
        self.assertTrue(body["restricted"])
        self.assertEqual(body["brief"]["objective"], "Assess the deal")
        self.assertNotIn("tasks", body)
        self.assertNotIn("mandates", body)
        self.assertNotIn("activity", body)
        self.assertEqual(len(body["approved_deliverables"]), 1)
        self.assertEqual(body["approved_deliverables"][0]["task_title"], "Approved memo")
        self.assertEqual(body["approved_deliverables"][0]["work_product"]["id"], approved_wp.id)

    # -- workspace overview -----------------------------------------------

    def test_workspace_overview_lists_accessible_engagements(self):
        status, body = self._get("/api/overview")
        self.assertEqual(status, 200)
        project_ids = {e["project"]["id"] for e in body["engagements"]}
        self.assertIn(self.project.id, project_ids)
        self.assertIn(self.other_project.id, project_ids)

    def test_workspace_overview_my_attention_is_scoped_to_the_caller(self):
        _, identities = self._get("/api/dev/identities")
        me = identities[0]["user"]["id"]
        someone_else = identities[1]["user"]["id"]

        _, my_task = self._post(f"/api/projects/{self.project.id}/tasks", {"title": "Mine", "assigned_to": me})
        self._post(f"/api/projects/{self.project.id}/tasks/{my_task['id']}/work-products", {"title": "x"})
        # Give it a real submission so it becomes "submitted" -
        # multipart is required for a real file; instead flip status via
        # a review-independent path: submit through work_products directly.
        work_products.create_work_product(self.project.id, my_task["id"], "Model", "m.xlsx", b"bytes", created_by=me)
        tasks.mark_submitted(self.project.id, my_task["id"])

        _, other_task = self._post(
            f"/api/projects/{self.project.id}/tasks", {"title": "Someone else's", "assigned_to": someone_else}
        )
        work_products.create_work_product(self.project.id, other_task["id"], "Model", "m.xlsx", b"bytes", created_by=someone_else)
        tasks.mark_submitted(self.project.id, other_task["id"])

        status, body = self._get("/api/overview")
        self.assertEqual(status, 200)
        my_task_ids = {t["id"] for t in body["my_attention"]}
        self.assertIn(my_task["id"], my_task_ids)
        self.assertNotIn(other_task["id"], my_task_ids)

    def test_workspace_overview_engagement_counts_are_real(self):
        _, task = self._post(f"/api/projects/{self.project.id}/tasks", {"title": "x"})
        status, body = self._get("/api/overview")
        self.assertEqual(status, 200)
        engagement = next(e for e in body["engagements"] if e["project"]["id"] == self.project.id)
        self.assertEqual(engagement["task_counts"], {"open": 1})


if __name__ == "__main__":
    unittest.main()
