"""Integration tests for the /api/ai/test-connection endpoint: the real HTTP
server, with the Anthropic client mocked so no network call is made.
"""

import contextlib
import io
import json
import sys
import threading
import types
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
import httpx2

import ai_client
import server

FAKE_SECRET = "sk-ant-api03-ENDPOINT-TEST-FAKE-SECRET-DO-NOT-LEAK"


def fake_text_response(text: str):
    block = types.SimpleNamespace(type="text", text=text)
    usage = types.SimpleNamespace(input_tokens=9, output_tokens=3)
    return types.SimpleNamespace(content=[block], model="claude-opus-5", usage=usage)


def make_status_error(cls, status_code: int, error_type: str, message: str):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(
        status_code, request=request, json={"error": {"type": error_type, "message": message}}
    )
    return cls(message, response=response, body=response.json())


class AiEndpointTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread

    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def setUp(self):
        self._env_patcher = patch.dict(
            "os.environ", {"ANTHROPIC_API_KEY": FAKE_SECRET, "ANTHROPIC_MODEL": "claude-opus-5"}
        )
        self._env_patcher.start()

    def tearDown(self):
        self._env_patcher.stop()

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def _post_test_connection(self):
        req = urllib.request.Request(self._url("/api/ai/test-connection"), data=b"", method="POST")
        try:
            res = urllib.request.urlopen(req)
            return res.status, res.read()
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read()

    def test_successful_connection_via_http(self):
        response = fake_text_response("DEAL_LAB_CONNECTED")
        with patch("ai_client.anthropic.Anthropic", return_value=MagicMock(**{"messages.create.return_value": response})):
            status, body = self._post_test_connection()

        payload = json.loads(body)
        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["model"], "claude-opus-5")
        self.assertTrue(payload["matched_expected"])

    def test_failure_returns_502_with_error_type(self):
        error = make_status_error(anthropic.RateLimitError, 429, "rate_limit_error", "slow down")
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = error
        with patch("ai_client.anthropic.Anthropic", return_value=mock_client):
            status, body = self._post_test_connection()

        payload = json.loads(body)
        self.assertEqual(status, 502)
        self.assertFalse(payload["success"])
        self.assertEqual(payload["error_type"], "rate_limit")

    def test_secret_never_appears_in_raw_http_response(self):
        error = make_status_error(
            anthropic.AuthenticationError, 401, "authentication_error", f"bad key {FAKE_SECRET}"
        )
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = error
        with patch("ai_client.anthropic.Anthropic", return_value=mock_client):
            status, raw_body = self._post_test_connection()

        self.assertNotIn(FAKE_SECRET.encode(), raw_body)

    def test_secret_never_appears_in_server_logs(self):
        response = fake_text_response("DEAL_LAB_CONNECTED")
        captured_stdout = io.StringIO()
        captured_stderr = io.StringIO()

        with patch("ai_client.anthropic.Anthropic", return_value=MagicMock(**{"messages.create.return_value": response})):
            with contextlib.redirect_stdout(captured_stdout), contextlib.redirect_stderr(captured_stderr):
                self._post_test_connection()

        self.assertNotIn(FAKE_SECRET, captured_stdout.getvalue())
        self.assertNotIn(FAKE_SECRET, captured_stderr.getvalue())

    def test_missing_api_key_via_http(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            status, body = self._post_test_connection()

        payload = json.loads(body)
        self.assertEqual(status, 502)
        self.assertEqual(payload["error_type"], "missing_api_key")


if __name__ == "__main__":
    unittest.main()
