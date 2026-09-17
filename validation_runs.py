"""Orchestrates a Validation Lab run: executes Milestone 7's existing
cross-format reconciliation path unchanged, and records the audit
information needed to judge whether that run was genuinely blind.

Blindness guarantee by construction: `start_new_run` below is the only
function in this module that calls into cross_format_analysis, and it is
called with nothing but a `list[documents.Document]` - the exact same input
type the plain Milestone 7 endpoint already passes. It never imports
`answer_keys.AnswerKeyVersion.content`, never receives it as a parameter,
and has no code path that could route it into a request. The only
answer-key data this module ever touches is metadata already treated as
non-secret by design: a version's id, version_number, checksum, and
locked_at timestamp - never `content`. grep this file for "content" to
confirm.

This module does not modify cross_format_analysis.py, its mandate, its
model configuration, or its citation behaviour in any way - it only calls
the existing `run_cross_format_analysis` and stores its own bookkeeping
around the call.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import answer_keys
import cross_format_analyses
import cross_format_analysis
import documents
import store


def mandate_fingerprint() -> tuple[str, str]:
    """Returns (mandate_version, sha256_checksum) for the exact
    cross_format_analysis prompt text currently in effect, computed fresh
    from the live module on every call - never hardcoded - so a checksum
    recorded on a run always reflects what that run actually sent, and a
    future change to the mandate is automatically reflected in new
    fingerprints without anyone needing to remember to update a constant.
    """
    fingerprint_source = (
        cross_format_analysis.MANDATE_VERSION + "\n" + cross_format_analysis.MANDATE + cross_format_analysis.STRUCTURE_INSTRUCTIONS
    )
    checksum = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    return cross_format_analysis.MANDATE_VERSION, checksum


class ValidationRunError(Exception):
    """Raised for a precondition failure that must block a run from
    starting at all (as opposed to the analysis itself failing, which is a
    normal, recorded outcome - see cross_format_analysis.CrossFormatAnalysisOutcome)."""


@dataclass
class ValidationRun:
    id: str
    validation_case_id: str
    cross_format_analysis_id: str
    answer_key_version_id: str
    answer_key_version_number: int
    answer_key_checksum: str | None
    answer_key_locked_at: str | None
    is_blind: bool
    mandate_version: str
    mandate_checksum: str
    pdf_document_ids: list[str]
    excel_document_ids: list[str]
    started_at: str
    completed_at: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "validation_case_id": self.validation_case_id,
            "cross_format_analysis_id": self.cross_format_analysis_id,
            "answer_key_version_id": self.answer_key_version_id,
            "answer_key_version_number": self.answer_key_version_number,
            "answer_key_checksum": self.answer_key_checksum,
            "answer_key_locked_at": self.answer_key_locked_at,
            "is_blind": self.is_blind,
            "mandate_version": self.mandate_version,
            "mandate_checksum": self.mandate_checksum,
            "pdf_document_ids": self.pdf_document_ids,
            "excel_document_ids": self.excel_document_ids,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "created_at": self.created_at,
        }


def init_validation_runs_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS validation_runs (
                id TEXT PRIMARY KEY,
                validation_case_id TEXT NOT NULL,
                cross_format_analysis_id TEXT NOT NULL,
                answer_key_version_id TEXT NOT NULL,
                answer_key_version_number INTEGER NOT NULL,
                answer_key_checksum TEXT,
                answer_key_locked_at TEXT,
                is_blind INTEGER NOT NULL,
                mandate_version TEXT NOT NULL,
                mandate_checksum TEXT NOT NULL,
                pdf_document_ids_json TEXT NOT NULL,
                excel_document_ids_json TEXT NOT NULL,
                started_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_validation_runs_case ON validation_runs(validation_case_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_run(row) -> ValidationRun:
    return ValidationRun(
        id=row["id"],
        validation_case_id=row["validation_case_id"],
        cross_format_analysis_id=row["cross_format_analysis_id"],
        answer_key_version_id=row["answer_key_version_id"],
        answer_key_version_number=row["answer_key_version_number"],
        answer_key_checksum=row["answer_key_checksum"],
        answer_key_locked_at=row["answer_key_locked_at"],
        is_blind=bool(row["is_blind"]),
        mandate_version=row["mandate_version"],
        mandate_checksum=row["mandate_checksum"],
        pdf_document_ids=json.loads(row["pdf_document_ids_json"]),
        excel_document_ids=json.loads(row["excel_document_ids_json"]),
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        created_at=row["created_at"],
    )


def _insert_run(
    *,
    validation_case_id: str,
    cross_format_analysis_id: str,
    answer_key_version: answer_keys.AnswerKeyVersion,
    is_blind: bool,
    pdf_document_ids: list[str],
    excel_document_ids: list[str],
    started_at: str,
    completed_at: str,
) -> ValidationRun:
    mandate_version, mandate_checksum = mandate_fingerprint()
    run = ValidationRun(
        id=uuid.uuid4().hex,
        validation_case_id=validation_case_id,
        cross_format_analysis_id=cross_format_analysis_id,
        answer_key_version_id=answer_key_version.id,
        answer_key_version_number=answer_key_version.version_number,
        answer_key_checksum=answer_key_version.checksum,
        answer_key_locked_at=answer_key_version.locked_at,
        is_blind=is_blind,
        mandate_version=mandate_version,
        mandate_checksum=mandate_checksum,
        pdf_document_ids=pdf_document_ids,
        excel_document_ids=excel_document_ids,
        started_at=started_at,
        completed_at=completed_at,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO validation_runs (
                id, validation_case_id, cross_format_analysis_id, answer_key_version_id,
                answer_key_version_number, answer_key_checksum, answer_key_locked_at, is_blind,
                mandate_version, mandate_checksum, pdf_document_ids_json, excel_document_ids_json,
                started_at, completed_at, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                run.id,
                run.validation_case_id,
                run.cross_format_analysis_id,
                run.answer_key_version_id,
                run.answer_key_version_number,
                run.answer_key_checksum,
                run.answer_key_locked_at,
                int(run.is_blind),
                run.mandate_version,
                run.mandate_checksum,
                json.dumps(run.pdf_document_ids),
                json.dumps(run.excel_document_ids),
                run.started_at,
                run.completed_at,
                run.created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return run


def start_new_run(
    validation_case_id: str, selected: list[documents.Document]
) -> tuple[ValidationRun, cross_format_analysis.CrossFormatAnalysisOutcome]:
    """Executes a brand-new, genuinely blind cross-format reconciliation
    run for a validation case. `selected` must be nothing but
    `documents.Document` objects the caller already validated belong to
    this project - this function has no other source of document data and
    never touches answer-key content.

    Raises ValidationRunError if the case's current answer-key version is
    not locked - a run may never begin without one, per the milestone's
    blindness requirements.
    """
    current_key = answer_keys.get_current_version(validation_case_id)
    if current_key is None or not current_key.is_locked:
        raise ValidationRunError("the answer key must be locked before a validation run can begin")

    started_at = datetime.now(timezone.utc).isoformat()
    outcome = cross_format_analysis.run_cross_format_analysis(selected)
    completed_at = datetime.now(timezone.utc).isoformat()

    pdf_docs = [d for d in selected if d.extension == ".pdf"]
    excel_docs = [d for d in selected if d.extension in (".xlsx", ".xls")]

    record = cross_format_analyses.create_cross_format_analysis(
        project_id=selected[0].project_id if selected else "",
        pdf_document_ids=[d.id for d in pdf_docs],
        pdf_document_filenames=[d.original_filename for d in pdf_docs],
        pdf_document_checksums=[d.sha256 for d in pdf_docs],
        excel_document_ids=[d.id for d in excel_docs],
        excel_document_filenames=[d.original_filename for d in excel_docs],
        excel_document_checksums=[d.sha256 for d in excel_docs],
        status="success" if outcome.success else "error",
        transmitted=outcome.transmitted,
        analysis_seconds=outcome.analysis_seconds,
        model=outcome.model,
        mandate_version=cross_format_analysis.MANDATE_VERSION,
        stop_reason=outcome.stop_reason,
        input_tokens=outcome.usage["input_tokens"] if outcome.usage else None,
        output_tokens=outcome.usage["output_tokens"] if outcome.usage else None,
        code_execution_requests=outcome.usage.get("code_execution_requests") if outcome.usage else None,
        error_type=outcome.error_type,
        error_message=outcome.error_message,
        segments=[s.to_dict() for s in outcome.segments] if outcome.segments else None,
        tool_trace=outcome.tool_trace,
        excel_cleanup=[c.to_dict() for c in outcome.excel_cleanup] if outcome.excel_cleanup else None,
        excel_verification=[v.to_dict() for v in outcome.excel_verification] if outcome.excel_verification else None,
    )

    # A run started only after the key was locked (checked above) is blind
    # by construction; the timestamp comparison is kept anyway as a
    # belt-and-braces check against clock skew or future refactors, rather
    # than assuming the precondition check above is the only guard.
    is_blind = current_key.locked_at is not None and current_key.locked_at <= started_at

    run = _insert_run(
        validation_case_id=validation_case_id,
        cross_format_analysis_id=record.id,
        answer_key_version=current_key,
        is_blind=is_blind,
        pdf_document_ids=record.pdf_document_ids,
        excel_document_ids=record.excel_document_ids,
        started_at=started_at,
        completed_at=completed_at,
    )
    return run, outcome


def attach_existing_analysis(
    validation_case_id: str, analysis: cross_format_analyses.CrossFormatAnalysis
) -> ValidationRun:
    """Links an *already-completed* cross-format analysis (run earlier
    through the plain Milestone 7 flow, or from a prior validation run) to
    this validation case, instead of transmitting anything new. Useful for
    retrospectively scoring an analysis that already exists - such a run is
    only "blind" if the current answer-key version was locked at or before
    that analysis's own creation time; otherwise it is explicitly recorded
    as retrospective (is_blind=False), never mislabeled.

    Still requires a locked answer-key version to exist, so every
    validation run - new or attached - always has a checksummed key to
    compare against.
    """
    current_key = answer_keys.get_current_version(validation_case_id)
    if current_key is None or not current_key.is_locked:
        raise ValidationRunError("the answer key must be locked before attaching an analysis to a validation case")

    is_blind = current_key.locked_at is not None and current_key.locked_at <= analysis.created_at

    return _insert_run(
        validation_case_id=validation_case_id,
        cross_format_analysis_id=analysis.id,
        answer_key_version=current_key,
        is_blind=is_blind,
        pdf_document_ids=analysis.pdf_document_ids,
        excel_document_ids=analysis.excel_document_ids,
        started_at=analysis.created_at,
        completed_at=analysis.completed_at,
    )


def list_runs_for_case(validation_case_id: str) -> list[ValidationRun]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM validation_runs WHERE validation_case_id = %s ORDER BY created_at DESC",
            (validation_case_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_run(row) for row in rows]


def get_run(validation_case_id: str, run_id: str) -> ValidationRun | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM validation_runs WHERE validation_case_id = %s AND id = %s",
            (validation_case_id, run_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_run(row) if row else None
