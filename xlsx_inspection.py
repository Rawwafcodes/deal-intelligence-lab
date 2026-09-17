"""Send one original Excel workbook (.xlsx or .xls) to Claude for inspection
using Anthropic's Files API + code-execution tool. Claude receives the
original file inside its sandboxed code-execution container and decides for
itself how to open and inspect it - this module never extracts, converts,
flattens, summarises, chunks, or otherwise locally interprets the workbook's
contents. The only local file access here is a narrow, post-hoc structural
check (sheet names and grid bounds only - never cell values) used solely to
verify that citations Claude returned actually exist in the workbook; see
`_open_workbook_structure` and its docstring for exactly where that line is
drawn.

Why Files API + code execution (not the `document` content block): Anthropic
directly documents that spreadsheets aren't supported by the `document`
content block ("For file types that the document block doesn't support (for
example, .docx and .xlsx)..."), and names container_upload + code execution
as the intended path for analyzing datasets/workbooks. Confirmed by
inspecting the installed anthropic SDK (1.5.0) and Anthropic's current docs
(platform.claude.com/docs/en/build-with-claude/files and
.../agents-and-tools/tool-use/code-execution-tool) - not from memory:
- `container_upload` content blocks and every `code_execution_*` tool type
  are part of the SDK's stable (non-beta) `MessageParam`/`ToolUnionParam`
  unions; the docs state explicitly "None of the three tool versions
  requires an anthropic-beta header."
- `code_execution_20260521` is used here: the same sandbox runtime as
  `code_execution_20260120` (REPL persistence, programmatic tool calling),
  with a tool description that tells Claude about a 90-second wall-clock
  budget per Python cell so it can pace long-running analysis.
- openpyxl and xlrd are pre-installed inside Anthropic's sandbox, so Claude
  can genuinely open and query the workbook itself.

Citations are Anthropic's PDF-only feature - there is no native citation
mechanism for code-execution/container_upload content. So "cite every
workbook-specific conclusion with its exact sheet and cell or range" is
implemented here as a citation *convention* this module defines and asks
Claude to follow (see CITATION_FORMAT_INSTRUCTIONS), then parses out of the
plain response text with CITATION_PREFIX_RE and verifies structurally. A citation
the model writes in some other shape simply won't be recognized as a
citation (and is never silently treated as one) - it stays as plain text.

Data retention (do not oversimplify this - see the milestone's evidence
requirements): this app always attempts to delete the Files API object
after analysis and records whether that deletion succeeded. That is not the
same as immediate, total server-side erasure:
- Per Anthropic's Files API docs, a deleted file "may persist in active
  Messages API calls and associated tool uses" that are already running,
  and deleted-file metadata can remain queryable for a period after
  deletion completes.
- Per Anthropic's code-execution docs, independently of Files API deletion,
  "Container data, including execution artifacts, uploaded files, and
  outputs, is retained for up to 30 days" - deleting the Files API object
  does not shorten or clear that separate container-side retention window.
- Neither the Files API nor the code-execution tool is eligible for Zero
  Data Retention (ZDR); both are explicitly listed as ZDR: not eligible.
This module's `remote_cleanup_attempted`/`remote_cleanup_succeeded` fields
describe only the Files API delete call outcome - never claim more than
that in UI copy built on top of this module.
"""

from __future__ import annotations

import os
import re
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anthropic
from anthropic.types import ContainerUploadBlockParam, MessageParam, TextBlockParam
from dotenv import load_dotenv

from anthropic_errors import is_insufficient_credit_error

import documents
import pdf_inspection

load_dotenv(Path(__file__).parent / ".env.local")

DEFAULT_MODEL = pdf_inspection.DEFAULT_MODEL

# Files API limit is 500 MB/file (platform.claude.com/docs/en/build-with-claude/files
# -> "Storage limits"). Unlike PDF base64 input, an upload isn't inlined into
# the request body, so there's no base64-inflation math here - this cap
# mirrors Anthropic's own limit directly, with the API's 413 as the backstop.
MAX_WORKBOOK_SOURCE_BYTES = 500 * 1024 * 1024

