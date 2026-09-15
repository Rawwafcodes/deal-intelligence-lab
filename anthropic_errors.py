"""Shared classification helpers for Anthropic API errors, used by every
*_client.py / *_inspection.py module in this app so a fix in how we
recognize a given failure only has to happen once.
"""

from __future__ import annotations

import anthropic


def is_insufficient_credit_error(exc: anthropic.APIStatusError) -> bool:
    """Anthropic represents "out of credit" inconsistently: sometimes as a
    dedicated 402 with error type "billing_error", but confirmed live
    against a real out-of-credit account, also as a plain 400
    "invalid_request_error" whose message reads "Your credit balance is
    too low to access the Anthropic API...". Checking status_code/type
    alone missed that second shape and surfaced it as a generic,
    unhelpful "unexpected_error" instead - so this also matches on the
    message text Anthropic actually uses for this condition.
    """
    if exc.status_code == 402 or getattr(exc, "type", None) == "billing_error":
        return True
    message = str(getattr(exc, "message", "") or "").lower()
    return "credit balance" in message
