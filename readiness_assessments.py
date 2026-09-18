"""Storage for `ReadinessAssessment` records (roadmap M14.4). Mirrors
`deliverables.py`'s own shape (one immutable row per assessment run,
never edited), but simpler: a readiness assessment is a report, not a
decision - there is nothing here for a human to approve, so unlike
`DeliverableVersion` there is no status/approver field at all. Running
the assessment again (e.g. after fixing an unmet item) simply creates
another row; every prior assessment stays visible, exactly as it was
computed at the time, per this app's own "immutable snapshot" convention
used everywhere else (findings, plan revisions, deliverable versions).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import store

import readiness


@dataclass
class ReadinessAssessmentRecord:
    id: str
    project_id: str
    workspace_id: str
    mandate_id: str | None
    run_id: str | None
    attempt_id: str | None
    ready: bool
    scope_description: str
    items: list[dict]
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "workspace_id": self.workspace_id,
            "mandate_id": self.mandate_id,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "ready": self.ready,
            "scope_description": self.scope_description,
            "items": self.items,
            "created_at": self.created_at,
        }


def init_readiness_assessments_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS readiness_assessments (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                mandate_id TEXT,
                run_id TEXT,
                attempt_id TEXT,
                ready INTEGER NOT NULL,
                scope_description TEXT NOT NULL,
                items_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_readiness_assessments_workspace ON readiness_assessments(workspace_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_record(row) -> ReadinessAssessmentRecord:
    return ReadinessAssessmentRecord(
        id=row["id"],
        project_id=row["project_id"],
        workspace_id=row["workspace_id"],
        mandate_id=row["mandate_id"],
        run_id=row["run_id"],
        attempt_id=row["attempt_id"],
        ready=bool(row["ready"]),
        scope_description=row["scope_description"],
        items=json.loads(row["items_json"]),
        created_at=row["created_at"],
    )


def create_readiness_assessment(
    *,
    project_id: str,
    workspace_id: str,
    mandate_id: str | None,
    run_id: str | None,
    attempt_id: str | None,
    assessment: "readiness.ReadinessAssessment",
) -> ReadinessAssessmentRecord:
    now = datetime.now(timezone.utc).isoformat()
    record = ReadinessAssessmentRecord(
        id=uuid.uuid4().hex, project_id=project_id, workspace_id=workspace_id, mandate_id=mandate_id,
        run_id=run_id, attempt_id=attempt_id, ready=assessment.ready,
        scope_description=assessment.scope_description, items=[i.to_dict() for i in assessment.items],
        created_at=now,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO readiness_assessments (
                id, project_id, workspace_id, mandate_id, run_id, attempt_id, ready, scope_description,
                items_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record.id, record.project_id, record.workspace_id, record.mandate_id, record.run_id,
                record.attempt_id, int(record.ready), record.scope_description, json.dumps(record.items),
                record.created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return record


def list_readiness_assessments(workspace_id: str) -> list[ReadinessAssessmentRecord]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM readiness_assessments WHERE workspace_id = %s ORDER BY created_at ASC",
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_record(r) for r in rows]


def get_readiness_assessment(workspace_id: str, assessment_id: str) -> ReadinessAssessmentRecord | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM readiness_assessments WHERE workspace_id = %s AND id = %s",
            (workspace_id, assessment_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_record(row) if row else None