ANALYSIS_MAX_TOKENS = 64000
# Code execution can genuinely run for several minutes per tool call, and a
# pause_turn continuation means more than one such call in one analysis.
ANALYSIS_CLIENT_TIMEOUT_SECONDS = 1800.0
# "pause_turn" means the API paused a long-running turn and expects the
# response sent back as-is to let Claude continue - not a failure. Bounded
# so a pathological workbook can't loop forever.
MAX_PAUSE_CONTINUATIONS = 5

CODE_EXECUTION_TOOL_TYPE = "code_execution_20260521"

# Local audit-trail storage only (not provider-side logs): cap how much of
# each tool call's stdout/stderr we keep, so a command that dumps a lot of
# spreadsheet content into its output doesn't balloon our own database.
TOOL_TRACE_TEXT_CAP = 2000

MANDATE_VERSION = "2"

MANDATE = (
    "Inspect this original workbook directly using code execution.\n\n"
    "Develop an understanding of the workbook's purpose and structure. "
    "Determine which sheets, cells, formulas, assumptions, checks and "
    "relationships are material. Use code to verify your conclusions.\n\n"
    "Identify:\n"
    "- workbook purpose;\n"
    "- sheet structure and relationships;\n"
    "- key financial metrics and periods;\n"
    "- important assumptions;\n"
    "- material hardcoded inputs;\n"
    "- formula patterns and irregularities;\n"
    "- errors, broken links or unresolved checks;\n"
    "- hidden sheets or relevant hidden content;\n"
    "- external workbook dependencies;\n"
    "- ambiguities and limitations.\n\n"
    "Do not treat every hardcoded value as an error. Do not use external "
    "knowledge. Cite every workbook-specific conclusion with its exact "
    "sheet and cell or range."
)

STRUCTURE_INSTRUCTIONS = (
    "\n\nStructure your reply with exactly these section headings, each "
    "alone on its own line starting with '## ', in this order:\n"
    "## Workbook Identification and Purpose\n"
    "## Sheet Map\n"
    "## Key Periods, Units and Currencies\n"
    "## Principal Metrics\n"
    "## Material Assumptions\n"
    "## Formula and Dependency Observations\n"
    "## Potential Issues\n"
    "## Limitations\n"
    "## Analysis Actions Performed\n\n"
    "Under \"Analysis Actions Performed\", briefly describe what you "
    "actually did with code execution (which sheets you opened, what you "
    "checked) so the process can be reviewed.\n\n"
    "Citation format - use this exact format for every workbook-specific "
    "claim, immediately after the fact it supports:\n"
    "('Sheet Name'!CellRef [value]) for a hardcoded or calculated value\n"
    "('Sheet Name'!CellRef [formula]) for a formula\n"
    "('Sheet Name'!CellRef [label]) for a text label\n"
    "For a range, use CellRef1:CellRef2, e.g. ('Sheet Name'!B7:B12 "
    "[value]).\n"
    "Always wrap the sheet name in single quotes, exactly as it appears in "
    "the workbook, even if it has no spaces. Only cite a sheet or cell you "
    "have actually opened or computed with code - never estimate or guess "
    "a reference. Put nothing else inside the parentheses - state the "
    "value, formula, or label as ordinary text before or after the "
    "citation, not inside it, e.g. write \"the growth rate is 8% "
    "('Assumptions'!B2 [value])\", not \"('Assumptions'!B2 [value] 8%)\"."
)

# Matches the citation *prefix* only - up to and including the "[kind]"
# tag, deliberately not the closing paren (see _parse_segments for why).
# Confirmed live, Claude reliably follows the sheet!ref/[kind] shape but
# sometimes appends the cell's actual value or label text before the
# closing paren for readability, e.g. ('Assumptions'!B4 [value] 1000000) -
# an earlier, stricter pattern requiring "]` immediately followed by `)`
# silently failed to recognize citations shaped exactly like that.
CITATION_PREFIX_RE = re.compile(
    r"\('([^']+)'!"
    r"(\$?[A-Za-z]{1,3}\$?[0-9]+)"
    r"(?::(\$?[A-Za-z]{1,3}\$?[0-9]+))?"
    r"\s*\[(value|formula|label)\]"
)

