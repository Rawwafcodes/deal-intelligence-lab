"""Tests for anthropic_errors.py. Regression coverage for a real bug found
via live testing: Anthropic represents "out of credit" both as a dedicated
402/"billing_error" and - confirmed against a real out-of-credit account -
as a plain 400 "invalid_request_error" whose message reads "Your credit
balance is too low...". The status_code/type-only check used to miss the
second shape entirely.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic
import httpx2

from anthropic_errors import is_insufficient_credit_error


def make_status_error(cls, status_code: int, error_type: str, message: str):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx2.Response(
        status_code, request=request, json={"error": {"type": error_type, "message": message}}
    )
    return cls(message, response=response, body=response.json())


class AnthropicErrorsTests(unittest.TestCase):
    def test_dedicated_402_billing_error_is_recognized(self):
        error = make_status_error(anthropic.APIStatusError, 402, "billing_error", "credit balance too low")
        self.assertTrue(is_insufficient_credit_error(error))

    def test_real_world_400_invalid_request_shape_is_recognized(self):
        # The exact status/type/message combination observed live against a
        # genuinely out-of-credit account.
        error = make_status_error(
            anthropic.APIStatusError,
            400,
            "invalid_request_error",
            "Your credit balance is too low to access the Anthropic API. "
            "Please go to Plans & Billing to upgrade or purchase credits.",
        )
        self.assertTrue(is_insufficient_credit_error(error))

    def test_unrelated_400_is_not_misclassified(self):
        error = make_status_error(anthropic.APIStatusError, 400, "invalid_request_error", "max_tokens is too large")
        self.assertFalse(is_insufficient_credit_error(error))

    def test_unrelated_404_is_not_misclassified(self):
        error = make_status_error(anthropic.NotFoundError, 404, "not_found_error", "model: bogus not found")
        self.assertFalse(is_insufficient_credit_error(error))


if __name__ == "__main__":
    unittest.main()
