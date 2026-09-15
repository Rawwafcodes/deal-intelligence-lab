"""Minimal Anthropic API connection test.

Scope is deliberately narrow: this only checks that the app can reach the
Claude API with the configured key and model. It never sends uploaded
documents, and never returns, prints, or logs the API key itself.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import anthropic
from dotenv import load_dotenv

from anthropic_errors import is_insufficient_credit_error

load_dotenv(Path(__file__).parent / ".env.local")

DEFAULT_MODEL = "claude-opus-5"
EXPECTED_REPLY = "DEAL_LAB_CONNECTED"

# Generous headroom even though the expected reply is short: on current
# models (e.g. Claude Opus 5) thinking is on by default and its tokens are
# billed against max_tokens, so a tight cap can truncate the visible text
# before it's written. output_config.effort="low" below keeps reasoning
# minimal for this trivial request; this ceiling is the safety margin.
TEST_MAX_TOKENS = 1024

_ERROR_MESSAGES = {
    "missing_api_key": "No API key is configured. Set ANTHROPIC_API_KEY (or add it to .env.local) and try again.",
    "invalid_api_key": "The configured API key was rejected. Check ANTHROPIC_API_KEY and try again.",
    "insufficient_credit": "The Anthropic account has insufficient credit for this request.",
    "rate_limit": "Rate limit reached. Wait a moment and try again.",
    "network_error": "Could not reach the Anthropic API. Check your internet connection and try again.",
    "model_unavailable": "The configured model is not available. Check ANTHROPIC_MODEL and try again.",
    "truncated_response": (
        "Claude's reply was cut off before finishing (hit the output token limit). "
        "This is a truncated-response error, not a successful connection."
    ),
    "empty_response": "Claude responded with no text content, so the connection could not be confirmed.",
    "unexpected_error": "The connection test failed unexpectedly.",
}


@dataclass
class ConnectionResult:
    success: bool
    model: str | None = None
    reply_text: str | None = None
    matched_expected: bool = False
    usage: dict | None = None
    stop_reason: str | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "model": self.model,
            "reply_text": self.reply_text,
            "matched_expected": self.matched_expected,
            "usage": self.usage,
            "stop_reason": self.stop_reason,
            "error_type": self.error_type,
            "error_message": self.error_message,
        }


def _redact(text: str, secret: str | None) -> str:
    if not secret:
        return text
    return text.replace(secret, "[redacted]")


def test_connection() -> ConnectionResult:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    configured_model = os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL

    if not api_key:
        return ConnectionResult(
            success=False,
            model=configured_model,
            error_type="missing_api_key",
            error_message=_ERROR_MESSAGES["missing_api_key"],
        )

    client = anthropic.Anthropic(api_key=api_key)

    try:
        response = client.messages.create(
            model=configured_model,
            max_tokens=TEST_MAX_TOKENS,
            # Keep reasoning minimal for this trivial connectivity check
            # rather than disabling thinking outright (disabling it on
            # Claude Opus 5 has its own failure modes - see ai_client tests).
            output_config={"effort": "low"},
            messages=[
                {
                    "role": "user",
                    "content": f"Reply with exactly this text and nothing else: {EXPECTED_REPLY}",
                }
            ],
        )
    except anthropic.AuthenticationError as exc:
        return ConnectionResult(
            success=False,
            model=configured_model,
            error_type="invalid_api_key",
            error_message=_redact(_ERROR_MESSAGES["invalid_api_key"], api_key),
        )
    except anthropic.NotFoundError as exc:
        return ConnectionResult(
            success=False,
            model=configured_model,
            error_type="model_unavailable",
            error_message=_redact(_ERROR_MESSAGES["model_unavailable"], api_key),
        )
    except anthropic.RateLimitError as exc:
        return ConnectionResult(
            success=False,
            model=configured_model,
            error_type="rate_limit",
            error_message=_redact(_ERROR_MESSAGES["rate_limit"], api_key),
        )
    except anthropic.APIStatusError as exc:
        if is_insufficient_credit_error(exc):
            return ConnectionResult(
                success=False,
                model=configured_model,
                error_type="insufficient_credit",
                error_message=_redact(_ERROR_MESSAGES["insufficient_credit"], api_key),
            )
        return ConnectionResult(
            success=False,
            model=configured_model,
            error_type="unexpected_error",
            error_message=_redact(f"API error ({exc.status_code}): {exc.message}", api_key),
        )
    except anthropic.APIConnectionError as exc:
        return ConnectionResult(
            success=False,
            model=configured_model,
            error_type="network_error",
            error_message=_redact(_ERROR_MESSAGES["network_error"], api_key),
        )
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return ConnectionResult(
            success=False,
            model=configured_model,
            error_type="unexpected_error",
            error_message=_redact(f"{_ERROR_MESSAGES['unexpected_error']} ({exc})", api_key),
        )

    # Combine every text block (a reply can legitimately arrive as more than
    # one) and ignore non-text blocks (e.g. "thinking") - concatenation order
    # follows response.content, which the API returns in generation order.
    reply_text = "".join(block.text for block in response.content if block.type == "text").strip()
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    # A max_tokens stop is a truncated response, not a working connection -
    # report it as its own error rather than grading the partial text.
    if response.stop_reason == "max_tokens":
        return ConnectionResult(
            success=False,
            model=response.model,
            reply_text=reply_text,
            usage=usage,
            stop_reason=response.stop_reason,
            error_type="truncated_response",
            error_message=_ERROR_MESSAGES["truncated_response"],
        )

    if not reply_text:
        return ConnectionResult(
            success=False,
            model=response.model,
            reply_text=reply_text,
            usage=usage,
            stop_reason=response.stop_reason,
            error_type="empty_response",
            error_message=_ERROR_MESSAGES["empty_response"],
        )

    return ConnectionResult(
        success=True,
        model=response.model,
        reply_text=reply_text,
        matched_expected=reply_text == EXPECTED_REPLY,
        usage=usage,
        stop_reason=response.stop_reason,
    )