_ERROR_MESSAGES = {
    "missing_api_key": "No API key is configured. Set ANTHROPIC_API_KEY (or add it to .env.local) and try again.",
    "invalid_api_key": "The configured API key was rejected. Check ANTHROPIC_API_KEY and try again.",
    "insufficient_credit": "The Anthropic account has insufficient credit for this request.",
    "rate_limit": "Rate limit reached. Wait a moment and try again.",
    "network_error": "Could not reach the Anthropic API. Check your internet connection and try again.",
    "model_unavailable": "The configured model is not available. Check ANTHROPIC_MODEL and try again.",
    "missing_file": "The stored file for this document is missing on disk.",
    "oversized_workbook": (
        f"This workbook is larger than the {MAX_WORKBOOK_SOURCE_BYTES // (1024 * 1024)} MB "
        "this app will upload for inspection."
    ),
    "not_workbook": "Only .xlsx or .xls workbooks can be inspected with this action.",
    "upload_failed": "Uploading the workbook to Anthropic failed.",
    "still_paused": "Claude's analysis paused repeatedly and did not finish in the allotted number of turns.",
    "refused": "Claude declined to analyze this workbook.",
    "truncated_response": (
        "Claude's analysis was cut off before finishing (hit the output token limit). "
        "The partial analysis below is incomplete."
    ),
    "empty_response": "Claude returned no analysis text.",
    "unexpected_error": "The workbook inspection failed unexpectedly.",
}


@dataclass
class Citation:
    sheet: str
    ref: str
    kind: str  # "value" | "formula" | "label"
    exists: bool | None  # None: could not be verified locally
    raw_text: str

    def to_dict(self) -> dict:
        return {
            "sheet": self.sheet,
            "ref": self.ref,
            "kind": self.kind,
            "exists": self.exists,
            "raw_text": self.raw_text,
        }


@dataclass
class Segment:
    type: str  # "text" | "citation"
    text: str | None = None
    citation: Citation | None = None

    def to_dict(self) -> dict:
        if self.type == "citation":
            assert self.citation is not None
            return {"type": "citation", "citation": self.citation.to_dict()}
        return {"type": "text", "text": self.text}


@dataclass
class XlsxInspectionOutcome:
    success: bool
    transmitted: bool
    remote_cleanup_attempted: bool
    remote_cleanup_succeeded: bool | None
    verification_available: bool
    verification_unavailable_reason: str | None
    analysis_seconds: float
    model: str
    stop_reason: str | None = None
    usage: dict | None = None
    segments: list[Segment] | None = None
    tool_trace: list[dict] | None = None
    error_type: str | None = None
    error_message: str | None = None


def _redact(text: str, secret: str | None) -> str:
    if not secret:
        return text
    return text.replace(secret, "[redacted]")


_FORBIDDEN_FILENAME_CHARS = re.compile(r'[<>:"|?*\\/\x00-\x1f]')


def _files_api_safe_filename(name: str) -> str:
    """Anthropic's Files API rejects filenames containing <>:"|?*\\/ or
    control characters. Sanitize only the name we send upstream; the
    document's own display filename is untouched."""
    safe = _FORBIDDEN_FILENAME_CHARS.sub("_", name).strip()
    return safe or "workbook"


# ---------------------------------------------------------------------------
# Citation parsing and structural verification
# ---------------------------------------------------------------------------


def _parse_segments(text: str) -> list[Segment]:
    """Splits text on citation matches. A citation's trailing content (the
    cell's value/label, or a formula like `=NPV(Assumptions.B3,B2:B4)`) can
    itself contain parentheses, so the citation's own closing paren can't
    be found with a simple "up to the next )" regex - that stops at the
    formula's own inner `)` and leaves a stray `)` dangling as text. So
    only the prefix up to "[kind]" is matched by regex; the closing paren
    is then found by scanning forward and tracking paren depth, correctly
    skipping over any balanced nested parentheses in between.
    """
    segments: list[Segment] = []
    pos = 0
    search_start = 0
    while True:
        match = CITATION_PREFIX_RE.search(text, search_start)
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
            # No matching close paren before the text ends - not a
            # well-formed citation; keep scanning past this opening paren.
            search_start = match.start() + 1
            continue

        citation_end = i
        if match.start() > pos:
            segments.append(Segment(type="text", text=text[pos : match.start()]))
        sheet, start_ref, end_ref, kind = match.groups()
        ref = f"{start_ref}:{end_ref}" if end_ref else start_ref
        raw_text = text[match.start() : citation_end]
        segments.append(Segment(type="citation", citation=Citation(sheet=sheet, ref=ref, kind=kind, exists=None, raw_text=raw_text)))
        pos = citation_end
        search_start = citation_end

    if pos < len(text):
        segments.append(Segment(type="text", text=text[pos:]))
    return segments


