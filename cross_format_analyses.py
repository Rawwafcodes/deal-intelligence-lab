"""Storage for the audit trail of cross-format (PDF + Excel) reconciliation
runs sent to Anthropic. Records are write-once (insert only, no update
function) - the same immutability approach as cross_analyses.py and
xlsx_inspections.py. Each record freezes the exact PDF and Excel document IDs,
filenames and checksums it was run against, transmission and cleanup status
for every uploaded workbook, the mandate version, model, token usage, stop
reason, timing, and the findings themselves. Nothing here is sent anywhere;
this is a local SQLite audit trail only.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import store


@dataclass
class CrossFormatAnalysis:
    id: str
    project_id: str
    pdf_document_ids: list[str]
    pdf_document_filenames: list[str]
    pdf_document_checksums: list[str]
    excel_document_ids: list[str]
    excel_document_filenames: list[str]
    excel_document_checksums: list[str]
    status: str  # "success" | "error"
    transmitted: bool
    created_at: str
    completed_at: str
    analysis_seconds: float
    model: str
    mandate_version: str
    stop_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    code_execution_requests: int | None
    error_type: str | None
    error_message: str | None
    segments: list[dict[str, Any]] | None
    tool_trace: list[dict[str, Any]] | None
    excel_cleanup: list[dict[str, Any]] | None
    excel_verification: list[dict[str, Any]] | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "pdf_document_ids": self.pdf_document_ids,
            "pdf_document_filenames": self.pdf_document_filenames,
            "pdf_document_checksums": self.pdf_document_checksums,
            "excel_document_ids": self.excel_document_ids,
            "excel_document_filenames": self.excel_document_filenames,
            "excel_document_checksums": self.excel_document_checksums,
            "status": self.status,
            "transmitted": self.transmitted,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "analysis_seconds": self.analysis_seconds,
            "model": self.model,
            "mandate_version": self.mandate_version,
            "stop_reason": self.stop_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "code_execution_requests": self.code_execution_requests,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "segments": self.segments,
            "tool_trace": self.tool_trace,
            "excel_cleanup": self.excel_cleanup,
            "excel_verification": self.excel_verification,
        }


def init_cross_format_analyses_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cross_format_analyses (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                pdf_document_ids_json TEXT NOT NULL,
                pdf_document_filenames_json TEXT NOT NULL,
                pdf_document_checksums_json TEXT NOT NULL,
                excel_document_ids_json TEXT NOT NULL,
                excel_document_filenames_json TEXT NOT NULL,
                excel_document_checksums_json TEXT NOT NULL,
                status TEXT NOT NULL,
                transmitted INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                analysis_seconds REAL NOT NULL,
                model TEXT NOT NULL,
                mandate_version TEXT NOT NULL,
                stop_reason TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                code_execution_requests INTEGER,
                error_type TEXT,
                error_message TEXT,
                segments_json TEXT,
                tool_trace_json TEXT,
                excel_cleanup_json TEXT,
                excel_verification_json TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_cross_format_analyses_project ON cross_format_analyses(project_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_cross_format_analysis(row) -> CrossFormatAnalysis:
    return CrossFormatAnalysis(
        id=row["id"],
        project_id=row["project_id"],
        pdf_document_ids=json.loads(row["pdf_document_ids_json"]),
        pdf_document_filenames=json.loads(row["pdf_document_filenames_json"]),
        pdf_document_checksums=json.loads(row["pdf_document_checksums_json"]),
        excel_document_ids=json.loads(row["excel_document_ids_json"]),
        excel_document_filenames=json.loads(row["excel_document_filenames_json"]),
        excel_document_checksums=json.loads(row["excel_document_checksums_json"]),
        status=row["status"],
        transmitted=bool(row["transmitted"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        analysis_seconds=row["analysis_seconds"],
        model=row["model"],
        mandate_version=row["mandate_version"],
        stop_reason=row["stop_reason"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        code_execution_requests=row["code_execution_requests"],
        error_type=row["error_type"],
        error_message=row["error_message"],
        segments=json.loads(row["segments_json"]) if row["segments_json"] else None,
        tool_trace=json.loads(row["tool_trace_json"]) if row["tool_trace_json"] else None,
        excel_cleanup=json.loads(row["excel_cleanup_json"]) if row["excel_cleanup_json"] else None,
        excel_verification=json.loads(row["excel_verification_json"]) if row["excel_verification_json"] else None,
    )


def create_cross_format_analysis(
    *,
    project_id: str,
    pdf_document_ids: list[str],
    pdf_document_filenames: list[str],
    pdf_document_checksums: list[str],
    excel_document_ids: list[str],
    excel_document_filenames: list[str],
    excel_document_checksums: list[str],
    status: str,
    transmitted: bool,
    analysis_seconds: float,
    model: str,
    mandate_version: str,
    stop_reason: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    code_execution_requests: int | None,
    error_type: str | None,
    error_message: str | None,
    segments: list[dict[str, Any]] | None,
    tool_trace: list[dict[str, Any]] | None,
    excel_cleanup: list[dict[str, Any]] | None,
    excel_verification: list[dict[str, Any]] | None,
) -> CrossFormatAnalysis:
    now = datetime.now(timezone.utc).isoformat()
    record = CrossFormatAnalysis(
        id=uuid.uuid4().hex,
        project_id=project_id,
        pdf_document_ids=pdf_document_ids,
        pdf_document_filenames=pdf_document_filenames,
        pdf_document_checksums=pdf_document_checksums,
        excel_document_ids=excel_document_ids,
        excel_document_filenames=excel_document_filenames,
        excel_document_checksums=excel_document_checksums,
        status=status,
        transmitted=transmitted,
        created_at=now,
        completed_at=now,
        analysis_seconds=analysis_seconds,
        model=model,
        mandate_version=mandate_version,
        stop_reason=stop_reason,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        code_execution_requests=code_execution_requests,
        error_type=error_type,
        error_message=error_message,
        segments=segments,
        tool_trace=tool_trace,
        excel_cleanup=excel_cleanup,
        excel_verification=excel_verification,
    )

    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO cross_format_analyses (
                id, project_id, pdf_document_ids_json, pdf_document_filenames_json,
                pdf_document_checksums_json, excel_document_ids_json,
                excel_document_filenames_json, excel_document_checksums_json,
                status, transmitted, created_at, completed_at, analysis_seconds,
                model, mandate_version, stop_reason, input_tokens, output_tokens,
                code_execution_requests, error_type, error_message, segments_json,
                tool_trace_json, excel_cleanup_json, excel_verification_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.project_id,
                json.dumps(record.pdf_document_ids),
                json.dumps(record.pdf_document_filenames),
                json.dumps(record.pdf_document_checksums),
                json.dumps(record.excel_document_ids),
                json.dumps(record.excel_document_filenames),
                json.dumps(record.excel_document_checksums),
                record.status,
                int(record.transmitted),
                record.created_at,
                record.completed_at,
                record.analysis_seconds,
                record.model,
                record.mandate_version,
                record.stop_reason,
                record.input_tokens,
                record.output_tokens,
                record.code_execution_requests,
                record.error_type,
                record.error_message,
                json.dumps(record.segments) if record.segments is not None else None,
                json.dumps(record.tool_trace) if record.tool_trace is not None else None,
                json.dumps(record.excel_cleanup) if record.excel_cleanup is not None else None,
                json.dumps(record.excel_verification) if record.excel_verification is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return record


def get_cross_format_analysis(project_id: str, cross_format_analysis_id: str) -> CrossFormatAnalysis | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM cross_format_analyses WHERE project_id = ? AND id = ?",
            (project_id, cross_format_analysis_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_cross_format_analysis(row) if row else None
