"""Tests for mandate_planning.py (Task 12.4). The real Anthropic client is
always mocked here - these tests never make a network call or consume API
credit, the same convention tests/test_cross_format_analysis.py and
tests/test_ai_endpoint.py already use for their own AI-calling modules.

mandate_planning.py is a pure function of its inputs (no database access at
all) - see its own module docstring - so these tests exercise it directly,
with no project/document fixtures. mandates.propose_plan_llm's own
independent re-verification of a candidate plan (document existence,
project scoping, validate_selection, the untrusted-plan validator) is
covered separately in tests/test_mandates.py::LlmPlanningTests, where a real
project/document set actually exists to verify against.
"""

import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
import httpx2

import mandate_planning

FAKE_SECRET = "sk-ant-api03-MANDATE-PLANNING-TEST-FAKE-SECRET-DO-NOT-LEAK"


def make_status_error(cls, status_code: int, error_type: str, message: str, path: str = "/v1/messages"):
    request = httpx2.Request("POST", f"https://api.anthropic.com{path}")
    response = httpx2.Response(
        status_code, request=request, json={"error": {"type": error_type, "message": message}}
    )
    return cls(message, response=response, body=response.json())


def fake_response(payload: dict, model: str = "claude-sonnet-5", in_tok: int = 800, out_tok: int = 120,
                   stop_reason: str = "end_turn"):
    text_block = types.SimpleNamespace(type="text", text=json.dumps(payload))
    usage = types.SimpleNamespace(input_tokens=in_tok, output_tokens=out_tok)
    return types.SimpleNamespace(content=[text_block], model=model, usage=usage, stop_reason=stop_reason)


DOC = mandate_planning.DocumentSummary(id="doc-1", original_filename="term_sheet.pdf", extension=".pdf")
TEMPLATE = mandate_planning.TemplateSummary(
    key="reconciliation", name="Cross-format reconciliation", description="Reconcile PDFs against Excel.",
    needs_documents=True,
)


