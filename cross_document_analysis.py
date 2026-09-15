"""Send a small, user-selected group of original PDFs to Claude in one
request for cross-document analysis, using Anthropic's native multi-document
PDF input and native citations (no OCR, extraction, chunking, embedding, or
local interpretation of PDF content on our side).

Design decision (base64 vs. Files API): each selected PDF is sent inline as
its own base64 `document` content block in a single request, exactly as in
single-document inspection (pdf_inspection.py) - see that module's docstring
for the base64-vs-Files-API reasoning and the data-retention caveat, both of
which apply identically here. Base64 remains sufficient for a "small group"
of documents: Anthropic's 32 MB request-size limit and 600-page limit apply
to the *whole* request regardless of how many document blocks it contains
(https://platform.claude.com/docs/en/build-with-claude/pdf-support), so this
module enforces the same local pre-flight byte budget as pdf_inspection.py,
applied to the *sum* of the selected files' sizes. If a future milestone
needs a much larger combined document set, revisit this and use the Files
API to keep the request payload itself small (referencing by file_id avoids
the ~4/3 base64 inflation, though it does not relax the page-count limit).

Citations: each `document` block has `citations: {"enabled": true}` set, and
`title` set to the document's own filename, exactly as in single-document
inspection. With multiple documents in one request, each citation Claude
returns carries a `document_index` - the 0-based position of the document
block it came from, in the order those blocks were placed in the request
(confirmed against Anthropic's citations documentation, which shows this
indexing explicitly for a multi-document example). We record that same
ordering when building the request and use it to resolve every citation
back to the exact document ID and checksum it came from - never inventing
or guessing which document a citation belongs to.

Citations remain incompatible with `output_config.format` (structured
outputs), so - as in pdf_inspection.py - this module asks Claude to
structure its own reply with markdown-style section headings and a
consistent labeled-field template per finding, rather than requesting JSON.
"""

from __future__ import annotations

import base64
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import anthropic
from anthropic.types import DocumentBlockParam, MessageParam, TextBlockParam
from dotenv import load_dotenv

import documents
import pdf_inspection

load_dotenv(Path(__file__).parent / ".env.local")

DEFAULT_MODEL = pdf_inspection.DEFAULT_MODEL

# Same reasoning and arithmetic as pdf_inspection.MAX_PDF_SOURCE_BYTES, but
# applied here to the *combined* size of every selected document, since the
# 32 MB request-size limit is shared across the whole request either way.
MAX_TOTAL_SOURCE_BYTES = pdf_inspection.MAX_PDF_SOURCE_BYTES

MIN_DOCUMENTS = 2
# "A small user-selected group of documents" per the milestone scope, not a
# provider limit - keeps requests reviewable in the confirmation dialog and
# within realistic analysis time. Override via env if a project genuinely
# needs more.
MAX_DOCUMENTS = int(os.environ.get("DEAL_LAB_MAX_CROSS_ANALYSIS_DOCUMENTS", 12))

ANALYSIS_MAX_TOKENS = 32000

# Bump this whenever MANDATE or STRUCTURE_INSTRUCTIONS changes materially,
# so stored analysis records stay traceable to the exact prompt that
# produced them.
MANDATE_VERSION = "1"

MANDATE = (
    "Read these original documents as parts of one transaction. Build a "
    "connected understanding of their purposes and relationships. Identify "
    "material agreements, inconsistencies, unsupported cross-document "
    "claims, ambiguities and questions requiring investigation.\n\n"
    "Do not assume every difference is a contradiction. Consider document "
    "dates, scope, definitions, versions and qualifications.\n\n"
    "Every factual statement must use Anthropic's native citation "
    "metadata. A cross-document inconsistency must cite the relevant "
    "evidence from each affected document. Do not use external knowledge."
)

STRUCTURE_INSTRUCTIONS = (
    "\n\nStructure your reply with exactly these section headings, each "
    "alone on its own line starting with '## ', in this order:\n"
    "## Combined Document Understanding\n"
    "## Relationship Between the Documents\n"
    "## Material Facts\n"
    "## Potential Inconsistencies\n"
    "## Unsupported Cross-Document Claims\n"
    "## Missing or Unresolved Information\n"
    "## Ambiguity and Alternative Interpretations\n"
    "## Recommended Questions or Actions\n"
    "## Files or Content Could Not Interpret\n\n"
    "Within \"Potential Inconsistencies\" and \"Unsupported Cross-Document "
    "Claims\", write every finding as a bullet using exactly this "
    "template, with each labeled field on its own line inside the bullet "
    "(do not add other fields or omit any of these):\n"
    "- **Title:** a short finding title\n"
    "**Classification:** material agreement | inconsistency | unsupported "
    "claim | ambiguity | missing information | question for investigation\n"
    "**Severity:** low | medium | high\n"
    "**Explanation:** what you found and why\n"
    "**Commercial relevance:** why this matters to the transaction\n"
    "**Uncertainty:** fully supported by citations | partially supported "
    "| uncited - state exactly which parts\n"
    "**Recommended action:** a concrete next step\n\n"
    "A finding that alleges a cross-document inconsistency must cite the "
    "relevant passage from every document involved - never present it as "
    "grounded unless every side is cited. If any side cannot be cited, say "
    "so explicitly in \"Uncertainty\" rather than treating the finding as "
    "fully grounded, and never invent a filename or page reference for a "
    "side you could not find support for."
)

