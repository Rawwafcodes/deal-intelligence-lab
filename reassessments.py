"""Storage for the audit trail of targeted reassessment runs (Task 15.2)
and the individual per-finding items they propose. Mirrors integrity_
reviews.py's own shape closely: a write-once audit record plus per-item
rows, each starting "pending" and changed only by an explicit human
acknowledgment (server.py's item-decision handler) - never auto-applied.

Unlike an Integrity Review candidate, acknowledging a ReassessmentItem
never creates a new shared finding - the finding this item is about
already exists and is never mutated (docs/03-domain-model.md: "Read
operations never re-extract or mutate historical findings"). Acknowledging
only (a) records that a human looked at the proposed reassessment and
(b) optionally updates the *workflow* fields (resolution_status/
reviewer_notes) of the target finding, through workspaces.py's own
existing update_finding_workflow - never this module's job to reach into
workspaces.py itself (server.py composes the two, same as everywhere
else in this app). Once every item for a Reassessment has been
acknowledged, the workspace's staleness flag is cleared
(version_dependencies.clear_staleness) - Task 15.1's own deferred
"no un-staling" boundary, resolved here.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import store

ITEM_DECISIONS = {"pending", "acknowledged"}


class ReassessmentItemDecisionError(Exception):
    pass


@dataclass
class Reassessment:
    id: str
    project_id: str
    workspace_id: str
    mandate_id: str | None
    run_id: str | None
    attempt_id: str | None
    document_id: str
    old_version_id: str
    new_version_id: str
    status: str  # "success" | "error"
    transmitted: bool
    created_at: str
    completed_at: str
    analysis_seconds: float
    model: str
    reassessment_template_version: str
    stop_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    error_type: str | None
    error_message: str | None
    executive_summary: str
    what_changed: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "workspace_id": self.workspace_id,
            "mandate_id": self.mandate_id,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "document_id": self.document_id,
            "old_version_id": self.old_version_id,
            "new_version_id": self.new_version_id,
            "status": self.status,
            "transmitted": self.transmitted,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "analysis_seconds": self.analysis_seconds,
            "model": self.model,
            "reassessment_template_version": self.reassessment_template_version,
            "stop_reason": self.stop_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "executive_summary": self.executive_summary,
            "what_changed": self.what_changed,
        }


@dataclass
class ReassessmentItem:
    id: str
    reassessment_id: str
    item_index: int
    finding_title: str
    finding_id: str | None
    status: str
    explanation: str
    evidence_of_change: str
    raw_text: str
    pdf_citations: list[dict[str, Any]]
    decision: str
    decision_notes: str
    decided_by: str | None
    decided_at: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reassessment_id": self.reassessment_id,
            "item_index": self.item_index,
            "finding_title": self.finding_title,
            "finding_id": self.finding_id,
            "status": self.status,
            "explanation": self.explanation,
            "evidence_of_change": self.evidence_of_change,
            "raw_text": self.raw_text,
            "pdf_citations": self.pdf_citations,
            "decision": self.decision,
            "decision_notes": self.decision_notes,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def init_reassessments_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reassessments (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                mandate_id TEXT,
                run_id TEXT,
                attempt_id TEXT,
                document_id TEXT NOT NULL,
                old_version_id TEXT NOT NULL,
                new_version_id TEXT NOT NULL,
                status TEXT NOT NULL,
                transmitted INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                analysis_seconds REAL NOT NULL,
                model TEXT NOT NULL,
                reassessment_template_version TEXT NOT NULL,
                stop_reason TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                error_type TEXT,
                error_message TEXT,
                executive_summary TEXT NOT NULL DEFAULT '',
                what_changed TEXT NOT NULL DEFAULT ''
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reassessments_workspace ON reassessments(workspace_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reassessment_items (
                id TEXT PRIMARY KEY,
                reassessment_id TEXT NOT NULL,
                item_index INTEGER NOT NULL,
                finding_title TEXT NOT NULL DEFAULT '',
                finding_id TEXT,
                status TEXT NOT NULL DEFAULT '',
                explanation TEXT NOT NULL DEFAULT '',
                evidence_of_change TEXT NOT NULL DEFAULT '',
                raw_text TEXT NOT NULL DEFAULT '',
                pdf_citations_json TEXT NOT NULL DEFAULT '[]',
                decision TEXT NOT NULL DEFAULT 'pending',
                decision_notes TEXT NOT NULL DEFAULT '',
                decided_by TEXT,
                decided_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reassessment_items_reassessment ON reassessment_items(reassessment_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_reassessment(row) -> Reassessment:
    return Reassessment(
        id=row["id"], project_id=row["project_id"], workspace_id=row["workspace_id"], mandate_id=row["mandate_id"],
        run_id=row["run_id"], attempt_id=row["attempt_id"], document_id=row["document_id"],
        old_version_id=row["old_version_id"], new_version_id=row["new_version_id"], status=row["status"],
        transmitted=bool(row["transmitted"]), created_at=row["created_at"], completed_at=row["completed_at"],
        analysis_seconds=row["analysis_seconds"], model=row["model"],
        reassessment_template_version=row["reassessment_template_version"], stop_reason=row["stop_reason"],
        input_tokens=row["input_tokens"], output_tokens=row["output_tokens"], error_type=row["error_type"],
        error_message=row["error_message"], executive_summary=row["executive_summary"],
        what_changed=row["what_changed"],
    )


def create_reassessment(
    *,
    project_id: str,
    workspace_id: str,
    mandate_id: str | None,
    run_id: str | None,
    attempt_id: str | None,
    document_id: str,
    old_version_id: str,
    new_version_id: str,
    status: str,
    transmitted: bool,
    analysis_seconds: float,
    model: str,
    reassessment_template_version: str,
    stop_reason: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    error_type: str | None,
    error_message: str | None,
    executive_summary: str,
    what_changed: str,
) -> Reassessment:
    now = datetime.now(timezone.utc).isoformat()
    record = Reassessment(
        id=uuid.uuid4().hex, project_id=project_id, workspace_id=workspace_id, mandate_id=mandate_id, run_id=run_id,
        attempt_id=attempt_id, document_id=document_id, old_version_id=old_version_id, new_version_id=new_version_id,
        status=status, transmitted=transmitted, created_at=now, completed_at=now, analysis_seconds=analysis_seconds,
        model=model, reassessment_template_version=reassessment_template_version, stop_reason=stop_reason,
        input_tokens=input_tokens, output_tokens=output_tokens, error_type=error_type, error_message=error_message,
        executive_summary=executive_summary, what_changed=what_changed,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO reassessments (
                id, project_id, workspace_id, mandate_id, run_id, attempt_id, document_id, old_version_id,
                new_version_id, status, transmitted, created_at, completed_at, analysis_seconds, model,
                reassessment_template_version, stop_reason, input_tokens, output_tokens, error_type,
                error_message, executive_summary, what_changed
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record.id, record.project_id, record.workspace_id, record.mandate_id, record.run_id,
                record.attempt_id, record.document_id, record.old_version_id, record.new_version_id, record.status,
                int(record.transmitted), record.created_at, record.completed_at, record.analysis_seconds,
                record.model, record.reassessment_template_version, record.stop_reason, record.input_tokens,
                record.output_tokens, record.error_type, record.error_message, record.executive_summary,
                record.what_changed,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return record


def get_reassessment(project_id: str, reassessment_id: str) -> Reassessment | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM reassessments WHERE project_id = %s AND id = %s", (project_id, reassessment_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_reassessment(row) if row else None


def list_reassessments(project_id: str, workspace_id: str | None = None) -> list[Reassessment]:
    conn = store.get_connection()
    try:
        if workspace_id is not None:
            rows = conn.execute(
                "SELECT * FROM reassessments WHERE project_id = %s AND workspace_id = %s ORDER BY created_at",
                (project_id, workspace_id),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM reassessments WHERE project_id = %s ORDER BY created_at", (project_id,)
            ).fetchall()
    finally:
        conn.close()
    return [_row_to_reassessment(r) for r in rows]


def _row_to_item(row) -> ReassessmentItem:
    return ReassessmentItem(
        id=row["id"], reassessment_id=row["reassessment_id"], item_index=row["item_index"],
        finding_title=row["finding_title"], finding_id=row["finding_id"], status=row["status"],
        explanation=row["explanation"], evidence_of_change=row["evidence_of_change"], raw_text=row["raw_text"],
        pdf_citations=json.loads(row["pdf_citations_json"]), decision=row["decision"],
        decision_notes=row["decision_notes"], decided_by=row["decided_by"], decided_at=row["decided_at"],
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


def create_items(reassessment_id: str, items: list[dict[str, Any]]) -> list[ReassessmentItem]:
    """`items` is a list of dicts shaped like `reassessment.
    ReassessmentItemOutcome.to_dict()`, each additionally carrying a
    resolved `finding_id` (str | None) - the executor's own job to match
    the model's reported `finding_title` against the workspace's real
    findings before calling this."""
    now = datetime.now(timezone.utc).isoformat()
    created: list[ReassessmentItem] = []
    conn = store.get_connection()
    try:
        for item in items:
            row = ReassessmentItem(
                id=uuid.uuid4().hex, reassessment_id=reassessment_id, item_index=item["index"],
                finding_title=item.get("finding_title", ""), finding_id=item.get("finding_id"),
                status=item.get("status", ""), explanation=item.get("explanation", ""),
                evidence_of_change=item.get("evidence_of_change", ""), raw_text=item.get("raw_text", ""),
                pdf_citations=item.get("pdf_citations", []), decision="pending", decision_notes="",
                decided_by=None, decided_at=None, created_at=now, updated_at=now,
            )
            conn.execute(
                """
                INSERT INTO reassessment_items (
                    id, reassessment_id, item_index, finding_title, finding_id, status, explanation,
                    evidence_of_change, raw_text, pdf_citations_json, decision, decision_notes,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row.id, row.reassessment_id, row.item_index, row.finding_title, row.finding_id, row.status,
                    row.explanation, row.evidence_of_change, row.raw_text, json.dumps(row.pdf_citations),
                    row.decision, row.decision_notes, row.created_at, row.updated_at,
                ),
            )
            created.append(row)
        conn.commit()
    finally:
        conn.close()
    return created


