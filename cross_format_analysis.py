"""Send a user-selected group of original PDFs *and* Excel workbooks to
Claude in one request, so Claude can reconcile narrative deal documents
against financial models as evidence for a single transaction - not inspect
or summarize each file separately.

This module composes the two provider-native mechanisms already proven by
earlier milestones, in one analytical context:

- PDFs are sent exactly as in pdf_inspection.py / cross_document_analysis.py:
  inline base64 `document` content blocks with `citations: {"enabled": true}`
  turned on, so Claude's native PDF citation feature applies. See those
  modules' docstrings for the base64-vs-Files-API reasoning, which applies
  identically here.
- Excel workbooks are sent exactly as in xlsx_inspection.py: each is
  uploaded to Anthropic's Files API, then handed to Claude as a
  `container_upload` content block inside the same message, alongside a
  `code_execution` tool so Claude can open and query every workbook itself.
  Excel has no native citation feature, so this module reuses xlsx_inspection's
  citation *convention* (a citation written inline in Claude's own reply,
  then mechanically checked against the real workbook - see
  `_open_workbook_structure` reuse below), extended with a workbook label so
  a citation can never be ambiguous when more than one workbook is selected
  (see "Multi-workbook citation resolution" below).

Whether the API actually supports mixing a `document` content block, several
`container_upload` blocks, and the `code_execution` tool in one request is
not something this app assumes from memory: the installed anthropic SDK
(1.5.0) was inspected directly, and `DocumentBlockParam` and
`ContainerUploadBlockParam` are both plain members of the same
`ContentBlockParam` union that a message's `content` list accepts - there is
no field-level exclusivity between them, and `tools` is an independent,
top-level request parameter. Each mechanism is already proven working
in isolation by earlier milestones; this module's own live verification run
is the actual proof that Anthropic's API honors them combined exactly as
requested, since that combination has no existing worked example to point
to. If a live run showed the two could not coexist, that would be reported
here rather than silently worked around with local extraction.

Multi-workbook citation resolution: unlike single-workbook inspection, more
than one Excel workbook can be selected, and two of them could easily share
a sheet name (e.g. every model has an "Assumptions" tab) or even a similar
filename. Resolving a citation by filename or sheet name alone is exactly
what the milestone forbids ("a citation must never silently point to the
wrong workbook when filenames or sheet names are similar"). So, mirroring
how cross_document_analysis.py resolves a PDF citation via the API's own
`document_index` rather than by title text, every selected workbook is
assigned a stable, app-generated label ("Workbook 1", "Workbook 2", ...) in
the order it appears in the request, Claude is instructed to cite using that
exact label, and this module resolves a citation back to a document_id via
that label - never via the filename Claude may also mention in prose. An
unrecognized label resolves to no document (`document_id=None`) and the
citation is marked as not existing, rather than guessed.

Citations remain incompatible with `output_config.format` (structured
outputs), so - as in every earlier inspection module - this module asks
Claude to structure its own reply with markdown-style section headings and a
consistent labeled-field template per finding, rather than requesting JSON.

Provider file cleanup: exactly one Files API object exists per selected
Excel workbook (PDFs are never uploaded to the Files API here). Every
workbook that was actually uploaded gets an independent, `finally`-style
deletion attempt - on success, on a later provider error, on a parsing
failure, and on an unexpected exception - and this module records each
attempt's outcome separately; see xlsx_inspection.py's module docstring for
what "cleanup succeeded" does and does not imply about Anthropic's broader
data retention for the Files API and code execution.
"""

from __future__ import annotations

import base64
import os
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import anthropic
from anthropic.types import ContainerUploadBlockParam, DocumentBlockParam, MessageParam, TextBlockParam
from dotenv import load_dotenv

from anthropic_errors import is_insufficient_credit_error

import cross_document_analysis
import documents
import pdf_inspection
import xlsx_inspection

load_dotenv(Path(__file__).parent / ".env.local")

DEFAULT_MODEL = pdf_inspection.DEFAULT_MODEL

MIN_PDF_DOCUMENTS = 1
MIN_EXCEL_DOCUMENTS = 1

