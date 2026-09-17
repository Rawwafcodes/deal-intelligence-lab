"""Integration tests for the workbook-inspection HTTP endpoints: the real
server, with the Anthropic client mocked so no network call is made.
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
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import openpyxl

import documents
import identity
import server
import store
import xlsx_inspections

FAKE_SECRET = "sk-ant-api03-XLSX-ENDPOINT-TEST-FAKE-SECRET-DO-NOT-LEAK"


def build_sample_workbook(path: Path) -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "Revenue Model"
    ws["B7"] = 100
    wb.save(path)
    return path.read_bytes()


def fake_text_block(text: str):
    return types.SimpleNamespace(type="text", text=text)


def fake_response(content_blocks, stop_reason: str = "end_turn"):
    usage = types.SimpleNamespace(
        input_tokens=4000, output_tokens=800, server_tool_use=types.SimpleNamespace(code_execution_requests=2)
    )
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


class XlsxInspectEndpointTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread
    project: store.Project

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_data_dir = documents.DATA_DIR
        documents.DATA_DIR = Path(cls._tmpdir.name) / "DealLabData"
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()
        documents.init_documents_db()
        xlsx_inspections.init_xlsx_inspections_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.project = store.create_project("Project Falcon", "test project")
        workbook_bytes = build_sample_workbook(Path(cls._tmpdir.name) / "model.xlsx")
        result = documents.save_uploaded_file(cls.project.id, "model.xlsx", "", workbook_bytes)
        assert result.status == "success" and result.document is not None
        cls.document = result.document

        cls.other_project = store.create_project("Project Osprey", "a different project")

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)
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

    def _inspect_url(self, project_id: str, document_id: str) -> str:
        return f"/api/projects/{project_id}/documents/{document_id}/inspect-workbook"

    def test_confirmation_is_required(self):
        status, _ = self._post_json(self._inspect_url(self.project.id, self.document.id), {"confirm": False})
        self.assertEqual(status, 400)

        status, _ = self._post_json(self._inspect_url(self.project.id, self.document.id), {})
        self.assertEqual(status, 400)

    def test_non_workbook_document_is_rejected(self):
        result = documents.save_uploaded_file(self.project.id, "notes.txt", "", b"just text")
        assert result.document is not None
        with patch("xlsx_inspection.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                self._inspect_url(self.project.id, result.document.id), {"confirm": True}
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 400)

    def test_successful_inspection_via_http(self):
        text = "Revenue is 100 ('Revenue Model'!B7 [value])."
        response = fake_response([fake_text_block(text)])

        with patch("xlsx_inspection.anthropic.Anthropic", return_value=mock_client_for(response)):
            status, body = self._post_json(self._inspect_url(self.project.id, self.document.id), {"confirm": True})

        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["transmitted"])
        self.assertTrue(payload["remote_cleanup_attempted"])
        self.assertTrue(payload["remote_cleanup_succeeded"])
        self.assertTrue(payload["verification_available"])
        self.assertEqual(payload["document_checksum"], self.document.sha256)
        citation_segments = [s for s in payload["segments"] if s["type"] == "citation"]
        self.assertEqual(len(citation_segments), 1)
        self.assertTrue(citation_segments[0]["citation"]["exists"])

        get_status, get_body = self._get(f"/api/projects/{self.project.id}/workbook-inspections/{payload['id']}")
        self.assertEqual(get_status, 200)
        self.assertEqual(json.loads(get_body)["id"], payload["id"])

    def test_project_isolation_document_from_other_project_is_not_found(self):
        with patch("xlsx_inspection.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                self._inspect_url(self.other_project.id, self.document.id), {"confirm": True}
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 404)

    def test_project_isolation_record_from_other_project_is_not_found(self):
        response = fake_response([fake_text_block("## Workbook Identification and Purpose\nA model.")])
        with patch("xlsx_inspection.anthropic.Anthropic", return_value=mock_client_for(response)):
            status, body = self._post_json(self._inspect_url(self.project.id, self.document.id), {"confirm": True})
        inspection_id = json.loads(body)["id"]

        get_status, _ = self._get(f"/api/projects/{self.other_project.id}/workbook-inspections/{inspection_id}")
        self.assertEqual(get_status, 404)

    def test_truncated_response_returns_502_via_http(self):
        response = fake_response(
            [fake_text_block("## Workbook Identification and Purpose\nPartial")], stop_reason="max_tokens"
        )
        with patch("xlsx_inspection.anthropic.Anthropic", return_value=mock_client_for(response)):
            status, body = self._post_json(self._inspect_url(self.project.id, self.document.id), {"confirm": True})

        payload = json.loads(body)
        self.assertEqual(status, 502)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "truncated_response")

    def test_unknown_document_is_not_found(self):
        with patch("xlsx_inspection.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                self._inspect_url(self.project.id, "does-not-exist"), {"confirm": True}
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 404)

    def test_secret_and_workbook_bytes_never_appear_in_server_logs(self):
        response = fake_response([fake_text_block("## Workbook Identification and Purpose\nA model.")])
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("xlsx_inspection.anthropic.Anthropic", return_value=mock_client_for(response)):
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
                self._post_json(self._inspect_url(self.project.id, self.document.id), {"confirm": True})

        self.assertNotIn(FAKE_SECRET, captured_stdout.getvalue())
        self.assertNotIn(FAKE_SECRET, captured_stderr.getvalue())

    def test_secret_never_appears_in_raw_http_response(self):
        import anthropic
        import httpx2

        request = httpx2.Request("POST", "https://api.anthropic.com/v1/files")
        http_response = httpx2.Response(
            401,
            request=request,
            json={"error": {"type": "authentication_error", "message": f"bad key {FAKE_SECRET}"}},
        )
        error = anthropic.AuthenticationError(
            f"bad key {FAKE_SECRET}", response=http_response, body=http_response.json()
        )
        mock_client = MagicMock()
        mock_client.files.upload.side_effect = error

        with patch("xlsx_inspection.anthropic.Anthropic", return_value=mock_client):
            status, raw_body = self._post_json(self._inspect_url(self.project.id, self.document.id), {"confirm": True})

        self.assertEqual(status, 502)
        self.assertNotIn(FAKE_SECRET.encode(), raw_body)


if __name__ == "__main__":
    unittest.main()