def list_items(reassessment_id: str) -> list[ReassessmentItem]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM reassessment_items WHERE reassessment_id = %s ORDER BY item_index", (reassessment_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_item(r) for r in rows]


def get_item(reassessment_id: str, item_id: str) -> ReassessmentItem | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM reassessment_items WHERE reassessment_id = %s AND id = %s", (reassessment_id, item_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_item(row) if row else None


def acknowledge_item(reassessment_id: str, item_id: str, decided_by: str | None, decision_notes: str = "") -> ReassessmentItem:
    existing = get_item(reassessment_id, item_id)
    if existing is None:
        raise ReassessmentItemDecisionError("item not found")

    now = datetime.now(timezone.utc).isoformat()
    conn = store.get_connection()
    try:
        conn.execute(
            """
            UPDATE reassessment_items SET decision = 'acknowledged', decision_notes = %s, decided_by = %s,
                                           decided_at = %s, updated_at = %s
            WHERE reassessment_id = %s AND id = %s
            """,
            (decision_notes, decided_by, now, now, reassessment_id, item_id),
        )
        conn.commit()
    finally:
        conn.close()
    updated = get_item(reassessment_id, item_id)
    assert updated is not None
    return updated


def all_items_acknowledged(reassessment_id: str) -> bool:
    items = list_items(reassessment_id)
    return bool(items) and all(i.decision == "acknowledged" for i in items)
