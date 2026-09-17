"""Deal Workspace (Milestone 9): turns one completed cross-format
reconciliation into a structured, human-controlled review workspace.

Design principle - AI content is immutable by construction, not convention:
this module never lets an AI-origin finding's content be rewritten after
the fact. Its content (title, classification, severity, explanation,
evidence, citations, ...) is parsed out of the write-once
`cross_format_analyses` record via `evaluations.extract_findings` exactly
once, at workspace-creation time, and persisted as an immutable snapshot
(`ai_snapshot_json`) - it is never re-parsed on a later read. What this
module stores beyond that snapshot is only the human side: workflow state
per finding (review status, human-adjusted severity, resolution,
ownership, notes), duplicate relationships, human-added findings,
information requests, the executive memo, and an audit log of who changed
what.

One workspace exists per analysis (enforced with a UNIQUE constraint on
cross_format_analysis_id) and is created idempotently - opening an already-
open workspace never re-creates or duplicates its findings, and never
contacts Anthropic.

Finding identity: an AI-origin finding's id is `ai-<uuid>`, minted once at
materialization time and never reused or recomputed - it carries no
positional meaning (see Task 11.2: the prior scheme, `ai-<index>`, tied a
finding's identity to its position in the parser's output, so a parser fix
could silently reattach existing review state to different content; the
migration from that scheme lives in `migrate_finding_ids.py`).
`ai_finding_index` and `ai_extraction_version` are kept as provenance only
- which position, under which parser version, produced this snapshot -
never as identity or as a way to re-derive content. `ai_content_hash` is a
sha256 of the snapshot, an integrity check, also not an identity. A
human-added finding's id is `human-<uuid>` and already stores its own
content directly (no snapshot columns needed). Both kinds share one
workflow-state row shape so the UI can treat them uniformly, while
`origin` keeps them distinguishable everywhere they're displayed, counted,
or exported.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import store
import cross_format_analyses
import evaluations

REVIEW_STATUSES = {"unreviewed", "accepted", "partially_accepted", "rejected", "unverifiable"}
SEVERITIES = {"informational", "low", "medium", "high", "critical"}
RESOLUTION_STATUSES = {"open", "awaiting_information", "management_responded", "resolved", "accepted_risk"}
REQUEST_PRIORITIES = {"low", "medium", "high"}
REQUEST_STATUSES = {"draft", "sent", "answered", "closed"}
MEMO_RECOMMENDATIONS = {
    "proceed",
    "proceed_with_conditions",
    "pause_pending_information",
    "do_not_proceed",
    "no_conclusion",
}

_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "informational": 4}


class WorkspaceValidationError(Exception):
    pass


class FindingRevisionConflictError(Exception):
    """Task 11.5: raised instead of silently overwriting when a caller's
    `expected_revision` no longer matches the finding's current revision -
    someone else's update landed first. Carries the finding's current,
    already-merged state so the caller can show the user what actually
    changed and offer reload/reapply (docs/05-experience.md: 'Concurrent
    writes produce an explicit conflict and allow reload/reapply'), rather
    than just a bare error."""

    def __init__(self, current: dict[str, Any]):
        super().__init__("finding was updated by someone else - reload before saving again")
        self.current = current


# -- schema -------------------------------------------------------------


def _ensure_finding_snapshot_columns(conn) -> None:
    """Additive, idempotent: adds the Task 11.2 snapshot columns to a
    workspace_findings table created before they existed. Postgres supports
    `ADD COLUMN IF NOT EXISTS` natively (unlike SQLite, which needed a
    PRAGMA-based existence check here before Task 11.3a) - running this
    against an already-migrated table is a no-op."""
    for column in ("ai_extraction_version", "ai_snapshot_json", "ai_content_hash"):
        conn.execute(f"ALTER TABLE workspace_findings ADD COLUMN IF NOT EXISTS {column} TEXT")


def init_workspaces_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                cross_format_analysis_id TEXT UNIQUE,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        # Task 14.2: a Workspace is now created for either a
        # CrossFormatAnalysis or an IntegrityReview - exactly one of the
        # two id columns is ever set per row. DROP NOT NULL is a
        # metadata-only, non-rewriting operation on an existing table
        # (safe on the real, populated `public` schema); every existing
        # row keeps its real cross_format_analysis_id unchanged, and a
        # nullable UNIQUE column still enforces uniqueness across every
        # non-NULL value (Postgres treats multiple NULLs as distinct).
        conn.execute("ALTER TABLE workspaces ALTER COLUMN cross_format_analysis_id DROP NOT NULL")
        conn.execute("ALTER TABLE workspaces ADD COLUMN IF NOT EXISTS integrity_review_id TEXT")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_workspaces_integrity_review "
            "ON workspaces(integrity_review_id) WHERE integrity_review_id IS NOT NULL"
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workspaces_project ON workspaces(project_id)")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_findings (
                id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                origin TEXT NOT NULL,
                ai_finding_index INTEGER,
                ai_extraction_version TEXT,
                ai_snapshot_json TEXT,
                ai_content_hash TEXT,
                human_title TEXT NOT NULL DEFAULT '',
                human_classification TEXT NOT NULL DEFAULT '',
                human_severity TEXT,
                human_explanation TEXT NOT NULL DEFAULT '',
                human_commercial_relevance TEXT NOT NULL DEFAULT '',
                human_uncertainty TEXT NOT NULL DEFAULT '',
                human_recommended_action TEXT NOT NULL DEFAULT '',
                human_evidence_notes TEXT NOT NULL DEFAULT '',
                human_evidence_document_ids_json TEXT NOT NULL DEFAULT '[]',
                review_status TEXT NOT NULL DEFAULT 'unreviewed',
                adjusted_severity TEXT,
                resolution_status TEXT NOT NULL DEFAULT 'open',
                assigned_owner TEXT NOT NULL DEFAULT '',
                management_response TEXT NOT NULL DEFAULT '',
                reviewer_notes TEXT NOT NULL DEFAULT '',
                due_date_text TEXT NOT NULL DEFAULT '',
                is_duplicate INTEGER NOT NULL DEFAULT 0,
                duplicate_of TEXT,
                duplicate_marked_by TEXT,
                duplicate_marked_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (workspace_id, id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workspace_findings_workspace ON workspace_findings(workspace_id)"
        )
        _ensure_finding_snapshot_columns(conn)
        # Task 11.5: optimistic-concurrency revision counter. Additive,
        # idempotent, same as the snapshot columns above - existing rows
        # get DEFAULT 1, matching "the current, only version" exactly the
        # same way Task 11.4's document version_number default did.
        conn.execute("ALTER TABLE workspace_findings ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_requests (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                question TEXT NOT NULL,
                related_finding_ids_json TEXT NOT NULL DEFAULT '[]',
                priority TEXT NOT NULL DEFAULT 'medium',
                assigned_recipient TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'draft',
                management_response TEXT NOT NULL DEFAULT '',
                reviewer_followup TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workspace_requests_workspace ON workspace_requests(workspace_id)"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_memos (
                workspace_id TEXT PRIMARY KEY,
                executive_conclusion TEXT NOT NULL DEFAULT '',
                transaction_overview TEXT NOT NULL DEFAULT '',
                critical_issues TEXT NOT NULL DEFAULT '',
                high_priority_issues TEXT NOT NULL DEFAULT '',
                financial_valuation_implications TEXT NOT NULL DEFAULT '',
                missing_information TEXT NOT NULL DEFAULT '',
                confirmed_consistencies TEXT NOT NULL DEFAULT '',
                recommended_next_actions TEXT NOT NULL DEFAULT '',
                overall_recommendation TEXT NOT NULL DEFAULT 'no_conclusion',
                status TEXT NOT NULL DEFAULT 'draft',
                approved_by TEXT,
                approved_at TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workspace_audit_log (
                id TEXT PRIMARY KEY,
                workspace_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                entity_type TEXT,
                entity_id TEXT,
                detail_json TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workspace_audit_log_workspace ON workspace_audit_log(workspace_id)"
        )
        conn.commit()
    finally:
        conn.close()


# -- dataclasses ----------------------------------------------------------


@dataclass
class Workspace:
    """Task 14.2: `cross_format_analysis_id` and `integrity_review_id`
    are now both nullable, exactly one set per row - a Workspace is
    always created for exactly one analysis-producing record, whichever
    kind it is. Every pre-14.2 workspace (real Universal Logic data
    included) keeps `cross_format_analysis_id` set and
    `integrity_review_id` NULL, unchanged."""

    id: str
    project_id: str
    cross_format_analysis_id: str | None
    created_at: str
    updated_at: str
    integrity_review_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "cross_format_analysis_id": self.cross_format_analysis_id,
            "integrity_review_id": self.integrity_review_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class WorkspaceRequest:
    id: str
    workspace_id: str
    question: str
    related_finding_ids: list[str]
    priority: str
    assigned_recipient: str
    status: str
    management_response: str
    reviewer_followup: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "question": self.question,
            "related_finding_ids": self.related_finding_ids,
            "priority": self.priority,
            "assigned_recipient": self.assigned_recipient,
            "status": self.status,
            "management_response": self.management_response,
            "reviewer_followup": self.reviewer_followup,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class WorkspaceMemo:
    workspace_id: str
    executive_conclusion: str
    transaction_overview: str
    critical_issues: str
    high_priority_issues: str
    financial_valuation_implications: str
    missing_information: str
    confirmed_consistencies: str
    recommended_next_actions: str
    overall_recommendation: str
    status: str
    approved_by: str | None
    approved_at: str | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "workspace_id": self.workspace_id,
            "executive_conclusion": self.executive_conclusion,
            "transaction_overview": self.transaction_overview,
            "critical_issues": self.critical_issues,
            "high_priority_issues": self.high_priority_issues,
            "financial_valuation_implications": self.financial_valuation_implications,
            "missing_information": self.missing_information,
            "confirmed_consistencies": self.confirmed_consistencies,
            "recommended_next_actions": self.recommended_next_actions,
            "overall_recommendation": self.overall_recommendation,
            "status": self.status,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class AuditEvent:
    id: str
    workspace_id: str
    event_type: str
    entity_type: str | None
    entity_id: str | None
    detail: dict | None
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workspace_id": self.workspace_id,
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "detail": self.detail,
            "created_at": self.created_at,
        }


# -- audit log --------------------------------------------------------------


def _log_event(
    conn,
    workspace_id: str,
    event_type: str,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO workspace_audit_log (id, workspace_id, event_type, entity_type, entity_id, detail_json, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """,
        (
            uuid.uuid4().hex,
            workspace_id,
            event_type,
            entity_type,
            entity_id,
            json.dumps(detail) if detail is not None else None,
            datetime.now(timezone.utc).isoformat(),
        ),
    )


