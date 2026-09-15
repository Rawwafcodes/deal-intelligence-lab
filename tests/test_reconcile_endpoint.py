"""Integration tests for the cross-format reconciliation HTTP endpoints: the
real server, with the Anthropic client mocked so no network call is made.
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

import openpyxl

import cross_format_analyses
import documents
import server
import store

FAKE_SECRET = "sk-ant-api03-RECONCILE-ENDPOINT-TEST-FAKE-SECRET-DO-NOT-LEAK"
PDF_BYTES = b"%PDF-1.4\n%Information memorandum, harmless test bytes\n%%EOF"


def build_sample_workbook(path: Path) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Revenue Model"
    ws["B7"] = 100
    wb.save(path)
    return path.read_bytes()


def fake_text_block(text: str, citations=None):
    return types.SimpleNamespace(type="text", text=text, citations=citations)


def fake_response(content_blocks, stop_reason: str = "end_turn"):
    usage = types.SimpleNamespace(input_tokens=6000, output_tokens=1500)
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


def mock_client_for(response):
    mock_client = MagicMock()
    mock_client.files.upload.return_value = types.SimpleNamespace(id="file_abc123")
    mock_client.files.delete.return_value = types.SimpleNamespace(id="file_abc123", type="file_deleted")
    mock_client.messages.stream.return_value = _stream_cm(response)
    return mock_client


class ReconcileEndpointTests(unittest.TestCase):
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

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.project = store.create_project("Project Falcon", "test project")
        pdf_result = documents.save_uploaded_file(cls.project.id, "im.pdf", "", PDF_BYTES)
        assert pdf_result.status == "success" and pdf_result.document is not None
        cls.pdf_doc = pdf_result.document

        workbook_bytes = build_sample_workbook(Path(cls._tmpdir.name) / "model.xlsx")
        xlsx_result = documents.save_uploaded_file(cls.project.id, "model.xlsx", "", workbook_bytes)
        assert xlsx_result.status == "success" and xlsx_result.document is not None
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

    def _reconcile_url(self, project_id: str | None = None) -> str:
        return f"/api/projects/{project_id or self.project.id}/reconciliation"

    def test_confirmation_is_required(self):
        status, _ = self._post_json(
            self._reconcile_url(), {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id], "confirm": False}
        )
        self.assertEqual(status, 400)

        status, _ = self._post_json(self._reconcile_url(), {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id]})
        self.assertEqual(status, 400)

    def test_document_ids_must_be_a_list_of_strings(self):
        status, _ = self._post_json(self._reconcile_url(), {"document_ids": "nope", "confirm": True})
        self.assertEqual(status, 400)

        status, _ = self._post_json(self._reconcile_url(), {"document_ids": [1, 2], "confirm": True})
        self.assertEqual(status, 400)

    def test_duplicate_document_id_rejected(self):
        with patch("cross_format_analysis.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                self._reconcile_url(),
                {"document_ids": [self.pdf_doc.id, self.pdf_doc.id, self.xlsx_doc.id], "confirm": True},
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 400)

    def test_unknown_document_id_is_not_found(self):
        with patch("cross_format_analysis.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                self._reconcile_url(),
                {"document_ids": [self.pdf_doc.id, "does-not-exist"], "confirm": True},
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 404)

    def test_cross_project_document_id_is_rejected(self):
        # A document id belonging to another project must never be
        # resolvable through this project's endpoint - never "forged in".
        other_pdf_result = documents.save_uploaded_file(
            self.other_project.id, "other.pdf", "", b"%PDF-1.4\n%other\n%%EOF"
        )
        assert other_pdf_result.document is not None
        with patch("cross_format_analysis.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                self._reconcile_url(),
                {"document_ids": [other_pdf_result.document.id, self.xlsx_doc.id], "confirm": True},
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 404)

    def test_project_isolation_documents_from_other_project_are_not_found(self):
        with patch("cross_format_analysis.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                self._reconcile_url(self.other_project.id),
                {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id], "confirm": True},
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 404)

    def test_successful_reconciliation_via_http(self):
        text = "Revenue matches the model ('Workbook 1'!'Revenue Model'!B7 [value])."
        response = fake_response([fake_text_block(text)])

        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            status, body = self._post_json(
                self._reconcile_url(), {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id], "confirm": True}
            )

        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["transmitted"])
        self.assertEqual(payload["pdf_document_ids"], [self.pdf_doc.id])
        self.assertEqual(payload["excel_document_ids"], [self.xlsx_doc.id])
        self.assertEqual(payload["pdf_document_filenames"], ["im.pdf"])
        self.assertEqual(payload["excel_document_filenames"], ["model.xlsx"])
        self.assertTrue(payload["excel_cleanup"][0]["attempted"])
        self.assertTrue(payload["excel_cleanup"][0]["succeeded"])
        excel_parts = [p for s in payload["segments"] for p in s["parts"] if p["type"] == "excel_citation"]
        self.assertTrue(excel_parts[0]["citation"]["exists"])

        get_status, get_body = self._get(f"/api/projects/{self.project.id}/reconciliations/{payload['id']}")
        self.assertEqual(get_status, 200)
        self.assertEqual(json.loads(get_body)["id"], payload["id"])

    def test_reconciliation_record_persists_across_simulated_restart(self):
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            status, body = self._post_json(
                self._reconcile_url(), {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id], "confirm": True}
            )
        record_id = json.loads(body)["id"]

        # Simulate restarting the app: re-run schema init (idempotent) and
        # fetch through a brand new sqlite connection, exactly as a fresh
        # process would.
        cross_format_analyses.init_cross_format_analyses_db()
        fetched = cross_format_analyses.get_cross_format_analysis(self.project.id, record_id)
        self.assertIsNotNone(fetched)
        assert fetched is not None
        self.assertEqual(fetched.id, record_id)

    def test_project_isolation_record_from_other_project_is_not_found(self):
        response = fake_response([fake_text_block("## Executive Conclusion\nConsistent.")])
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            status, body = self._post_json(
                self._reconcile_url(), {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id], "confirm": True}
            )
        record_id = json.loads(body)["id"]

        get_status, _ = self._get(f"/api/projects/{self.other_project.id}/reconciliations/{record_id}")
        self.assertEqual(get_status, 404)

    def test_truncated_response_returns_502_via_http(self):
        response = fake_response([fake_text_block("## Executive Conclusion\nPartial")], stop_reason="max_tokens")
        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            status, body = self._post_json(
                self._reconcile_url(), {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id], "confirm": True}
            )

        payload = json.loads(body)
        self.assertEqual(status, 502)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "truncated_response")

    def test_secret_never_appears_in_raw_http_response(self):
        import anthropic
        import httpx2

        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        http_response = httpx2.Response(
            401,
            request=request,
            json={"error": {"type": "authentication_error", "message": f"bad key {FAKE_SECRET}"}},
        )
        error = anthropic.AuthenticationError(
            f"bad key {FAKE_SECRET}", response=http_response, body=http_response.json()
        )
        mock_client = MagicMock()
        mock_client.files.upload.return_value = types.SimpleNamespace(id="file_abc123")
        mock_client.files.delete.return_value = types.SimpleNamespace(id="file_abc123", type="file_deleted")
        mock_client.messages.stream.side_effect = error

        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client):
            status, raw_body = self._post_json(
                self._reconcile_url(), {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id], "confirm": True}
            )

        self.assertEqual(status, 502)
        self.assertNotIn(FAKE_SECRET.encode(), raw_body)

    def test_secret_and_file_bytes_never_appear_in_server_logs(self):
        response = fake_response([fake_text_block("## Executive Conclusion\nA test reconciliation.")])
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("cross_format_analysis.anthropic.Anthropic", return_value=mock_client_for(response)):
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
                self._post_json(
                    self._reconcile_url(), {"document_ids": [self.pdf_doc.id, self.xlsx_doc.id], "confirm": True}
                )

        self.assertNotIn(FAKE_SECRET, captured_stdout.getvalue())
        self.assertNotIn(FAKE_SECRET, captured_stderr.getvalue())
        self.assertNotIn(PDF_BYTES.decode("latin-1"), captured_stdout.getvalue())
        self.assertNotIn(PDF_BYTES.decode("latin-1"), captured_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