@dataclass
class _SheetStructure:
    hidden: bool
    max_row: int
    max_col: int


class WorkbookVerificationUnavailable(Exception):
    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


_OLE2_SIGNATURE = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def _open_workbook_structure(path: Path, extension: str) -> dict[str, _SheetStructure]:
    """Read only structural metadata (sheet names, hidden state, used
    dimensions) - never cell values, formulas, or labels. This is the one
    place this module reads the workbook locally, and it exists solely to
    check whether a cited sheet/cell reference actually exists, per the
    milestone's evidence requirements - not to interpret what the workbook
    says. Raises WorkbookVerificationUnavailable if the file can't be
    opened this way (e.g. it looks encrypted, or isn't a valid workbook);
    callers must treat that as "verification unavailable", not as a verdict
    on Claude's analysis, which may still have succeeded independently
    inside Claude's own sandboxed code execution.
    """
    if extension == ".xlsx":
        try:
            import openpyxl
        except ImportError as exc:  # pragma: no cover - dependency always installed
            raise WorkbookVerificationUnavailable("openpyxl_unavailable") from exc

        def _load(read_only: bool):
            try:
                return openpyxl.load_workbook(path, read_only=read_only, data_only=False)
            except zipfile.BadZipFile as exc:
                header = path.read_bytes()[:8]
                if header.startswith(_OLE2_SIGNATURE):
                    raise WorkbookVerificationUnavailable("encrypted_workbook") from exc
                raise WorkbookVerificationUnavailable("malformed_workbook") from exc
            except Exception as exc:
                raise WorkbookVerificationUnavailable("malformed_workbook") from exc

        workbook = _load(read_only=True)
        try:
            structure = {}
            # openpyxl's read-only mode takes each sheet's used range from the
            # file's stored <dimension> declaration rather than scanning cells,
            # for speed. A workbook saved by a tool that omits or mis-states
            # that declaration (confirmed live: not every workbook that opens
            # cleanly writes one) makes max_row/max_column come back None for
            # every sheet - silently coercing that to "1 row, 1 column" would
            # then reject every real citation into the file as out of range.
            # Reopen in normal mode (which computes bounds by scanning, not by
            # trusting the declaration) only when that happens, so a citation
            # is never marked non-existent because of how the file was saved
            # rather than what it actually contains.
            needs_full_scan = any(
                worksheet.max_row is None or worksheet.max_column is None
                for worksheet in workbook.worksheets
            )
            if needs_full_scan:
                workbook.close()
                workbook = _load(read_only=False)
            for worksheet in workbook.worksheets:
                structure[worksheet.title] = _SheetStructure(
                    hidden=worksheet.sheet_state != "visible",
                    max_row=worksheet.max_row or 1,
                    max_col=worksheet.max_column or 1,
                )
            return structure
        finally:
            workbook.close()

    if extension == ".xls":
        try:
            import xlrd
        except ImportError as exc:  # pragma: no cover - dependency always installed
            raise WorkbookVerificationUnavailable("xlrd_unavailable") from exc

        try:
            legacy_book = xlrd.open_workbook(str(path))
        except Exception as exc:
            header = path.read_bytes()[:8]
            if header.startswith(_OLE2_SIGNATURE):
                # A bare OLE2 container without a valid BIFF stream inside
                # is the shape a password-protected legacy .xls takes.
                raise WorkbookVerificationUnavailable("encrypted_workbook") from exc
            raise WorkbookVerificationUnavailable("malformed_workbook") from exc

        return {
            sheet.name: _SheetStructure(
                hidden=sheet.visibility != 0,
                max_row=max(sheet.nrows, 1),
                max_col=max(sheet.ncols, 1),
            )
            for sheet in legacy_book.sheets()
        }

    raise WorkbookVerificationUnavailable("unsupported_extension")