_ERROR_MESSAGES = {
    "missing_api_key": "No API key is configured. Set ANTHROPIC_API_KEY (or add it to .env.local) and try again.",
    "invalid_api_key": "The configured API key was rejected. Check ANTHROPIC_API_KEY and try again.",
    "insufficient_credit": "The Anthropic account has insufficient credit for this request.",
    "rate_limit": "Rate limit reached. Wait a moment and try again.",
    "network_error": "Could not reach the Anthropic API. Check your internet connection and try again.",
    "model_unavailable": "The configured model is not available. Check ANTHROPIC_MODEL and try again.",
    "missing_file": "A stored file for one of the selected documents is missing on disk.",
    "too_few_documents": f"Cross-document analysis needs at least {MIN_DOCUMENTS} documents.",
    "too_many_documents": f"Select at most {MAX_DOCUMENTS} documents for one cross-document run.",
    "not_pdf": "Only PDF documents can be included in cross-document analysis.",
    "oversized_total": (
        f"The selected documents total more than {MAX_TOTAL_SOURCE_BYTES // (1024 * 1024)} MB, "
        "which this app will not send in one request (Anthropic's own limit is a 32 MB request)."
    ),
    "encrypted_pdf": "One of the selected PDFs is password-protected or encrypted, so Claude cannot read it.",
    "malformed_pdf": "One of the selected PDFs could not be read - it may be corrupted or not a valid PDF.",
    "invalid_pdf": "Claude could not process one of the selected PDFs.",
    "refused": "Claude declined to analyze these documents.",
    "truncated_response": (
        "Claude's analysis was cut off before finishing (hit the output token limit). "
        "The partial analysis below is incomplete."
    ),
    "empty_response": "Claude returned no analysis text.",
    "unexpected_error": "The cross-document analysis failed unexpectedly.",
}


