"""Storage for the audit trail of cross-document analysis runs sent to
Anthropic. Records are write-once: this module only ever inserts a new row
and reads existing ones - there is no update function, so a record can't be
silently changed after the fact. Each record freezes the exact document IDs
and checksums it was run against, the mandate version, model, token usage,
stop reason, and timing, alongside the findings themselves. Nothing here is
sent anywhere; this is a local SQLite audit trail only.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import store


@dataclass
class CrossAnalysis:
    id: str
    project_id: str
    document_ids: list[str]
    document_filenames: list[str]
    document_checksums: list[str]
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
    error_type: str | None
    error_message: str | None
    segments: list[dict[str, Any]] | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "document_ids": self.document_ids,
            "document_filenames": self.document_filenames,
            "document_checksums": self.document_checksums,
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
            "error_type": self.error_type,
            "error_message": self.error_message,
            "segments": self.segments,
        }


def init_cross_analyses_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cross_analyses (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                document_ids_json TEXT NOT NULL,
                document_filenames_json TEXT NOT NULL,
                document_checksums_json TEXT NOT NULL,
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
                error_type TEXT,
                error_message TEXT,
                segments_json TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cross_analyses_project ON cross_analyses(project_id)")
        conn.commit()
    finally:
        conn.close()


def _row_to_cross_analysis(row) -> CrossAnalysis:
    return CrossAnalysis(
        id=row["id"],
        project_id=row["project_id"],
        document_ids=json.loads(row["document_ids_json"]),
        document_filenames=json.loads(row["document_filenames_json"]),
        document_checksums=json.loads(row["document_checksums_json"]),
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
        error_type=row["error_type"],
        error_message=row["error_message"],
        segments=json.loads(row["segments_json"]) if row["segments_json"] else None,
    )


def create_cross_analysis(
    *,
    project_id: str,
    document_ids: list[str],
    document_filenames: list[str],
    document_checksums: list[str],
    status: str,
    transmitted: bool,
    analysis_seconds: float,
    model: str,
    mandate_version: str,
    stop_reason: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    error_type: str | None,
    error_message: str | None,
    segments: list[dict[str, Any]] | None,
) -> CrossAnalysis:
    now = datetime.now(timezone.utc).isoformat()
    record = CrossAnalysis(
        id=uuid.uuid4().hex,
        project_id=project_id,
        document_ids=document_ids,
        document_filenames=document_filenames,
        document_checksums=document_checksums,
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
        error_type=error_type,
        error_message=error_message,
        segments=segments,
    )

    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO cross_analyses (
                id, project_id, document_ids_json, document_filenames_json,
                document_checksums_json, status, transmitted, created_at,
                completed_at, analysis_seconds, model, mandate_version,
                stop_reason, input_tokens, output_tokens, error_type,
                error_message, segments_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.id,
                record.project_id,
                json.dumps(record.document_ids),
                json.dumps(record.document_filenames),
                json.dumps(record.document_checksums),
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
                record.error_type,
                record.error_message,
                json.dumps(record.segments) if record.segments is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return record


def get_cross_analysis(project_id: str, cross_analysis_id: str) -> CrossAnalysis | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM cross_analyses WHERE project_id = ? AND id = ?", (project_id, cross_analysis_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_cross_analysis(row) if row else None