def _verify_citations(segments: list[Segment], structure: dict[str, _SheetStructure]) -> None:
    """Mutates each Citation's `exists` field in place. Only checks address
    existence (sheet name match + cell/range within that sheet's used grid)
    - never whether the "value"/"formula"/"label" tag or the surrounding
    claim is correct, per "existence validation must not reinterpret
    Claude's conclusion."
    """
    from openpyxl.utils.cell import range_boundaries

    for segment in segments:
        if segment.type != "citation" or segment.citation is None:
            continue
        citation = segment.citation
        sheet_structure = structure.get(citation.sheet)
        if sheet_structure is None:
            citation.exists = False
            continue
        try:
            min_col, min_row, max_col, max_row = range_boundaries(citation.ref)
        except (ValueError, TypeError):
            citation.exists = False
            continue
        # An unbounded reference (e.g. "A:A", a whole-column range) isn't a
        # single cell or bounded range, so range_boundaries leaves a bound
        # as None - not a valid citation under this module's format.
        if min_col is None or min_row is None or max_col is None or max_row is None:
            citation.exists = False
            continue
        citation.exists = (
            1 <= min_row <= sheet_structure.max_row
            and 1 <= max_row <= sheet_structure.max_row
            and 1 <= min_col <= sheet_structure.max_col
            and 1 <= max_col <= sheet_structure.max_col
        )


# ---------------------------------------------------------------------------
# Tool-call trace capture
# ---------------------------------------------------------------------------


def _cap(text: str) -> str:
    if len(text) <= TOOL_TRACE_TEXT_CAP:
        return text
    return text[:TOOL_TRACE_TEXT_CAP] + f"... [truncated, {len(text)} chars total]"


def _extract_tool_trace(content_blocks: Any) -> list[dict]:
    trace: list[dict] = []
    for block in content_blocks:
        block_type = getattr(block, "type", None)
        if block_type == "server_tool_use":
            trace.append({"kind": "tool_use", "tool": getattr(block, "name", None), "input": _cap(str(getattr(block, "input", "")))})
        elif block_type == "bash_code_execution_tool_result":
            content = block.content
            content_type = getattr(content, "type", None)
            if content_type == "bash_code_execution_result":
                trace.append(
                    {
                        "kind": "bash_result",
                        "return_code": content.return_code,
                        "stdout": _cap(content.stdout),
                        "stderr": _cap(content.stderr),
                    }
                )
            elif content_type == "bash_code_execution_tool_result_error":
                trace.append({"kind": "bash_error", "error_code": content.error_code})
        elif block_type == "text_editor_code_execution_tool_result":
            content = block.content
            content_type = getattr(content, "type", None)
            entry: dict = {"kind": "text_editor_result", "result_type": content_type}
            if content_type == "text_editor_code_execution_tool_result_error":
                entry["error_code"] = content.error_code
            trace.append(entry)
    return trace