# Anthropic does not impose a document-*count* limit for either mechanism -
# only the aggregate PDF byte/page limits (MAX_TOTAL_PDF_SOURCE_BYTES below)
# and, per workbook, the Files API's own size limit apply. These counts are
# purely a generous app-side sanity ceiling against a pathological selection
# (e.g. hundreds of files fat-fingered into one run), not a provider number -
# raise them freely via the env vars if a real data room needs more.
MAX_PDF_DOCUMENTS = int(os.environ.get("DEAL_LAB_MAX_RECONCILE_PDF_DOCUMENTS", 40))
MAX_EXCEL_DOCUMENTS = int(os.environ.get("DEAL_LAB_MAX_RECONCILE_EXCEL_DOCUMENTS", 20))

# Same reasoning as cross_document_analysis.MAX_TOTAL_SOURCE_BYTES: the
# inline base64 PDF blocks share Anthropic's 32 MB whole-request limit, so
# the combined *PDF* byte budget is capped locally before ever contacting
# the API. Excel workbooks are uploaded via the Files API, not inlined, so
# they are capped individually instead (see MAX_EXCEL_WORKBOOK_SOURCE_BYTES).
MAX_TOTAL_PDF_SOURCE_BYTES = pdf_inspection.MAX_PDF_SOURCE_BYTES
MAX_EXCEL_WORKBOOK_SOURCE_BYTES = xlsx_inspection.MAX_WORKBOOK_SOURCE_BYTES

ANALYSIS_MAX_TOKENS = 64000
# Code execution can genuinely run for several minutes per tool call, and a
# pause_turn continuation means more than one such call in one analysis -
# same reasoning as xlsx_inspection.py.
ANALYSIS_CLIENT_TIMEOUT_SECONDS = 1800.0
MAX_PAUSE_CONTINUATIONS = 5

CODE_EXECUTION_TOOL_TYPE = xlsx_inspection.CODE_EXECUTION_TOOL_TYPE

TOOL_TRACE_TEXT_CAP = xlsx_inspection.TOOL_TRACE_TEXT_CAP

# Bump whenever MANDATE or STRUCTURE_INSTRUCTIONS changes materially, so
# stored records stay traceable to the exact prompt that produced them.
MANDATE_VERSION = "1"

MANDATE = (
    "You have been given original PDF documents and original Excel "
    "workbooks that are evidence relating to one transaction. Treat them "
    "together as one body of evidence, not as separate analyses to "
    "summarize independently.\n\n"
    "1. Identify the transaction and the role each source plays in it.\n"
    "2. Understand each workbook's structure, assumptions, formulas and "
    "outputs - open and query every workbook yourself using code "
    "execution; do not guess at its contents.\n"
    "3. Compare financial and commercial claims across the PDFs and the "
    "spreadsheets.\n"
    "4. Identify contradictions, unsupported assumptions, missing "
    "information, calculation or formula concerns, and material "
    "consistencies.\n"
    "5. Clearly distinguish a fact you found stated in a source from your "
    "own inference or interpretation.\n"
    "6. Never claim that two values conflict without having examined both "
    "sources yourself.\n"
    "7. State uncertainty explicitly wherever the evidence is incomplete.\n"
    "8. Never invent a fact or a citation, and do not use external "
    "knowledge.\n"
    "9. Focus on issues that could affect valuation, consideration, "
    "financing, profitability, risk, negotiations or diligence."
)

