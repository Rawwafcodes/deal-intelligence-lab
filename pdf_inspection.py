"""Send one original PDF directly to Claude for inspection, using Anthropic's
native PDF document input (no OCR, extraction, chunking, or embeddings on
our side — Claude reads the PDF bytes itself).

Design decision (base64 vs. Files API): this sends the PDF inline as a
base64 `document` content block rather than uploading it to Anthropic's
Files API first. Each inspection is a one-shot, single-document request —
there is no reuse across multiple calls that would justify uploading and
keeping a remote copy. Base64 input keeps zero remote state on Anthropic's
side (nothing to track or delete afterwards), matching "least unnecessary
remote persistence." If a future milestone needs repeated analysis of the
same document, revisit this and use the Files API (with explicit deletion
of the remote copy once done).

Provider limits this module works within (see Anthropic's PDF support
docs): 32 MB maximum request size, 600 pages maximum per request (100 on
models with a context window under 1M tokens — not a concern for the
default model, Claude Opus 5, which has a 1M window). We enforce a local
23 MB *source* file size cap (base64 inflates bytes by ~4/3, so 23 MB of
PDF becomes ~30.6 MB of request body, leaving headroom for the prompt
text) before ever contacting the API. We cannot cheaply check the page
count ourselves without parsing the PDF, which is out of scope for this
milestone (see module docstring above); an over-the-page-limit PDF is
instead reported as a "too large" error surfaced by the API itself.

Citations: each `document` content block has `citations: {"enabled": true}`
turned on, which is Anthropic's native citation feature for PDFs. The API
splits its answer into text segments, and any segment that is grounded in
the document carries a `citations` list with the cited page range. We pass
that structure straight through — we never invent or renumber a citation.
Citations are incompatible with `output_config.format` (structured
outputs), so this module asks Claude to structure its own reply with
markdown-style section headings instead of requesting JSON.
"""

from __future__ import annotations

import base64
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from anthropic.types import DocumentBlockParam, MessageParam, TextBlockParam
from dotenv import load_dotenv

import documents

load_dotenv(Path(__file__).parent / ".env.local")

DEFAULT_MODEL = "claude-opus-5"

# Local pre-flight cap on the *source* PDF, well under Anthropic's 32 MB
# whole-request limit once base64 (~4/3 inflation) and prompt text are
# accounted for. See module docstring for the arithmetic.
MAX_PDF_SOURCE_BYTES = 23 * 1024 * 1024

ANALYSIS_MAX_TOKENS = 32000

MANDATE = (
    "Inspect this original PDF directly. Explain what the document is, "
    "identify its principal subjects and material statements, and cite "
    "the relevant page for every factual statement. Report any pages or "
    "content you could not interpret. Do not use external knowledge and "
    "do not make unsupported assumptions."
)

STRUCTURE_INSTRUCTIONS = (
    "\n\nStructure your reply with exactly these section headings, each "
    "alone on its own line starting with '## ', in this order:\n"
    "## Document Identification\n"
    "## Document Type and Purpose\n"
    "## Summary\n"
    "## Principal Subjects\n"
    "## Material Factual Statements\n"
    "## Ambiguities and Limitations\n"
    "## Pages or Content You Could Not Interpret\n\n"
    "Under \"Material Factual Statements\", write one statement per bullet "
    "point, and support every factual statement with a citation to the "
    "page it came from. If a statement cannot be tied to a specific page "
    "in the document, label that bullet \"(uncited)\" rather than "
    "inventing a page reference."
)

_ERROR_MESSAGES = {
    "missing_api_key": "No API key is configured. Set ANTHROPIC_API_KEY (or add it to .env.local) and try again.",
    "invalid_api_key": "The configured API key was rejected. Check ANTHROPIC_API_KEY and try again.",
    "insufficient_credit": "The Anthropic account has insufficient credit for this request.",
    "rate_limit": "Rate limit reached. Wait a moment and try again.",
    "network_error": "Could not reach the Anthropic API. Check your internet connection and try again.",
    "model_unavailable": "The configured model is not available. Check ANTHROPIC_MODEL and try again.",
    "missing_file": "The stored file for this document is missing on disk.",
    "oversized_pdf": (
        f"This PDF is larger than the {MAX_PDF_SOURCE_BYTES // (1024 * 1024)} MB this app will "
        "send for inspection (Anthropic's own limit is a 32 MB request)."
    ),
    "encrypted_pdf": "This PDF is password-protected or encrypted, so Claude cannot read it.",
    "malformed_pdf": "This PDF could not be read — it may be corrupted or not a valid PDF.",
    "invalid_pdf": "Claude could not process this PDF.",
    "refused": "Claude declined to analyze this document.",
    "truncated_response": (
        "Claude's analysis was cut off before finishing (hit the output token limit). "
        "The partial analysis below is incomplete."
    ),
    "empty_response": "Claude returned no analysis text.",
    "unexpected_error": "The inspection failed unexpectedly.",
}


@dataclass
class Citation:
    cited_text: str
    document_title: str | None
    start_page: int
    end_page: int

    def to_dict(self) -> dict:
        return {
            "cited_text": self.cited_text,
            "document_title": self.document_title,
            "start_page": self.start_page,
            "end_page": self.end_page,
        }


@dataclass
class AnalysisSegment:
    text: str
    citations: list[Citation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"text": self.text, "citations": [c.to_dict() for c in self.citations]}


@dataclass
class InspectionOutcome:
    success: bool
    transmitted: bool
    analysis_seconds: float
    model: str
    stop_reason: str | None = None
    usage: dict | None = None
    segments: list[AnalysisSegment] | None = None
    error_type: str | None = None
    error_message: str | None = None