def _extract_segments(content_blocks: Any) -> list[Segment]:
    text = "".join(block.text for block in content_blocks if getattr(block, "type", None) == "text")
    return _parse_segments(text)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def inspect_workbook(document: documents.Document) -> XlsxInspectionOutcome:
    start = time.monotonic()
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    configured_model = os.environ.get("ANTHROPIC_MODEL", "").strip() or DEFAULT_MODEL

    def elapsed() -> float:
        return time.monotonic() - start

    if not api_key:
        return XlsxInspectionOutcome(
            success=False,
            transmitted=False,
            remote_cleanup_attempted=False,
            remote_cleanup_succeeded=None,
            verification_available=False,
            verification_unavailable_reason="not_attempted",
            analysis_seconds=elapsed(),
            model=configured_model,
            error_type="missing_api_key",
            error_message=_ERROR_MESSAGES["missing_api_key"],
        )

    if document.extension not in (".xlsx", ".xls"):
        return XlsxInspectionOutcome(
            success=False,
            transmitted=False,
            remote_cleanup_attempted=False,
            remote_cleanup_succeeded=None,
            verification_available=False,
            verification_unavailable_reason="not_attempted",
            analysis_seconds=elapsed(),
            model=configured_model,
            error_type="not_workbook",
            error_message=_ERROR_MESSAGES["not_workbook"],
        )

    stored_path = documents.stored_file_path(document)
    if not stored_path.is_file():
        return XlsxInspectionOutcome(
            success=False,
            transmitted=False,
            remote_cleanup_attempted=False,
            remote_cleanup_succeeded=None,
            verification_available=False,
            verification_unavailable_reason="not_attempted",
            analysis_seconds=elapsed(),
            model=configured_model,
            error_type="missing_file",
            error_message=_ERROR_MESSAGES["missing_file"],
        )

    if document.size_bytes > MAX_WORKBOOK_SOURCE_BYTES:
        return XlsxInspectionOutcome(
            success=False,
            transmitted=False,
            remote_cleanup_attempted=False,
            remote_cleanup_succeeded=None,
            verification_available=False,
            verification_unavailable_reason="not_attempted",
            analysis_seconds=elapsed(),
            model=configured_model,
            error_type="oversized_workbook",
            error_message=_ERROR_MESSAGES["oversized_workbook"],
        )

    client = anthropic.Anthropic(api_key=api_key, timeout=ANALYSIS_CLIENT_TIMEOUT_SECONDS)
    mime_type = documents.ALLOWED_EXTENSIONS[document.extension]
    safe_filename = _files_api_safe_filename(document.original_filename)

    def fail(error_type: str, message: str, transmitted: bool = False, cleanup_attempted: bool = False, cleanup_ok: bool | None = None) -> XlsxInspectionOutcome:
        return XlsxInspectionOutcome(
            success=False,
            transmitted=transmitted,
            remote_cleanup_attempted=cleanup_attempted,
            remote_cleanup_succeeded=cleanup_ok,
            verification_available=False,
            verification_unavailable_reason="not_attempted",
            analysis_seconds=elapsed(),
            model=configured_model,
            error_type=error_type,
            error_message=_redact(message, api_key),
        )

    try:
        with open(stored_path, "rb") as fh:
            uploaded = client.files.upload(file=(safe_filename, fh, mime_type))
    except anthropic.AuthenticationError:
        return fail("invalid_api_key", _ERROR_MESSAGES["invalid_api_key"])
    except anthropic.RateLimitError:
        return fail("rate_limit", _ERROR_MESSAGES["rate_limit"])
    except anthropic.APIStatusError as exc:
        if is_insufficient_credit_error(exc):
            return fail("insufficient_credit", _ERROR_MESSAGES["insufficient_credit"])
        if exc.status_code == 413:
            return fail("oversized_workbook", _ERROR_MESSAGES["oversized_workbook"])
        return fail("upload_failed", f"{_ERROR_MESSAGES['upload_failed']} API error ({exc.status_code}): {exc.message}")
    except anthropic.APIConnectionError:
        return fail("network_error", _ERROR_MESSAGES["network_error"])
    except Exception as exc:  # pragma: no cover - defensive catch-all
        return fail("upload_failed", f"{_ERROR_MESSAGES['upload_failed']} ({exc})")

    file_id = uploaded.id
    transmitted = True

    def cleanup() -> bool:
        try:
            client.files.delete(file_id)
            return True
        except Exception:
            return False

    container_upload: ContainerUploadBlockParam = {"type": "container_upload", "file_id": file_id}
    text_block: TextBlockParam = {"type": "text", "text": MANDATE + STRUCTURE_INSTRUCTIONS}
    messages: list[MessageParam] = [{"role": "user", "content": [text_block, container_upload]}]

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
            tool_trace.extend(_extract_tool_trace(response.content))

            if response.stop_reason != "pause_turn":
                break
            messages = messages + [{"role": "assistant", "content": response.content}]
        else:
            cleanup_ok = cleanup()
            return fail(
                "still_paused",
                _ERROR_MESSAGES["still_paused"],
                transmitted=True,
                cleanup_attempted=True,
                cleanup_ok=cleanup_ok,
            )
    except anthropic.AuthenticationError:
        cleanup_ok = cleanup()
        return fail("invalid_api_key", _ERROR_MESSAGES["invalid_api_key"], transmitted=True, cleanup_attempted=True, cleanup_ok=cleanup_ok)
    except anthropic.NotFoundError:
        cleanup_ok = cleanup()
        return fail("model_unavailable", _ERROR_MESSAGES["model_unavailable"], transmitted=True, cleanup_attempted=True, cleanup_ok=cleanup_ok)
    except anthropic.RateLimitError:
        cleanup_ok = cleanup()
        return fail("rate_limit", _ERROR_MESSAGES["rate_limit"], transmitted=True, cleanup_attempted=True, cleanup_ok=cleanup_ok)
    except anthropic.APIStatusError as exc:
        cleanup_ok = cleanup()
        if is_insufficient_credit_error(exc):
            return fail("insufficient_credit", _ERROR_MESSAGES["insufficient_credit"], transmitted=True, cleanup_attempted=True, cleanup_ok=cleanup_ok)
        return fail(
            "unexpected_error",
            f"API error ({exc.status_code}): {exc.message}",
            transmitted=True,
            cleanup_attempted=True,
            cleanup_ok=cleanup_ok,
        )
    except anthropic.APIConnectionError:
        cleanup_ok = cleanup()
        return fail("network_error", _ERROR_MESSAGES["network_error"], transmitted=True, cleanup_attempted=True, cleanup_ok=cleanup_ok)
    except Exception as exc:  # pragma: no cover - defensive catch-all
        cleanup_ok = cleanup()
        return fail("unexpected_error", f"{_ERROR_MESSAGES['unexpected_error']} ({exc})", transmitted=True, cleanup_attempted=True, cleanup_ok=cleanup_ok)

    assert response is not None
    analysis_seconds = elapsed()
    usage_dict: dict[str, Any] = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        # Derived from our own captured trace rather than
        # response.usage.server_tool_use: confirmed against a live response
        # with genuine tool calls, the installed SDK's ServerToolUsage type
        # only exposes web_fetch_requests/web_search_requests - no
        # code_execution_requests field - even though Anthropic's own docs
        # show one. Counting "tool_use" entries in our trace is reliable
        # regardless of what that SDK type does or doesn't expose.
        "code_execution_requests": sum(1 for entry in tool_trace if entry["kind"] == "tool_use"),
    }

    cleanup_ok = cleanup()

    segments = _extract_segments(response.content)

    verification_available = True
    verification_unavailable_reason: str | None = None
    try:
        structure = _open_workbook_structure(stored_path, document.extension)
        _verify_citations(segments, structure)
    except WorkbookVerificationUnavailable as exc:
        verification_available = False
        verification_unavailable_reason = exc.reason

    if response.stop_reason == "refusal":
        explanation = getattr(response.stop_details, "explanation", None) if response.stop_details else None
        return XlsxInspectionOutcome(
            success=False,
            transmitted=True,
            remote_cleanup_attempted=True,
            remote_cleanup_succeeded=cleanup_ok,
            verification_available=verification_available,
            verification_unavailable_reason=verification_unavailable_reason,
            analysis_seconds=analysis_seconds,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage_dict,
            tool_trace=tool_trace,
            error_type="refused",
            error_message=explanation or _ERROR_MESSAGES["refused"],
        )

    if response.stop_reason == "max_tokens":
        return XlsxInspectionOutcome(
            success=False,
            transmitted=True,
            remote_cleanup_attempted=True,
            remote_cleanup_succeeded=cleanup_ok,
            verification_available=verification_available,
            verification_unavailable_reason=verification_unavailable_reason,
            analysis_seconds=analysis_seconds,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage_dict,
            segments=segments,
            tool_trace=tool_trace,
            error_type="truncated_response",
            error_message=_ERROR_MESSAGES["truncated_response"],
        )

    if not segments or not any((s.text or "").strip() for s in segments if s.type == "text"):
        return XlsxInspectionOutcome(
            success=False,
            transmitted=True,
            remote_cleanup_attempted=True,
            remote_cleanup_succeeded=cleanup_ok,
            verification_available=verification_available,
            verification_unavailable_reason=verification_unavailable_reason,
            analysis_seconds=analysis_seconds,
            model=response.model,
            stop_reason=response.stop_reason,
            usage=usage_dict,
            tool_trace=tool_trace,
            error_type="empty_response",
            error_message=_ERROR_MESSAGES["empty_response"],
        )

    return XlsxInspectionOutcome(
        success=True,
        transmitted=True,
        remote_cleanup_attempted=True,
        remote_cleanup_succeeded=cleanup_ok,
        verification_available=verification_available,
        verification_unavailable_reason=verification_unavailable_reason,
        analysis_seconds=analysis_seconds,
        model=response.model,
        stop_reason=response.stop_reason,
        usage=usage_dict,
        segments=segments,
        tool_trace=tool_trace,
    )