STRUCTURE_INSTRUCTIONS = (
    "\n\nStructure your reply with exactly these section headings, each "
    "alone on its own line starting with '## ', in this order:\n"
    "## Executive Conclusion\n"
    "## Sources Reviewed\n"
    "## Reconciliation Findings\n"
    "## Unresolved Questions\n"
    "## Analysis Limitations\n\n"
    "Under \"Executive Conclusion\", give a concise assessment of whether "
    "the materials appear internally consistent and name the most "
    "important issues requiring attention.\n\n"
    "Under \"Sources Reviewed\", write one bullet per source (every PDF and "
    "every workbook you were given, with none skipped) using exactly this "
    "template:\n"
    "- **Filename:** the exact filename you were given for this source\n"
    "**Type:** pdf | excel\n"
    "**Purpose:** what this source appears to be\n"
    "**Interpreted:** yes | partially | no\n"
    "**Limitations:** any limitation you encountered reading this source, "
    "or \"none\"\n\n"
    "Under \"Reconciliation Findings\", write every finding as a bullet "
    "using exactly this template, with each labeled field on its own line "
    "inside the bullet (do not add other fields or omit any of these):\n"
    "- **Title:** a short finding title\n"
    "**Classification:** cross-source conflict | unsupported model "
    "assumption | missing evidence | calculation or formula concern | "
    "definition/methodology mismatch | timing or period mismatch | "
    "confirmed consistency | unable to reconcile\n"
    "**Severity:** critical | high | medium | low | informational\n"
    "**Explanation:** what you found and why\n"
    "**PDF evidence:** the relevant PDF passage, which must carry a native "
    "citation - if no PDF evidence applies to this finding, write exactly "
    "\"No PDF evidence located\" rather than leaving it out or inventing one\n"
    "**Workbook evidence:** the relevant workbook fact, cited with the "
    "citation format below - if no workbook evidence applies, write "
    "exactly \"No workbook evidence located\" rather than leaving it out or "
    "inventing one\n"
    "**Commercial or financial relevance:** why this matters to the "
    "transaction (valuation, consideration, financing, profitability, "
    "risk, negotiation or diligence)\n"
    "**Uncertainty:** fully supported by citations | partially supported | "
    "uncited - state exactly which parts, and if either evidence field is "
    "missing or a citation could not be produced, say so here rather than "
    "presenting the finding as fully grounded\n"
    "**Recommended action:** a concrete next step, such as a question to "
    "raise with management, the seller, advisers, or the model owner\n\n"
    "A finding alleging a cross-source conflict must cite evidence from "
    "every side it compares - never present it as grounded unless every "
    "side is cited. Never invent a filename, page, sheet, or cell "
    "reference for evidence you could not actually find.\n\n"
    "Excel citation format - use this exact format for every "
    "workbook-specific claim, immediately after the fact it supports:\n"
    "('Workbook N'!'Sheet Name'!CellRef [value]) for a hardcoded or "
    "calculated value\n"
    "('Workbook N'!'Sheet Name'!CellRef [formula]) for a formula\n"
    "('Workbook N'!'Sheet Name'!CellRef [label]) for a text label\n"
    "For a range, use CellRef1:CellRef2, e.g. ('Workbook 1'!'Assumptions'!"
    "B7:B12 [value]). Replace \"Workbook N\" with the exact workbook label "
    "you were given for that workbook (e.g. \"Workbook 1\", \"Workbook 2\") "
    "- never its filename. Always wrap the sheet name in single quotes, "
    "exactly as it appears in the workbook. Only cite a sheet or cell you "
    "have actually opened or computed with code - never estimate or guess "
    "a reference. Put nothing else inside the parentheses.\n\n"
    "Under \"Unresolved Questions\", list questions an analyst should raise "
    "with management, the seller, advisers, or the model owner, one per "
    "bullet.\n\n"
    "Under \"Analysis Limitations\", explain anything you could not read, "
    "calculate, verify or reconcile."
)

_ERROR_MESSAGES = {
    "missing_api_key": "No API key is configured. Set ANTHROPIC_API_KEY (or add it to .env.local) and try again.",
    "invalid_api_key": "The configured API key was rejected. Check ANTHROPIC_API_KEY and try again.",
    "insufficient_credit": "The Anthropic account has insufficient credit for this request.",
    "rate_limit": "Rate limit reached. Wait a moment and try again.",
    "network_error": "Could not reach the Anthropic API. Check your internet connection and try again.",
    "model_unavailable": "The configured model is not available. Check ANTHROPIC_MODEL and try again.",
    "missing_file": "A stored file for one of the selected documents is missing on disk.",
    "no_documents": "Select at least one PDF and one Excel workbook.",
    "unsupported_type": "Only PDF and Excel (.xlsx/.xls) documents can be included in a cross-format reconciliation.",
    "missing_pdf": f"At least {MIN_PDF_DOCUMENTS} PDF document is required for cross-format reconciliation.",
    "missing_excel": f"At least {MIN_EXCEL_DOCUMENTS} Excel workbook is required for cross-format reconciliation.",
    "too_many_pdf_documents": f"Select at most {MAX_PDF_DOCUMENTS} PDF documents for one reconciliation run.",
    "too_many_excel_documents": f"Select at most {MAX_EXCEL_DOCUMENTS} Excel workbooks for one reconciliation run.",
    "oversized_pdf_total": (
        f"The selected PDFs total more than {MAX_TOTAL_PDF_SOURCE_BYTES // (1024 * 1024)} MB, "
        "which this app will not send in one request (Anthropic's own limit is a 32 MB request)."
    ),
    "oversized_excel_workbook": (
        f"One of the selected workbooks is larger than the "
        f"{MAX_EXCEL_WORKBOOK_SOURCE_BYTES // (1024 * 1024)} MB this app will upload for analysis."
    ),
    "encrypted_pdf": "One of the selected PDFs is password-protected or encrypted, so Claude cannot read it.",
    "malformed_pdf": "One of the selected PDFs could not be read - it may be corrupted or not a valid PDF.",
    "invalid_pdf": "Claude could not process one of the selected PDFs.",
    "upload_failed": "Uploading a workbook to Anthropic failed.",
    "still_paused": "Claude's analysis paused repeatedly and did not finish in the allotted number of turns.",
    "refused": "Claude declined to analyze these documents.",
    "truncated_response": (
        "Claude's analysis was cut off before finishing (hit the output token limit). "
        "The partial analysis below is incomplete."
    ),
    "empty_response": "Claude returned no analysis text.",
    "unexpected_error": "The cross-format reconciliation failed unexpectedly.",
}

