"""Integration tests for roadmap M12.1-M12.2's HTTP surface: mandates,
plans, runs and attempts, driven entirely through the fixture planner and
the one fixture-only capability - no real analytical capability, no AI
call.

Task 12.2 changed run start/resume from synchronous (the HTTP response
already reflects the finished run) to queue-and-hand-off: POST .../runs
now returns 202 with the run "queued", and a real, independent Worker
background thread (started in setUpClass, exactly like server.py:main()
starts one for the real app) finishes it shortly afterward. Tests that
need the final state poll GET .../runs/<id> with a short, bounded wait
(_wait_for_terminal_status) rather than assuming the POST response is final.
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

import cross_format_analyses
import documents
import identity
import mandate_planning
import mandates
import server
import store
import version_dependencies
import workspaces
from cross_format_analysis import CrossFormatAnalysisOutcome

_TERMINAL_RUN_STATUSES = {"succeeded", "failed", "cancelled", "outcome_unknown", "waiting_for_input"}


class MandateEndpointTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread
    worker: "mandates.Worker"

    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()
        version_dependencies.init_version_dependencies_db()
        mandates.init_mandates_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()
        # Exactly the same wiring server.py:main() uses for the real app -
        # a real background thread, independent of any request.
        cls.worker = mandates.Worker(poll_interval=0.02)
        cls.worker.start()

    @classmethod
    def tearDownClass(cls):
        cls.worker.stop()
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def setUp(self):
        self.project = store.create_project("Acme Merger", "")

    def _wait_for_terminal_run(self, mandate_id: str, run_id: str, timeout: float = 2.0) -> dict:
        deadline = time.monotonic() + timeout
        status, run = self._get(self._mandates_url(f"/{mandate_id}/runs/{run_id}"))
        while run.get("status") not in _TERMINAL_RUN_STATUSES and time.monotonic() < deadline:
            time.sleep(0.02)
            status, run = self._get(self._mandates_url(f"/{mandate_id}/runs/{run_id}"))
        self.assertIn(run.get("status"), _TERMINAL_RUN_STATUSES, f"run stuck at {run.get('status')!r}")
        return run

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

    # -- templates ----------------------------------------------------------

    def test_list_templates(self):
        status, templates = self._get("/api/mandate-templates")
        self.assertEqual(status, 200)
        keys = {t["key"] for t in templates}
        self.assertIn("fixture-echo", keys)
        self.assertIn("fixture-echo-with-review", keys)

    # -- mandate creation / listing ---------------------------------------

    def test_create_and_list_mandate(self):
        status, mandate = self._post(self._mandates_url(), {"objective": "Assess the Acme deal"})
        self.assertEqual(status, 201)
        self.assertEqual(mandate["status"], "draft")
        self.assertEqual(mandate["plans"], [])
        self.assertEqual(mandate["runs"], [])

        status, listed = self._get(self._mandates_url())
        self.assertEqual(status, 200)
        self.assertEqual([m["id"] for m in listed], [mandate["id"]])

    def test_blank_objective_is_rejected(self):
        status, _ = self._post(self._mandates_url(), {"objective": "   "})
        self.assertEqual(status, 400)

    def test_mandate_on_unknown_project_is_not_found(self):
        status, _ = self._get("/api/projects/does-not-exist/mandates")
        self.assertEqual(status, 404)

    def test_mandate_from_wrong_project_is_not_found(self):
        other = store.create_project("Other Deal", "")
        _, mandate = self._post(self._mandates_url(), {"objective": "Acme only"})
        status, _ = self._get(f"/api/projects/{other.id}/mandates/{mandate['id']}")
        self.assertEqual(status, 404)

    # -- full lifecycle, single-stage template -----------------------------

    def test_full_lifecycle_single_stage(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the Acme deal"})
        mandate_id = mandate["id"]

        status, plan = self._post(
            self._mandates_url(f"/{mandate_id}/plan"), {"template_key": "fixture-echo"}
        )
        self.assertEqual(status, 201)
        self.assertEqual(plan["status"], "proposed")

        status, mandate_after_propose = self._get(self._mandates_url(f"/{mandate_id}"))
        self.assertEqual(mandate_after_propose["status"], "awaiting_approval")

        status, approved = self._post(
            self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]}
        )
        self.assertEqual(status, 200)
        self.assertEqual(approved["status"], "approved")

        status, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))
        self.assertEqual(status, 202)  # accepted for processing, not completed (Task 12.2)
        self.assertEqual(run["status"], "queued")
        self.assertEqual(run["attempts"], [])

        run = self._wait_for_terminal_run(mandate_id, run["id"])
        self.assertEqual(run["status"], "succeeded")
        self.assertEqual(len(run["attempts"]), 1)
        self.assertEqual(run["attempts"][0]["output"]["echoed"], "Assess the Acme deal")

        status, final_mandate = self._get(self._mandates_url(f"/{mandate_id}"))
        self.assertEqual(final_mandate["status"], "completed")
        self.assertEqual(len(final_mandate["runs"]), 1)

    # -- human checkpoint / resume ------------------------------------------

    def test_run_with_human_checkpoint_then_resume(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the deal"})
        mandate_id = mandate["id"]
        _, plan = self._post(
            self._mandates_url(f"/{mandate_id}/plan"), {"template_key": "fixture-echo-with-review"}
        )
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})

        status, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))
        self.assertEqual(status, 202)
        run = self._wait_for_terminal_run(mandate_id, run["id"])
        self.assertEqual(run["status"], "waiting_for_input")

        status, mandate_mid_run = self._get(self._mandates_url(f"/{mandate_id}"))
        self.assertEqual(mandate_mid_run["status"], "active")

        status, resumed = self._post(
            self._mandates_url(f"/{mandate_id}/runs/{run['id']}/resume"),
            {"stage_id": "review", "decision": "approved by reviewer"},
        )
        self.assertEqual(status, 200)
        self.assertEqual(resumed["status"], "queued")  # handed back to the worker, not finished inline

        resumed = self._wait_for_terminal_run(mandate_id, run["id"])
        self.assertEqual(resumed["status"], "succeeded")

        status, final_mandate = self._get(self._mandates_url(f"/{mandate_id}"))
        self.assertEqual(final_mandate["status"], "completed")

    def test_cancel_run_while_waiting_for_input(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the deal"})
        mandate_id = mandate["id"]
        _, plan = self._post(
            self._mandates_url(f"/{mandate_id}/plan"), {"template_key": "fixture-echo-with-review"}
        )
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})
        _, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))
        run = self._wait_for_terminal_run(mandate_id, run["id"])
        self.assertEqual(run["status"], "waiting_for_input")

        status, cancelled = self._post(self._mandates_url(f"/{mandate_id}/runs/{run['id']}/cancel"))
        self.assertEqual(status, 200)
        self.assertEqual(cancelled["status"], "cancelled")

    def test_cancel_run_while_queued_is_accepted_and_resolves_cleanly(self):
        # Task 12.2: a "queued" run can now be cancelled at all (12.1 could
        # only cancel a run parked at a human checkpoint) - proven here
        # over the real HTTP surface against the real background worker
        # thread (poll_interval=0.02s, same wiring as server.py:main()).
        # The *deterministic* proof that cancelling strictly before
        # dispatch means the stage never runs is
        # test_mandates.py::MandateLifecycleTests::
        # test_cancel_run_while_queued_is_never_dispatched, which uses
        # poll_once() precisely because a real background thread's poll
        # tick and a real HTTP round trip race each other in wall-clock
        # time - fixture.echo is near-instant, so either outcome
        # (cancelled before dispatch, or it finishes first) is a
        # legitimate real-world interleaving here, not a bug either way.
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the deal"})
        mandate_id = mandate["id"]
        _, plan = self._post(self._mandates_url(f"/{mandate_id}/plan"), {"template_key": "fixture-echo"})
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})

        status, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))
        self.assertEqual(run["status"], "queued")
        status, cancel_response = self._post(self._mandates_url(f"/{mandate_id}/runs/{run['id']}/cancel"))
        self.assertEqual(status, 200)
        self.assertIn(cancel_response["status"], ("cancel_requested", "cancelled"))

        final = self._wait_for_terminal_run(mandate_id, run["id"])
        self.assertIn(final["status"], ("cancelled", "succeeded"))
        if final["status"] == "cancelled":
            self.assertEqual(final["attempts"], [])  # the echo stage never ran

    def test_budget_limit_is_enforced_over_http(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the deal"})
        mandate_id = mandate["id"]
        _, plan = self._post(self._mandates_url(f"/{mandate_id}/plan"), {"template_key": "fixture-echo"})
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})

        status, run = self._post(self._mandates_url(f"/{mandate_id}/runs"), {"budget_limit": 0.1})
        self.assertEqual(status, 202)
        final = self._wait_for_terminal_run(mandate_id, run["id"])
        self.assertEqual(final["status"], "failed")
        self.assertIn("budget exceeded", final["attempts"][0]["error"])

    def test_start_run_rejects_a_non_numeric_budget_limit(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the deal"})
        mandate_id = mandate["id"]
        _, plan = self._post(self._mandates_url(f"/{mandate_id}/plan"), {"template_key": "fixture-echo"})
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})

        status, _ = self._post(self._mandates_url(f"/{mandate_id}/runs"), {"budget_limit": "a lot"})
        self.assertEqual(status, 400)

    # -- plan rejection -----------------------------------------------------

    def test_reject_plan_returns_mandate_to_draft(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the deal"})
        mandate_id = mandate["id"]
        _, plan = self._post(self._mandates_url(f"/{mandate_id}/plan"), {"template_key": "fixture-echo"})

        status, rejected = self._post(
            self._mandates_url(f"/{mandate_id}/plan/reject"), {"plan_id": plan["id"]}
        )
        self.assertEqual(status, 200)
        self.assertEqual(rejected["status"], "rejected")

        status, mandate_after = self._get(self._mandates_url(f"/{mandate_id}"))
        self.assertEqual(mandate_after["status"], "draft")

    # -- validation / not-found paths ---------------------------------------

    def test_propose_plan_with_unknown_template_is_rejected(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the deal"})
        status, _ = self._post(
            self._mandates_url(f"/{mandate['id']}/plan"), {"template_key": "not-a-real-template"}
        )
        self.assertEqual(status, 400)

    def test_run_before_approval_is_rejected(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the deal"})
        status, _ = self._post(self._mandates_url(f"/{mandate['id']}/runs"))
        self.assertEqual(status, 400)

    def test_approve_unknown_plan_is_not_found(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the deal"})
        status, _ = self._post(
            self._mandates_url(f"/{mandate['id']}/plan/approve"), {"plan_id": "does-not-exist"}
        )
        self.assertEqual(status, 404)

    def test_run_item_and_list_endpoints(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Assess the deal"})
        mandate_id = mandate["id"]
        _, plan = self._post(self._mandates_url(f"/{mandate_id}/plan"), {"template_key": "fixture-echo"})
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})
        _, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))

        status, fetched = self._get(self._mandates_url(f"/{mandate_id}/runs/{run['id']}"))
        self.assertEqual(status, 200)
        self.assertEqual(fetched["id"], run["id"])

        status, listed = self._get(self._mandates_url(f"/{mandate_id}/runs"))
        self.assertEqual(status, 200)
        self.assertEqual([r["id"] for r in listed], [run["id"]])


class ReconciliationEndpointTests(unittest.TestCase):
    """Task 12.3's real capability, over the real HTTP surface. Same
    no-real-network-call convention as ReconciliationCapabilityTests in
    tests/test_mandates.py - cross_format_analysis.run_cross_format_analysis
    is mocked; the point of this class is proving the HTTP contract
    (stage_inputs in the propose body, the pinned manifest round-tripping
    through JSON) works, not re-proving the adapter logic already covered
    at the module level."""

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
        self.project = store.create_project("Acme Merger", "")
        self.pdf_doc = documents.save_uploaded_file(
            self.project.id, "im.pdf", "", b"%PDF-1.4\n%test bytes\n%%EOF"
        ).document
        self.xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-endpoint-bytes"
        ).document

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

    def test_list_templates_includes_reconciliation(self):
        status, templates = self._get("/api/mandate-templates")
        keys = {t["key"] for t in templates}
        self.assertIn("reconciliation", keys)

    def test_propose_reconciliation_plan_requires_stage_inputs(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile Q3 financials"})
        status, _ = self._post(self._mandates_url(f"/{mandate['id']}/plan"), {"template_key": "reconciliation"})
        self.assertEqual(status, 400)

    def test_propose_reconciliation_plan_pins_versions(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile Q3 financials"})
        status, plan = self._post(
            self._mandates_url(f"/{mandate['id']}/plan"),
            {
                "template_key": "reconciliation",
                "stage_inputs": {"reconcile": {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id]}},
            },
        )
        self.assertEqual(status, 201)
        stage = plan["stages"][0]
        self.assertEqual(sorted(stage["input"]["document_ids"]), sorted([self.pdf_doc.id, self.xlsx_doc.id]))
        self.assertIn(self.pdf_doc.id, stage["input"]["pinned_versions"])

    def test_full_reconciliation_lifecycle_over_http(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile Q3 financials"})
        mandate_id = mandate["id"]
        _, plan = self._post(
            self._mandates_url(f"/{mandate_id}/plan"),
            {
                "template_key": "reconciliation",
                "stage_inputs": {"reconcile": {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id]}},
            },
        )
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})

        fake_outcome = CrossFormatAnalysisOutcome(
            success=True, transmitted=True, analysis_seconds=3.1, model="claude-opus-5",
            stop_reason="end_turn", usage={"input_tokens": 100, "output_tokens": 50}, segments=None,
        )
        with patch("mandates.cross_format_analysis.run_cross_format_analysis", return_value=fake_outcome):
            status, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))
            self.assertEqual(status, 202)
            self.assertEqual(run["status"], "queued")
            final = self._wait_for_terminal_run(mandate_id, run["id"])

        self.assertEqual(final["status"], "succeeded")
        output = final["attempts"][0]["output"]
        self.assertTrue(output["workspace_created"])
        self.assertIsNotNone(cross_format_analyses.get_cross_format_analysis(
            self.project.id, output["cross_format_analysis_id"]
        ))

        status, final_mandate = self._get(self._mandates_url(f"/{mandate_id}"))
        self.assertEqual(final_mandate["status"], "completed")


class ReconciliationWithReviewEndpointTests(unittest.TestCase):
    """Task 12.5 (reuse proof), over the real HTTP surface: the
    `reconciliation-with-review` template is a configuration-only
    combination of the already-tested reconciliation capability (Task
    12.3) and the already-tested human_checkpoint resume flow (Task
    12.1/12.2) - this class proves the HTTP contract for that combination
    specifically (the run genuinely pauses after real output exists, and
    /resume genuinely completes it), not either building block again."""

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
        self.project = store.create_project("Acme Merger", "")
        self.pdf_doc = documents.save_uploaded_file(
            self.project.id, "im.pdf", "", b"%PDF-1.4\n%test bytes\n%%EOF"
        ).document
        self.xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-review-endpoint-bytes"
        ).document

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

    def test_list_templates_includes_reconciliation_with_review(self):
        status, templates = self._get("/api/mandate-templates")
        keys = {t["key"] for t in templates}
        self.assertIn("reconciliation-with-review", keys)

    def test_full_lifecycle_pauses_for_review_then_completes(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile Q3 financials, then review"})
        mandate_id = mandate["id"]
        _, plan = self._post(
            self._mandates_url(f"/{mandate_id}/plan"),
            {
                "template_key": "reconciliation-with-review",
                "stage_inputs": {"reconcile": {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id]}},
            },
        )
        self._post(self._mandates_url(f"/{mandate_id}/plan/approve"), {"plan_id": plan["id"]})

        fake_outcome = CrossFormatAnalysisOutcome(
            success=True, transmitted=True, analysis_seconds=2.4, model="claude-opus-5",
            stop_reason="end_turn", usage={"input_tokens": 80, "output_tokens": 40}, segments=None,
        )
        with patch("mandates.cross_format_analysis.run_cross_format_analysis", return_value=fake_outcome):
            status, run = self._post(self._mandates_url(f"/{mandate_id}/runs"))
            self.assertEqual(status, 202)
            run = self._wait_for_terminal_run(mandate_id, run["id"])

        self.assertEqual(run["status"], "waiting_for_input")
        reconcile_attempt = next(a for a in run["attempts"] if a["stage_id"] == "reconcile")
        self.assertEqual(reconcile_attempt["status"], "succeeded")
        self.assertTrue(reconcile_attempt["output"]["workspace_created"])

        status, mid_mandate = self._get(self._mandates_url(f"/{mandate_id}"))
        self.assertEqual(mid_mandate["status"], "active")  # not completed - a human still needs to review

        status, resumed = self._post(
            self._mandates_url(f"/{mandate_id}/runs/{run['id']}/resume"),
            {"stage_id": "review", "decision": "Findings reviewed - no blocking issues."},
        )
        self.assertEqual(status, 200)
        resumed = self._wait_for_terminal_run(mandate_id, run["id"])
        self.assertEqual(resumed["status"], "succeeded")

        status, final_mandate = self._get(self._mandates_url(f"/{mandate_id}"))
        self.assertEqual(final_mandate["status"], "completed")
        # The real reconciliation output the review stage was gating
        # remains reachable afterward, unaffected by the checkpoint.
        self.assertIsNotNone(cross_format_analyses.get_cross_format_analysis(
            self.project.id, reconcile_attempt["output"]["cross_format_analysis_id"]
        ))


class LlmPlanningEndpointTests(unittest.TestCase):
    """Task 12.4's real capability, over the real HTTP surface. Same
    no-real-network-call convention as tests/test_mandates.py's own
    LlmPlanningTests - mandate_planning.propose_candidate_plan is mocked;
    the point of this class is proving the HTTP contract (the new
    /plan/propose-ai route, its status-code split between a created plan,
    an honest "unsupported" outcome, and a provider-error outcome, and
    feedback round-tripping through JSON)."""

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
        self.project = store.create_project("Acme Merger", "")
        self.pdf_doc = documents.save_uploaded_file(
            self.project.id, "im.pdf", "", b"%PDF-1.4\n%test bytes\n%%EOF"
        ).document
        self.xlsx_doc = documents.save_uploaded_file(
            self.project.id, "model.xlsx", "", b"PK\x03\x04fake-xlsx-llm-planning-endpoint-bytes"
        ).document

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

    def _fake_outcome(self, **overrides):
        defaults = dict(
            status="proposed", template_key="reconciliation",
            document_ids=[self.pdf_doc.id, self.xlsx_doc.id],
            reasoning="Clear PDF/Excel pair.", unsupported_reason=None,
            model="claude-sonnet-5", usage={"input_tokens": 500, "output_tokens": 80},
        )
        defaults.update(overrides)
        return mandate_planning.PlanProposalOutcome(**defaults)

    def test_confident_proposal_returns_201_with_a_real_plan(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile the term sheet"})
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_outcome()):
            status, body = self._post(self._mandates_url(f"/{mandate['id']}/plan/propose-ai"))
        self.assertEqual(status, 201)
        self.assertEqual(body["status"], "proposed")
        self.assertEqual(body["plan"]["proposed_by"], "llm")
        self.assertEqual(body["plan"]["planner_reasoning"], "Clear PDF/Excel pair.")
        self.assertEqual(
            sorted(body["plan"]["stages"][0]["input"]["document_ids"]),
            sorted([self.pdf_doc.id, self.xlsx_doc.id]),
        )

        status, mandate_after = self._get(self._mandates_url(f"/{mandate['id']}"))
        self.assertEqual(mandate_after["status"], "awaiting_approval")
        # Not auto-approved: the human gate is untouched by this route.
        self.assertIsNone(mandate_after["current_plan_id"])

    def test_unsupported_outcome_returns_200_with_no_plan(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile something"})
        outcome = self._fake_outcome(
            status="unsupported", template_key=None, document_ids=[],
            unsupported_reason="ambiguous document pairing",
        )
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            status, body = self._post(self._mandates_url(f"/{mandate['id']}/plan/propose-ai"))
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "unsupported")
        self.assertEqual(body["reason"], "ambiguous document pairing")
        self.assertIsNone(body["plan"])

        status, mandate_after = self._get(self._mandates_url(f"/{mandate['id']}"))
        self.assertEqual(mandate_after["status"], "draft")
        self.assertEqual(mandate_after["plans"], [])

    def test_provider_error_returns_502(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile something"})
        outcome = mandate_planning.PlanProposalOutcome(
            status="error", error_type="rate_limit", error_message="Rate limit reached.",
        )
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            status, body = self._post(self._mandates_url(f"/{mandate['id']}/plan/propose-ai"))
        self.assertEqual(status, 502)
        self.assertEqual(body["error"], "Rate limit reached.")

    def test_hallucinated_document_id_is_unsupported_not_a_server_error(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile something"})
        outcome = self._fake_outcome(document_ids=[self.pdf_doc.id, "does-not-exist"])
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=outcome):
            status, body = self._post(self._mandates_url(f"/{mandate['id']}/plan/propose-ai"))
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "unsupported")
        self.assertIn("does-not-exist", body["reason"])

    def test_feedback_round_trips_to_the_planner(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile the term sheet"})
        with patch(
            "mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_outcome()
        ) as mock_call:
            status, _ = self._post(
                self._mandates_url(f"/{mandate['id']}/plan/propose-ai"),
                {"feedback": "Use model.xlsx, not an older workbook."},
            )
        self.assertEqual(status, 201)
        self.assertEqual(mock_call.call_args.kwargs["feedback"], "Use model.xlsx, not an older workbook.")

    def test_feedback_must_be_a_string(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile something"})
        status, _ = self._post(self._mandates_url(f"/{mandate['id']}/plan/propose-ai"), {"feedback": 5})
        self.assertEqual(status, 400)

    def test_reproposing_creates_a_new_revision_not_a_mutation(self):
        _, mandate = self._post(self._mandates_url(), {"objective": "Reconcile the term sheet"})
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_outcome()):
            _, first = self._post(self._mandates_url(f"/{mandate['id']}/plan/propose-ai"))
        with patch("mandates.mandate_planning.propose_candidate_plan", return_value=self._fake_outcome()):
            _, second = self._post(
                self._mandates_url(f"/{mandate['id']}/plan/propose-ai"),
                {"feedback": "Double-check the pair."},
            )
        self.assertEqual(second["plan"]["revision_number"], first["plan"]["revision_number"] + 1)

        status, mandate_after = self._get(self._mandates_url(f"/{mandate['id']}"))
        plans_by_id = {p["id"]: p for p in mandate_after["plans"]}
        self.assertEqual(plans_by_id[first["plan"]["id"]]["status"], "superseded")
        self.assertEqual(plans_by_id[second["plan"]["id"]]["status"], "proposed")

    def test_mandate_not_found(self):
        status, _ = self._post(self._mandates_url("/does-not-exist/plan/propose-ai"))
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