def _redact(text: str, secret: str | None) -> str:
    if not secret:
        return text
    return text.replace(secret, "[redacted]")


def _classify_bad_request(message: str) -> str:
    lowered = message.lower()
    if "encrypt" in lowered or "password" in lowered:
        return "encrypted_pdf"
    if any(
        kw in lowered
        for kw in (
            "corrupt",
            "damaged",
            "malformed",
            "could not be read",
            "cannot be parsed",
            "not a valid pdf",
            "was not valid",
            "not valid",
            "unable to process",
            "invalid pdf",
        )
    ):
        return "malformed_pdf"
    if any(kw in lowered for kw in ("too many pages", "exceeds", "maximum", "too large")):
        return "oversized_pdf"
    return "invalid_pdf"


def _extract_segments(content_blocks) -> list[AnalysisSegment]:
    segments = []
    for block in content_blocks:
        if getattr(block, "type", None) != "text":
            continue
        citations = []
        for c in getattr(block, "citations", None) or []:
            if getattr(c, "type", None) == "page_location":
                citations.append(
                    Citation(
                        cited_text=c.cited_text,
                        document_title=c.document_title,
                        start_page=c.start_page_number,
                        end_page=c.end_page_number,
                    )
                )
        segments.append(AnalysisSegment(text=block.text, citations=citations))
    return segments


def inspect_document(document: documents.Document) -> InspectionOutcome:
    start = time.monotonic()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    configured_model = os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL

    if not api_key:
        return InspectionOutcome(
            success=False,
            transmitted=False,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="missing_api_key",
            error_message=_ERROR_MESSAGES["missing_api_key"],
        )

    stored_path = documents.stored_file_path(document)
    if not stored_path.is_file():
        return InspectionOutcome(
            success=False,
            transmitted=False,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="missing_file",
            error_message=_ERROR_MESSAGES["missing_file"],
        )

    if document.size_bytes > MAX_PDF_SOURCE_BYTES:
        return InspectionOutcome(
            success=False,
            transmitted=False,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="oversized_pdf",
            error_message=_ERROR_MESSAGES["oversized_pdf"],
        )

    pdf_bytes = stored_path.read_bytes()
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")

    client = anthropic.Anthropic(api_key=api_key)

    document_block: DocumentBlockParam = {
        "type": "document",
        "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
        "title": document.original_filename,
        "citations": {"enabled": True},
    }
    text_block: TextBlockParam = {"type": "text", "text": MANDATE + STRUCTURE_INSTRUCTIONS}
    messages: list[MessageParam] = [{"role": "user", "content": [document_block, text_block]}]

    try:
        with client.messages.stream(
            model=configured_model,
            max_tokens=ANALYSIS_MAX_TOKENS,
            thinking={"type": "adaptive"},
            output_config={"effort": "high"},
            messages=messages,
        ) as stream:
            response = stream.get_final_message()
    except anthropic.AuthenticationError:
        return InspectionOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="invalid_api_key",
            error_message=_redact(_ERROR_MESSAGES["invalid_api_key"], api_key),
        )
    except anthropic.NotFoundError:
        return InspectionOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="model_unavailable",
            error_message=_redact(_ERROR_MESSAGES["model_unavailable"], api_key),
        )
    except anthropic.RateLimitError:
        return InspectionOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="rate_limit",
            error_message=_redact(_ERROR_MESSAGES["rate_limit"], api_key),
        )
    except anthropic.BadRequestError as exc:
        error_type = _classify_bad_request(str(exc.message))
        return InspectionOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type=error_type,
            error_message=_redact(
                _ERROR_MESSAGES.get(error_type, _ERROR_MESSAGES["invalid_pdf"]), api_key
            ),
        )
    except anthropic.APIStatusError as exc:
        if exc.status_code == 402 or getattr(exc, "type", None) == "billing_error":
            return InspectionOutcome(
                success=False,
                transmitted=True,
                analysis_seconds=time.monotonic() - start,
                model=configured_model,
                error_type="insufficient_credit",
                error_message=_redact(_ERROR_MESSAGES["insufficient_credit"], api_key),
            )
        return InspectionOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="unexpected_error",
            error_message=_redact(f"API error ({exc.status_code}): {exc.message}", api_key),
        )
    except anthropic.APIConnectionError:
        return InspectionOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="network_error",
            error_message=_redact(_ERROR_MESSAGES["network_error"], api_key),
        )
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return InspectionOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="unexpected_error",
            error_message=_redact(f"{_ERROR_MESSAGES['unexpected_error']} ({exc})", api_key),
        )

    analysis_seconds = time.monotonic() - start
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
    }
    segments = _extract_segments(response.content)

    if response.stop_reason == "refusal":
        explanation = getattr(response.stop_details, "explanation", None) if response.stop_details else None
        return InspectionOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=analysis_seconds,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage,
            error_type="refused",
            error_message=explanation or _ERROR_MESSAGES["refused"],
        )

    if response.stop_reason == "max_tokens":
        return InspectionOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=analysis_seconds,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage,
            segments=segments,
            error_type="truncated_response",
            error_message=_ERROR_MESSAGES["truncated_response"],
        )

    if not segments or not any(s.text.strip() for s in segments):
        return InspectionOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=analysis_seconds,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage,
            error_type="empty_response",
            error_message=_ERROR_MESSAGES["empty_response"],
        )

    return InspectionOutcome(
        success=True,
        transmitted=True,
        analysis_seconds=analysis_seconds,
        model=response.model,
        stop_reason=response.stop_reason,
        usage=usage,
        segments=segments,
    )