EXCEL_CITATION_PREFIX_RE = re.compile(
    r"\('(Workbook \d+)'!'([^']+)'!"
    r"(\$?[A-Za-z]{1,3}\$?[0-9]+)"
    r"(?::(\$?[A-Za-z]{1,3}\$?[0-9]+))?"
    r"\s*\[(value|formula|label)\]"
)


@dataclass
class PdfCitation:
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
class ExcelCitation:
    workbook_label: str
    document_id: str | None
    document_filename: str | None
    sheet: str
    ref: str
    kind: str  # "value" | "formula" | "label"
    exists: bool | None  # None: could not be verified locally
    raw_text: str

    def to_dict(self) -> dict:
        return {
            "workbook_label": self.workbook_label,
            "document_id": self.document_id,
            "document_filename": self.document_filename,
            "sheet": self.sheet,
            "ref": self.ref,
            "kind": self.kind,
            "exists": self.exists,
            "raw_text": self.raw_text,
        }


@dataclass
class Part:
    type: str  # "text" | "excel_citation"
    text: str | None = None
    citation: ExcelCitation | None = None

    def to_dict(self) -> dict:
        if self.type == "excel_citation":
            assert self.citation is not None
            return {"type": "excel_citation", "citation": self.citation.to_dict()}
        return {"type": "text", "text": self.text}


@dataclass
class AnalysisSegment:
    # Ordered text / embedded-Excel-citation pieces parsed out of this
    # content block's raw text (see _parse_excel_parts).
    parts: list[Part] = field(default_factory=list)
    # Anthropic's native PDF citations, attached by the API to this whole
    # block - independent of, and orthogonal to, the Excel citations found
    # by parsing the same block's text.
    pdf_citations: list[PdfCitation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "parts": [p.to_dict() for p in self.parts],
            "pdf_citations": [c.to_dict() for c in self.pdf_citations],
        }


@dataclass
class SourceVerification:
    document_id: str
    available: bool
    unavailable_reason: str | None

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "available": self.available,
            "unavailable_reason": self.unavailable_reason,
        }


@dataclass
class ExcelCleanupResult:
    document_id: str
    document_filename: str
    attempted: bool
    succeeded: bool | None

    def to_dict(self) -> dict:
        return {
            "document_id": self.document_id,
            "document_filename": self.document_filename,
            "attempted": self.attempted,
            "succeeded": self.succeeded,
        }


@dataclass
class CrossFormatAnalysisOutcome:
    success: bool
    transmitted: bool
    analysis_seconds: float
    model: str
    stop_reason: str | None = None
    usage: dict | None = None
    segments: list[AnalysisSegment] | None = None
    tool_trace: list[dict] | None = None
    excel_cleanup: list[ExcelCleanupResult] | None = None
    excel_verification: list[SourceVerification] | None = None
    error_type: str | None = None
    error_message: str | None = None


def _redact(text: str, secret: str | None) -> str:
    if not secret:
        return text
    return text.replace(secret, "[redacted]")


