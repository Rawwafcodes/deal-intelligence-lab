"""Review decisions (Task 13.2: docs/03-domain-model.md's "ReviewDecision /
Approval | Append-only actor, target version, rationale, time and
evidence").

A ReviewDecision always targets one exact, immutable SubmissionVersion
(work_products.py) - never a WorkProduct "in general," and never
"whatever the current version turns out to be by the time someone reads
this." This is what makes docs/08-roadmap.md's own M13.2 line true by
construction, not by convention: "Approval is version-specific and
cannot silently transfer to a new version." If a work product gets a new
version after being approved, the old ReviewDecision row still points at
the old version id; `is_current_version_approved` below simply compares
that id against the work product's *current* one and correctly answers
"no" for the new version - there is no special-casing anywhere for "an
approval that used to apply."

Append-only: a ReviewDecision is never edited or deleted once recorded.
Returning work, then later approving a resubmission, does not erase the
return - both decisions remain, a complete history, matching docs/03's
"Append-only actor, target version, rationale, time and evidence."

Deliberately does not import tasks.py or work_products.py - the same
"neither module depends on the other, composed only at the API boundary"
shape this app already uses for workstreams+identity (11.4b) and
tasks+work_products (13.1). `server.py` is what looks up a Task/
WorkProduct before calling into this module and what updates the Task's
own status afterward.

Scope note (Task 13.2, disclosed): a Task may in principle carry more
than one WorkProduct (13.1's own design). A review decision always
targets one specific WorkProduct's current version explicitly - the
common case (one work product per task) is fully precise; for a task
with several work products, each keeps its own complete, exact-version
review history via this module, and the Task's own `status` (tasks.py)
is simply the outcome of whichever work product was most recently
reviewed, a convenience label, not a second source of truth. No
task-wide "all work products must be approved" consensus rule is built
here - out of scope, undesigned, not needed by anything that exists yet.

Explicitly deferred (M14.2's own job, not this task's): linking a
returned decision to an Integrity-Review-produced finding. Building an
unused, unvalidated field for that now would be schema speculation ahead
of the feature that would ever populate it - the roadmap's own "preserve
hooks without implementing Integrity Review" is satisfied by this
module's shape (one exact-version target, append-only, auditable), not
by a placeholder foreign key nothing yet writes to. Linking a decision to
an existing task Comment, by contrast, is built here - Comments already
exist (13.1) and the reference is cheaply, meaningfully validatable now.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import store

REVIEW_DECISIONS = {"approved", "returned"}


class ReviewValidationError(Exception):
    pass


@dataclass
class ReviewDecision:
    id: str
    task_id: str
    work_product_id: str
    submission_version_id: str
    reviewer_id: str | None
    decision: str
    rationale: str
    related_comment_id: str | None
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "work_product_id": self.work_product_id,
            "submission_version_id": self.submission_version_id,
            "reviewer_id": self.reviewer_id,
            "decision": self.decision,
            "rationale": self.rationale,
            "related_comment_id": self.related_comment_id,
            "created_at": self.created_at,
        }


def init_reviews_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS review_decisions (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                work_product_id TEXT NOT NULL,
                submission_version_id TEXT NOT NULL,
                reviewer_id TEXT,
                decision TEXT NOT NULL,
                rationale TEXT NOT NULL DEFAULT '',
                related_comment_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_review_decisions_task ON review_decisions(task_id)")
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_review_decisions_work_product ON review_decisions(work_product_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_decision(row) -> ReviewDecision:
    return ReviewDecision(
        row["id"], row["task_id"], row["work_product_id"], row["submission_version_id"],
        row["reviewer_id"], row["decision"], row["rationale"], row["related_comment_id"], row["created_at"],
    )


def record_decision(
    task_id: str, work_product_id: str, submission_version_id: str, reviewer_id: str | None,
    decision: str, rationale: str = "", related_comment_id: str | None = None,
) -> ReviewDecision:
    if decision not in REVIEW_DECISIONS:
        raise ReviewValidationError(f"decision must be one of {sorted(REVIEW_DECISIONS)}")
    rationale = rationale.strip()
    if decision == "returned" and not rationale:
        raise ReviewValidationError("a rationale is required when returning work for revision")

    record = ReviewDecision(
        id=uuid.uuid4().hex, task_id=task_id, work_product_id=work_product_id,
        submission_version_id=submission_version_id, reviewer_id=reviewer_id, decision=decision,
        rationale=rationale, related_comment_id=related_comment_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO review_decisions (id, task_id, work_product_id, submission_version_id, reviewer_id,
                                           decision, rationale, related_comment_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (record.id, record.task_id, record.work_product_id, record.submission_version_id,
             record.reviewer_id, record.decision, record.rationale, record.related_comment_id,
             record.created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return record


def list_decisions_for_task(task_id: str) -> list[ReviewDecision]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM review_decisions WHERE task_id = %s ORDER BY created_at ASC", (task_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_decision(r) for r in rows]


def list_decisions_for_work_product(work_product_id: str) -> list[ReviewDecision]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM review_decisions WHERE work_product_id = %s ORDER BY created_at ASC",
            (work_product_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_decision(r) for r in rows]


def latest_decision_for_work_product(work_product_id: str) -> ReviewDecision | None:
    decisions = list_decisions_for_work_product(work_product_id)
    return decisions[-1] if decisions else None


def is_current_version_approved(work_product_id: str, current_version_id: str | None) -> bool:
    """True only if the *latest* decision for this work product is
    "approved" and it targeted the work product's *current* version. A
    work product with a newer, unreviewed version correctly reports
    False here even though an older version was once approved - the
    literal mechanism behind "approval is version-specific and cannot
    silently transfer to a new version." Takes plain ids rather than a
    work_products.WorkProduct object so this module never needs to import
    work_products.py at all, not even for typing - the caller (server.py,
    which already imports both) passes `work_product.id`/
    `work_product.current_version_id` directly."""
    latest = latest_decision_for_work_product(work_product_id)
    return (
        latest is not None
        and latest.decision == "approved"
        and latest.submission_version_id == current_version_id
    )
