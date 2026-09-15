"""Integration tests for the Validation Lab HTTP endpoints (Milestone 8):
the real server, with the Anthropic client mocked so no network call is
made. Includes the end-to-end blindness proof: a unique secret marker
placed inside a locked answer key must never appear in the mocked
Anthropic request, the uploaded workbook bytes, application stdout/stderr,
or the analysis result.
"""

import contextlib
import io
import json
import sys
import tempfile
import threading
import types
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import answer_keys
import cross_format_analyses
import documents
import evaluations
import server
import store
import validation_cases
import validation_runs

FAKE_SECRET = "sk-ant-api03-VALIDATION-ENDPOINT-TEST-FAKE-SECRET-DO-NOT-LEAK"
PDF_BYTES = b"%PDF-1.4\n%Information memorandum, harmless test bytes\n%%EOF"
XLSX_BYTES = b"PK\x03\x04fake-xlsx-bytes-for-endpoint-tests"


def fake_text_block(text: str):
    return types.SimpleNamespace(type="text", text=text, citations=None)


def fake_response(content_blocks, stop_reason: str = "end_turn"):
    usage = types.SimpleNamespace(input_tokens=3000, output_tokens=900)
    return types.SimpleNamespace(
        content=content_blocks,
        model="claude-opus-5",
        usage=usage,
        stop_reason=stop_reason,
        stop_details=None,
        container=types.SimpleNamespace(id="container_1"),
    )


def _stream_cm(response):
    mock_stream = MagicMock()
    mock_stream.get_final_message.return_value = response
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_stream)
    cm.__exit__ = MagicMock(return_value=False)
    return cm


def mock_client_for(response, captured_upload_bytes=None):
    mock_client = MagicMock()

    def upload(*, file, **kwargs):
        filename, fileobj, mime_type = file
        if captured_upload_bytes is not None:
            captured_upload_bytes.append(fileobj.read())
        return types.SimpleNamespace(id="file_abc123")

    mock_client.files.upload.side_effect = upload
    mock_client.files.delete.return_value = types.SimpleNamespace(id="file_abc123", type="file_deleted")
    mock_client.messages.stream.return_value = _stream_cm(response)
    return mock_client


class ValidationEndpointTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread
    project: store.Project

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_db_path = store.DB_PATH
        cls._original_data_dir = documents.DATA_DIR
        store.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        store.init_db()
        documents.init_documents_db()
        cross_format_analyses.init_cross_format_analyses_db()
        validation_cases.init_validation_cases_db()
        answer_keys.init_answer_keys_db()
        validation_runs.init_validation_runs_db()
        evaluations.init_evaluations_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.project = store.create_project("Project Falcon", "validation endpoint tests")
        pdf_result = documents.save_uploaded_file(cls.project.id, "im.pdf", "", PDF_BYTES)
        cls.pdf_doc = pdf_result.document
        xlsx_result = documents.save_uploaded_file(cls.project.id, "model.xlsx", "", XLSX_BYTES)
        cls.xlsx_doc = xlsx_result.document

        cls.other_project = store.create_project("Project Osprey", "a different project")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.DB_PATH = cls._original_db_path
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

    def _post_json(self, path: str, payload):
        data = json.dumps(payload).encode("utf-8") if payload is not None else b""
        req = urllib.request.Request(
            self._url(path), data=data, headers={"Content-Type": "application/json"}, method="POST"
        )
        try:
            res = urllib.request.urlopen(req)
            return res.status, res.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def _get(self, path: str):
        try:
            res = urllib.request.urlopen(self._url(path))
            return res.status, res.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def _cases_url(self, project_id: str | None = None) -> str:
        return f"/api/projects/{project_id or self.project.id}/validation-cases"

    def _create_case(self, *, pdf_ids=None, excel_ids=None):
        status, body = self._post_json(
            self._cases_url(),
            {
                "name": f"Case {self.id()}",
                "description": "test case",
                "pdf_document_ids": pdf_ids if pdf_ids is not None else [self.pdf_doc.id],
                "excel_document_ids": excel_ids if excel_ids is not None else [self.xlsx_doc.id],
            },
        )
        return status, json.loads(body)

    # -- case creation & selection validation --------------------------------

    def test_create_validation_case_requires_pdf_and_excel(self):
        status, payload = self._create_case(pdf_ids=[self.pdf_doc.id], excel_ids=[])
        self.assertEqual(status, 400)

        status, payload = self._create_case(pdf_ids=[], excel_ids=[self.xlsx_doc.id])
        self.assertEqual(status, 400)

    def test_create_validation_case_rejects_duplicate_document_ids(self):
        status, payload = self._create_case(pdf_ids=[self.pdf_doc.id, self.pdf_doc.id], excel_ids=[self.xlsx_doc.id])
        self.assertEqual(status, 400)

    def test_create_validation_case_rejects_wrong_extension_in_wrong_slot(self):
        status, payload = self._create_case(pdf_ids=[self.xlsx_doc.id], excel_ids=[self.pdf_doc.id])
        self.assertEqual(status, 400)

    def test_create_validation_case_success(self):
        status, payload = self._create_case()
        self.assertEqual(status, 201)
        self.assertEqual(payload["pdf_document_ids"], [self.pdf_doc.id])
        self.assertEqual(payload["excel_document_ids"], [self.xlsx_doc.id])

        get_status, get_body = self._get(f"{self._cases_url()}/{payload['id']}")
        self.assertEqual(get_status, 200)
        detail = json.loads(get_body)
        self.assertEqual(detail["case"]["id"], payload["id"])
        self.assertFalse(detail["answer_key"]["is_locked"])
        self.assertIn("content", detail["answer_key"])  # draft always visible

    # -- project isolation ----------------------------------------------------

    def test_validation_case_project_isolation(self):
        status, payload = self._create_case()
        case_id = payload["id"]
        get_status, _ = self._get(f"/api/projects/{self.other_project.id}/validation-cases/{case_id}")
        self.assertEqual(get_status, 404)

    def test_forged_validation_case_id_rejected(self):
        get_status, _ = self._get(f"{self._cases_url()}/does-not-exist")
        self.assertEqual(get_status, 404)

    def test_cross_project_document_in_case_creation_rejected(self):
        other_pdf = documents.save_uploaded_file(self.other_project.id, "other.pdf", "", b"%PDF-1.4\n%o\n%%EOF").document
        status, payload = self._post_json(
            self._cases_url(),
            {
                "name": "Cross-project attempt",
                "pdf_document_ids": [other_pdf.id],
                "excel_document_ids": [self.xlsx_doc.id],
            },
        )
        self.assertEqual(status, 404)

    # -- answer key lifecycle via HTTP ---------------------------------------

    def _answer_key_url(self, case_id: str) -> str:
        return f"{self._cases_url()}/{case_id}/answer-key"

    def test_answer_key_content_saved_and_retrieved_while_draft(self):
        _, case = self._create_case()
        status, body = self._post_json(
            self._answer_key_url(case["id"]),
            {"content": {"issues": [{"id": "i1", "title": "Revenue conflict"}], "must_not_claim": []}},
        )
        self.assertEqual(status, 200)
        get_status, get_body = self._get(self._answer_key_url(case["id"]))
        payload = json.loads(get_body)
        self.assertEqual(payload["content"]["issues"][0]["title"], "Revenue conflict")

    def test_locking_requires_confirm_and_nonempty_content(self):
        _, case = self._create_case()
        lock_url = f"{self._answer_key_url(case['id'])}/lock"
        status, _ = self._post_json(lock_url, {"confirm": False})
        self.assertEqual(status, 400)
        status, _ = self._post_json(lock_url, {"confirm": True})
        self.assertEqual(status, 400)  # empty content

        self._post_json(
            self._answer_key_url(case["id"]),
            {"content": {"issues": [{"id": "i1", "title": "X"}], "must_not_claim": []}},
        )
        status, body = self._post_json(lock_url, {"confirm": True})
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload["is_locked"])
        self.assertIsNotNone(payload["checksum"])

    def test_locked_answer_key_cannot_be_edited_via_http(self):
        _, case = self._create_case()
        self._post_json(
            self._answer_key_url(case["id"]),
            {"content": {"issues": [{"id": "i1", "title": "X"}], "must_not_claim": []}},
        )
        self._post_json(f"{self._answer_key_url(case['id'])}/lock", {"confirm": True})

        status, _ = self._post_json(
            self._answer_key_url(case["id"]),
            {"content": {"issues": [{"id": "i1", "title": "Tampered"}], "must_not_claim": []}},
        )
        self.assertEqual(status, 409)

    def test_revision_creates_new_editable_version(self):
        _, case = self._create_case()
        self._post_json(
            self._answer_key_url(case["id"]),
            {"content": {"issues": [{"id": "i1", "title": "X"}], "must_not_claim": []}},
        )
        self._post_json(f"{self._answer_key_url(case['id'])}/lock", {"confirm": True})
        status, body = self._post_json(f"{self._answer_key_url(case['id'])}/revise", {"confirm": True})
        self.assertEqual(status, 201)
        revision = json.loads(body)
        self.assertEqual(revision["version_number"], 2)
        self.assertFalse(revision["is_locked"])

    def test_answer_key_hidden_after_lock_until_a_run_completes(self):
        _, case = self._create_case()
        self._post_json(
            self._answer_key_url(case["id"]),
            {"content": {"issues": [{"id": "i1", "title": "X"}], "must_not_claim": []}},
        )
        self._post_json(f"{self._answer_key_url(case['id'])}/lock", {"confirm": True})

        get_status, get_body = self._get(self._answer_key_url(case["id"]))
        payload = json.loads(get_body)
        self.assertTrue(payload["content_hidden"])
        self.assertNotIn("content", payload)

    def test_run_cannot_start_with_unlocked_answer_key(self):
        _, case = self._create_case()
        status, body = self._post_json(
            f"{self._cases_url()}/{case['id']}/runs", {"confirm": True, "mode": "new"}
        )
        self.assertEqual(status, 400)

    # -- blindness proof via full HTTP workflow ------------------------------

    def test_full_blind_workflow_and_secret_marker_never_leaks(self):
        secret = "MARKER-79c1e0a2-do-not-leak"

        _, case = self._create_case()
        case_id = case["id"]

        self._post_json(
            self._answer_key_url(case_id),
            {
                "content": {
                    "issues": [
                        {
                            "id": "i1",
                            "title": f"Revenue conflict {secret}",
                            "expected_severity": "critical",
                            "evaluator_notes": secret,
                        }
                    ],
                    "must_not_claim": [{"id": "m1", "statement": f"Do not claim {secret}"}],
                }
            },
        )
        lock_status, lock_body = self._post_json(f"{self._answer_key_url(case_id)}/lock", {"confirm": True})
        self.assertEqual(lock_status, 200)
        locked_payload = json.loads(lock_body)
        self.assertIn(secret, json.dumps(locked_payload))  # confirmation echo right after locking is fine

        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        captured_upload_bytes: list[bytes] = []
        mock_client = mock_client_for(response, captured_upload_bytes)

        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client):
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
                run_status, run_body = self._post_json(
                    f"{self._cases_url()}/{case_id}/runs", {"confirm": True, "mode": "new"}
                )

        self.assertEqual(run_status, 200)
        run_payload = json.loads(run_body)
        self.assertTrue(run_payload["is_blind"])

        # 1. Never in the mocked Anthropic messages.stream call.
        _, stream_kwargs = mock_client.messages.stream.call_args
        self.assertNotIn(secret, json.dumps(stream_kwargs, default=str))

        # 2. Never in the uploaded workbook bytes.
        for uploaded_bytes in captured_upload_bytes:
            self.assertNotIn(secret.encode(), uploaded_bytes)

        # 3. Never in application stdout/stderr.
        self.assertNotIn(secret, captured_stdout.getvalue())
        self.assertNotIn(secret, captured_stderr.getvalue())

        # 4. Never in the run's own response, or the raw analysis result.
        self.assertNotIn(secret, run_body.decode())
        analysis_status, analysis_body = self._get(
            f"/api/projects/{self.project.id}/reconciliations/{run_payload['cross_format_analysis_id']}"
        )
        self.assertNotIn(secret, analysis_body.decode())

        # 5. The general answer-key endpoint stays hidden even after the run
        #    (this case's current version *does* now have a run against
        #    it, so it becomes revealable per the "after completion" rule -
        #    confirm that's exactly when it becomes visible, not before).
        get_status, get_body = self._get(self._answer_key_url(case_id))
        payload = json.loads(get_body)
        self.assertFalse(payload["content_hidden"])
        self.assertIn(secret, json.dumps(payload))  # now legitimately revealed, post-completion

        # 6. But the answer-key content never appears in the persisted
        #    cross_format_analyses record's stored segments/tool_trace -
        #    i.e. Claude's own recorded reply never echoes it back either.
        self.assertNotIn(secret, analysis_body.decode())

    def test_answer_key_not_revealed_via_report_before_evaluation_exists_for_other_case(self):
        # A locked-but-unused answer key in a *different* case must not be
        # revealed by fetching another case's report.
        secret = "OTHER-CASE-SECRET-marker"
        _, other_case = self._create_case()
        self._post_json(
            self._answer_key_url(other_case["id"]),
            {"content": {"issues": [{"id": "i1", "title": secret}], "must_not_claim": []}},
        )
        self._post_json(f"{self._answer_key_url(other_case['id'])}/lock", {"confirm": True})

        _, case = self._create_case()
        self._post_json(
            self._answer_key_url(case["id"]),
            {"content": {"issues": [{"id": "i1", "title": "unrelated"}], "must_not_claim": []}},
        )
        self._post_json(f"{self._answer_key_url(case['id'])}/lock", {"confirm": True})

        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            run_status, run_body = self._post_json(
                f"{self._cases_url()}/{case['id']}/runs", {"confirm": True, "mode": "new"}
            )
        run_id = json.loads(run_body)["id"]

        report_status, report_body = self._get(f"{self._cases_url()}/{case['id']}/runs/{run_id}/report")
        self.assertNotIn(secret, report_body.decode())

    # -- attach-existing mode / retrospective labeling -----------------------

    def test_attach_existing_from_other_project_rejected(self):
        _, case = self._create_case()
        self._post_json(
            self._answer_key_url(case["id"]),
            {"content": {"issues": [{"id": "i1", "title": "X"}], "must_not_claim": []}},
        )
        self._post_json(f"{self._answer_key_url(case['id'])}/lock", {"confirm": True})

        other_pdf = documents.save_uploaded_file(self.other_project.id, "o.pdf", "", b"%PDF-1.4\n%o\n%%EOF").document
        other_xlsx = documents.save_uploaded_file(self.other_project.id, "o.xlsx", "", b"PK\x03\x04").document
        other_record = cross_format_analyses.create_cross_format_analysis(
            project_id=self.other_project.id,
            pdf_document_ids=[other_pdf.id],
            pdf_document_filenames=["o.pdf"],
            pdf_document_checksums=[other_pdf.sha256],
            excel_document_ids=[other_xlsx.id],
            excel_document_filenames=["o.xlsx"],
            excel_document_checksums=[other_xlsx.sha256],
            status="success",
            transmitted=True,
            analysis_seconds=1.0,
            model="claude-opus-5",
            mandate_version="1",
            stop_reason="end_turn",
            input_tokens=1,
            output_tokens=1,
            code_execution_requests=0,
            error_type=None,
            error_message=None,
            segments=None,
            tool_trace=None,
            excel_cleanup=None,
            excel_verification=None,
        )
        status, _ = self._post_json(
            f"{self._cases_url()}/{case['id']}/runs",
            {"confirm": True, "mode": "existing", "cross_format_analysis_id": other_record.id},
        )
        self.assertEqual(status, 404)

    def test_marking_retrospective_run_as_blind_pass_is_rejected(self):
        _, case = self._create_case()
        # Analysis already exists before the key is locked -> retrospective.
        record = cross_format_analyses.create_cross_format_analysis(
            project_id=self.project.id,
            pdf_document_ids=[self.pdf_doc.id],
            pdf_document_filenames=["im.pdf"],
            pdf_document_checksums=[self.pdf_doc.sha256],
            excel_document_ids=[self.xlsx_doc.id],
            excel_document_filenames=["model.xlsx"],
            excel_document_checksums=[self.xlsx_doc.sha256],
            status="success",
            transmitted=True,
            analysis_seconds=1.0,
            model="claude-opus-5",
            mandate_version="1",
            stop_reason="end_turn",
            input_tokens=1,
            output_tokens=1,
            code_execution_requests=0,
            error_type=None,
            error_message=None,
            segments=None,
            tool_trace=None,
            excel_cleanup=None,
            excel_verification=None,
        )
        self._post_json(
            self._answer_key_url(case["id"]),
            {"content": {"issues": [{"id": "i1", "title": "X"}], "must_not_claim": []}},
        )
        self._post_json(f"{self._answer_key_url(case['id'])}/lock", {"confirm": True})

        status, body = self._post_json(
            f"{self._cases_url()}/{case['id']}/runs",
            {"confirm": True, "mode": "existing", "cross_format_analysis_id": record.id},
        )
        self.assertEqual(status, 201)
        run = json.loads(body)
        self.assertFalse(run["is_blind"])

        eval_url = f"{self._cases_url()}/{case['id']}/runs/{run['id']}/evaluation"
        status, _ = self._post_json(eval_url, {"final_status": "passed"})
        self.assertEqual(status, 400)
        status, body = self._post_json(eval_url, {"final_status": "not_a_blind_test"})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["final_status"], "not_a_blind_test")

    # -- evaluation + report + metrics via HTTP ------------------------------

    def test_evaluation_and_report_full_cycle(self):
        _, case = self._create_case()
        self._post_json(
            self._answer_key_url(case["id"]),
            {
                "content": {
                    "issues": [{"id": "i1", "title": "Revenue conflict", "expected_severity": "critical"}],
                    "must_not_claim": [],
                }
            },
        )
        self._post_json(f"{self._answer_key_url(case['id'])}/lock", {"confirm": True})

        finding_text = (
            "## Reconciliation Findings\n"
            "- **Title:** Revenue mismatch\n"
            "**Classification:** cross-source conflict\n"
            "**Severity:** critical\n"
            "**Explanation:** figures differ.\n"
            "**PDF evidence:** the IM says $12m.\n"
            "**Workbook evidence:** the model says $10m.\n"
            "**Commercial or financial relevance:** matters.\n"
            "**Uncertainty:** fully supported\n"
            "**Recommended action:** ask.\n"
        )
        response = fake_response([fake_text_block(finding_text)])
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            run_status, run_body = self._post_json(
                f"{self._cases_url()}/{case['id']}/runs", {"confirm": True, "mode": "new"}
            )
        run_id = json.loads(run_body)["id"]

        eval_url = f"{self._cases_url()}/{case['id']}/runs/{run_id}/evaluation"
        status, body = self._post_json(
            eval_url,
            {
                "expected_issue_ratings": {"i1": {"status": "found_completely", "linked_finding_indices": [0]}},
                "finding_ratings": {"0": {"status": "correct_material", "citation_check": "correct"}},
                "human_conclusion": "Solid result.",
                "final_status": "passed",
            },
        )
        self.assertEqual(status, 200)

        report_status, report_body = self._get(f"{self._cases_url()}/{case['id']}/runs/{run_id}/report")
        self.assertEqual(report_status, 200)
        report = json.loads(report_body)
        self.assertEqual(len(report["findings"]), 1)
        self.assertEqual(report["metrics"]["critical_recall"]["numerator"], 1)
        self.assertEqual(report["metrics"]["critical_recall"]["denominator"], 1)
        self.assertEqual(report["evaluation"]["final_status"], "passed")
        self.assertEqual(report["answer_key"]["content"]["issues"][0]["title"], "Revenue conflict")

    def test_evaluation_persists_across_simulated_restart(self):
        _, case = self._create_case()
        self._post_json(
            self._answer_key_url(case["id"]),
            {"content": {"issues": [{"id": "i1", "title": "X"}], "must_not_claim": []}},
        )
        self._post_json(f"{self._answer_key_url(case['id'])}/lock", {"confirm": True})
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            run_status, run_body = self._post_json(
                f"{self._cases_url()}/{case['id']}/runs", {"confirm": True, "mode": "new"}
            )
        run_id = json.loads(run_body)["id"]
        eval_url = f"{self._cases_url()}/{case['id']}/runs/{run_id}/evaluation"
        self._post_json(eval_url, {"human_conclusion": "durable conclusion"})

        # Simulate an app restart: re-run schema init (idempotent) and
        # fetch again.
        evaluations.init_evaluations_db()
        get_status, get_body = self._get(eval_url)
        self.assertEqual(json.loads(get_body)["human_conclusion"], "durable conclusion")

    def test_forged_run_id_rejected(self):
        _, case = self._create_case()
        status, _ = self._get(f"{self._cases_url()}/{case['id']}/runs/does-not-exist")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