@dataclass
class Citation:
    cited_text: str
    document_id: str | None
    document_title: str | None
    start_page: int
    end_page: int

    def to_dict(self) -> dict:
        return {
            "cited_text": self.cited_text,
            "document_id": self.document_id,
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
class CrossAnalysisOutcome:
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


def validate_selection(selected: list[documents.Document]) -> tuple[str, str] | None:
    """Local pre-flight checks that don't need the network. Returns
    (error_type, error_message) if the selection is invalid, else None."""
    if len(selected) < MIN_DOCUMENTS:
        return "too_few_documents", _ERROR_MESSAGES["too_few_documents"]
    if len(selected) > MAX_DOCUMENTS:
        return "too_many_documents", _ERROR_MESSAGES["too_many_documents"]
    if any(d.extension != ".pdf" for d in selected):
        return "not_pdf", _ERROR_MESSAGES["not_pdf"]
    if sum(d.size_bytes for d in selected) > MAX_TOTAL_SOURCE_BYTES:
        return "oversized_total", _ERROR_MESSAGES["oversized_total"]
    return None


def _classify_bad_request(message: str) -> str:
    # Anthropic's validation errors on a bad document embed the offending
    # content-block index, e.g. "messages.0.content.2.document...". Since we
    # control block ordering (documents first, in selection order, then the
    # instruction text last), that index maps straight back to one of the
    # selected documents when it falls within range.
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
        return "oversized_total"
    return "invalid_pdf"


_CONTENT_INDEX_RE = re.compile(r"content\.(\d+)\.")


def _describe_offending_document(message: str, selected: list[documents.Document]) -> str | None:
    match = _CONTENT_INDEX_RE.search(message)
    if not match:
        return None
    index = int(match.group(1))
    if 0 <= index < len(selected):
        return selected[index].original_filename
    return None


def _extract_segments(content_blocks, selected: list[documents.Document]) -> list[AnalysisSegment]:
    segments = []
    for block in content_blocks:
        if getattr(block, "type", None) != "text":
            continue
        citations = []
        for c in getattr(block, "citations", None) or []:
            if getattr(c, "type", None) == "page_location":
                document_index = getattr(c, "document_index", None)
                document_id = (
                    selected[document_index].id
                    if document_index is not None and 0 <= document_index < len(selected)
                    else None
                )
                citations.append(
                    Citation(
                        cited_text=c.cited_text,
                        document_id=document_id,
                        document_title=c.document_title,
                        start_page=c.start_page_number,
                        end_page=c.end_page_number,
                    )
                )
        segments.append(AnalysisSegment(text=block.text, citations=citations))
    return segments


def run_cross_analysis(selected: list[documents.Document]) -> CrossAnalysisOutcome:
    start = time.monotonic()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    configured_model = os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL

    if not api_key:
        return CrossAnalysisOutcome(
            success=False,
            transmitted=False,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="missing_api_key",
            error_message=_ERROR_MESSAGES["missing_api_key"],
        )

    validation_error = validate_selection(selected)
    if validation_error is not None:
        error_type, error_message = validation_error
        return CrossAnalysisOutcome(
            success=False,
            transmitted=False,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type=error_type,
            error_message=error_message,
        )

    document_blocks: list[DocumentBlockParam] = []
    for document in selected:
        stored_path = documents.stored_file_path(document)
        if not stored_path.is_file():
            return CrossAnalysisOutcome(
                success=False,
                transmitted=False,
                analysis_seconds=time.monotonic() - start,
                model=configured_model,
                error_type="missing_file",
                error_message=_ERROR_MESSAGES["missing_file"],
            )
        pdf_b64 = base64.standard_b64encode(stored_path.read_bytes()).decode("ascii")
        document_blocks.append(
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                "title": document.original_filename,
                "citations": {"enabled": True},
            }
        )

    client = anthropic.Anthropic(api_key=api_key)

    intro = (
        f"You have been given {len(selected)} original PDF documents for this analysis, "
        "in this order: " + ", ".join(f'{i + 1}. "{d.original_filename}"' for i, d in enumerate(selected)) + "."
    )
    text_block: TextBlockParam = {"type": "text", "text": intro + "\n\n" + MANDATE + STRUCTURE_INSTRUCTIONS}
    messages: list[MessageParam] = [{"role": "user", "content": [*document_blocks, text_block]}]

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
        return CrossAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="invalid_api_key",
            error_message=_redact(_ERROR_MESSAGES["invalid_api_key"], api_key),
        )
    except anthropic.NotFoundError:
        return CrossAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="model_unavailable",
            error_message=_redact(_ERROR_MESSAGES["model_unavailable"], api_key),
        )
    except anthropic.RateLimitError:
        return CrossAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="rate_limit",
            error_message=_redact(_ERROR_MESSAGES["rate_limit"], api_key),
        )
    except anthropic.BadRequestError as exc:
        error_type = _classify_bad_request(str(exc.message))
        message = _ERROR_MESSAGES.get(error_type, _ERROR_MESSAGES["invalid_pdf"])
        offending = _describe_offending_document(str(exc.message), selected)
        if offending:
            message = f'{message} (document: "{offending}")'
        return CrossAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type=error_type,
            error_message=_redact(message, api_key),
        )
    except anthropic.APIStatusError as exc:
        if exc.status_code == 402 or getattr(exc, "type", None) == "billing_error":
            return CrossAnalysisOutcome(
                success=False,
                transmitted=True,
                analysis_seconds=time.monotonic() - start,
                model=configured_model,
                error_type="insufficient_credit",
                error_message=_redact(_ERROR_MESSAGES["insufficient_credit"], api_key),
            )
        return CrossAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="unexpected_error",
            error_message=_redact(f"API error ({exc.status_code}): {exc.message}", api_key),
        )
    except anthropic.APIConnectionError:
        return CrossAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=time.monotonic() - start,
            model=configured_model,
            error_type="network_error",
            error_message=_redact(_ERROR_MESSAGES["network_error"], api_key),
        )
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return CrossAnalysisOutcome(
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
    segments = _extract_segments(response.content, selected)

    if response.stop_reason == "refusal":
        explanation = getattr(response.stop_details, "explanation", None) if response.stop_details else None
        return CrossAnalysisOutcome(
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
        return CrossAnalysisOutcome(
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
        return CrossAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=analysis_seconds,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage,
            error_type="empty_response",
            error_message=_ERROR_MESSAGES["empty_response"],
        )

    return CrossAnalysisOutcome(
        success=True,
        transmitted=True,
        analysis_seconds=analysis_seconds,
        model=response.model,
        stop_reason=response.stop_reason,
        usage=usage,
        segments=segments,
    )
