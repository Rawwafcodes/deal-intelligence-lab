"""Integration tests for Task 14.2's real HTTP surface: the integrity-
review capability's mandate lifecycle end to end, the new `GET .../
integrity-reviews[/<id>]` read routes, and the candidate-decision
endpoint's role enforcement and publish behavior. Same no-real-network-
call convention as every other mandate-capability endpoint test class -
`integrity_review.run_integrity_review` is mocked; the point of this
class is the HTTP/authorization contract, not re-proving the adapter
logic already covered at the module level in tests/test_integrity_
review.py.
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

import deal_briefs
import documents
import identity
import integrity_review
import integrity_reviews
import mandates
import server
import store
import tasks
import version_dependencies
import work_products
import workspaces
import workstreams

_TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled", "outcome_unknown", "waiting_for_input"}

PDF_BYTES = b"%PDF-1.4\n%Integrity Review endpoint test bytes\n%%EOF"


def _fake_outcome():
    return integrity_review.IntegrityReviewOutcome(
        success=True, transmitted=True, analysis_seconds=2.0, model="claude-opus-5", stop_reason="end_turn",
        usage={"input_tokens": 500, "output_tokens": 200},
        candidates=[integrity_review.IntegrityCandidateOutcome(
            index=0, title="Working capital double-counted", classification="calculation or derivation divergence",
            severity="high", assertion="the memo states net investment of $91.75m.",
            conflicting_or_missing_evidence="the source term sheet states $102.358m all-in.",
            why_it_matters="changes the offer price analysis.", uncertainty="fully supported by citations",
            recommended_resolution="ask the analyst to reconcile.", deterministic_or_judgment="model_judgment",
        )],
        materials_reviewed_text="Submission Under Review: memo.pdf",
    )


class IntegrityReviewEndpointTests(unittest.TestCase):
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
        work_products.DATA_DIR = documents.DATA_DIR
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()
        documents.init_documents_db()
        tasks.init_tasks_db()
        work_products.init_work_products_db()
        workspaces.init_workspaces_db()
        deal_briefs.init_deal_briefs_db()
        workstreams.init_workstreams_db()
        integrity_reviews.init_integrity_reviews_db()
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
        self.project = store.create_project("Integrity Review Endpoint Tests", "")
        self.other_project = store.create_project("Other Deal", "")
        self.task = tasks.create_task(self.project.id, "Draft the valuation memo")
        self.target_wp = work_products.create_work_product(
            self.project.id, self.task.id, "Valuation memo", "memo.pdf", PDF_BYTES, created_by="analyst-1"
        ).work_product
        self.source_doc = documents.save_uploaded_file(self.project.id, "im.pdf", "", PDF_BYTES).document

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

    def _stage_input(self):
        return {
            "target": {"work_product_id": self.target_wp.id, "version_id": self.target_wp.current_version_id},
            "documents": [{"document_id": self.source_doc.id, "version_id": self.source_doc.current_version_id}],
        }

    def _wait_for_terminal_run(self, mandate_id: str, run_id: str, timeout: float = 2.0) -> dict:
        deadline = time.monotonic() + timeout
        status, run = self._get(self._mandates_url(f"/{mandate_id}/runs/{run_id}"))
        while run.get("status") not in _TERMINAL_RUN_STATUSES and time.monotonic() < deadline:
            time.sleep(0.02)
            status, run = self._get(self._mandates_url(f"/{mandate_id}/runs/{run_id}"))
        self.assertIn(run.get("status"), _TERMINAL_RUN_STATUSES, f"run stuck at {run.get('status')!r}")
        return run

    def _run_to_waiting_review(self):
        """Proposes, approves, and executes an integrity-review mandate
        (mocked provider call) through to its human_checkpoint pause;
        returns (mandate_id, review_id, run_id)."""
        _, mandate = self._post(self._mandates_url(), {"objective": "Review the valuation memo"})
        mandate_id = mandate["id"]
        status, plan = self._post(
            self._mandates_url(f"/{mandate_id}/plan"),
            {"template_key": "integrity-review", "stage_inputs": {"review": self._stage_input()}},
        )
        self.assertEqual(status, 201)
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})

        with patch("mandates.integrity_review.run_integrity_review", return_value=_fake_outcome()):
            status, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))
            self.assertEqual(status, 202)
            final = self._wait_for_terminal_run(mandate_id, run["id"])

        self.assertEqual(final["status"], "waiting_for_input")
        review_id = final["attempts"][0]["output"]["integrity_review_id"]
        return mandate_id, review_id, run["id"]

    # -- template listing and propose contract -------------------------------

    def test_list_templates_includes_integrity_review(self):
        status, templates = self._get("/api/mandate-templates")
        keys = {t["key"] for t in templates}
        self.assertIn("integrity-review", keys)

    def test_propose_integrity_review_plan_requires_target(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Review the memo"})
        status, _ = self._post(
            self._mandates_url(f"/{mandate['id']}/plan"),
            {"template_key": "integrity-review", "stage_inputs": {"review": {"documents": [
                {"document_id": self.source_doc.id, "version_id": self.source_doc.current_version_id}
            ]}}},
        )
        self.assertEqual(status, 400)

    # -- full lifecycle over HTTP --------------------------------------------

    def test_full_integrity_review_lifecycle_over_http(self):
        mandate_id, review_id, run_id = self._run_to_waiting_review()

        status, review = self._get(f"/api/projects/{self.project.id}/integrity-reviews/{review_id}")
        self.assertEqual(status, 200)
        self.assertEqual(len(review["candidates"]), 1)
        self.assertEqual(review["candidates"][0]["decision"], "pending")
        self.assertEqual(review["published_findings"], [])

        candidate_id = review["candidates"][0]["id"]
        status, updated = self._post(
            f"/api/projects/{self.project.id}/integrity-reviews/{review_id}/candidates/{candidate_id}/decision",
            {"decision": "accepted", "decision_notes": "Confirmed against the term sheet."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["decision"], "accepted")
        self.assertIsNotNone(updated["published_finding_id"])

        status, review_after = self._get(f"/api/projects/{self.project.id}/integrity-reviews/{review_id}")
        self.assertEqual(status, 200)
        self.assertEqual(len(review_after["published_findings"]), 1)
        published = review_after["published_findings"][0]
        self.assertEqual(published["origin"], "integrity")
        self.assertEqual(published["title"], "Working capital double-counted")
        self.assertEqual(published["lineage"]["target"]["work_product_id"], self.target_wp.id)
        # Found live during this task's own real paid proof run: lineage
        # must identify the originating mandate/run, not just the review.
        self.assertEqual(published["lineage"]["mandate_id"], mandate_id)
        self.assertEqual(published["lineage"]["run_id"], run_id)

        # Resuming the mandate's own human_checkpoint is a separate,
        # generic action from deciding individual candidates - reuses the
        # exact same GET .../runs/<id>/resume mechanism every other
        # human_checkpoint template already exercises.
        status, _ = self._post(
            self._mandates_url(f"/{mandate_id}/runs/{run_id}/resume"),
            {"stage_id": "checkpoint", "decision": "reviewed"},
        )
        self.assertEqual(status, 200)
        final = self._wait_for_terminal_run(mandate_id, run_id)
        self.assertEqual(final["status"], "succeeded")

    def test_rejecting_a_candidate_never_publishes_it(self):
        mandate_id, review_id, run_id = self._run_to_waiting_review()
        status, review = self._get(f"/api/projects/{self.project.id}/integrity-reviews/{review_id}")
        candidate_id = review["candidates"][0]["id"]

        status, updated = self._post(
            f"/api/projects/{self.project.id}/integrity-reviews/{review_id}/candidates/{candidate_id}/decision",
            {"decision": "rejected", "decision_notes": "Already known and accepted as intentional."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["decision"], "rejected")
        self.assertIsNone(updated["published_finding_id"])

        status, review_after = self._get(f"/api/projects/{self.project.id}/integrity-reviews/{review_id}")
        self.assertEqual(review_after["published_findings"], [])

    # -- role enforcement -----------------------------------------------------

    def test_external_executive_cannot_decide_a_candidate(self):
        mandate_id, review_id, run_id = self._run_to_waiting_review()
        status, review = self._get(f"/api/projects/{self.project.id}/integrity-reviews/{review_id}")
        candidate_id = review["candidates"][0]["id"]

        external = identity.create_user(f"external-{uuid.uuid4().hex}@example.com", "External Reviewer")
        identity.add_deal_membership(self.project.id, external.id, "external_executive")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": external.id})

        status, _ = client.post(
            f"/api/projects/{self.project.id}/integrity-reviews/{review_id}/candidates/{candidate_id}/decision",
            {"decision": "accepted"},
        )
        self.assertEqual(status, 403)

    def test_analyst_can_decide_a_candidate(self):
        """docs/06's own table: 'Recommend finding disposition: Yes' for
        analyst, reviewer and deal_lead alike - not reviewer/deal_lead
        only, unlike the stricter review-decision (approval) endpoint."""
        mandate_id, review_id, run_id = self._run_to_waiting_review()
        status, review = self._get(f"/api/projects/{self.project.id}/integrity-reviews/{review_id}")
        candidate_id = review["candidates"][0]["id"]

        analyst = identity.create_user(f"analyst-{uuid.uuid4().hex}@example.com", "Analyst Reviewer")
        identity.add_deal_membership(self.project.id, analyst.id, "analyst")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": analyst.id})

        status, updated = client.post(
            f"/api/projects/{self.project.id}/integrity-reviews/{review_id}/candidates/{candidate_id}/decision",
            {"decision": "rejected", "decision_notes": "Not material."},
        )
        self.assertEqual(status, 200)
        self.assertEqual(updated["decision"], "rejected")

    def test_revoked_member_is_denied(self):
        """Required test #3: revoked member denied."""
        mandate_id, review_id, run_id = self._run_to_waiting_review()

        member = identity.create_user(f"member-{uuid.uuid4().hex}@example.com", "Temp Analyst")
        identity.add_deal_membership(self.project.id, member.id, "analyst")
        client = _Client(self.port)
        client.post("/api/dev/session", {"user_id": member.id})
        status, _ = client.get(f"/api/projects/{self.project.id}/integrity-reviews/{review_id}")
        self.assertEqual(status, 200)

        identity.revoke_deal_membership(self.project.id, member.id)
        status, _ = client.get(f"/api/projects/{self.project.id}/integrity-reviews/{review_id}")
        self.assertEqual(status, 404)

    # -- project isolation ----------------------------------------------------

    def test_integrity_review_from_another_project_is_not_found(self):
        mandate_id, review_id, run_id = self._run_to_waiting_review()
        status, _ = self._get(f"/api/projects/{self.other_project.id}/integrity-reviews/{review_id}")
        self.assertEqual(status, 404)

    def test_unknown_integrity_review_is_not_found(self):
        status, _ = self._get(f"/api/projects/{self.project.id}/integrity-reviews/not-a-real-review")
        self.assertEqual(status, 404)

    def test_unknown_candidate_is_not_found(self):
        mandate_id, review_id, run_id = self._run_to_waiting_review()
        status, _ = self._post(
            f"/api/projects/{self.project.id}/integrity-reviews/{review_id}/candidates/not-a-real-candidate/decision",
            {"decision": "accepted"},
        )
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