def validate_selection(selected: list[documents.Document]) -> tuple[str, str] | None:
    """Local pre-flight checks that don't need the network. Returns
    (error_type, error_message) if the selection is invalid, else None."""
    if not selected:
        return "no_documents", _ERROR_MESSAGES["no_documents"]

    unsupported = [d for d in selected if d.extension not in (".pdf", ".xlsx", ".xls")]
    if unsupported:
        return "unsupported_type", _ERROR_MESSAGES["unsupported_type"]

    pdfs = [d for d in selected if d.extension == ".pdf"]
    excels = [d for d in selected if d.extension in (".xlsx", ".xls")]

    if len(pdfs) < MIN_PDF_DOCUMENTS:
        return "missing_pdf", _ERROR_MESSAGES["missing_pdf"]
    if len(excels) < MIN_EXCEL_DOCUMENTS:
        return "missing_excel", _ERROR_MESSAGES["missing_excel"]
    if len(pdfs) > MAX_PDF_DOCUMENTS:
        return "too_many_pdf_documents", _ERROR_MESSAGES["too_many_pdf_documents"]
    if len(excels) > MAX_EXCEL_DOCUMENTS:
        return "too_many_excel_documents", _ERROR_MESSAGES["too_many_excel_documents"]
    if sum(d.size_bytes for d in pdfs) > MAX_TOTAL_PDF_SOURCE_BYTES:
        return "oversized_pdf_total", _ERROR_MESSAGES["oversized_pdf_total"]
    if any(d.size_bytes > MAX_EXCEL_WORKBOOK_SOURCE_BYTES for d in excels):
        return "oversized_excel_workbook", _ERROR_MESSAGES["oversized_excel_workbook"]
    return None


_CONTENT_INDEX_RE = re.compile(r"content\.(\d+)\.")


def _describe_offending_pdf(message: str, pdf_documents: list[documents.Document]) -> str | None:
    # Anthropic's validation errors on a bad document block embed the
    # offending content-block index (e.g. "messages.0.content.2.document...").
    # PDF document blocks are always placed first, in selection order, so an
    # index within range maps straight back to the offending PDF. An index
    # past the PDF blocks belongs to a container_upload or the trailing text
    # block, neither of which this classifier is used for.
    match = _CONTENT_INDEX_RE.search(message)
    if not match:
        return None
    index = int(match.group(1))
    if 0 <= index < len(pdf_documents):
        return pdf_documents[index].original_filename
    return None


def _parse_excel_parts(text: str, label_to_document: dict[str, documents.Document]) -> list[Part]:
    """Splits text on Excel-citation matches, mirroring
    xlsx_inspection._parse_segments's paren-balancing approach (a citation's
    trailing value/formula text can itself contain parentheses, so the
    citation's own closing paren is found by scanning forward and tracking
    paren depth rather than a naive "up to the next )" regex). Citations
    here additionally carry a workbook label, resolved against the run's own
    label-to-document map rather than the filename Claude may also mention
    in prose - see the module docstring's "Multi-workbook citation
    resolution" section for why.
    """
    parts: list[Part] = []
    pos = 0
    search_start = 0
    while True:
        match = EXCEL_CITATION_PREFIX_RE.search(text, search_start)
        if not match:
            break

        depth = 1  # already inside the citation's own opening "("
        i = match.end()
        while i < len(text) and depth > 0:
            if text[i] == "(":
                depth += 1
            elif text[i] == ")":
                depth -= 1
            i += 1

        if depth != 0:
            search_start = match.start() + 1
            continue

        citation_end = i
        if match.start() > pos:
            parts.append(Part(type="text", text=text[pos : match.start()]))

        label, sheet, start_ref, end_ref, kind = match.groups()
        ref = f"{start_ref}:{end_ref}" if end_ref else start_ref
        raw_text = text[match.start() : citation_end]
        doc = label_to_document.get(label)
        citation = ExcelCitation(
            workbook_label=label,
            document_id=doc.id if doc else None,
            document_filename=doc.original_filename if doc else None,
            sheet=sheet,
            ref=ref,
            kind=kind,
            exists=None,
            raw_text=raw_text,
        )
        parts.append(Part(type="excel_citation", citation=citation))
        pos = citation_end
        search_start = citation_end

    if pos < len(text):
        parts.append(Part(type="text", text=text[pos:]))
    return parts


