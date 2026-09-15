"""Storage for the audit trail of Excel-workbook inspection runs sent to
Anthropic. Records are write-once (insert only, no update function) - the
same immutability approach as inspections.py and cross_analyses.py. Each
record captures whether the workbook was transmitted, whether the remote
Files API object's deletion was attempted and whether it succeeded, whether
citation existence-verification was possible for this run, the model, token
usage, stop reason, timing, findings, and a capped code-execution trace.
Nothing here is sent anywhere; this is a local SQLite audit trail only. See
xlsx_inspection.py's module docstring for what "remote cleanup succeeded"
does and does not imply about provider-side retention.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import store


@dataclass
class XlsxInspection:
    id: str
    project_id: str
    document_id: str
    document_filename: str
    document_checksum: str
    status: str  # "success" | "error"
    transmitted: bool
    remote_cleanup_attempted: bool
    remote_cleanup_succeeded: bool | None
    verification_available: bool
    verification_unavailable_reason: str | None
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

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "document_id": self.document_id,
            "document_filename": self.document_filename,
            "document_checksum": self.document_checksum,
            "status": self.status,
            "transmitted": self.transmitted,
            "remote_cleanup_attempted": self.remote_cleanup_attempted,
            "remote_cleanup_succeeded": self.remote_cleanup_succeeded,
            "verification_available": self.verification_available,
            "verification_unavailable_reason": self.verification_unavailable_reason,
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
        }


def init_xlsx_inspections_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS xlsx_inspections (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                document_filename TEXT NOT NULL,
                document_checksum TEXT NOT NULL,
                status TEXT NOT NULL,
                transmitted INTEGER NOT NULL,
                remote_cleanup_attempted INTEGER NOT NULL,
                remote_cleanup_succeeded INTEGER,
                verification_available INTEGER NOT NULL,
                verification_unavailable_reason TEXT,
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
                tool_trace_json TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_xlsx_inspections_project ON xlsx_inspections(project_id)")
        conn.commit()
    finally:
        conn.close()


def _bool_or_none(value: int | None) -> bool | None:
    return None if value is None else bool(value)


def _row_to_xlsx_inspection(row) -> XlsxInspection:
    return XlsxInspection(
        id=row["id"],
        project_id=row["project_id"],
        document_id=row["document_id"],
        document_filename=row["document_filename"],
        document_checksum=row["document_checksum"],
        status=row["status"],
        transmitted=bool(row["transmitted"]),
        remote_cleanup_attempted=bool(row["remote_cleanup_attempted"]),
        remote_cleanup_succeeded=_bool_or_none(row["remote_cleanup_succeeded"]),
        verification_available=bool(row["verification_available"]),
        verification_unavailable_reason=row["verification_unavailable_reason"],
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
    )


def create_xlsx_inspection(
    *,
    project_id: str,
    document_id: str,
    document_filename: str,
    document_checksum: str,
    status: str,
    transmitted: bool,
    remote_cleanup_attempted: bool,
    remote_cleanup_succeeded: bool | None,
    verification_available: bool,
    verification_unavailable_reason: str | None,
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
) -> XlsxInspection:
    now = datetime.now(timezone.utc).isoformat()
    record = XlsxInspection(
        id=uuid.uuid4().hex,
        project_id=project_id,
        document_id=document_id,
        document_filename=document_filename,
        document_checksum=document_checksum,
        status=status,
        transmitted=transmitted,
        remote_cleanup_attempted=remote_cleanup_attempted,
        remote_cleanup_succeeded=remote_cleanup_succeeded,
        verification_available=verification_available,
        verification_unavailable_reason=verification_unavailable_reason,
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
    )

    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO xlsx_inspections (
                id, project_id, document_id, document_filename, document_checksum,
                status, transmitted, remote_cleanup_attempted, remote_cleanup_succeeded,
                verification_available, verification_unavailable_reason,
                created_at, completed_at, analysis_seconds, model, mandate_version,
                stop_reason, input_tokens, output_tokens, code_execution_requests,
                error_type, error_message, segments_json, tool_trace_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.project_id,
                record.document_id,
                record.document_filename,
                record.document_checksum,
                record.status,
                int(record.transmitted),
                int(record.remote_cleanup_attempted),
                None if record.remote_cleanup_succeeded is None else int(record.remote_cleanup_succeeded),
                int(record.verification_available),
                record.verification_unavailable_reason,
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
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return record


def get_xlsx_inspection(project_id: str, xlsx_inspection_id: str) -> XlsxInspection | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM xlsx_inspections WHERE project_id = ? AND id = ?", (project_id, xlsx_inspection_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_xlsx_inspection(row) if row else None
