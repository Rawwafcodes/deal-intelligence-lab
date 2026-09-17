"""Storage for the audit trail of Work-product Integrity Review runs
(Task 14.2) and the individual candidate challenges they propose - never
sent anywhere itself, a local Postgres audit trail only. Mirrors
cross_format_analyses.py's own "write-once record, freeze every
identifier used" shape exactly.

Security boundary this module exists to enforce: candidates are
persisted here, NOT in workspaces.py's shared `workspace_findings` table
- a candidate becomes a real, shared finding only through
`publish_candidate_as_finding` below, called exclusively from an
explicit human accept decision (server.py's candidate-decision handler).
A rejected or still-pending candidate is fully auditable via this
module's own tables but never appears in the shared findings register,
the workspace memo, or any findings count - the M14.2 spec's own
"Rejected candidates remain auditable in the run but do not become
headline findings" requirement, enforced structurally by never inserting
an unaccepted candidate into workspace_findings at all, not by a status
flag on a shared row.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import store

CANDIDATE_DECISIONS = {"pending", "accepted", "rejected", "duplicate", "unresolved"}


@dataclass
class IntegrityReview:
    id: str
    project_id: str
    # Task 14.2 lineage fix: the mandate/run/attempt that produced this
    # review - the M14.2 spec's own "Published findings identify:
    # Originating mandate/run/attempt" requirement. Nullable because a
    # capability executor receives no run/attempt context at all until
    # mandates._run_stages injects it (see that function's own comment) -
    # every real review created from this point on has all three; only a
    # record created before this fix (none exist outside this session's
    # own live-proof run, itself backfilled - see STATUS.md) would not.
    mandate_id: str | None
    run_id: str | None
    attempt_id: str | None
    target_work_product_id: str
    target_version_id: str
    source_document_ids: list[str]
    source_version_ids: list[str]
    peer_work_product_ids: list[str]
    peer_version_ids: list[str]
    brief_version_id: str | None
    workstream_id: str | None
    review_scope: str
    status: str  # "success" | "error"
    transmitted: bool
    created_at: str
    completed_at: str
    analysis_seconds: float
    model: str
    review_template_version: str
    stop_reason: str | None
    input_tokens: int | None
    output_tokens: int | None
    code_execution_requests: int | None
    error_type: str | None
    error_message: str | None
    materials_reviewed_text: str | None
    tool_trace: list[dict[str, Any]] | None
    excel_cleanup: list[dict[str, Any]] | None
    excel_verification: list[dict[str, Any]] | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "mandate_id": self.mandate_id,
            "run_id": self.run_id,
            "attempt_id": self.attempt_id,
            "target_work_product_id": self.target_work_product_id,
            "target_version_id": self.target_version_id,
            "source_document_ids": self.source_document_ids,
            "source_version_ids": self.source_version_ids,
            "peer_work_product_ids": self.peer_work_product_ids,
            "peer_version_ids": self.peer_version_ids,
            "brief_version_id": self.brief_version_id,
            "workstream_id": self.workstream_id,
            "review_scope": self.review_scope,
            "status": self.status,
            "transmitted": self.transmitted,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
            "analysis_seconds": self.analysis_seconds,
            "model": self.model,
            "review_template_version": self.review_template_version,
            "stop_reason": self.stop_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "code_execution_requests": self.code_execution_requests,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "materials_reviewed_text": self.materials_reviewed_text,
            "tool_trace": self.tool_trace,
            "excel_cleanup": self.excel_cleanup,
            "excel_verification": self.excel_verification,
        }


@dataclass
class IntegrityReviewCandidate:
    id: str
    integrity_review_id: str
    candidate_index: int
    title: str
    classification: str
    severity: str
    assertion: str
    conflicting_or_missing_evidence: str
    why_it_matters: str
    uncertainty: str
    recommended_resolution: str
    deterministic_or_judgment: str
    raw_text: str
    pdf_citations: list[dict[str, Any]]
    excel_citations: list[dict[str, Any]]
    decision: str
    decision_notes: str
    decided_by: str | None
    decided_at: str | None
    duplicate_of_finding_id: str | None
    published_finding_id: str | None
    edits: dict[str, str] | None
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "integrity_review_id": self.integrity_review_id,
            "candidate_index": self.candidate_index,
            "title": self.title,
            "classification": self.classification,
            "severity": self.severity,
            "assertion": self.assertion,
            "conflicting_or_missing_evidence": self.conflicting_or_missing_evidence,
            "why_it_matters": self.why_it_matters,
            "uncertainty": self.uncertainty,
            "recommended_resolution": self.recommended_resolution,
            "deterministic_or_judgment": self.deterministic_or_judgment,
            "raw_text": self.raw_text,
            "pdf_citations": self.pdf_citations,
            "excel_citations": self.excel_citations,
            "decision": self.decision,
            "decision_notes": self.decision_notes,
            "decided_by": self.decided_by,
            "decided_at": self.decided_at,
            "duplicate_of_finding_id": self.duplicate_of_finding_id,
            "published_finding_id": self.published_finding_id,
            "edits": self.edits,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    # Only these fields may be overridden by a human edit at decision time
    # (the M14.2 spec's own "Edit classification/severity/explanation") -
    # assertion/evidence/citations are the model's own record of what it
    # actually found and are never rewritten by a reviewer.
    EDITABLE_FIELDS = ("title", "classification", "severity", "why_it_matters")

    def effective_content(self) -> dict[str, Any]:
        """The candidate's full content - every field workspaces.
        publish_integrity_candidate_as_finding's snapshot needs - with any
        human edit (title/classification/severity/why_it_matters only)
        applied on top. Never mutates the candidate's own immutable parsed
        fields; a rejected or still-pending candidate's row is untouched
        by this - it only matters at the moment of publication."""
        content = {
            "title": self.title,
            "classification": self.classification,
            "severity": self.severity,
            "assertion": self.assertion,
            "conflicting_or_missing_evidence": self.conflicting_or_missing_evidence,
            "why_it_matters": self.why_it_matters,
            "uncertainty": self.uncertainty,
            "recommended_resolution": self.recommended_resolution,
            "deterministic_or_judgment": self.deterministic_or_judgment,
            "raw_text": self.raw_text,
            "pdf_citations": self.pdf_citations,
            "excel_citations": self.excel_citations,
        }
        if self.edits:
            content.update({k: v for k, v in self.edits.items() if k in self.EDITABLE_FIELDS})
        return content


def init_integrity_reviews_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS integrity_reviews (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                mandate_id TEXT,
                run_id TEXT,
                attempt_id TEXT,
                target_work_product_id TEXT NOT NULL,
                target_version_id TEXT NOT NULL,
                source_document_ids_json TEXT NOT NULL,
                source_version_ids_json TEXT NOT NULL,
                peer_work_product_ids_json TEXT NOT NULL,
                peer_version_ids_json TEXT NOT NULL,
                brief_version_id TEXT,
                workstream_id TEXT,
                review_scope TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                transmitted INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT NOT NULL,
                analysis_seconds REAL NOT NULL,
                model TEXT NOT NULL,
                review_template_version TEXT NOT NULL,
                stop_reason TEXT,
                input_tokens INTEGER,
                output_tokens INTEGER,
                code_execution_requests INTEGER,
                error_type TEXT,
                error_message TEXT,
                materials_reviewed_text TEXT,
                tool_trace_json TEXT,
                excel_cleanup_json TEXT,
                excel_verification_json TEXT
            )
            """
        )
        # Additive, idempotent - a table already created earlier this
        # task (real, in-use data included) gets these three lineage
        # columns without any row rewrite.
        conn.execute("ALTER TABLE integrity_reviews ADD COLUMN IF NOT EXISTS mandate_id TEXT")
        conn.execute("ALTER TABLE integrity_reviews ADD COLUMN IF NOT EXISTS run_id TEXT")
        conn.execute("ALTER TABLE integrity_reviews ADD COLUMN IF NOT EXISTS attempt_id TEXT")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_integrity_reviews_project ON integrity_reviews(project_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS integrity_review_candidates (
                id TEXT PRIMARY KEY,
                integrity_review_id TEXT NOT NULL,
                candidate_index INTEGER NOT NULL,
                title TEXT NOT NULL DEFAULT '',
                classification TEXT NOT NULL DEFAULT '',
                severity TEXT NOT NULL DEFAULT '',
                assertion TEXT NOT NULL DEFAULT '',
                conflicting_or_missing_evidence TEXT NOT NULL DEFAULT '',
                why_it_matters TEXT NOT NULL DEFAULT '',
                uncertainty TEXT NOT NULL DEFAULT '',
                recommended_resolution TEXT NOT NULL DEFAULT '',
                deterministic_or_judgment TEXT NOT NULL DEFAULT '',
                raw_text TEXT NOT NULL DEFAULT '',
                pdf_citations_json TEXT NOT NULL DEFAULT '[]',
                excel_citations_json TEXT NOT NULL DEFAULT '[]',
                decision TEXT NOT NULL DEFAULT 'pending',
                decision_notes TEXT NOT NULL DEFAULT '',
                decided_by TEXT,
                decided_at TEXT,
                duplicate_of_finding_id TEXT,
                published_finding_id TEXT,
                edits_json TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_integrity_review_candidates_review "
            "ON integrity_review_candidates(integrity_review_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_review(row) -> IntegrityReview:
    return IntegrityReview(
        id=row["id"],
        project_id=row["project_id"],
        mandate_id=row["mandate_id"],
        run_id=row["run_id"],
        attempt_id=row["attempt_id"],
        target_work_product_id=row["target_work_product_id"],
        target_version_id=row["target_version_id"],
        source_document_ids=json.loads(row["source_document_ids_json"]),
        source_version_ids=json.loads(row["source_version_ids_json"]),
        peer_work_product_ids=json.loads(row["peer_work_product_ids_json"]),
        peer_version_ids=json.loads(row["peer_version_ids_json"]),
        brief_version_id=row["brief_version_id"],
        workstream_id=row["workstream_id"],
        review_scope=row["review_scope"],
        status=row["status"],
        transmitted=bool(row["transmitted"]),
        created_at=row["created_at"],
        completed_at=row["completed_at"],
        analysis_seconds=row["analysis_seconds"],
        model=row["model"],
        review_template_version=row["review_template_version"],
        stop_reason=row["stop_reason"],
        input_tokens=row["input_tokens"],
        output_tokens=row["output_tokens"],
        code_execution_requests=row["code_execution_requests"],
        error_type=row["error_type"],
        error_message=row["error_message"],
        materials_reviewed_text=row["materials_reviewed_text"],
        tool_trace=json.loads(row["tool_trace_json"]) if row["tool_trace_json"] else None,
        excel_cleanup=json.loads(row["excel_cleanup_json"]) if row["excel_cleanup_json"] else None,
        excel_verification=json.loads(row["excel_verification_json"]) if row["excel_verification_json"] else None,
    )


def create_integrity_review(
    *,
    project_id: str,
    mandate_id: str | None = None,
    run_id: str | None = None,
    attempt_id: str | None = None,
    target_work_product_id: str,
    target_version_id: str,
    source_document_ids: list[str],
    source_version_ids: list[str],
    peer_work_product_ids: list[str],
    peer_version_ids: list[str],
    brief_version_id: str | None,
    workstream_id: str | None,
    review_scope: str,
    status: str,
    transmitted: bool,
    analysis_seconds: float,
    model: str,
    review_template_version: str,
    stop_reason: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    code_execution_requests: int | None,
    error_type: str | None,
    error_message: str | None,
    materials_reviewed_text: str | None,
    tool_trace: list[dict[str, Any]] | None,
    excel_cleanup: list[dict[str, Any]] | None,
    excel_verification: list[dict[str, Any]] | None,
) -> IntegrityReview:
    now = datetime.now(timezone.utc).isoformat()
    record = IntegrityReview(
        id=uuid.uuid4().hex, project_id=project_id, mandate_id=mandate_id, run_id=run_id, attempt_id=attempt_id,
        target_work_product_id=target_work_product_id,
        target_version_id=target_version_id, source_document_ids=source_document_ids,
        source_version_ids=source_version_ids, peer_work_product_ids=peer_work_product_ids,
        peer_version_ids=peer_version_ids, brief_version_id=brief_version_id, workstream_id=workstream_id,
        review_scope=review_scope, status=status, transmitted=transmitted, created_at=now, completed_at=now,
        analysis_seconds=analysis_seconds, model=model, review_template_version=review_template_version,
        stop_reason=stop_reason, input_tokens=input_tokens, output_tokens=output_tokens,
        code_execution_requests=code_execution_requests, error_type=error_type, error_message=error_message,
        materials_reviewed_text=materials_reviewed_text, tool_trace=tool_trace, excel_cleanup=excel_cleanup,
        excel_verification=excel_verification,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO integrity_reviews (
                id, project_id, mandate_id, run_id, attempt_id, target_work_product_id, target_version_id,
                source_document_ids_json, source_version_ids_json,
                peer_work_product_ids_json, peer_version_ids_json,
                brief_version_id, workstream_id, review_scope, status, transmitted,
                created_at, completed_at, analysis_seconds, model, review_template_version,
                stop_reason, input_tokens, output_tokens, code_execution_requests,
                error_type, error_message, materials_reviewed_text,
                tool_trace_json, excel_cleanup_json, excel_verification_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                record.id, record.project_id, record.mandate_id, record.run_id, record.attempt_id,
                record.target_work_product_id, record.target_version_id,
                json.dumps(record.source_document_ids), json.dumps(record.source_version_ids),
                json.dumps(record.peer_work_product_ids), json.dumps(record.peer_version_ids),
                record.brief_version_id, record.workstream_id, record.review_scope, record.status,
                int(record.transmitted), record.created_at, record.completed_at, record.analysis_seconds,
                record.model, record.review_template_version, record.stop_reason, record.input_tokens,
                record.output_tokens, record.code_execution_requests, record.error_type, record.error_message,
                record.materials_reviewed_text,
                json.dumps(record.tool_trace) if record.tool_trace is not None else None,
                json.dumps(record.excel_cleanup) if record.excel_cleanup is not None else None,
                json.dumps(record.excel_verification) if record.excel_verification is not None else None,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return record


def get_integrity_review(project_id: str, review_id: str) -> IntegrityReview | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM integrity_reviews WHERE project_id = %s AND id = %s", (project_id, review_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_review(row) if row else None


def list_integrity_reviews(project_id: str) -> list[IntegrityReview]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM integrity_reviews WHERE project_id = %s ORDER BY created_at", (project_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_review(r) for r in rows]


def _row_to_candidate(row) -> IntegrityReviewCandidate:
    return IntegrityReviewCandidate(
        id=row["id"],
        integrity_review_id=row["integrity_review_id"],
        candidate_index=row["candidate_index"],
        title=row["title"],
        classification=row["classification"],
        severity=row["severity"],
        assertion=row["assertion"],
        conflicting_or_missing_evidence=row["conflicting_or_missing_evidence"],
        why_it_matters=row["why_it_matters"],
        uncertainty=row["uncertainty"],
        recommended_resolution=row["recommended_resolution"],
        deterministic_or_judgment=row["deterministic_or_judgment"],
        raw_text=row["raw_text"],
        pdf_citations=json.loads(row["pdf_citations_json"]),
        excel_citations=json.loads(row["excel_citations_json"]),
        decision=row["decision"],
        decision_notes=row["decision_notes"],
        decided_by=row["decided_by"],
        decided_at=row["decided_at"],
        duplicate_of_finding_id=row["duplicate_of_finding_id"],
        published_finding_id=row["published_finding_id"],
        edits=json.loads(row["edits_json"]) if row["edits_json"] else None,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_candidates(review_id: str, candidates: list[dict[str, Any]]) -> list[IntegrityReviewCandidate]:
    """Persists every parsed candidate exactly as produced - immutable
    content, same as an "ai" origin finding's own snapshot. `candidates`
    is a list of dicts shaped like `integrity_review.
    IntegrityCandidateOutcome.to_dict()`."""
    now = datetime.now(timezone.utc).isoformat()
    created: list[IntegrityReviewCandidate] = []
    conn = store.get_connection()
    try:
        for candidate in candidates:
            row = IntegrityReviewCandidate(
                id=uuid.uuid4().hex, integrity_review_id=review_id, candidate_index=candidate["index"],
                title=candidate.get("title", ""), classification=candidate.get("classification", ""),
                severity=candidate.get("severity", ""), assertion=candidate.get("assertion", ""),
                conflicting_or_missing_evidence=candidate.get("conflicting_or_missing_evidence", ""),
                why_it_matters=candidate.get("why_it_matters", ""), uncertainty=candidate.get("uncertainty", ""),
                recommended_resolution=candidate.get("recommended_resolution", ""),
                deterministic_or_judgment=candidate.get("deterministic_or_judgment", ""),
                raw_text=candidate.get("raw_text", ""), pdf_citations=candidate.get("pdf_citations", []),
                excel_citations=candidate.get("excel_citations", []), decision="pending", decision_notes="",
                decided_by=None, decided_at=None, duplicate_of_finding_id=None, published_finding_id=None,
                edits=None, created_at=now, updated_at=now,
            )
            conn.execute(
                """
                INSERT INTO integrity_review_candidates (
                    id, integrity_review_id, candidate_index, title, classification, severity,
                    assertion, conflicting_or_missing_evidence, why_it_matters, uncertainty,
                    recommended_resolution, deterministic_or_judgment, raw_text,
                    pdf_citations_json, excel_citations_json, decision, decision_notes,
                    created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    row.id, row.integrity_review_id, row.candidate_index, row.title, row.classification,
                    row.severity, row.assertion, row.conflicting_or_missing_evidence, row.why_it_matters,
                    row.uncertainty, row.recommended_resolution, row.deterministic_or_judgment, row.raw_text,
                    json.dumps(row.pdf_citations), json.dumps(row.excel_citations), row.decision,
                    row.decision_notes, row.created_at, row.updated_at,
                ),
            )
            created.append(row)
        conn.commit()
    finally:
        conn.close()
    return created


def list_candidates(review_id: str) -> list[IntegrityReviewCandidate]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM integrity_review_candidates WHERE integrity_review_id = %s ORDER BY candidate_index",
            (review_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_candidate(r) for r in rows]


def get_candidate(review_id: str, candidate_id: str) -> IntegrityReviewCandidate | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM integrity_review_candidates WHERE integrity_review_id = %s AND id = %s",
            (review_id, candidate_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_candidate(row) if row else None


class CandidateDecisionError(Exception):
    pass


def record_candidate_decision(
    review_id: str, candidate_id: str, decision: str, decided_by: str | None,
    decision_notes: str = "", edits: dict[str, str] | None = None,
    duplicate_of_finding_id: str | None = None, published_finding_id: str | None = None,
) -> IntegrityReviewCandidate:
    """Records a human's decision on exactly one candidate - accept,
    reject, mark as a duplicate of an existing finding, or leave
    unresolved (the M14.2 spec's own four options plus "edit," which is
    carried as `edits` alongside an "accepted" decision rather than a
    fifth decision value). A candidate already decided can be re-decided
    (the human changed their mind) - this overwrites the decision fields
    but never the immutable parsed content above them."""
    if decision not in CANDIDATE_DECISIONS or decision == "pending":
        raise CandidateDecisionError(f"invalid decision: {decision!r}")
    existing = get_candidate(review_id, candidate_id)
    if existing is None:
        raise CandidateDecisionError("candidate not found")
    if decision == "duplicate" and not duplicate_of_finding_id:
        raise CandidateDecisionError("duplicate_of_finding_id is required when marking a candidate as a duplicate")
    if edits and not set(edits).issubset(IntegrityReviewCandidate.EDITABLE_FIELDS):
        raise CandidateDecisionError(
            f"edits may only include {IntegrityReviewCandidate.EDITABLE_FIELDS}"
        )

    now = datetime.now(timezone.utc).isoformat()
    conn = store.get_connection()
    try:
        conn.execute(
            """
            UPDATE integrity_review_candidates
            SET decision = %s, decision_notes = %s, decided_by = %s, decided_at = %s,
                duplicate_of_finding_id = %s, published_finding_id = %s, edits_json = %s, updated_at = %s
            WHERE integrity_review_id = %s AND id = %s
            """,
            (
                decision, decision_notes, decided_by, now, duplicate_of_finding_id, published_finding_id,
                json.dumps(edits) if edits else None, now, review_id, candidate_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    updated = get_candidate(review_id, candidate_id)
    assert updated is not None
    return updated