def _extract_segments(
    content_blocks: Any,
    pdf_documents: list[documents.Document],
    label_to_document: dict[str, documents.Document],
) -> list[AnalysisSegment]:
    segments = []
    for block in content_blocks:
        if getattr(block, "type", None) != "text":
            continue
        pdf_citations = []
        for c in getattr(block, "citations", None) or []:
            if getattr(c, "type", None) == "page_location":
                document_index = getattr(c, "document_index", None)
                document_id = (
                    pdf_documents[document_index].id
                    if document_index is not None and 0 <= document_index < len(pdf_documents)
                    else None
                )
                pdf_citations.append(
                    PdfCitation(
                        cited_text=c.cited_text,
                        document_id=document_id,
                        document_title=c.document_title,
                        start_page=c.start_page_number,
                        end_page=c.end_page_number,
                    )
                )
        parts = _parse_excel_parts(block.text, label_to_document)
        segments.append(AnalysisSegment(parts=parts, pdf_citations=pdf_citations))
    return segments


def _verify_excel_citations(
    segments: list[AnalysisSegment], excel_documents: list[documents.Document]
) -> list[SourceVerification]:
    """Mutates each ExcelCitation's `exists` field in place, and returns one
    SourceVerification per selected workbook. Reuses xlsx_inspection's own
    structural-reading function (sheet names and grid bounds only - never
    cell values) per the milestone's instruction to validate every Excel
    citation "using the existing Milestone 6 approach" - this module only
    adds the multi-workbook orchestration xlsx_inspection has no need for.
    """
    from openpyxl.utils.cell import range_boundaries

    structures_by_document_id: dict[str, dict[str, xlsx_inspection._SheetStructure]] = {}
    verifications: list[SourceVerification] = []

    for doc in excel_documents:
        try:
            structure = xlsx_inspection._open_workbook_structure(documents.stored_file_path(doc), doc.extension)
            structures_by_document_id[doc.id] = structure
            verifications.append(SourceVerification(document_id=doc.id, available=True, unavailable_reason=None))
        except xlsx_inspection.WorkbookVerificationUnavailable as exc:
            verifications.append(
                SourceVerification(document_id=doc.id, available=False, unavailable_reason=exc.reason)
            )

    for segment in segments:
        for part in segment.parts:
            if part.type != "excel_citation" or part.citation is None:
                continue
            citation = part.citation
            if citation.document_id is None:
                # An unrecognized workbook label - never guess which
                # workbook this was meant to cite.
                citation.exists = False
                continue
            workbook_structure = structures_by_document_id.get(citation.document_id)
            if workbook_structure is None:
                citation.exists = None  # verification unavailable for this specific workbook
                continue
            sheet_structure = workbook_structure.get(citation.sheet)
            if sheet_structure is None:
                citation.exists = False
                continue
            try:
                min_col, min_row, max_col, max_row = range_boundaries(citation.ref)
            except (ValueError, TypeError):
                citation.exists = False
                continue
            if min_col is None or min_row is None or max_col is None or max_row is None:
                citation.exists = False
                continue
            citation.exists = (
                1 <= min_row <= sheet_structure.max_row
                and 1 <= max_row <= sheet_structure.max_row
                and 1 <= min_col <= sheet_structure.max_col
                and 1 <= max_col <= sheet_structure.max_col
            )

    return verifications


@dataclass
class _ExcelUpload:
    document: documents.Document
    file_id: str


