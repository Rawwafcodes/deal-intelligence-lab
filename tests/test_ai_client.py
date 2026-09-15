"""Tests for ai_client.py. The real Anthropic client is always mocked here -
these tests never make a network call or consume API credit.
"""

import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
import httpx2

import ai_client

FAKE_SECRET = "sk-ant-api03-TOTALLY-FAKE-SECRET-VALUE-DO-NOT-LEAK"


def make_status_error(cls, status_code: int, error_type: str, message: str):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(
        status_code, request=request, json={"error": {"type": error_type, "message": message}}
    )
    return cls(message, response=response, body=response.json())


def make_connection_error(message: str) -> anthropic.APIConnectionError:
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return anthropic.APIConnectionError(message=message, request=request)


def fake_response(
    content_blocks,
    model: str = "claude-opus-5",
    in_tok: int = 12,
    out_tok: int = 5,
    stop_reason: str = "end_turn",
):
    usage = types.SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok)
    return types.SimpleNamespace(content=content_blocks, model=model, usage=usage, stop_reason=stop_reason)


def fake_text_response(text: str, **kwargs):
    block = types.SimpleNamespace(type="text", text=text)
    return fake_response([block], **kwargs)


def fake_thinking_block(text: str = ""):
    return types.SimpleNamespace(type="thinking", thinking=text)


def fake_text_block(text: str):
    return types.SimpleNamespace(type="text", text=text)


class AiClientTests(unittest.TestCase):
    def setUp(self):
        self._env_patcher = patch.dict(
            "os.environ", {"ANTHROPIC_API_KEY": FAKE_SECRET, "ANTHROPIC_MODEL": "claude-opus-5"}
        )
        self._env_patcher.start()

    def tearDown(self):
        self._env_patcher.stop()

    def _mock_client(self, create_side_effect=None, create_return_value=None):
        mock_client = MagicMock()
        if create_side_effect is not None:
            mock_client.messages.create.side_effect = create_side_effect
        else:
            mock_client.messages.create.return_value = create_return_value
        return patch("ai_client.anthropic.Anthropic", return_value=mock_client)

    def test_missing_api_key(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            result = ai_client.test_connection()
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "missing_api_key")

    def test_successful_connection(self):
        response = fake_text_response("DEAL_LAB_CONNECTED")
        with self._mock_client(create_return_value=response):
            result = ai_client.test_connection()

        self.assertTrue(result.success)
        self.assertEqual(result.model, "claude-opus-5")
        self.assertTrue(result.matched_expected)
        self.assertEqual(result.usage, {"input_tokens": 12, "output_tokens": 5})

    def test_unexpected_reply_text_is_reported_but_not_a_failure(self):
        response = fake_text_response("something else entirely")
        with self._mock_client(create_return_value=response):
            result = ai_client.test_connection()

        self.assertTrue(result.success)
        self.assertFalse(result.matched_expected)
        self.assertEqual(result.reply_text, "something else entirely")

    def test_reply_split_across_multiple_text_blocks_is_combined(self):
        # A thinking block (empty .thinking text, since display defaults to
        # "omitted") followed by the reply split across two text blocks.
        response = fake_response(
            [fake_thinking_block(), fake_text_block("DEAL_LAB_"), fake_text_block("CONNECTED")]
        )
        with self._mock_client(create_return_value=response):
            result = ai_client.test_connection()

        self.assertTrue(result.success)
        self.assertEqual(result.reply_text, "DEAL_LAB_CONNECTED")
        self.assertTrue(result.matched_expected)

    def test_max_tokens_truncation_is_a_failure_not_a_success(self):
        # Reproduces the original bug report: thinking ate most of a tight
        # max_tokens budget, leaving only a partial reply.
        response = fake_response(
            [fake_thinking_block(), fake_text_block("DEA")],
            out_tok=20,
            stop_reason="max_tokens",
        )
        with self._mock_client(create_return_value=response):
            result = ai_client.test_connection()

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "truncated_response")
        self.assertEqual(result.stop_reason, "max_tokens")
        # The partial text is preserved for diagnosis, not hidden.
        self.assertEqual(result.reply_text, "DEA")

    def test_empty_response_is_a_failure(self):
        response = fake_response([fake_thinking_block()], stop_reason="end_turn")
        with self._mock_client(create_return_value=response):
            result = ai_client.test_connection()

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "empty_response")
        self.assertEqual(result.reply_text, "")

    def test_invalid_api_key(self):
        error = make_status_error(anthropic.AuthenticationError, 401, "authentication_error", "invalid x-api-key")
        with self._mock_client(create_side_effect=error):
            result = ai_client.test_connection()

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "invalid_api_key")

    def test_insufficient_credit(self):
        error = make_status_error(anthropic.APIStatusError, 402, "billing_error", "credit balance too low")
        with self._mock_client(create_side_effect=error):
            result = ai_client.test_connection()

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "insufficient_credit")

    def test_rate_limit(self):
        error = make_status_error(anthropic.RateLimitError, 429, "rate_limit_error", "slow down")
        with self._mock_client(create_side_effect=error):
            result = ai_client.test_connection()

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "rate_limit")

    def test_network_failure(self):
        error = make_connection_error("Connection error.")
        with self._mock_client(create_side_effect=error):
            result = ai_client.test_connection()

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "network_error")

    def test_model_unavailable(self):
        error = make_status_error(anthropic.NotFoundError, 404, "not_found_error", "model: bogus-model not found")
        with self._mock_client(create_side_effect=error):
            result = ai_client.test_connection()

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "model_unavailable")

    def test_generic_api_status_error(self):
        error = make_status_error(anthropic.APIStatusError, 400, "invalid_request_error", "bad request shape")
        with self._mock_client(create_side_effect=error):
            result = ai_client.test_connection()

        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "unexpected_error")

    def test_secret_never_appears_in_any_result_field(self):
        # Simulate an SDK error message that happens to echo the key back -
        # ai_client must redact it regardless of where it came from.
        error = make_status_error(
            anthropic.AuthenticationError, 401, "authentication_error", f"invalid api key: {FAKE_SECRET}"
        )
        with self._mock_client(create_side_effect=error):
            result = ai_client.test_connection()

        result_dict = result.to_dict()
        for value in result_dict.values():
            self.assertNotIn(FAKE_SECRET, str(value))

    def test_request_uses_generous_max_tokens_and_low_effort(self):
        # Regression guard for the original bug: max_tokens=20 left almost no
        # room once thinking (on by default on Claude Opus 5) was billed
        # against it. Both the headroom and the effort cap must hold.
        response = fake_text_response("DEAL_LAB_CONNECTED")
        mock_client = MagicMock()
        mock_client.messages.create.return_value = response
        with patch("ai_client.anthropic.Anthropic", return_value=mock_client):
            ai_client.test_connection()

        _, kwargs = mock_client.messages.create.call_args
        self.assertGreaterEqual(kwargs["max_tokens"], 256)
        self.assertEqual(kwargs["output_config"], {"effort": "low"})

    def test_successful_result_dict_never_contains_secret(self):
        response = fake_text_response("DEAL_LAB_CONNECTED")
        with self._mock_client(create_return_value=response):
            result = ai_client.test_connection()

        for value in result.to_dict().values():
            self.assertNotIn(FAKE_SECRET, str(value))


if __name__ == "__main__":
    unittest.main()