def log_export(workspace_id: str, export_name: str) -> None:
    conn = store.get_connection()
    try:
        _log_event(conn, workspace_id, "export_generated", entity_type="export", entity_id=export_name)
        conn.commit()
    finally:
        conn.close()


def list_audit_log(workspace_id: str) -> list[AuditEvent]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM workspace_audit_log WHERE workspace_id = %s ORDER BY created_at ASC", (workspace_id,)
        ).fetchall()
    finally:
        conn.close()
    return [
        AuditEvent(
            id=row["id"],
            workspace_id=row["workspace_id"],
            event_type=row["event_type"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            detail=json.loads(row["detail_json"]) if row["detail_json"] else None,
            created_at=row["created_at"],
        )
        for row in rows
    ]


# -- workspace lifecycle ------------------------------------------------


def _row_to_workspace(row) -> Workspace:
    return Workspace(
        id=row["id"],
        project_id=row["project_id"],
        cross_format_analysis_id=row["cross_format_analysis_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        integrity_review_id=row["integrity_review_id"],
    )


def get_workspace(project_id: str, workspace_id: str) -> Workspace | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE project_id = %s AND id = %s", (project_id, workspace_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_workspace(row) if row else None


def get_workspace_for_analysis(project_id: str, cross_format_analysis_id: str) -> Workspace | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE project_id = %s AND cross_format_analysis_id = %s",
            (project_id, cross_format_analysis_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_workspace(row) if row else None


def get_or_create_workspace(
    project_id: str, analysis: cross_format_analyses.CrossFormatAnalysis
) -> tuple[Workspace, bool]:
    """Idempotent: returns (workspace, created). Never contacts Anthropic -
    it only reads the already-completed analysis record. Materializes one
    workflow-state row per AI finding at creation time (not lazily), so
    "every extracted finding appears as an individual structured record"
    holds immediately after this call."""
    existing = get_workspace_for_analysis(project_id, analysis.id)
    if existing is not None:
        return existing, False

    now = datetime.now(timezone.utc).isoformat()
    workspace = Workspace(
        id=uuid.uuid4().hex,
        project_id=project_id,
        cross_format_analysis_id=analysis.id,
        created_at=now,
        updated_at=now,
    )

    findings = evaluations.extract_findings(analysis.segments)

    conn = store.get_connection()
    try:
        try:
            conn.execute(
                "INSERT INTO workspaces (id, project_id, cross_format_analysis_id, created_at, updated_at) VALUES (%s, %s, %s, %s, %s)",
                (workspace.id, workspace.project_id, workspace.cross_format_analysis_id, workspace.created_at, workspace.updated_at),
            )
        except Exception:
            # Lost a create race against another request for the same
            # analysis (UNIQUE constraint) - fall through to re-read below.
            conn.rollback()
            existing = get_workspace_for_analysis(project_id, analysis.id)
            if existing is not None:
                return existing, False
            raise

        for finding in findings:
            _insert_ai_finding_row(conn, workspace.id, finding, now)

        _log_event(
            conn,
            workspace.id,
            "workspace_created",
            entity_type="workspace",
            entity_id=workspace.id,
            detail={"finding_count": len(findings)},
        )
        conn.commit()
    finally:
        conn.close()

    return workspace, True


def get_workspace_for_integrity_review(project_id: str, integrity_review_id: str) -> Workspace | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workspaces WHERE project_id = %s AND integrity_review_id = %s",
            (project_id, integrity_review_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_workspace(row) if row else None


def get_or_create_workspace_for_integrity_review(project_id: str, integrity_review_id: str) -> tuple[Workspace, bool]:
    """Task 14.2's analogue of get_or_create_workspace - idempotent,
    returns (workspace, created). Deliberately materializes *no* findings
    at creation time (unlike the reconciliation path): an Integrity
    Review's candidates are not findings until a human explicitly accepts
    one (see integrity_reviews.py's own module docstring and
    publish_integrity_candidate_as_finding below) - an empty workspace,
    ready to receive published findings, is the entire job of this
    function."""
    existing = get_workspace_for_integrity_review(project_id, integrity_review_id)
    if existing is not None:
        return existing, False

    now = datetime.now(timezone.utc).isoformat()
    workspace = Workspace(
        id=uuid.uuid4().hex, project_id=project_id, cross_format_analysis_id=None,
        created_at=now, updated_at=now, integrity_review_id=integrity_review_id,
    )
    conn = store.get_connection()
    try:
        try:
            conn.execute(
                "INSERT INTO workspaces (id, project_id, integrity_review_id, created_at, updated_at) "
                "VALUES (%s, %s, %s, %s, %s)",
                (workspace.id, workspace.project_id, workspace.integrity_review_id, workspace.created_at, workspace.updated_at),
            )
        except Exception:
            # Lost a create race against another request for the same
            # review (the partial UNIQUE index) - fall through to re-read.
            conn.rollback()
            existing = get_workspace_for_integrity_review(project_id, integrity_review_id)
            if existing is not None:
                return existing, False
            raise
        _log_event(
            conn, workspace.id, "workspace_created", entity_type="workspace", entity_id=workspace.id,
            detail={"integrity_review_id": integrity_review_id},
        )
        conn.commit()
    finally:
        conn.close()
    return workspace, True


# The snapshot persisted for every AI-origin finding - the same 12 keys
# _merged_finding has always assembled as "content" for display, now
# captured once at materialization time instead of recomputed on every read.
_AI_SNAPSHOT_FIELDS = (
    "title",
    "classification",
    "severity",
    "explanation",
    "pdf_evidence",
    "workbook_evidence",
    "commercial_relevance",
    "uncertainty",
    "recommended_action",
    "raw_text",
    "pdf_citations",
    "excel_citations",
)
_AI_SNAPSHOT_LIST_FIELDS = {"pdf_citations", "excel_citations"}


def _build_ai_snapshot(finding: dict[str, Any]) -> dict[str, Any]:
    return {
        key: finding.get(key, [] if key in _AI_SNAPSHOT_LIST_FIELDS else "")
        for key in _AI_SNAPSHOT_FIELDS
    }


def _snapshot_hash(snapshot: dict[str, Any]) -> str:
    """sha256 of the snapshot's canonical JSON - an integrity check
    (detects unexpected changes to a supposedly-immutable row), not an
    identity. See the module docstring's "Finding identity" note."""
    canonical = json.dumps(snapshot, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _insert_ai_finding_row(conn, workspace_id: str, finding: dict[str, Any], now: str) -> str:
    """Mints a fresh UUID id and persists this finding's content as an
    immutable snapshot. Returns the new finding id."""
    finding_id = f"ai-{uuid.uuid4().hex}"
    snapshot = _build_ai_snapshot(finding)
    conn.execute(
        """
        INSERT INTO workspace_findings (
            id, workspace_id, origin, ai_finding_index, ai_extraction_version,
            ai_snapshot_json, ai_content_hash,
            human_evidence_document_ids_json, created_at, updated_at
        ) VALUES (%s, %s, 'ai', %s, %s, %s, %s, '[]', %s, %s)
        """,
        (
            finding_id,
            workspace_id,
            finding["index"],
            evaluations.EXTRACTION_VERSION,
            json.dumps(snapshot),
            _snapshot_hash(snapshot),
            now,
            now,
        ),
    )
    return finding_id


def publish_integrity_candidate_as_finding(
    workspace_id: str, candidate_index: int, content: dict[str, Any],
    review_template_version: str, lineage: dict[str, Any],
) -> dict[str, Any]:
    """Task 14.2: the *only* way an Integrity Review candidate ever
    becomes a real, shared finding - called exclusively from an explicit
    human accept decision (server.py's candidate-decision handler), never
    automatically when a review's capability stage finishes. `content`
    already reflects any human edit (see integrity_reviews.
    IntegrityReviewCandidate.effective_content); the snapshot persisted
    here is then immutable in the same way an "ai" origin finding's own
    snapshot is - a later change to the *candidate* row (impossible,
    since candidates are never edited after a decision) or to the source
    IntegrityReview record cannot retroactively alter a published
    finding. `lineage` carries the M14.2 spec's own required fields:
    originating mandate/run/attempt, target/source/peer versions used,
    review template version, and the human publication decision."""
    now = datetime.now(timezone.utc).isoformat()
    finding_id = f"integrity-{uuid.uuid4().hex}"
    snapshot = {**content, "lineage": lineage}
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO workspace_findings (
                id, workspace_id, origin, ai_finding_index, ai_extraction_version,
                ai_snapshot_json, ai_content_hash,
                human_evidence_document_ids_json, created_at, updated_at
            ) VALUES (%s, %s, 'integrity', %s, %s, %s, %s, '[]', %s, %s)
            """,
            (
                finding_id, workspace_id, candidate_index, review_template_version,
                json.dumps(snapshot), _snapshot_hash(snapshot), now, now,
            ),
        )
        _log_event(
            conn, workspace_id, "integrity_finding_published", entity_type="finding", entity_id=finding_id,
            detail={"candidate_index": candidate_index},
        )
        conn.commit()
    finally:
        conn.close()
    created = _get_finding_state_row(workspace_id, finding_id)
    assert created is not None
    return _merged_finding(created)


# -- findings -------------------------------------------------------------


def _row_to_finding_state(row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "workspace_id": row["workspace_id"],
        "origin": row["origin"],
        "ai_finding_index": row["ai_finding_index"],
        "ai_extraction_version": row["ai_extraction_version"],
        "ai_snapshot": json.loads(row["ai_snapshot_json"]) if row["ai_snapshot_json"] else None,
        "human_content": {
            "title": row["human_title"],
            "classification": row["human_classification"],
            "severity": row["human_severity"],
            "explanation": row["human_explanation"],
            "commercial_relevance": row["human_commercial_relevance"],
            "uncertainty": row["human_uncertainty"],
            "recommended_action": row["human_recommended_action"],
            "evidence_notes": row["human_evidence_notes"],
            "evidence_document_ids": json.loads(row["human_evidence_document_ids_json"]),
        },
        "review_status": row["review_status"],
        "adjusted_severity": row["adjusted_severity"],
        "resolution_status": row["resolution_status"],
        "assigned_owner": row["assigned_owner"],
        "management_response": row["management_response"],
        "reviewer_notes": row["reviewer_notes"],
        "due_date_text": row["due_date_text"],
        "is_duplicate": bool(row["is_duplicate"]),
        "duplicate_of": row["duplicate_of"],
        "duplicate_marked_by": row["duplicate_marked_by"],
        "duplicate_marked_at": row["duplicate_marked_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "revision": row["revision"],
    }


def _list_finding_state_rows(workspace_id: str) -> list[dict[str, Any]]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM workspace_findings WHERE workspace_id = %s ORDER BY created_at ASC", (workspace_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_finding_state(row) for row in rows]


def _get_finding_state_row(workspace_id: str, finding_id: str) -> dict[str, Any] | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workspace_findings WHERE workspace_id = %s AND id = %s", (workspace_id, finding_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_finding_state(row) if row else None


_INTEGRITY_EXTRA_KEYS = (
    "assertion", "conflicting_or_missing_evidence", "deterministic_or_judgment", "recommended_resolution", "lineage",
)


def _merged_finding(state: dict[str, Any]) -> dict[str, Any]:
    integrity_extras = {
        "assertion": "", "conflicting_or_missing_evidence": "", "deterministic_or_judgment": "",
        "recommended_resolution": "", "lineage": {},
    }
    if state["origin"] in ("ai", "integrity"):
        # Content comes straight from the immutable snapshot persisted at
        # materialization time (Task 11.2) - never re-parsed from the
        # analysis record on a read. `ai` is {} only for a not-yet-migrated
        # legacy row (see migrate_finding_ids.py), same as a missing key
        # used to fall back to "" before. Task 14.2's "integrity" origin
        # shares this exact branch - it is the same "immutable model-
        # authored snapshot, human overlay for workflow state" shape,
        # just sourced from an IntegrityReview instead of a
        # CrossFormatAnalysis, with its own extra fields (see
        # _INTEGRITY_EXTRA_KEYS) layered on top.
        ai = state["ai_snapshot"] or {}
        content = {
            "title": ai.get("title", ""),
            "classification": ai.get("classification", ""),
            "severity": ai.get("severity", ""),
            "explanation": ai.get("explanation") or ai.get("why_it_matters", ""),
            "pdf_evidence": ai.get("pdf_evidence", ""),
            "workbook_evidence": ai.get("workbook_evidence", ""),
            "commercial_relevance": ai.get("commercial_relevance") or ai.get("why_it_matters", ""),
            "uncertainty": ai.get("uncertainty", ""),
            "recommended_action": ai.get("recommended_action") or ai.get("recommended_resolution", ""),
            "raw_text": ai.get("raw_text", ""),
            "pdf_citations": ai.get("pdf_citations", []),
            "excel_citations": ai.get("excel_citations", []),
            "evidence_notes": "",
            "evidence_document_ids": [],
        }
        if state["origin"] == "integrity":
            integrity_extras = {
                "assertion": ai.get("assertion", ""),
                "conflicting_or_missing_evidence": ai.get("conflicting_or_missing_evidence", ""),
                "deterministic_or_judgment": ai.get("deterministic_or_judgment", ""),
                "recommended_resolution": ai.get("recommended_resolution", ""),
                "lineage": ai.get("lineage", {}),
            }
    else:
        human = state["human_content"]
        content = {
            "title": human["title"],
            "classification": human["classification"],
            "severity": human["severity"] or "",
            "explanation": human["explanation"],
            "pdf_evidence": "",
            "workbook_evidence": "",
            "commercial_relevance": human["commercial_relevance"],
            "uncertainty": human["uncertainty"],
            "recommended_action": human["recommended_action"],
            "raw_text": "",
            "pdf_citations": [],
            "excel_citations": [],
            "evidence_notes": human["evidence_notes"],
            "evidence_document_ids": human["evidence_document_ids"],
        }

    effective_severity = state["adjusted_severity"] or content["severity"] or None

    return {
        "id": state["id"],
        "workspace_id": state["workspace_id"],
        "origin": state["origin"],
        "ai_finding_index": state["ai_finding_index"],
        **content,
        **integrity_extras,
        "effective_severity": effective_severity,
        "review_status": state["review_status"],
        "adjusted_severity": state["adjusted_severity"],
        "resolution_status": state["resolution_status"],
        "assigned_owner": state["assigned_owner"],
        "management_response": state["management_response"],
        "reviewer_notes": state["reviewer_notes"],
        "due_date_text": state["due_date_text"],
        "is_duplicate": state["is_duplicate"],
        "duplicate_of": state["duplicate_of"],
        "duplicate_marked_by": state["duplicate_marked_by"],
        "duplicate_marked_at": state["duplicate_marked_at"],
        "created_at": state["created_at"],
        "updated_at": state["updated_at"],
        "revision": state["revision"],
    }


def list_findings(
    workspace: Workspace, analysis: cross_format_analyses.CrossFormatAnalysis | None = None
) -> list[dict[str, Any]]:
    """Every finding - ai, human, and (Task 14.2) integrity origin. AI/
    integrity content comes from each row's immutable snapshot (Task
    11.2) - never re-parsed from the analysis record on a read, never
    stale, never editable. `analysis` is accepted for call-site symmetry
    (a reconciliation-backed workspace's caller already has it loaded for
    other purposes) but is no longer read for finding content, and is
    genuinely optional - an integrity-review-backed workspace has no
    CrossFormatAnalysis at all. Duplicate finding ids (for lineage) are
    resolved into each canonical finding's `duplicate_finding_ids` here."""
    states = _list_finding_state_rows(workspace.id)
    merged = [_merged_finding(s) for s in states]

    duplicates_by_canonical: dict[str, list[str]] = {}
    for m in merged:
        if m["is_duplicate"] and m["duplicate_of"]:
            duplicates_by_canonical.setdefault(m["duplicate_of"], []).append(m["id"])
    for m in merged:
        m["duplicate_finding_ids"] = duplicates_by_canonical.get(m["id"], [])

    merged.sort(
        key=lambda m: (
            _SEVERITY_RANK.get((m["effective_severity"] or "").lower(), 99),
            m["created_at"],
        )
    )
    return merged


def get_finding(
    workspace: Workspace, analysis: cross_format_analyses.CrossFormatAnalysis | None, finding_id: str
) -> dict[str, Any] | None:
    for finding in list_findings(workspace, analysis):
        if finding["id"] == finding_id:
            return finding
    return None


def update_finding_workflow(
    workspace_id: str, finding_id: str, updates: dict, expected_revision: int | None = None
) -> dict[str, Any]:
    """Merge-updates the workflow-state fields of one finding (AI or
    human). Never touches content fields - those are either re-derived
    (AI origin) or edited through update_human_finding_content (human
    origin) so this one function can't be used to quietly rewrite what
    Claude said.

    Task 11.5: `expected_revision`, when supplied, must match the
    finding's current `revision` or this raises FindingRevisionConflictError
    instead of writing anything - no silent last-write-wins
    (docs/03-domain-model.md: 'Updates supply expected revision; conflicts
    return a recoverable conflict response'). Omitting it (None) skips the
    check entirely, so any caller that doesn't yet know about revisions
    (there are none left in this codebase, but the parameter is optional
    on principle - see the same optionality reasoning used for other
    additive fields in this app) behaves exactly as before this task."""
    existing = _get_finding_state_row(workspace_id, finding_id)
    if existing is None:
        raise ValueError("finding not found")

    if expected_revision is not None and existing["revision"] != expected_revision:
        raise FindingRevisionConflictError(current=_merged_finding(existing))

    changed: dict[str, Any] = {}

    if "review_status" in updates:
        value = updates["review_status"]
        if value not in REVIEW_STATUSES:
            raise WorkspaceValidationError(f"invalid review_status: {value}")
        changed["review_status"] = value

    if "adjusted_severity" in updates:
        value = updates["adjusted_severity"]
        if value is not None and value not in SEVERITIES:
            raise WorkspaceValidationError(f"invalid adjusted_severity: {value}")
        changed["adjusted_severity"] = value

    if "resolution_status" in updates:
        value = updates["resolution_status"]
        if value not in RESOLUTION_STATUSES:
            raise WorkspaceValidationError(f"invalid resolution_status: {value}")
        changed["resolution_status"] = value

    for text_field in ("assigned_owner", "management_response", "reviewer_notes", "due_date_text"):
        if text_field in updates:
            changed[text_field] = str(updates[text_field] or "")

    if not changed:
        return existing

    now = datetime.now(timezone.utc).isoformat()
    set_clause = ", ".join(f"{k} = %s" for k in changed) + ", updated_at = %s, revision = revision + 1"
    conn = store.get_connection()
    try:
        conn.execute(
            f"UPDATE workspace_findings SET {set_clause} WHERE workspace_id = %s AND id = %s",
            (*changed.values(), now, workspace_id, finding_id),
        )
        event_type = (
            "severity_changed"
            if "adjusted_severity" in changed
            else "assignment"
            if "assigned_owner" in changed
            else "resolution_change"
            if "resolution_status" in changed
            else "management_response"
            if "management_response" in changed
            else "finding_reviewed"
        )
        _log_event(
            conn, workspace_id, event_type, entity_type="finding", entity_id=finding_id, detail=changed
        )
        conn.commit()
    finally:
        conn.close()

    updated = _get_finding_state_row(workspace_id, finding_id)
    assert updated is not None
    return updated


def create_human_finding(workspace_id: str, data: dict) -> dict[str, Any]:
    title = str(data.get("title", "")).strip()
    if not title:
        raise WorkspaceValidationError("title is required")
    severity = data.get("severity")
    if severity is not None and severity not in SEVERITIES:
        raise WorkspaceValidationError(f"invalid severity: {severity}")
    evidence_document_ids = data.get("evidence_document_ids") or []
    if not isinstance(evidence_document_ids, list) or not all(isinstance(d, str) for d in evidence_document_ids):
        raise WorkspaceValidationError("evidence_document_ids must be a list of document id strings")

    now = datetime.now(timezone.utc).isoformat()
    finding_id = f"human-{uuid.uuid4().hex}"

    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO workspace_findings (
                id, workspace_id, origin, ai_finding_index,
                human_title, human_classification, human_severity, human_explanation,
                human_commercial_relevance, human_uncertainty, human_recommended_action,
                human_evidence_notes, human_evidence_document_ids_json,
                created_at, updated_at
            ) VALUES (%s, %s, 'human', NULL, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                finding_id,
                workspace_id,
                title,
                str(data.get("classification", "") or ""),
                severity,
                str(data.get("explanation", "") or ""),
                str(data.get("commercial_relevance", "") or ""),
                str(data.get("uncertainty", "") or ""),
                str(data.get("recommended_action", "") or ""),
                str(data.get("evidence_notes", "") or ""),
                json.dumps(evidence_document_ids),
                now,
                now,
            ),
        )
        _log_event(
            conn,
            workspace_id,
            "human_finding_created",
            entity_type="finding",
            entity_id=finding_id,
            detail={"title": title},
        )
        conn.commit()
    finally:
        conn.close()

    created = _get_finding_state_row(workspace_id, finding_id)
    assert created is not None
    return created


def delete_human_finding(workspace_id: str, finding_id: str) -> None:
    existing = _get_finding_state_row(workspace_id, finding_id)
    if existing is None:
        raise ValueError("finding not found")
    if existing["origin"] != "human":
        raise WorkspaceValidationError("only a human-added finding can be deleted")

    conn = store.get_connection()
    try:
        conn.execute("DELETE FROM workspace_findings WHERE workspace_id = %s AND id = %s", (workspace_id, finding_id))
        # Clear lineage on anything that pointed at this finding as canonical.
        conn.execute(
            "UPDATE workspace_findings SET is_duplicate = 0, duplicate_of = NULL, duplicate_marked_by = NULL, "
            "duplicate_marked_at = NULL WHERE workspace_id = %s AND duplicate_of = %s",
            (workspace_id, finding_id),
        )
        _log_event(
            conn,
            workspace_id,
            "human_finding_deleted",
            entity_type="finding",
            entity_id=finding_id,
            detail={"title": existing["human_content"]["title"]},
        )
        conn.commit()
    finally:
        conn.close()


def set_duplicate(workspace_id: str, finding_id: str, duplicate_of: str | None, marked_by: str) -> dict[str, Any]:
    existing = _get_finding_state_row(workspace_id, finding_id)
    if existing is None:
        raise ValueError("finding not found")

    if duplicate_of is not None:
        if duplicate_of == finding_id:
            raise WorkspaceValidationError("a finding cannot be marked as a duplicate of itself")
        canonical = _get_finding_state_row(workspace_id, duplicate_of)
        if canonical is None:
            raise WorkspaceValidationError("canonical finding not found in this workspace")
        if canonical["is_duplicate"] and canonical["duplicate_of"]:
            raise WorkspaceValidationError("the canonical finding is itself marked as a duplicate")

    now = datetime.now(timezone.utc).isoformat()
    conn = store.get_connection()
    try:
        conn.execute(
            """
            UPDATE workspace_findings
            SET is_duplicate = %s, duplicate_of = %s, duplicate_marked_by = %s, duplicate_marked_at = %s, updated_at = %s
            WHERE workspace_id = %s AND id = %s
            """,
            (
                1 if duplicate_of else 0,
                duplicate_of,
                marked_by if duplicate_of else None,
                now if duplicate_of else None,
                now,
                workspace_id,
                finding_id,
            ),
        )
        _log_event(
            conn,
            workspace_id,
            "duplicate_marking",
            entity_type="finding",
            entity_id=finding_id,
            detail={"duplicate_of": duplicate_of, "marked_by": marked_by},
        )
        conn.commit()
    finally:
        conn.close()

    updated = _get_finding_state_row(workspace_id, finding_id)
    assert updated is not None
    return updated


# -- information requests ------------------------------------------------


def _row_to_request(row) -> WorkspaceRequest:
    return WorkspaceRequest(
        id=row["id"],
        workspace_id=row["workspace_id"],
        question=row["question"],
        related_finding_ids=json.loads(row["related_finding_ids_json"]),
        priority=row["priority"],
        assigned_recipient=row["assigned_recipient"],
        status=row["status"],
        management_response=row["management_response"],
        reviewer_followup=row["reviewer_followup"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def list_requests(workspace_id: str) -> list[WorkspaceRequest]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM workspace_requests WHERE workspace_id = %s ORDER BY created_at ASC", (workspace_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_request(row) for row in rows]


def get_request(workspace_id: str, request_id: str) -> WorkspaceRequest | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workspace_requests WHERE workspace_id = %s AND id = %s", (workspace_id, request_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_request(row) if row else None


def create_request(workspace_id: str, data: dict) -> WorkspaceRequest:
    question = str(data.get("question", "")).strip()
    if not question:
        raise WorkspaceValidationError("question is required")
    priority = data.get("priority", "medium")
    if priority not in REQUEST_PRIORITIES:
        raise WorkspaceValidationError(f"invalid priority: {priority}")
    related = data.get("related_finding_ids") or []
    if not isinstance(related, list) or not all(isinstance(f, str) for f in related):
        raise WorkspaceValidationError("related_finding_ids must be a list of finding id strings")

    now = datetime.now(timezone.utc).isoformat()
    request = WorkspaceRequest(
        id=uuid.uuid4().hex,
        workspace_id=workspace_id,
        question=question,
        related_finding_ids=related,
        priority=priority,
        assigned_recipient=str(data.get("assigned_recipient", "") or ""),
        status="draft",
        management_response="",
        reviewer_followup="",
        created_at=now,
        updated_at=now,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO workspace_requests (
                id, workspace_id, question, related_finding_ids_json, priority, assigned_recipient,
                status, management_response, reviewer_followup, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                request.id,
                request.workspace_id,
                request.question,
                json.dumps(request.related_finding_ids),
                request.priority,
                request.assigned_recipient,
                request.status,
                request.management_response,
                request.reviewer_followup,
                request.created_at,
                request.updated_at,
            ),
        )
        _log_event(conn, workspace_id, "request_created", entity_type="request", entity_id=request.id)
        conn.commit()
    finally:
        conn.close()
    return request


def update_request(workspace_id: str, request_id: str, updates: dict) -> WorkspaceRequest:
    existing = get_request(workspace_id, request_id)
    if existing is None:
        raise ValueError("request not found")

    if "question" in updates:
        question = str(updates["question"]).strip()
        if not question:
            raise WorkspaceValidationError("question cannot be empty")
        existing.question = question

    if "priority" in updates:
        if updates["priority"] not in REQUEST_PRIORITIES:
            raise WorkspaceValidationError(f"invalid priority: {updates['priority']}")
        existing.priority = updates["priority"]

    if "status" in updates:
        if updates["status"] not in REQUEST_STATUSES:
            raise WorkspaceValidationError(f"invalid status: {updates['status']}")
        existing.status = updates["status"]

    if "related_finding_ids" in updates:
        related = updates["related_finding_ids"]
        if not isinstance(related, list) or not all(isinstance(f, str) for f in related):
            raise WorkspaceValidationError("related_finding_ids must be a list of finding id strings")
        existing.related_finding_ids = related

    for text_field in ("assigned_recipient", "management_response", "reviewer_followup"):
        if text_field in updates:
            setattr(existing, text_field, str(updates[text_field] or ""))

    existing.updated_at = datetime.now(timezone.utc).isoformat()

    conn = store.get_connection()
    try:
        conn.execute(
            """
            UPDATE workspace_requests SET
                question = %s, related_finding_ids_json = %s, priority = %s, assigned_recipient = %s,
                status = %s, management_response = %s, reviewer_followup = %s, updated_at = %s
            WHERE workspace_id = %s AND id = %s
            """,
            (
                existing.question,
                json.dumps(existing.related_finding_ids),
                existing.priority,
                existing.assigned_recipient,
                existing.status,
                existing.management_response,
                existing.reviewer_followup,
                existing.updated_at,
                workspace_id,
                request_id,
            ),
        )
        event_type = "management_response" if "management_response" in updates else "request_updated"
        _log_event(
            conn,
            workspace_id,
            event_type,
            entity_type="request",
            entity_id=request_id,
            detail={k: v for k, v in updates.items()},
        )
        conn.commit()
    finally:
        conn.close()
    return existing


# -- executive memo ---------------------------------------------------------


def _row_to_memo(row) -> WorkspaceMemo:
    return WorkspaceMemo(
        workspace_id=row["workspace_id"],
        executive_conclusion=row["executive_conclusion"],
        transaction_overview=row["transaction_overview"],
        critical_issues=row["critical_issues"],
        high_priority_issues=row["high_priority_issues"],
        financial_valuation_implications=row["financial_valuation_implications"],
        missing_information=row["missing_information"],
        confirmed_consistencies=row["confirmed_consistencies"],
        recommended_next_actions=row["recommended_next_actions"],
        overall_recommendation=row["overall_recommendation"],
        status=row["status"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def get_memo(workspace_id: str) -> WorkspaceMemo | None:
    conn = store.get_connection()
    try:
        row = conn.execute("SELECT * FROM workspace_memos WHERE workspace_id = %s", (workspace_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_memo(row) if row else None


def _generate_memo_content(
    workspace: Workspace, analysis: cross_format_analyses.CrossFormatAnalysis
) -> dict[str, str]:
    """Deterministic synthesis from the current, human-reviewed workspace
    state - no Anthropic call, no free-text generation. Every sentence here
    is built from counts and stored field values, never invented."""
    findings = [f for f in list_findings(workspace, analysis) if not f["is_duplicate"]]
    accepted = [f for f in findings if f["review_status"] in ("accepted", "partially_accepted")]

    def effective_sev(f: dict) -> str:
        return (f["effective_severity"] or "").lower()

    critical = [f for f in accepted if effective_sev(f) == "critical"]
    high = [f for f in accepted if effective_sev(f) == "high"]
    open_critical_high = [
        f for f in accepted if effective_sev(f) in ("critical", "high") and f["resolution_status"] not in ("resolved", "accepted_risk")
    ]
    missing_info = [
        f for f in accepted if f["classification"] == "missing evidence" or "uncited" in f["uncertainty"].lower()
    ]
    consistencies = [f for f in accepted if f["classification"] == "confirmed consistency"]

    def bullet_list(items: list[dict], text_fn) -> str:
        if not items:
            return "None recorded from the reviewed findings."
        return "\n".join(f"- {text_fn(f)}" for f in items)

    executive_conclusion = (
        f"Of {len(findings)} findings on record ({len(accepted)} accepted or partially accepted by the "
        f"reviewer), {len(critical)} are critical and {len(high)} are high severity. "
        f"{len(open_critical_high)} critical/high finding(s) remain open as of this draft. "
        "This conclusion reflects only findings a human reviewer has accepted; it is not an automated "
        "recommendation."
    )
    transaction_overview = (
        f"Reconciliation of {len(analysis.pdf_document_filenames)} PDF source(s) and "
        f"{len(analysis.excel_document_filenames)} Excel workbook(s), analyzed with {analysis.model} "
        f"on {analysis.created_at}."
    )
    critical_issues = bullet_list(critical, lambda f: f"{f['title']} ({f['resolution_status']})")
    high_priority_issues = bullet_list(high, lambda f: f"{f['title']} ({f['resolution_status']})")
    financial_valuation_implications = bullet_list(
        [f for f in critical + high if f["commercial_relevance"]],
        lambda f: f["commercial_relevance"],
    )
    missing_information = bullet_list(
        missing_info, lambda f: f"{f['title']} — {f['recommended_action'] or 'no recommended action recorded'}"
    )
    confirmed_consistencies = bullet_list(consistencies, lambda f: f["title"])
    recommended_next_actions = bullet_list(
        [f for f in open_critical_high if f["recommended_action"]], lambda f: f["recommended_action"]
    )

    return {
        "executive_conclusion": executive_conclusion,
        "transaction_overview": transaction_overview,
        "critical_issues": critical_issues,
        "high_priority_issues": high_priority_issues,
        "financial_valuation_implications": financial_valuation_implications,
        "missing_information": missing_information,
        "confirmed_consistencies": confirmed_consistencies,
        "recommended_next_actions": recommended_next_actions,
    }


def get_or_create_memo(
    workspace: Workspace, analysis: cross_format_analyses.CrossFormatAnalysis
) -> WorkspaceMemo:
    existing = get_memo(workspace.id)
    if existing is not None:
        return existing

    content = _generate_memo_content(workspace, analysis)
    now = datetime.now(timezone.utc).isoformat()
    memo = WorkspaceMemo(
        workspace_id=workspace.id,
        overall_recommendation="no_conclusion",
        status="draft",
        approved_by=None,
        approved_at=None,
        created_at=now,
        updated_at=now,
        **content,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO workspace_memos (
                workspace_id, executive_conclusion, transaction_overview, critical_issues, high_priority_issues,
                financial_valuation_implications, missing_information, confirmed_consistencies,
                recommended_next_actions, overall_recommendation, status, approved_by, approved_at,
                created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                memo.workspace_id,
                memo.executive_conclusion,
                memo.transaction_overview,
                memo.critical_issues,
                memo.high_priority_issues,
                memo.financial_valuation_implications,
                memo.missing_information,
                memo.confirmed_consistencies,
                memo.recommended_next_actions,
                memo.overall_recommendation,
                memo.status,
                memo.approved_by,
                memo.approved_at,
                memo.created_at,
                memo.updated_at,
            ),
        )
        _log_event(conn, workspace.id, "memo_generated", entity_type="memo", entity_id=workspace.id)
        conn.commit()
    finally:
        conn.close()
    return memo


_MEMO_TEXT_FIELDS = (
    "executive_conclusion",
    "transaction_overview",
    "critical_issues",
    "high_priority_issues",
    "financial_valuation_implications",
    "missing_information",
    "confirmed_consistencies",
    "recommended_next_actions",
)


def update_memo(workspace_id: str, updates: dict) -> WorkspaceMemo:
    existing = get_memo(workspace_id)
    if existing is None:
        raise ValueError("memo not found")

    changed_fields = []
    for text_field in _MEMO_TEXT_FIELDS:
        if text_field in updates:
            setattr(existing, text_field, str(updates[text_field] or ""))
            changed_fields.append(text_field)

    if "overall_recommendation" in updates:
        value = updates["overall_recommendation"]
        if value not in MEMO_RECOMMENDATIONS:
            raise WorkspaceValidationError(f"invalid overall_recommendation: {value}")
        existing.overall_recommendation = value
        changed_fields.append("overall_recommendation")

    if not changed_fields:
        return existing

    # Editing an approved memo returns it to draft - approval is a
    # statement about one exact piece of text, not a standing permission
    # to keep editing under an "approved" label.
    reverted = existing.status == "approved"
    if reverted:
        existing.status = "draft"
        existing.approved_by = None
        existing.approved_at = None

    existing.updated_at = datetime.now(timezone.utc).isoformat()

    conn = store.get_connection()
    try:
        conn.execute(
            """
            UPDATE workspace_memos SET
                executive_conclusion = %s, transaction_overview = %s, critical_issues = %s, high_priority_issues = %s,
                financial_valuation_implications = %s, missing_information = %s, confirmed_consistencies = %s,
                recommended_next_actions = %s, overall_recommendation = %s, status = %s, approved_by = %s,
                approved_at = %s, updated_at = %s
            WHERE workspace_id = %s
            """,
            (
                existing.executive_conclusion,
                existing.transaction_overview,
                existing.critical_issues,
                existing.high_priority_issues,
                existing.financial_valuation_implications,
                existing.missing_information,
                existing.confirmed_consistencies,
                existing.recommended_next_actions,
                existing.overall_recommendation,
                existing.status,
                existing.approved_by,
                existing.approved_at,
                existing.updated_at,
                workspace_id,
            ),
        )
        _log_event(
            conn,
            workspace_id,
            "memo_edited",
            entity_type="memo",
            entity_id=workspace_id,
            detail={"fields": changed_fields, "reverted_to_draft": reverted},
        )
        conn.commit()
    finally:
        conn.close()
    return existing


def approve_memo(workspace_id: str, approver: str) -> WorkspaceMemo:
    existing = get_memo(workspace_id)
    if existing is None:
        raise ValueError("memo not found")
    if existing.status == "approved":
        raise WorkspaceValidationError("memo is already approved")

    now = datetime.now(timezone.utc).isoformat()
    existing.status = "approved"
    existing.approved_by = approver
    existing.approved_at = now
    existing.updated_at = now

    conn = store.get_connection()
    try:
        conn.execute(
            "UPDATE workspace_memos SET status = %s, approved_by = %s, approved_at = %s, updated_at = %s WHERE workspace_id = %s",
            (existing.status, existing.approved_by, existing.approved_at, existing.updated_at, workspace_id),
        )
        _log_event(
            conn, workspace_id, "memo_approved", entity_type="memo", entity_id=workspace_id,
            detail={"approved_by": approver},
        )
        conn.commit()
    finally:
        conn.close()
    return existing


# -- dashboard summary -------------------------------------------------


def compute_summary(
    workspace: Workspace, analysis: cross_format_analyses.CrossFormatAnalysis, requests: list[WorkspaceRequest]
) -> dict[str, Any]:
    all_findings = list_findings(workspace, analysis)
    findings = [f for f in all_findings if not f["is_duplicate"]]

    def counts_by(key_fn) -> dict[str, int]:
        out: dict[str, int] = {}
        for f in findings:
            key = key_fn(f) or "unspecified"
            out[key] = out.get(key, 0) + 1
        return out

    open_critical_high = [
        f for f in findings
        if (f["effective_severity"] or "").lower() in ("critical", "high")
        and f["resolution_status"] not in ("resolved", "accepted_risk")
    ]
    awaiting_response = [f for f in findings if f["resolution_status"] == "awaiting_information"]
    awaiting_requests = [r for r in requests if r.status == "sent"]

    origin_breakdown = counts_by(lambda f: f["origin"])

    return {
        "total_findings": len(findings),
        "total_findings_including_duplicates": len(all_findings),
        "duplicate_count": len(all_findings) - len(findings),
        "by_severity": counts_by(lambda f: (f["effective_severity"] or "").lower()),
        "by_classification": counts_by(lambda f: f["classification"]),
        "by_review_status": counts_by(lambda f: f["review_status"]),
        "by_resolution_status": counts_by(lambda f: f["resolution_status"]),
        "by_origin": origin_breakdown,
        "open_critical_high_count": len(open_critical_high),
        "awaiting_management_response_count": len(awaiting_response) + len(awaiting_requests),
        "document_count": len(analysis.pdf_document_ids) + len(analysis.excel_document_ids),
        "pdf_document_count": len(analysis.pdf_document_ids),
        "excel_document_count": len(analysis.excel_document_ids),
        "model": analysis.model,
        "input_tokens": analysis.input_tokens,
        "output_tokens": analysis.output_tokens,
        "analysis_created_at": analysis.created_at,
        "request_count": len(requests),
    }
