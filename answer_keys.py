"""Storage for private answer-key versions used by the Validation Lab
(Milestone 8).

Blindness design - read this before touching anything else in this module:

An answer key is evaluation material prepared independently by a human
(the user, an adviser, or another qualified reviewer) *before* a blind
analysis run, so a human can later compare it against what Claude found
without having told Claude what to look for. Its content must never reach
Anthropic in any form. This module is the *only* place answer-key content
is read or written, and it is deliberately never imported by
cross_format_analysis.py, xlsx_inspection.py, pdf_inspection.py,
ai_client.py, or any other module that builds a request to Anthropic - grep
this repository for "answer_keys" and "AnswerKey" to confirm that. The
orchestration layer that starts a validation run (validation_runs.py) only
ever reads this module's *metadata* (locked_at, checksum, version number)
for audit purposes - never `content`. See tests/test_answer_key_blindness.py
for an automated proof using a unique secret marker.

Versioning and locking:
- Each case has one or more AnswerKeyVersion rows, numbered from 1.
- A version starts as an editable draft (locked_at is None). Its content
  can be freely rewritten with update_draft_content() while in this state.
- lock() freezes it permanently: it stamps locked_at and computes a SHA-256
  checksum of its canonical (sorted-key, compact) JSON representation. From
  that point on, update_draft_content() refuses to touch it - the only way
  to revise a locked version is create_revision(), which makes a brand new
  version (copying the locked content forward as a starting point) so the
  original locked version, its checksum, and its lock timestamp are never
  overwritten or lost.
- get_current_version() always returns the highest-numbered version for a
  case - the one a fresh UI load should show and the one a new run must
  check for "is it locked yet".
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import store


class AnswerKeyLockedError(Exception):
    """Raised when an attempt is made to modify a locked answer-key version."""


def canonical_json(content: dict) -> str:
    """Stable, whitespace-minimal JSON used for both the stored
    representation and the checksum input, so the checksum is reproducible
    from the content alone."""
    return json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_checksum(content: dict) -> str:
    return hashlib.sha256(canonical_json(content).encode("utf-8")).hexdigest()


def empty_content() -> dict:
    return {"issues": [], "must_not_claim": []}


def new_issue(
    *,
    title: str,
    description: str = "",
    expected_classification: str = "",
    expected_severity: str = "",
    materiality: str = "",
    known_source: str = "",
    known_location: str = "",
    expected_value: str = "",
    evaluator_notes: str = "",
) -> dict:
    return {
        "id": uuid.uuid4().hex,
        "title": title,
        "description": description,
        "expected_classification": expected_classification,
        "expected_severity": expected_severity,
        "materiality": materiality,
        "known_source": known_source,
        "known_location": known_location,
        "expected_value": expected_value,
        "evaluator_notes": evaluator_notes,
    }


def new_must_not_claim(*, statement: str, notes: str = "") -> dict:
    return {"id": uuid.uuid4().hex, "statement": statement, "notes": notes}


@dataclass
class AnswerKeyVersion:
    id: str
    validation_case_id: str
    version_number: int
    content: dict[str, Any] = field(default_factory=empty_content)
    checksum: str | None = None
    created_at: str = ""
    locked_at: str | None = None

    @property
    def is_locked(self) -> bool:
        return self.locked_at is not None

    def to_dict(self, *, include_content: bool) -> dict:
        out = {
            "id": self.id,
            "validation_case_id": self.validation_case_id,
            "version_number": self.version_number,
            "checksum": self.checksum,
            "created_at": self.created_at,
            "locked_at": self.locked_at,
            "is_locked": self.is_locked,
            "issue_count": len(self.content.get("issues", [])),
            "must_not_claim_count": len(self.content.get("must_not_claim", [])),
        }
        if include_content:
            out["content"] = self.content
        return out


def init_answer_keys_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS answer_key_versions (
                id TEXT PRIMARY KEY,
                validation_case_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                content_json TEXT NOT NULL,
                checksum TEXT,
                created_at TEXT NOT NULL,
                locked_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_answer_key_versions_case ON answer_key_versions(validation_case_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_version(row) -> AnswerKeyVersion:
    return AnswerKeyVersion(
        id=row["id"],
        validation_case_id=row["validation_case_id"],
        version_number=row["version_number"],
        content=json.loads(row["content_json"]),
        checksum=row["checksum"],
        created_at=row["created_at"],
        locked_at=row["locked_at"],
    )


def create_initial_version(validation_case_id: str) -> AnswerKeyVersion:
    """Called once, when a validation case is created, so every case always
    has exactly one editable draft version to start from."""
    version = AnswerKeyVersion(
        id=uuid.uuid4().hex,
        validation_case_id=validation_case_id,
        version_number=1,
        content=empty_content(),
        checksum=None,
        created_at=datetime.now(timezone.utc).isoformat(),
        locked_at=None,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO answer_key_versions
                (id, validation_case_id, version_number, content_json, checksum, created_at, locked_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                version.id,
                version.validation_case_id,
                version.version_number,
                canonical_json(version.content),
                version.checksum,
                version.created_at,
                version.locked_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return version


def get_current_version(validation_case_id: str) -> AnswerKeyVersion | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM answer_key_versions WHERE validation_case_id = %s "
            "ORDER BY version_number DESC LIMIT 1",
            (validation_case_id,),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_version(row) if row else None


def get_version(validation_case_id: str, version_id: str) -> AnswerKeyVersion | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM answer_key_versions WHERE validation_case_id = %s AND id = %s",
            (validation_case_id, version_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_version(row) if row else None


def list_versions(validation_case_id: str) -> list[AnswerKeyVersion]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM answer_key_versions WHERE validation_case_id = %s ORDER BY version_number ASC",
            (validation_case_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_version(row) for row in rows]


def update_draft_content(validation_case_id: str, version_id: str, content: dict) -> AnswerKeyVersion:
    """Overwrites a draft version's content in place. Raises
    AnswerKeyLockedError if the version is already locked - a locked
    version's content_json is never touched again by this function."""
    existing = get_version(validation_case_id, version_id)
    if existing is None:
        raise ValueError("answer key version not found")
    if existing.is_locked:
        raise AnswerKeyLockedError("cannot modify a locked answer-key version; create a revision instead")

    conn = store.get_connection()
    try:
        conn.execute(
            "UPDATE answer_key_versions SET content_json = %s WHERE validation_case_id = %s AND id = %s",
            (canonical_json(content), validation_case_id, version_id),
        )
        conn.commit()
    finally:
        conn.close()
    updated = get_version(validation_case_id, version_id)
    assert updated is not None
    return updated


