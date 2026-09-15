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

load_dotenv(Path(__file__).parent / ".env.local")

DEFAULT_MODEL = "claude-opus-5"
EXPECTED_REPLY = "DEAL_LAB_CONNECTED"

_ERROR_MESSAGES = {
    "missing_api_key": "No API key is configured. Set ANTHROPIC_API_KEY (or add it to .env.local) and try again.",
    "invalid_api_key": "The configured API key was rejected. Check ANTHROPIC_API_KEY and try again.",
    "insufficient_credit": "The Anthropic account has insufficient credit for this request.",
    "rate_limit": "Rate limit reached. Wait a moment and try again.",
    "network_error": "Could not reach the Anthropic API. Check your internet connection and try again.",
    "model_unavailable": "The configured model is not available. Check ANTHROPIC_MODEL and try again.",
    "unexpected_error": "The connection test failed unexpectedly.",
}


@dataclass
class ConnectionResult:
    success: bool
    model: str | None = None
    reply_text: str | None = None
    matched_expected: bool = False
    usage: dict | None = None
    error_type: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "model": self.model,
            "reply_text": self.reply_text,
            "matched_expected": self.matched_expected,
            "usage": self.usage,
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
            max_tokens=20,
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
        if exc.status_code == 402 or getattr(exc, "type", None) == "billing_error":
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

    reply_text = "".join(block.text for block in response.content if block.type == "text").strip()
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }

    return ConnectionResult(
        success=True,
        model=response.model,
        reply_text=reply_text,
        matched_expected=reply_text == EXPECTED_REPLY,
        usage=usage,
    )
