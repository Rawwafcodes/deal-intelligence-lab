"""Storage for the audit trail of PDF-inspection requests sent to Anthropic.

Each row records that a document was (or was not) transmitted, which model
was used, token usage, stop reason, and how long the analysis took — the
result text itself (as structured segments with their citations) is stored
alongside on success. This table is local SQLite only; nothing here is sent
anywhere.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import store


@dataclass
class Inspection:
    id: str
    project_id: str
    document_id: str
    document_filename: str
    status: str  # "success" | "error"
    transmitted: bool
    created_at: str
    completed_at: str
    analysis_seconds: float
    model: str
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
            "document_id": self.document_id,
            "document_filename": self.document_filename,
            "status": self.status,
            "transmitted": self.transmitted,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "analysis_seconds": self.analysis_seconds,
            "model": self.model,
            "stop_reason": self.stop_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "segments": self.segments,
        }


def init_inspections_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS inspections (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                document_id TEXT NOT NULL,
                document_filename TEXT NOT NULL,
                status TEXT NOT NULL,
                transmitted INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                analysis_seconds REAL NOT NULL,
                model TEXT NOT NULL,
                stop_reason TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                error_type TEXT,
                error_message TEXT,
                segments_json TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inspections_project ON inspections(project_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_inspections_document ON inspections(document_id)")
        conn.commit()
    finally:
        conn.close()


def _row_to_inspection(row) -> Inspection:
    return Inspection(
        id=row["id"],
        project_id=row["project_id"],
        document_id=row["document_id"],
        document_filename=row["document_filename"],
        status=row["status"],
        transmitted=bool(row["transmitted"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        analysis_seconds=row["analysis_seconds"],
        model=row["model"],
        stop_reason=row["stop_reason"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        error_type=row["error_type"],
        error_message=row["error_message"],
        segments=json.loads(row["segments_json"]) if row["segments_json"] else None,
    )


def create_inspection(
    *,
    project_id: str,
    document_id: str,
    document_filename: str,
    status: str,
    transmitted: bool,
    analysis_seconds: float,
    model: str,
    stop_reason: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    error_type: str | None,
    error_message: str | None,
    segments: list[dict[str, Any]] | None,
) -> Inspection:
    now = datetime.now(timezone.utc).isoformat()
    inspection = Inspection(
        id=uuid.uuid4().hex,
        project_id=project_id,
        document_id=document_id,
        document_filename=document_filename,
        status=status,
        transmitted=transmitted,
        created_at=now,
        completed_at=now,
        analysis_seconds=analysis_seconds,
        model=model,
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
            INSERT INTO inspections (
                id, project_id, document_id, document_filename, status, transmitted,
                created_at, completed_at, analysis_seconds, model, stop_reason,
                input_tokens, output_tokens, error_type, error_message, segments_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                inspection.id,
                inspection.project_id,
                inspection.document_id,
                inspection.document_filename,
                inspection.status,
                int(inspection.transmitted),
                inspection.created_at,
                inspection.completed_at,
                inspection.analysis_seconds,
                inspection.model,
                inspection.stop_reason,
                inspection.input_tokens,
                inspection.output_tokens,
                inspection.error_type,
                inspection.error_message,
                json.dumps(inspection.segments) if inspection.segments is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return inspection


def get_inspection(project_id: str, inspection_id: str) -> Inspection | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM inspections WHERE project_id = %s AND id = %s", (project_id, inspection_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_inspection(row) if row else None
