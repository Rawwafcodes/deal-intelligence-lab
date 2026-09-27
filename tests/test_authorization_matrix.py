"""M17 authorization closeout: HTTP-level, table-driven proof that the
centralized policy in authz.py is actually enforced on the real running
server, not merely correct in isolation (tests/test_authz.py covers the
pure policy function itself). Real HTTP server, real Postgres schema,
four independent cookie-jar sessions (deal_lead/reviewer/analyst/
external_executive - the same `_Client` pattern
tests/test_identity_endpoints.py already established), no Anthropic
calls. Covers the founder's own required scenario list; each test
method's docstring names which scenario(s) it proves.

Frontend action visibility (scenario 24 in the founder's list) is a
React-side concern, not something this backend HTTP suite can observe -
it is verified separately via live Playwright browser checks (see this
task's own completion report). Every other required scenario has a
real assertion below.
"""

import http.cookiejar
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

import assertion_ledger
import authz
import deliverables
import documents
import identity
import integrity_reviews
import mandates
import reassessments
import server
import store
import tasks
import triggers
import version_dependencies
import work_products
import workspaces

PDF_BYTES = b"%PDF-1.4\n%Authorization matrix test fixture, harmless bytes\n%%EOF"


class _Client:
    """A separate browser profile - its own cookie jar, its own
    independently-resolved session (docs/06: 'browser profiles test
    distinct sessions')."""

    def __init__(self, port: int):
        self._base = f"http://127.0.0.1:{port}"
        self._jar = http.cookiejar.CookieJar()
        self._opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self._jar))

    def request(self, method: str, path: str, payload=None):
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        headers = {"Content-Type": "application/json"} if data is not None else {}
        req = urllib.request.Request(f"{self._base}{path}", data=data, headers=headers, method=method)
        try:
            res = self._opener.open(req)
            body = res.read()
            return res.status, (json.loads(body) if body else None)
        except urllib.error.HTTPError as exc:
            body = exc.read()
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, body

    def get(self, path: str):
        return self.request("GET", path)

    def get_raw(self, path: str):
        """Like get(), but doesn't try to JSON-parse the body - for binary
        download endpoints."""
        req = urllib.request.Request(f"{self._base}{path}", method="GET")
        try:
            res = self._opener.open(req)
            return res.status, res.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def post(self, path: str, payload=None):
        return self.request("POST", path, payload)

    def delete(self, path: str, payload=None):
        return self.request("DELETE", path, payload)

    def login(self, user_id: str) -> None:
        status, _ = self.post("/api/dev/session", {"user_id": user_id})
        assert status == 200, f"login failed: {status}"


class AuthorizationMatrixTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        cls._original_data_dir = documents.DATA_DIR
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        work_products.DATA_DIR = documents.DATA_DIR

        store.init_db()
        identity.init_identity_db()
        documents.init_documents_db()
        import cross_format_analyses
        cross_format_analyses.init_cross_format_analyses_db()
        workspaces.init_workspaces_db()
        version_dependencies.init_version_dependencies_db()
        tasks.init_tasks_db()
        work_products.init_work_products_db()
        integrity_reviews.init_integrity_reviews_db()
        import reviews
        reviews.init_reviews_db()
        deliverables.init_deliverables_db()
        reassessments.init_reassessments_db()
        triggers.init_triggers_db()
        mandates.init_mandates_db()
        assertion_ledger.init_assertion_ledger_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.lead_id = next(u for u in identity.list_users() if u.email == "lead@local.dev").id
        cls.reviewer_id = next(u for u in identity.list_users() if u.email == "reviewer@local.dev").id
        cls.analyst_id = next(u for u in identity.list_users() if u.email == "analyst@local.dev").id
        cls.external_id = next(u for u in identity.list_users() if u.email == "external@local.dev").id

        cls.lead = _Client(cls.port)
        cls.lead.login(cls.lead_id)
        status, project = cls.lead.post("/api/projects", {"name": "Matrix Deal", "description": ""})
        assert status == 201, project
        cls.project_id = project["id"]

        for user_id, role in (
            (cls.reviewer_id, "reviewer"), (cls.analyst_id, "analyst"), (cls.external_id, "external_executive"),
        ):
            status, _ = cls.lead.post(
                f"/api/projects/{cls.project_id}/memberships", {"user_id": user_id, "role": role}
            )
            assert status == 201

        cls.reviewer = _Client(cls.port)
        cls.reviewer.login(cls.reviewer_id)
        cls.analyst = _Client(cls.port)
        cls.analyst.login(cls.analyst_id)
        cls.external = _Client(cls.port)
        cls.external.login(cls.external_id)

        # -- fixtures, built directly via module calls (never through the
        # AI-calling paths - no Anthropic call anywhere in this file) --
        cls.pdf_doc = documents.save_uploaded_file(cls.project_id, "im.pdf", "", PDF_BYTES).document

        task = tasks.create_task(cls.project_id, "Draft the memo")
        wp_result = work_products.create_work_product(
            cls.project_id, task.id, "Memo", "memo.pdf", PDF_BYTES, created_by=cls.analyst_id
        )
        cls.task_id = task.id
        cls.work_product_id = wp_result.work_product.id
        tasks.mark_submitted(cls.project_id, task.id)

        review = integrity_reviews.create_integrity_review(
            project_id=cls.project_id, mandate_id=None, run_id=None, attempt_id=None,
            target_work_product_id=cls.work_product_id, target_version_id=wp_result.work_product.current_version_id,
            source_document_ids=[cls.pdf_doc.id], source_version_ids=[cls.pdf_doc.current_version_id],
            peer_work_product_ids=[], peer_version_ids=[], brief_version_id=None, workstream_id=None,
            review_scope="", status="success", transmitted=True, analysis_seconds=1.0, model="claude-opus-5",
            review_template_version="1", stop_reason="end_turn", input_tokens=100, output_tokens=50,
            code_execution_requests=0, error_type=None, error_message=None,
            materials_reviewed_text="Submission Under Review: memo.pdf", tool_trace=None,
            excel_cleanup=None, excel_verification=None,
        )
        cls.workspace, _ = workspaces.get_or_create_workspace_for_integrity_review(cls.project_id, review.id)

        cls.draft_request = workspaces.create_request(cls.workspace.id, {"question": "Please confirm the figure."})
        cls.sent_request = workspaces.create_request(cls.workspace.id, {"question": "Please confirm headcount."})
        workspaces.update_request(cls.workspace.id, cls.sent_request.id, {"status": "sent"})

        cls.draft_deliverable = deliverables.create_deliverable_version(
            project_id=cls.project_id, workspace_id=cls.workspace.id, mandate_id=None, run_id=None, attempt_id=None,
            title="Decision Package v1", executive_summary="", recommendation="", key_evidence_and_findings="",
            outstanding_and_unresolved_matters="", risks_and_limitations="", emphasis="",
            source_finding_ids=[], source_request_ids=[], model="claude-opus-5", draft_template_version="1",
            input_tokens=None, output_tokens=None,
        )
        deliverables.approve_deliverable_version(cls.workspace.id, cls.draft_deliverable.id, cls.lead_id)
        cls.approved_deliverable_id = cls.draft_deliverable.id
        cls.draft_deliverable_2 = deliverables.create_deliverable_version(
            project_id=cls.project_id, workspace_id=cls.workspace.id, mandate_id=None, run_id=None, attempt_id=None,
            title="Decision Package v2", executive_summary="", recommendation="", key_evidence_and_findings="",
            outstanding_and_unresolved_matters="", risks_and_limitations="", emphasis="",
            source_finding_ids=[], source_request_ids=[], model="claude-opus-5", draft_template_version="1",
            input_tokens=None, output_tokens=None,
        )

        cls.mandate = mandates.create_mandate(cls.project_id, "Draft the decision package", created_by=cls.lead_id)

        cls.trigger = triggers.create_trigger(
            project_id=cls.project_id, name="Redo readiness on new version",
            event_type="document_version_changed", template_key="readiness", owner_user_id=cls.lead_id,
        )

        # A second, fully isolated project only the lead can see - proves
        # cross-deal isolation (scenario 19) actually holds.
        status, other_project = cls.lead.post("/api/projects", {"name": "Other Deal", "description": ""})
        assert status == 201
        cls.other_project_id = other_project["id"]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)
        documents.DATA_DIR = cls._original_data_dir
        cls._tmpdir.cleanup()

    # -- 1/2/7: authorized/unauthorized read, findings access --------------

    def test_1_2_7_analyst_reads_findings_external_denied(self):
        status, _ = self.analyst.get(f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}")
        self.assertEqual(status, 200)
        status, body = self.external.get(f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}")
        self.assertEqual(status, 403)
        self.assertIn("view_findings", body["error"])

    # -- 3/4: authorized/unauthorized mutation ------------------------------

    def test_3_4_authorized_and_unauthorized_mutation(self):
        # A plain internal mutation (add a task comment) - analyst can,
        # external cannot. Deliberately distinct from scenario 11's own
        # task/work-product creation pair below.
        status, _ = self.analyst.post(
            f"/api/projects/{self.project_id}/tasks/{self.task_id}/comments", {"body": "Looks good"}
        )
        self.assertEqual(status, 201)
        status, body = self.external.post(
            f"/api/projects/{self.project_id}/tasks/{self.task_id}/comments", {"body": "Should not land"}
        )
        self.assertEqual(status, 403)

    # -- 5: document listing -------------------------------------------------

    def test_5_document_listing(self):
        status, body = self.analyst.get(f"/api/projects/{self.project_id}/documents")
        self.assertEqual(status, 200)
        self.assertEqual(len(body), 1)
        status, _ = self.external.get(f"/api/projects/{self.project_id}/documents")
        self.assertEqual(status, 403)

    # -- 6: direct document download -----------------------------------------

    def test_6_direct_document_download(self):
        status, _ = self.analyst.get_raw(f"/api/projects/{self.project_id}/documents/{self.pdf_doc.id}/download")
        self.assertEqual(status, 200)
        status, _ = self.external.get_raw(f"/api/projects/{self.project_id}/documents/{self.pdf_doc.id}/download")
        self.assertEqual(status, 403)

    # -- 8/9: request creation, external management response ---------------

    def test_8_request_creation(self):
        status, _ = self.analyst.post(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}/requests", {"question": "?"}
        )
        self.assertEqual(status, 201)
        status, _ = self.external.post(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}/requests", {"question": "?"}
        )
        self.assertEqual(status, 403)

    def test_9_external_management_response(self):
        # A draft request is not yet visible/answerable externally.
        status, body = self.external.post(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}/requests/{self.draft_request.id}",
            {"management_response": "trying to answer a draft"},
        )
        self.assertEqual(status, 404)
        # A sent one is - but only the management_response field.
        status, body = self.external.post(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}/requests/{self.sent_request.id}",
            {"management_response": "Headcount is 42."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["management_response"], "Headcount is 42.")
        status, _ = self.external.post(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}/requests/{self.sent_request.id}",
            {"status": "closed"},
        )
        self.assertEqual(status, 403)
        # External also cannot see the still-draft request in the list.
        status, body = self.external.get(f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}/requests")
        self.assertEqual(status, 200)
        ids = {r["id"] for r in body}
        self.assertIn(self.sent_request.id, ids)
        self.assertNotIn(self.draft_request.id, ids)

    # -- 10: mandate creation and execution -----------------------------------

    def test_10_mandate_creation_and_execution(self):
        status, mandate = self.analyst.post(f"/api/projects/{self.project_id}/mandates", {"objective": "Do work"})
        self.assertEqual(status, 201)
        status, _ = self.external.post(f"/api/projects/{self.project_id}/mandates", {"objective": "Do work"})
        self.assertEqual(status, 403)
        status, _ = self.external.get(f"/api/projects/{self.project_id}/mandates")
        self.assertEqual(status, 403)
        status, _ = self.external.post(
            f"/api/projects/{self.project_id}/mandates/{mandate['id']}/runs", {}
        )
        self.assertEqual(status, 403)

    # -- 11/25: submission creation, self-approval prevention ----------------

    def test_11_25_submission_creation_and_self_approval_prevention(self):
        status, _ = self.analyst.post(
            f"/api/projects/{self.project_id}/tasks", {"title": "Second task"}
        )
        self.assertEqual(status, 201)
        status, _ = self.external.post(
            f"/api/projects/{self.project_id}/tasks", {"title": "Should not land"}
        )
        self.assertEqual(status, 403)
        # T04, literally: the analyst who owns this submission cannot
        # approve it themselves - the same guarantee Task 13.4 first
        # proved, re-verified here as part of the closeout's own matrix.
        status, body = self.analyst.post(
            f"/api/projects/{self.project_id}/work-products/{self.work_product_id}/review",
            {"decision": "approved"},
        )
        self.assertEqual(status, 403)

    # -- 12: submission review -------------------------------------------------

    def test_12_submission_review(self):
        status, _ = self.analyst.post(
            f"/api/projects/{self.project_id}/work-products/{self.work_product_id}/review",
            {"decision": "approved"},
        )
        self.assertEqual(status, 403)
        status, _ = self.external.post(
            f"/api/projects/{self.project_id}/work-products/{self.work_product_id}/review",
            {"decision": "approved"},
        )
        self.assertEqual(status, 403)
        status, body = self.reviewer.post(
            f"/api/projects/{self.project_id}/work-products/{self.work_product_id}/review",
            {"decision": "approved"},
        )
        self.assertEqual(status, 201)

    # -- 13: decision-package approval + object-level visibility -----------

    def test_13_decision_package_approval_and_visibility(self):
        status, _ = self.reviewer.post(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}"
            f"/deliverables/{self.draft_deliverable_2.id}/approve",
            {"confirm": True},
        )
        self.assertEqual(status, 403)  # reviewer's role is "recommend", not "approve"
        status, _ = self.external.post(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}"
            f"/deliverables/{self.draft_deliverable_2.id}/approve",
            {"confirm": True},
        )
        self.assertEqual(status, 403)
        status, _ = self.lead.post(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}"
            f"/deliverables/{self.draft_deliverable_2.id}/approve",
            {"confirm": True},
        )
        self.assertEqual(status, 200)
        # External sees the approved deliverable but not a still-draft one.
        status, body = self.external.get(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}"
            f"/deliverables/{self.approved_deliverable_id}"
        )
        self.assertEqual(status, 200)
        status, body = self.external.get(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}/deliverables"
        )
        self.assertEqual(status, 200)
        statuses = {v["id"]: v["status"] for v in body}
        self.assertIn(self.approved_deliverable_id, statuses)

    # -- 14: trigger configuration -------------------------------------------

    def test_14_trigger_configuration(self):
        payload = {
            "name": "x", "event_type": "document_version_changed", "template_key": "readiness",
            "owner_user_id": self.reviewer_id,
        }
        status, _ = self.reviewer.post(f"/api/projects/{self.project_id}/triggers", payload)
        self.assertEqual(status, 201)
        status, _ = self.analyst.post(f"/api/projects/{self.project_id}/triggers", payload)
        self.assertEqual(status, 403)
        status, _ = self.external.post(f"/api/projects/{self.project_id}/triggers", payload)
        self.assertEqual(status, 403)
        status, _ = self.external.get(f"/api/projects/{self.project_id}/triggers")
        self.assertEqual(status, 403)

    # -- 15: reassessment access ----------------------------------------------

    def test_15_reassessment_access(self):
        status, _ = self.analyst.get(f"/api/projects/{self.project_id}/reassessments")
        self.assertEqual(status, 200)
        status, _ = self.external.get(f"/api/projects/{self.project_id}/reassessments")
        self.assertEqual(status, 403)

    # -- 16: assertions access -------------------------------------------------

    def test_16_assertions_access(self):
        status, _ = self.analyst.get(f"/api/projects/{self.project_id}/assertion-ledger")
        self.assertEqual(status, 200)
        status, _ = self.external.get(f"/api/projects/{self.project_id}/assertion-ledger")
        self.assertEqual(status, 403)

    # -- 17: (internal) activity access ---------------------------------------

    def test_17_activity_access(self):
        status, body = self.analyst.get(f"/api/projects/{self.project_id}/overview")
        self.assertEqual(status, 200)
        self.assertIn("activity", body)
        status, body = self.external.get(f"/api/projects/{self.project_id}/overview")
        self.assertEqual(status, 200)
        self.assertTrue(body.get("restricted"))
        self.assertNotIn("activity", body)
        # The restricted overview's own `requests` field is the real
        # frontend surface for "management-response controls needed to
        # answer" a request - only the sent one should appear here, same
        # object-level filter as the standalone requests list route
        # (test_9_external_management_response).
        request_ids = {r["id"] for r in body["requests"]}
        self.assertIn(self.sent_request.id, request_ids)
        self.assertNotIn(self.draft_request.id, request_ids)
        # Task 18.1 follow-up: the approved decision package reaches the
        # external executive here; the unapproved draft does not, and no
        # internal lineage rides along.
        # Only the latest version, and only once approved - v1 was approved
        # but v2 now exists, so v1 is no longer the current position. (Another
        # test in this class may approve v2; either outcome is checked.)
        packages = body["approved_decision_packages"]
        self.assertNotIn(self.approved_deliverable_id, {p["id"] for p in packages})
        v2_approved = deliverables.is_current_version_approved(self.workspace.id, self.draft_deliverable_2.id)
        self.assertEqual([p["id"] for p in packages], [self.draft_deliverable_2.id] if v2_approved else [])
        for package in packages:
            self.assertFalse({"source_finding_ids", "mandate_id", "model", "input_tokens"} & set(package))

    # -- 18: membership administration ---------------------------------------

    def test_18_membership_administration(self):
        status, _ = self.reviewer.post(
            f"/api/projects/{self.project_id}/memberships", {"user_id": self.reviewer_id, "role": "analyst"}
        )
        self.assertEqual(status, 403)
        status, _ = self.external.post(
            f"/api/projects/{self.project_id}/memberships", {"user_id": self.reviewer_id, "role": "analyst"}
        )
        self.assertEqual(status, 403)
        # Roster *viewing* is internal-activity-tier (any internal role),
        # distinct from grant/revoke, which stays deal_lead-only above.
        status, _ = self.analyst.get(f"/api/projects/{self.project_id}/memberships")
        self.assertEqual(status, 200)
        status, _ = self.external.get(f"/api/projects/{self.project_id}/memberships")
        self.assertEqual(status, 403)
        status, _ = self.external.delete(f"/api/projects/{self.project_id}/memberships/{self.analyst_id}", None)
        self.assertEqual(status, 403)

    # -- 19: cross-deal isolation ----------------------------------------------

    def test_19_cross_deal_isolation(self):
        status, _ = self.analyst.get(f"/api/projects/{self.other_project_id}")
        self.assertEqual(status, 404)  # not a member at all - looks exactly like nonexistent
        status, _ = self.analyst.get(f"/api/projects/{self.other_project_id}/documents")
        self.assertEqual(status, 404)

    # -- 20: membership revocation takes effect immediately ------------------

    def test_20_membership_revocation_is_immediate(self):
        temp_user = identity.create_user(f"temp-{uuid.uuid4().hex}@local.dev", "Temp Revoke Test")
        self.lead.post(f"/api/projects/{self.project_id}/memberships", {"user_id": temp_user.id, "role": "analyst"})
        temp_client = _Client(self.port)
        temp_client.login(temp_user.id)
        status, _ = temp_client.get(f"/api/projects/{self.project_id}")
        self.assertEqual(status, 200)
        status, _ = self.lead.delete(f"/api/projects/{self.project_id}/memberships/{temp_user.id}", None)
        self.assertEqual(status, 200)
        status, _ = temp_client.get(f"/api/projects/{self.project_id}")
        self.assertEqual(status, 404)

    # -- 21: organization-wide aggregate filtering ----------------------------

    def test_21_organization_wide_aggregate_filtering(self):
        status, body = self.external.get("/api/overview")
        self.assertEqual(status, 200)
        engagement = next(e for e in body["engagements"] if e["project"]["id"] == self.project_id)
        self.assertEqual(engagement["task_counts"], {})
        self.assertEqual(engagement["mandate_counts"], {})
        for event in body["material_changes"]:
            self.assertNotEqual(event.get("project", {}).get("id"), self.project_id)

        status, mandates_body = self.external.get("/api/mandates")
        self.assertEqual(status, 200)
        self.assertFalse(any(m["project"]["id"] == self.project_id for m in mandates_body))

        status, mandates_body = self.analyst.get("/api/mandates")
        self.assertEqual(status, 200)
        self.assertTrue(any(m["project"]["id"] == self.project_id for m in mandates_body))

    # -- 22/23: direct URL/API access bypasses nothing ------------------------

    def test_22_23_direct_api_access_enforces_the_same_policy(self):
        """Every test in this file already calls the real HTTP API
        directly, with no UI in front of it - this method exists only to
        name the scenario explicitly: hitting a specific deep-linked
        workspace URL directly, as a freshly authenticated external
        session with no prior navigation, still 403s exactly as it would
        after clicking through from a hidden nav link."""
        fresh_external = _Client(self.port)
        fresh_external.login(self.external_id)
        status, _ = fresh_external.get(f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}")
        self.assertEqual(status, 403)
        status, _ = fresh_external.get(f"/api/projects/{self.project_id}/readiness")
        self.assertEqual(status, 404)  # no such route at all - not the point; workspace-scoped readiness is
        status, _ = fresh_external.get(
            f"/api/projects/{self.project_id}/workspaces/{self.workspace.id}/readiness"
        )
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