def run_cross_format_analysis(selected: list[documents.Document]) -> CrossFormatAnalysisOutcome:
    start = time.monotonic()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    configured_model = os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL

    def elapsed() -> float:
        return time.monotonic() - start

    if not api_key:
        return CrossFormatAnalysisOutcome(
            success=False,
            transmitted=False,
            analysis_seconds=elapsed(),
            model=configured_model,
            error_type="missing_api_key",
            error_message=_ERROR_MESSAGES["missing_api_key"],
        )

    validation_error = validate_selection(selected)
    if validation_error is not None:
        error_type, error_message = validation_error
        return CrossFormatAnalysisOutcome(
            success=False,
            transmitted=False,
            analysis_seconds=elapsed(),
            model=configured_model,
            error_type=error_type,
            error_message=error_message,
        )

    pdf_documents = [d for d in selected if d.extension == ".pdf"]
    excel_documents = [d for d in selected if d.extension in (".xlsx", ".xls")]

    for document in selected:
        if not documents.stored_file_path(document).is_file():
            return CrossFormatAnalysisOutcome(
                success=False,
                transmitted=False,
                analysis_seconds=elapsed(),
                model=configured_model,
                error_type="missing_file",
                error_message=_ERROR_MESSAGES["missing_file"],
            )

    client = anthropic.Anthropic(api_key=api_key, timeout=ANALYSIS_CLIENT_TIMEOUT_SECONDS)

    pdf_blocks: list[DocumentBlockParam] = []
    for document in pdf_documents:
        pdf_bytes = documents.stored_file_path(document).read_bytes()
        pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("ascii")
        pdf_blocks.append(
            {
                "type": "document",
                "source": {"type": "base64", "media_type": "application/pdf", "data": pdf_b64},
                "title": document.original_filename,
                "citations": {"enabled": True},
            }
        )

    excel_labels = [f"Workbook {i + 1}" for i in range(len(excel_documents))]
    label_to_document = dict(zip(excel_labels, excel_documents))

    excel_uploads: list[_ExcelUpload] = []

    def cleanup_excel() -> list[ExcelCleanupResult]:
        results = []
        for upload in excel_uploads:
            try:
                client.files.delete(upload.file_id)
                succeeded = True
            except Exception:
                succeeded = False
            results.append(
                ExcelCleanupResult(
                    document_id=upload.document.id,
                    document_filename=upload.document.original_filename,
                    attempted=True,
                    succeeded=succeeded,
                )
            )
        return results

    def upload_fail(error_type: str, message: str) -> CrossFormatAnalysisOutcome:
        return CrossFormatAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=elapsed(),
            model=configured_model,
            excel_cleanup=cleanup_excel(),
            error_type=error_type,
            error_message=_redact(message, api_key),
        )

    for document in excel_documents:
        mime_type = documents.ALLOWED_EXTENSIONS[document.extension]
        safe_filename = xlsx_inspection._files_api_safe_filename(document.original_filename)
        try:
            with open(documents.stored_file_path(document), "rb") as fh:
                uploaded = client.files.upload(file=(safe_filename, fh, mime_type))
        except anthropic.AuthenticationError:
            return upload_fail("invalid_api_key", _ERROR_MESSAGES["invalid_api_key"])
        except anthropic.RateLimitError:
            return upload_fail("rate_limit", _ERROR_MESSAGES["rate_limit"])
        except anthropic.APIStatusError as exc:
            if is_insufficient_credit_error(exc):
                return upload_fail("insufficient_credit", _ERROR_MESSAGES["insufficient_credit"])
            if exc.status_code == 413:
                return upload_fail("oversized_excel_workbook", _ERROR_MESSAGES["oversized_excel_workbook"])
            return upload_fail(
                "upload_failed", f"{_ERROR_MESSAGES['upload_failed']} API error ({exc.status_code}): {exc.message}"
            )
        except anthropic.APIConnectionError:
            return upload_fail("network_error", _ERROR_MESSAGES["network_error"])
        except Exception as exc:  # pragma: no cover - defensive catch-all
            return upload_fail("upload_failed", f"{_ERROR_MESSAGES['upload_failed']} ({exc})")

        excel_uploads.append(_ExcelUpload(document=document, file_id=uploaded.id))

    container_blocks: list[ContainerUploadBlockParam] = [
        {"type": "container_upload", "file_id": upload.file_id} for upload in excel_uploads
    ]

    pdf_list = ", ".join(f'{i + 1}. "{d.original_filename}"' for i, d in enumerate(pdf_documents))
    excel_list = "; ".join(f'{label} = "{doc.original_filename}"' for label, doc in label_to_document.items())
    intro = (
        f"You have been given {len(pdf_documents)} original PDF document(s) and "
        f"{len(excel_documents)} original Excel workbook(s) as evidence for one transaction.\n\n"
        f"PDF documents, in this order: {pdf_list}.\n"
        f"Excel workbooks, each identified by a stable label you must cite exactly as shown: {excel_list}."
    )

    text_block: TextBlockParam = {"type": "text", "text": intro + "\n\n" + MANDATE + STRUCTURE_INSTRUCTIONS}
    messages: list[MessageParam] = [{"role": "user", "content": [*pdf_blocks, *container_blocks, text_block]}]

    def transmitted_fail(
        error_type: str, message: str, cleanup: list[ExcelCleanupResult]
    ) -> CrossFormatAnalysisOutcome:
        return CrossFormatAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=elapsed(),
            model=configured_model,
            excel_cleanup=cleanup,
            error_type=error_type,
            error_message=_redact(message, api_key),
        )

    container_id: str | None = None
    response = None
    tool_trace: list[dict] = []

    try:
        for _ in range(MAX_PAUSE_CONTINUATIONS + 1):
            kwargs: dict = dict(
                model=configured_model,
                max_tokens=ANALYSIS_MAX_TOKENS,
                thinking={"type": "adaptive"},
                output_config={"effort": "high"},
                tools=[{"type": CODE_EXECUTION_TOOL_TYPE, "name": "code_execution"}],
                messages=messages,
            )
            if container_id:
                kwargs["container"] = container_id

            with client.messages.stream(**kwargs) as stream:
                response = stream.get_final_message()

            if response.container:
                container_id = response.container.id
            tool_trace.extend(xlsx_inspection._extract_tool_trace(response.content))

            if response.stop_reason != "pause_turn":
                break
            messages = messages + [{"role": "assistant", "content": response.content}]
        else:
            return transmitted_fail("still_paused", _ERROR_MESSAGES["still_paused"], cleanup_excel())
    except anthropic.AuthenticationError:
        return transmitted_fail("invalid_api_key", _ERROR_MESSAGES["invalid_api_key"], cleanup_excel())
    except anthropic.NotFoundError:
        return transmitted_fail("model_unavailable", _ERROR_MESSAGES["model_unavailable"], cleanup_excel())
    except anthropic.RateLimitError:
        return transmitted_fail("rate_limit", _ERROR_MESSAGES["rate_limit"], cleanup_excel())
    except anthropic.BadRequestError as exc:
        error_type = cross_document_analysis._classify_bad_request(str(exc.message))
        message = _ERROR_MESSAGES.get(error_type, _ERROR_MESSAGES["invalid_pdf"])
        offending = _describe_offending_pdf(str(exc.message), pdf_documents)
        if offending:
            message = f'{message} (document: "{offending}")'
        return transmitted_fail(error_type, message, cleanup_excel())
    except anthropic.APIStatusError as exc:
        if is_insufficient_credit_error(exc):
            return transmitted_fail("insufficient_credit", _ERROR_MESSAGES["insufficient_credit"], cleanup_excel())
        return transmitted_fail(
            "unexpected_error", f"API error ({exc.status_code}): {exc.message}", cleanup_excel()
        )
    except anthropic.APIConnectionError:
        return transmitted_fail("network_error", _ERROR_MESSAGES["network_error"], cleanup_excel())
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return transmitted_fail("unexpected_error", f"{_ERROR_MESSAGES['unexpected_error']} ({exc})", cleanup_excel())

    assert response is not None
    analysis_seconds = elapsed()
    usage: dict[str, Any] = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        # Derived from our own captured trace, not response.usage.server_tool_use
        # - see xlsx_inspection.py's identical note on why.
        "code_execution_requests": sum(1 for entry in tool_trace if entry["kind"] == "tool_use"),
    }

    segments = _extract_segments(response.content, pdf_documents, label_to_document)
    excel_cleanup = cleanup_excel()
    excel_verification = _verify_excel_citations(segments, excel_documents)

    if response.stop_reason == "refusal":
        explanation = getattr(response.stop_details, "explanation", None) if response.stop_details else None
        return CrossFormatAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=analysis_seconds,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage,
            segments=segments,
            tool_trace=tool_trace,
            excel_cleanup=excel_cleanup,
            excel_verification=excel_verification,
            error_type="refused",
            error_message=explanation or _ERROR_MESSAGES["refused"],
        )

    if response.stop_reason == "max_tokens":
        return CrossFormatAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=analysis_seconds,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage,
            segments=segments,
            tool_trace=tool_trace,
            excel_cleanup=excel_cleanup,
            excel_verification=excel_verification,
            error_type="truncated_response",
            error_message=_ERROR_MESSAGES["truncated_response"],
        )

    has_text = any(
        (p.text or "").strip() for s in segments for p in s.parts if p.type == "text"
    )
    if not segments or not has_text:
        return CrossFormatAnalysisOutcome(
            success=False,
            transmitted=True,
            analysis_seconds=analysis_seconds,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage,
            tool_trace=tool_trace,
            excel_cleanup=excel_cleanup,
            excel_verification=excel_verification,
            error_type="empty_response",
            error_message=_ERROR_MESSAGES["empty_response"],
        )

    return CrossFormatAnalysisOutcome(
        success=True,
        transmitted=True,
        analysis_seconds=analysis_seconds,
        model=response.model,
        stop_reason=response.stop_reason,
        usage=usage,
        segments=segments,
        tool_trace=tool_trace,
        excel_cleanup=excel_cleanup,
        excel_verification=excel_verification,
    )