def lock_version(validation_case_id: str, version_id: str) -> AnswerKeyVersion:
    """Freezes a draft version permanently: stamps locked_at and computes
    its checksum from its content at this exact moment. Raises
    AnswerKeyLockedError if it is already locked (locking is not
    idempotent - re-locking would let a caller quietly move the timestamp
    forward, which must never happen)."""
    existing = get_version(validation_case_id, version_id)
    if existing is None:
        raise ValueError("answer key version not found")
    if existing.is_locked:
        raise AnswerKeyLockedError("this answer-key version is already locked")

    locked_at = datetime.now(timezone.utc).isoformat()
    checksum = compute_checksum(existing.content)

    conn = store.get_connection()
    try:
        conn.execute(
            "UPDATE answer_key_versions SET locked_at = %s, checksum = %s WHERE validation_case_id = %s AND id = %s",
            (locked_at, checksum, validation_case_id, version_id),
        )
        conn.commit()
    finally:
        conn.close()
    updated = get_version(validation_case_id, version_id)
    assert updated is not None
    return updated


def create_revision(validation_case_id: str) -> AnswerKeyVersion:
    """Creates a new draft version (current locked content copied forward
    as a starting point) so a mistake found in a locked version can be
    corrected without ever rewriting the original locked row. Requires the
    current version to actually be locked - revising a draft makes no
    sense, since the draft can simply be edited in place."""
    current = get_current_version(validation_case_id)
    if current is None:
        raise ValueError("validation case has no answer-key version yet")
    if not current.is_locked:
        raise AnswerKeyLockedError("the current version is still a draft; edit it directly instead of revising")

    revision = AnswerKeyVersion(
        id=uuid.uuid4().hex,
        validation_case_id=validation_case_id,
        version_number=current.version_number + 1,
        content=json.loads(canonical_json(current.content)),  # deep-copy via round-trip
        checksum=None,
        created_at=datetime.now(timezone.utc).isoformat(),
        locked_at=None,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO answer_key_versions
                (id, validation_case_id, version_number, content_json, checksum, created_at, locked_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                revision.id,
                revision.validation_case_id,
                revision.version_number,
                canonical_json(revision.content),
                revision.checksum,
                revision.created_at,
                revision.locked_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return revision
