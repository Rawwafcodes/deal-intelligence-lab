"""Integration tests for the PDF-inspection HTTP endpoints: the real server,
with the Anthropic client mocked so no network call is made.
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

import documents
import inspections
import identity
import server
import store

FAKE_SECRET = "sk-ant-api03-INSPECT-ENDPOINT-TEST-FAKE-SECRET-DO-NOT-LEAK"
SAMPLE_PDF_BYTES = b"%PDF-1.4\n%a harmless test pdf\n%%EOF"


def fake_citation(cited_text: str, start_page: int):
    return types.SimpleNamespace(
        type="page_location",
        cited_text=cited_text,
        document_title="sample.pdf",
        start_page_number=start_page,
        end_page_number=start_page,
    )


def fake_text_block(text: str, citations=None):
    return types.SimpleNamespace(type="text", text=text, citations=citations)


def fake_response(content_blocks, stop_reason: str = "end_turn"):
    usage = types.SimpleNamespace(input_tokens=5000, output_tokens=300)
    return types.SimpleNamespace(
        content=content_blocks,
        model="claude-opus-5",
        usage=usage,
        stop_reason=stop_reason,
        stop_details=None,
    )


def mock_stream_client(response):
    mock_client = MagicMock()
    mock_stream = MagicMock()
    mock_stream.get_final_message.return_value = response
    mock_client.messages.stream.return_value.__enter__.return_value = mock_stream
    return mock_client


class InspectEndpointTests(unittest.TestCase):
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
        inspections.init_inspections_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.project = store.create_project("Project Falcon", "test project")
        result = documents.save_uploaded_file(cls.project.id, "sample.pdf", "", SAMPLE_PDF_BYTES)
        assert result.status == "success" and result.document is not None
        cls.document = result.document

        other_project = store.create_project("Project Osprey", "a different project")
        cls.other_project = other_project

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

    def test_confirmation_is_required(self):
        status, body = self._post_json(
            f"/api/projects/{self.project.id}/documents/{self.document.id}/inspect", {"confirm": False}
        )
        self.assertEqual(status, 400)

        status, body = self._post_json(
            f"/api/projects/{self.project.id}/documents/{self.document.id}/inspect", {}
        )
        self.assertEqual(status, 400)

    def test_confirmation_missing_body_is_rejected(self):
        req = urllib.request.Request(
            self._url(f"/api/projects/{self.project.id}/documents/{self.document.id}/inspect"),
            data=b"",
            method="POST",
        )
        try:
            urllib.request.urlopen(req)
            self.fail("expected an HTTPError")
        except urllib.error.HTTPError as exc:
            self.assertEqual(exc.code, 400)

    def test_successful_inspection_via_http(self):
        citation = fake_citation("Revenue grew 12%.", start_page=3)
        block = fake_text_block("Revenue grew 12% year over year.", citations=[citation])
        response = fake_response([block])

        with patch("pdf_inspection.anthropic.Anthropic", return_value=mock_stream_client(response)):
            status, body = self._post_json(
                f"/api/projects/{self.project.id}/documents/{self.document.id}/inspect", {"confirm": True}
            )

        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["transmitted"])
        self.assertEqual(payload["model"], "claude-opus-5")
        self.assertEqual(payload["input_tokens"], 5000)
        self.assertEqual(len(payload["segments"]), 1)
        self.assertEqual(payload["segments"][0]["citations"][0]["start_page"], 3)

        # And the stored record is retrievable afterwards.
        get_status, get_body = self._get(f"/api/projects/{self.project.id}/inspections/{payload['id']}")
        self.assertEqual(get_status, 200)
        self.assertEqual(json.loads(get_body)["id"], payload["id"])

    def _get(self, path: str):
        try:
            res = urllib.request.urlopen(self._url(path))
            return res.status, res.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def test_project_isolation_document_from_other_project_is_not_found(self):
        with patch("pdf_inspection.anthropic.Anthropic") as mock_anthropic:
            status, body = self._post_json(
                f"/api/projects/{self.other_project.id}/documents/{self.document.id}/inspect",
                {"confirm": True},
            )
            mock_anthropic.assert_not_called()

        self.assertEqual(status, 404)

    def test_project_isolation_inspection_record_from_other_project_is_not_found(self):
        citation = fake_citation("Revenue grew 12%.", start_page=3)
        response = fake_response([fake_text_block("Revenue grew 12%.", citations=[citation])])
        with patch("pdf_inspection.anthropic.Anthropic", return_value=mock_stream_client(response)):
            status, body = self._post_json(
                f"/api/projects/{self.project.id}/documents/{self.document.id}/inspect", {"confirm": True}
            )
        inspection_id = json.loads(body)["id"]

        get_status, _ = self._get(f"/api/projects/{self.other_project.id}/inspections/{inspection_id}")
        self.assertEqual(get_status, 404)

    def test_non_pdf_document_is_rejected(self):
        result = documents.save_uploaded_file(self.project.id, "notes.txt", "", b"just text")
        assert result.document is not None
        with patch("pdf_inspection.anthropic.Anthropic") as mock_anthropic:
            status, body = self._post_json(
                f"/api/projects/{self.project.id}/documents/{result.document.id}/inspect", {"confirm": True}
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 400)

    def test_missing_citations_are_empty_via_http(self):
        response = fake_response([fake_text_block("## Summary\nA general uncited summary.")])
        with patch("pdf_inspection.anthropic.Anthropic", return_value=mock_stream_client(response)):
            status, body = self._post_json(
                f"/api/projects/{self.project.id}/documents/{self.document.id}/inspect", {"confirm": True}
            )

        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["segments"][0]["citations"], [])

    def test_truncated_response_returns_502_via_http(self):
        response = fake_response([fake_text_block("## Document Identification\nPartial")], stop_reason="max_tokens")
        with patch("pdf_inspection.anthropic.Anthropic", return_value=mock_stream_client(response)):
            status, body = self._post_json(
                f"/api/projects/{self.project.id}/documents/{self.document.id}/inspect", {"confirm": True}
            )

        payload = json.loads(body)
        self.assertEqual(status, 502)
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["error_type"], "truncated_response")
        self.assertEqual(payload["stop_reason"], "max_tokens")

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
        mock_client.messages.stream.side_effect = error

        with patch("pdf_inspection.anthropic.Anthropic", return_value=mock_client):
            status, raw_body = self._post_json(
                f"/api/projects/{self.project.id}/documents/{self.document.id}/inspect", {"confirm": True}
            )

        self.assertEqual(status, 502)
        self.assertNotIn(FAKE_SECRET.encode(), raw_body)

    def test_secret_and_pdf_bytes_never_appear_in_server_logs(self):
        response = fake_response([fake_text_block("## Document Identification\nA test document.")])
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("pdf_inspection.anthropic.Anthropic", return_value=mock_stream_client(response)):
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
                self._post_json(
                    f"/api/projects/{self.project.id}/documents/{self.document.id}/inspect", {"confirm": True}
                )

        self.assertNotIn(FAKE_SECRET, captured_stdout.getvalue())
        self.assertNotIn(FAKE_SECRET, captured_stderr.getvalue())
        self.assertNotIn(SAMPLE_PDF_BYTES.decode("latin-1"), captured_stdout.getvalue())
        self.assertNotIn(SAMPLE_PDF_BYTES.decode("latin-1"), captured_stderr.getvalue())

    def test_unknown_document_is_not_found(self):
        with patch("pdf_inspection.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                f"/api/projects/{self.project.id}/documents/does-not-exist/inspect", {"confirm": True}
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
