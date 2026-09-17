"""Integration tests for the cross-document-analysis HTTP endpoints: the
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
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import cross_analyses
import documents
import identity
import server
import store

FAKE_SECRET = "sk-ant-api03-CROSS-ANALYSIS-ENDPOINT-TEST-FAKE-SECRET-DO-NOT-LEAK"
DOC_A_BYTES = b"%PDF-1.4\n%NDA document, harmless test bytes\n%%EOF"
DOC_B_BYTES = b"%PDF-1.4\n%Term sheet document, harmless test bytes\n%%EOF"


def fake_citation(cited_text: str, document_index: int, start_page: int, document_title: str = "doc.pdf"):
    return types.SimpleNamespace(
        type="page_location",
        cited_text=cited_text,
        document_index=document_index,
        document_title=document_title,
        start_page_number=start_page,
        end_page_number=start_page,
    )


def fake_text_block(text: str, citations=None):
    return types.SimpleNamespace(type="text", text=text, citations=citations)


def fake_response(content_blocks, stop_reason: str = "end_turn"):
    usage = types.SimpleNamespace(input_tokens=8000, output_tokens=1200)
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


class CrossAnalysisEndpointTests(unittest.TestCase):
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
        cross_analyses.init_cross_analyses_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

        cls.project = store.create_project("Project Falcon", "test project")
        result_a = documents.save_uploaded_file(cls.project.id, "nda.pdf", "", DOC_A_BYTES)
        result_b = documents.save_uploaded_file(cls.project.id, "term_sheet.pdf", "", DOC_B_BYTES)
        assert result_a.status == "success" and result_a.document is not None
        assert result_b.status == "success" and result_b.document is not None
        cls.doc_a = result_a.document
        cls.doc_b = result_b.document

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

    def _cross_analysis_url(self) -> str:
        return f"/api/projects/{self.project.id}/cross-analysis"

    def test_confirmation_is_required(self):
        status, _ = self._post_json(
            self._cross_analysis_url(), {"document_ids": [self.doc_a.id, self.doc_b.id], "confirm": False}
        )
        self.assertEqual(status, 400)

        status, _ = self._post_json(self._cross_analysis_url(), {"document_ids": [self.doc_a.id, self.doc_b.id]})
        self.assertEqual(status, 400)

    def test_document_ids_must_be_a_list_of_strings(self):
        status, _ = self._post_json(self._cross_analysis_url(), {"document_ids": "not-a-list", "confirm": True})
        self.assertEqual(status, 400)

        status, _ = self._post_json(self._cross_analysis_url(), {"document_ids": [1, 2], "confirm": True})
        self.assertEqual(status, 400)

    def test_duplicate_document_selection_is_rejected(self):
        with patch("cross_document_analysis.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                self._cross_analysis_url(),
                {"document_ids": [self.doc_a.id, self.doc_a.id], "confirm": True},
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 400)

    def test_unknown_document_id_is_not_found(self):
        with patch("cross_document_analysis.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                self._cross_analysis_url(),
                {"document_ids": [self.doc_a.id, "does-not-exist"], "confirm": True},
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 404)

    def test_successful_cross_analysis_via_http(self):
        citation_a = fake_citation("NDA clause", document_index=0, start_page=2, document_title="nda.pdf")
        citation_b = fake_citation("Term sheet clause", document_index=1, start_page=5, document_title="term_sheet.pdf")
        block = fake_text_block(
            "The NDA and term sheet appear to conflict on this point.", citations=[citation_a, citation_b]
        )
        response = fake_response([block])

        with patch("cross_document_analysis.anthropic.Anthropic", return_value=mock_stream_client(response)):
            status, body = self._post_json(
                self._cross_analysis_url(),
                {"document_ids": [self.doc_a.id, self.doc_b.id], "confirm": True},
            )

        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "success")
        self.assertTrue(payload["transmitted"])
        self.assertEqual(payload["document_ids"], [self.doc_a.id, self.doc_b.id])
        self.assertEqual(payload["document_filenames"], ["nda.pdf", "term_sheet.pdf"])
        self.assertEqual(payload["document_checksums"], [self.doc_a.sha256, self.doc_b.sha256])
        self.assertEqual(payload["input_tokens"], 8000)
        citations = payload["segments"][0]["citations"]
        self.assertEqual(citations[0]["document_id"], self.doc_a.id)
        self.assertEqual(citations[1]["document_id"], self.doc_b.id)

        get_status, get_body = self._get(f"/api/projects/{self.project.id}/cross-analyses/{payload['id']}")
        self.assertEqual(get_status, 200)
        self.assertEqual(json.loads(get_body)["id"], payload["id"])

    def test_project_isolation_documents_from_other_project_are_not_found(self):
        with patch("cross_document_analysis.anthropic.Anthropic") as mock_anthropic:
            status, _ = self._post_json(
                f"/api/projects/{self.other_project.id}/cross-analysis",
                {"document_ids": [self.doc_a.id, self.doc_b.id], "confirm": True},
            )
            mock_anthropic.assert_not_called()
        self.assertEqual(status, 404)

    def test_project_isolation_record_from_other_project_is_not_found(self):
        block = fake_text_block("## Combined Document Understanding\nBoth relate.")
        response = fake_response([block])
        with patch("cross_document_analysis.anthropic.Anthropic", return_value=mock_stream_client(response)):
            status, body = self._post_json(
                self._cross_analysis_url(),
                {"document_ids": [self.doc_a.id, self.doc_b.id], "confirm": True},
            )
        analysis_id = json.loads(body)["id"]

        get_status, _ = self._get(f"/api/projects/{self.other_project.id}/cross-analyses/{analysis_id}")
        self.assertEqual(get_status, 404)

    def test_truncated_response_returns_502_via_http(self):
        block = fake_text_block("## Combined Document Understanding\nPartial")
        response = fake_response([block], stop_reason="max_tokens")
        with patch("cross_document_analysis.anthropic.Anthropic", return_value=mock_stream_client(response)):
            status, body = self._post_json(
                self._cross_analysis_url(),
                {"document_ids": [self.doc_a.id, self.doc_b.id], "confirm": True},
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
        mock_client.messages.stream.side_effect = error

        with patch("cross_document_analysis.anthropic.Anthropic", return_value=mock_client):
            status, raw_body = self._post_json(
                self._cross_analysis_url(),
                {"document_ids": [self.doc_a.id, self.doc_b.id], "confirm": True},
            )

        self.assertEqual(status, 502)
        self.assertNotIn(FAKE_SECRET.encode(), raw_body)

    def test_secret_and_pdf_bytes_never_appear_in_server_logs(self):
        block = fake_text_block("## Combined Document Understanding\nA test document pair.")
        response = fake_response([block])
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("cross_document_analysis.anthropic.Anthropic", return_value=mock_stream_client(response)):
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
                self._post_json(
                    self._cross_analysis_url(),
                    {"document_ids": [self.doc_a.id, self.doc_b.id], "confirm": True},
                )

        self.assertNotIn(FAKE_SECRET, captured_stdout.getvalue())
        self.assertNotIn(FAKE_SECRET, captured_stderr.getvalue())
        self.assertNotIn(DOC_A_BYTES.decode("latin-1"), captured_stdout.getvalue())
        self.assertNotIn(DOC_B_BYTES.decode("latin-1"), captured_stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
