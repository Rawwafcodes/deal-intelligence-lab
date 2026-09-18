"""Storage for `DeliverableVersion` records (roadmap M14.3, and
docs/workspace-shift/docs/03-domain-model.md's own "DeliverableVersion |
Draft/approved history and source dependencies" - a core record named in
that doc but never implemented until this task). One workspace can
accumulate several deliverable versions over time (e.g. a redraft after
new review activity); `version_number` is a monotonic counter per
workspace, mirroring `PlanRevision.revision_number`'s own shape.

Approval is version-specific by construction, the same discipline
`reviews.py`'s `is_current_version_approved` already established for
SubmissionVersion approvals: `is_current_version_approved` below compares
the workspace's *latest* version's id against the version actually
approved, so a new, unreviewed draft correctly reports "not approved"
even though an older version was genuinely approved. A version, once
created, is never edited or deleted - only superseded by a later one
(docs/03: "Editing creates a draft successor; the old approved version
remains visible").

Deliberately no separate "decision-package run" audit table the way
`cross_format_analyses.py`/`integrity_reviews.py` have one distinct from
their own findings/candidates tables: this capability's only real,
persistent output *is* the DeliverableVersion itself (model, tokens,
digest source ids, and content all live on one row), and a failed
drafting attempt leaves its own trace on the mandate Attempt record
(`error` field) rather than a separate row here - a disclosed scope
simplification, not an oversight (see decision_package.py's own module
docstring for why this capability's shape is much lighter than
reconciliation's or Integrity Review's)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import store

DELIVERABLE_STATUSES = {"draft", "approved", "superseded"}


class DeliverableValidationError(Exception):
    pass


@dataclass
class DeliverableVersion:
    id: str
    project_id: str
    workspace_id: str
    version_number: int
    status: str
    # Task 14.3, same lineage pattern as IntegrityReview (Task 14.2's own
    # lineage fix): nullable because a capability executor receives no
    # run/attempt context until mandates._run_stages injects it.
    mandate_id: str | None
    run_id: str | None
    attempt_id: str | None
    title: str
    executive_summary: str
    recommendation: str
    key_evidence_and_findings: str
    outstanding_and_unresolved_matters: str
    risks_and_limitations: str
    emphasis: str
    source_finding_ids: list[str]
    source_request_ids: list[str]
    model: str
    draft_template_version: str
    input_tokens: int | None
    output_tokens: int | None
    created_at: str
    approved_by: str | None
    approved_at: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "workspace_id": self.workspace_id,
            "version_number": self.version_number,
            "status": self.status,
            "mandate_id": self.mandate_id,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "title": self.title,
            "executive_summary": self.executive_summary,
            "recommendation": self.recommendation,
            "key_evidence_and_findings": self.key_evidence_and_findings,
            "outstanding_and_unresolved_matters": self.outstanding_and_unresolved_matters,
            "risks_and_limitations": self.risks_and_limitations,
            "emphasis": self.emphasis,
            "source_finding_ids": self.source_finding_ids,
            "source_request_ids": self.source_request_ids,
            "model": self.model,
            "draft_template_version": self.draft_template_version,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "created_at": self.created_at,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
        }


def init_deliverables_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS deliverable_versions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'draft',
                mandate_id TEXT,
                run_id TEXT,
                attempt_id TEXT,
                title TEXT NOT NULL DEFAULT '',
                executive_summary TEXT NOT NULL DEFAULT '',
                recommendation TEXT NOT NULL DEFAULT '',
                key_evidence_and_findings TEXT NOT NULL DEFAULT '',
                outstanding_and_unresolved_matters TEXT NOT NULL DEFAULT '',
                risks_and_limitations TEXT NOT NULL DEFAULT '',
                emphasis TEXT NOT NULL DEFAULT '',
                source_finding_ids_json TEXT NOT NULL DEFAULT '[]',
                source_request_ids_json TEXT NOT NULL DEFAULT '[]',
                model TEXT NOT NULL,
                draft_template_version TEXT NOT NULL,
                input_tokens INTEGER,
                output_tokens INTEGER,
                created_at TEXT NOT NULL,
                approved_by TEXT,
                approved_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_deliverable_versions_workspace ON deliverable_versions(workspace_id)"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_deliverable_versions_workspace_version "
            "ON deliverable_versions(workspace_id, version_number)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_deliverable(row) -> DeliverableVersion:
    return DeliverableVersion(
        id=row["id"],
        project_id=row["project_id"],
        workspace_id=row["workspace_id"],
        version_number=row["version_number"],
        status=row["status"],
        mandate_id=row["mandate_id"],
        run_id=row["run_id"],
        attempt_id=row["attempt_id"],
        title=row["title"],
        executive_summary=row["executive_summary"],
        recommendation=row["recommendation"],
        key_evidence_and_findings=row["key_evidence_and_findings"],
        outstanding_and_unresolved_matters=row["outstanding_and_unresolved_matters"],
        risks_and_limitations=row["risks_and_limitations"],
        emphasis=row["emphasis"],
        source_finding_ids=json.loads(row["source_finding_ids_json"]),
        source_request_ids=json.loads(row["source_request_ids_json"]),
        model=row["model"],
        draft_template_version=row["draft_template_version"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        created_at=row["created_at"],
        approved_by=row["approved_by"],
        approved_at=row["approved_at"],
    )


def list_deliverable_versions(workspace_id: str) -> list[DeliverableVersion]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM deliverable_versions WHERE workspace_id = %s ORDER BY version_number ASC",
            (workspace_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_deliverable(r) for r in rows]


def get_deliverable_version(workspace_id: str, deliverable_id: str) -> DeliverableVersion | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM deliverable_versions WHERE workspace_id = %s AND id = %s",
            (workspace_id, deliverable_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_deliverable(row) if row else None


def latest_deliverable_version(workspace_id: str) -> DeliverableVersion | None:
    versions = list_deliverable_versions(workspace_id)
    return versions[-1] if versions else None


def create_deliverable_version(
    *,
    project_id: str,
    workspace_id: str,
    mandate_id: str | None,
    run_id: str | None,
    attempt_id: str | None,
    title: str,
    executive_summary: str,
    recommendation: str,
    key_evidence_and_findings: str,
    outstanding_and_unresolved_matters: str,
    risks_and_limitations: str,
    emphasis: str,
    source_finding_ids: list[str],
    source_request_ids: list[str],
    model: str,
    draft_template_version: str,
    input_tokens: int | None,
    output_tokens: int | None,
) -> DeliverableVersion:
    """Only ever called on a successful draft (see decision_package.py's
    own module docstring for why a failed attempt leaves no row here). A
    prior version for this workspace, if any, is left completely
    untouched - it remains visible at whatever status it already had
    (docs/03: "the old approved version remains visible"); this function
    never marks a prior version "superseded" on the row itself, since
    `is_current_version_approved`/`latest_deliverable_version` already
    determine current-ness by version_number, not by a mutated status
    flag on the old row."""
    existing = list_deliverable_versions(workspace_id)
    version_number = (existing[-1].version_number + 1) if existing else 1
    now = datetime.now(timezone.utc).isoformat()
    record = DeliverableVersion(
        id=uuid.uuid4().hex, project_id=project_id, workspace_id=workspace_id, version_number=version_number,
        status="draft", mandate_id=mandate_id, run_id=run_id, attempt_id=attempt_id, title=title,
        executive_summary=executive_summary, recommendation=recommendation,
        key_evidence_and_findings=key_evidence_and_findings,
        outstanding_and_unresolved_matters=outstanding_and_unresolved_matters,
        risks_and_limitations=risks_and_limitations, emphasis=emphasis,
        source_finding_ids=source_finding_ids, source_request_ids=source_request_ids, model=model,
        draft_template_version=draft_template_version, input_tokens=input_tokens, output_tokens=output_tokens,
        created_at=now, approved_by=None, approved_at=None,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO deliverable_versions (
                id, project_id, workspace_id, version_number, status, mandate_id, run_id, attempt_id,
                title, executive_summary, recommendation, key_evidence_and_findings,
                outstanding_and_unresolved_matters, risks_and_limitations, emphasis,
                source_finding_ids_json, source_request_ids_json, model, draft_template_version,
                input_tokens, output_tokens, created_at, approved_by, approved_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record.id, record.project_id, record.workspace_id, record.version_number, record.status,
                record.mandate_id, record.run_id, record.attempt_id, record.title, record.executive_summary,
                record.recommendation, record.key_evidence_and_findings, record.outstanding_and_unresolved_matters,
                record.risks_and_limitations, record.emphasis, json.dumps(record.source_finding_ids),
                json.dumps(record.source_request_ids), record.model, record.draft_template_version,
                record.input_tokens, record.output_tokens, record.created_at, record.approved_by,
                record.approved_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return record


def is_current_version_approved(workspace_id: str, version_id: str) -> bool:
    """True only if the workspace's *latest* deliverable version is
    "approved" and its id matches `version_id` - the exact
    reviews.is_current_version_approved shape, applied to
    DeliverableVersion instead of SubmissionVersion. A newer, unapproved
    draft correctly makes an older approved version report False here."""
    latest = latest_deliverable_version(workspace_id)
    return latest is not None and latest.status == "approved" and latest.id == version_id


def approve_deliverable_version(workspace_id: str, deliverable_id: str, approver: str) -> DeliverableVersion:
    """Approves exactly one, exact deliverable version - never "whatever
    is current" implicitly. Refuses to approve a version that is not the
    workspace's latest (a newer draft superseded it - re-run the drafting
    capability's output review instead of approving stale text) or one
    already approved."""
    existing = get_deliverable_version(workspace_id, deliverable_id)
    if existing is None:
        raise ValueError("deliverable version not found")
    latest = latest_deliverable_version(workspace_id)
    assert latest is not None
    if latest.id != existing.id:
        raise DeliverableValidationError(
            f"cannot approve version {existing.version_number} - a newer draft "
            f"(version {latest.version_number}) exists for this workspace"
        )
    if existing.status == "approved":
        raise DeliverableValidationError("this deliverable version is already approved")

    now = datetime.now(timezone.utc).isoformat()
    conn = store.get_connection()
    try:
        conn.execute(
            "UPDATE deliverable_versions SET status = 'approved', approved_by = %s, approved_at = %s WHERE id = %s",
            (approver, now, existing.id),
        )
        conn.commit()
    finally:
        conn.close()
    updated = get_deliverable_version(workspace_id, deliverable_id)
    assert updated is not None
    return updated