class MandatePlanningTests(unittest.TestCase):
    def setUp(self):
        self._env_patcher = patch.dict(
            "os.environ", {"ANTHROPIC_API_KEY": FAKE_SECRET, "ANTHROPIC_MODEL": ""}
        )
        self._env_patcher.start()

    def tearDown(self):
        self._env_patcher.stop()

    def _mock_client(self, create_return=None, create_side_effect=None):
        mock_client = MagicMock()
        if create_side_effect is not None:
            mock_client.messages.create.side_effect = create_side_effect
        else:
            mock_client.messages.create.return_value = create_return
        return patch("mandate_planning.anthropic.Anthropic", return_value=mock_client), mock_client

    # -- missing key, never reaches the network at all -----------------

    def test_missing_api_key_never_calls_the_client(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": ""}):
            with patch("mandate_planning.anthropic.Anthropic") as mock_ctor:
                outcome = mandate_planning.propose_candidate_plan("Assess the deal", [DOC], [TEMPLATE])
        mock_ctor.assert_not_called()
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "missing_api_key")

    # -- a well-formed "proposed" reply ---------------------------------

    def test_proposed_reply_is_parsed(self):
        payload = {
            "status": "proposed", "template_key": "reconciliation", "document_ids": ["doc-1", "doc-2"],
            "reasoning": "Clear PDF/Excel pair for the term sheet.", "unsupported_reason": None,
        }
        patcher, mock_client = self._mock_client(create_return=fake_response(payload))
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Reconcile the term sheet", [DOC], [TEMPLATE])

        self.assertEqual(outcome.status, "proposed")
        self.assertEqual(outcome.template_key, "reconciliation")
        self.assertEqual(outcome.document_ids, ["doc-1", "doc-2"])
        self.assertEqual(outcome.reasoning, "Clear PDF/Excel pair for the term sheet.")
        self.assertEqual(outcome.model, "claude-sonnet-5")
        self.assertEqual(outcome.usage, {"input_tokens": 800, "output_tokens": 120})

        # The structured-output schema was actually requested, not just
        # asked for in prose - docs/04: "Use schema validation where
        # provider features allow it."
        kwargs = mock_client.messages.create.call_args.kwargs
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(kwargs["output_config"]["format"]["schema"], mandate_planning.PLAN_PROPOSAL_SCHEMA)
        self.assertEqual(kwargs["model"], mandate_planning.DEFAULT_MODEL)

        # The objective, template, and document metadata actually reached
        # the prompt - never file content, only the id/filename/extension
        # DocumentSummary carries.
        prompt = kwargs["messages"][0]["content"]
        self.assertIn("Reconcile the term sheet", prompt)
        self.assertIn("doc-1", prompt)
        self.assertIn("term_sheet.pdf", prompt)
        self.assertIn("reconciliation", prompt)

    def test_env_model_override_is_respected(self):
        payload = {"status": "unsupported", "template_key": None, "document_ids": [],
                   "reasoning": "n/a", "unsupported_reason": "no matching capability"}
        patcher, mock_client = self._mock_client(create_return=fake_response(payload, model="claude-opus-5"))
        with patch.dict("os.environ", {"ANTHROPIC_MODEL": "claude-opus-5"}), patcher:
            mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(mock_client.messages.create.call_args.kwargs["model"], "claude-opus-5")

    def test_feedback_is_included_in_the_prompt(self):
        payload = {"status": "unsupported", "template_key": None, "document_ids": [],
                   "reasoning": "n/a", "unsupported_reason": "still ambiguous"}
        patcher, mock_client = self._mock_client(create_return=fake_response(payload))
        with patcher:
            mandate_planning.propose_candidate_plan(
                "Reconcile the deal", [DOC], [TEMPLATE], feedback="Use the Q3 workbook, not Q2."
            )
        prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        self.assertIn("Use the Q3 workbook, not Q2.", prompt)

    # -- a well-formed "unsupported" reply -------------------------------

    def test_unsupported_reply_is_parsed(self):
        payload = {
            "status": "unsupported", "template_key": None, "document_ids": [],
            "reasoning": "Five PDFs and three workbooks; no unambiguous pair.",
            "unsupported_reason": "ambiguous document pairing",
        }
        patcher, _ = self._mock_client(create_return=fake_response(payload))
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Reconcile something", [DOC], [TEMPLATE])
        self.assertEqual(outcome.status, "unsupported")
        self.assertIsNone(outcome.template_key)
        self.assertEqual(outcome.document_ids, [])
        self.assertEqual(outcome.unsupported_reason, "ambiguous document pairing")

    # -- malformed replies never crash, and are never trusted ------------

    def test_non_json_reply_is_an_error(self):
        text_block = types.SimpleNamespace(type="text", text="Sure, here is my plan: reconcile the documents.")
        response = types.SimpleNamespace(
            content=[text_block], model="claude-sonnet-5",
            usage=types.SimpleNamespace(input_tokens=10, output_tokens=10), stop_reason="end_turn",
        )
        patcher, _ = self._mock_client(create_return=response)
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "invalid_reply")

    def test_reply_with_invalid_status_value_is_an_error(self):
        # Schema validation on the provider side should make this
        # unreachable, but this module trusts nothing about the reply's
        # *content* just because JSON parsing succeeded.
        payload = {"status": "yes_probably", "template_key": "reconciliation", "document_ids": [],
                   "reasoning": "x", "unsupported_reason": None}
        patcher, _ = self._mock_client(create_return=fake_response(payload))
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "invalid_reply")

    def test_malformed_document_ids_defaults_to_empty_list(self):
        payload = {"status": "proposed", "template_key": "reconciliation", "document_ids": "doc-1",
                   "reasoning": "x", "unsupported_reason": None}
        patcher, _ = self._mock_client(create_return=fake_response(payload))
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [DOC], [TEMPLATE])
        self.assertEqual(outcome.document_ids, [])

    def test_max_tokens_stop_is_an_error(self):
        payload_text = json.dumps({"status": "proposed", "template_key": "reconciliation"})[:-1]  # truncated
        text_block = types.SimpleNamespace(type="text", text=payload_text)
        response = types.SimpleNamespace(
            content=[text_block], model="claude-sonnet-5",
            usage=types.SimpleNamespace(input_tokens=10, output_tokens=10), stop_reason="max_tokens",
        )
        patcher, _ = self._mock_client(create_return=response)
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "invalid_reply")

    def test_empty_reply_is_an_error(self):
        response = types.SimpleNamespace(
            content=[], model="claude-sonnet-5",
            usage=types.SimpleNamespace(input_tokens=10, output_tokens=0), stop_reason="end_turn",
        )
        patcher, _ = self._mock_client(create_return=response)
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "invalid_reply")

    # -- provider error taxonomy, mirroring ai_client.py's own -----------

    def test_authentication_error(self):
        error = make_status_error(anthropic.AuthenticationError, 401, "authentication_error", "bad key")
        patcher, _ = self._mock_client(create_side_effect=error)
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "invalid_api_key")

    def test_not_found_error(self):
        error = make_status_error(anthropic.NotFoundError, 404, "not_found_error", "no such model")
        patcher, _ = self._mock_client(create_side_effect=error)
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "model_unavailable")

    def test_rate_limit_error(self):
        error = make_status_error(anthropic.RateLimitError, 429, "rate_limit_error", "slow down")
        patcher, _ = self._mock_client(create_side_effect=error)
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "rate_limit")

    def test_insufficient_credit_error(self):
        error = make_status_error(
            anthropic.APIStatusError, 400, "invalid_request_error",
            "Your credit balance is too low to access the Anthropic API.",
        )
        patcher, _ = self._mock_client(create_side_effect=error)
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "insufficient_credit")

    def test_generic_api_status_error(self):
        error = make_status_error(anthropic.APIStatusError, 500, "api_error", "server exploded")
        patcher, _ = self._mock_client(create_side_effect=error)
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "unexpected_error")

    def test_connection_error(self):
        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        error = anthropic.APIConnectionError(message="could not connect", request=request)
        patcher, _ = self._mock_client(create_side_effect=error)
        with patcher:
            outcome = mandate_planning.propose_candidate_plan("Assess the deal", [], [TEMPLATE])
        self.assertEqual(outcome.status, "error")
        self.assertEqual(outcome.error_type, "network_error")


if __name__ == "__main__":
    unittest.main()
