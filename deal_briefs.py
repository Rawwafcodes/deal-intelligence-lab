"""Deal brief (Task 11.4: docs/03-domain-model.md's "Deal / BriefVersion |
Parties, objective, perspective, scope, periods, uncertainties; brief is
context, not evidence").

A brief is never edited in place: saving a change always appends a new,
immutable BriefVersion row rather than mutating the current one, the same
"stable parent, immutable history" shape Task 11.4's document versions
already established - here there is no parent/child split at all (no
files, no storage indirection needed), just an append-only version log per
project, so "current" is simply the newest row.

Deliberately free text, not a structured form with its own validation
rules: docs/04-mandate-engine.md's mandate composer will eventually read
this as *context*, not as evidence to be verified - so this module does
not interpret, verify, or cross-check its content against anything.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import store

BRIEF_FIELDS = ("parties", "objective", "perspective", "scope", "periods", "uncertainties")


@dataclass
class BriefVersion:
    id: str
    project_id: str
    version_number: int
    parties: str
    objective: str
    perspective: str
    scope: str
    periods: str
    uncertainties: str
    created_at: str
    created_by: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "version_number": self.version_number,
            "parties": self.parties,
            "objective": self.objective,
            "perspective": self.perspective,
            "scope": self.scope,
            "periods": self.periods,
            "uncertainties": self.uncertainties,
            "created_at": self.created_at,
            "created_by": self.created_by,
        }


def init_deal_briefs_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS brief_versions (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                parties TEXT NOT NULL DEFAULT '',
                objective TEXT NOT NULL DEFAULT '',
                perspective TEXT NOT NULL DEFAULT '',
                scope TEXT NOT NULL DEFAULT '',
                periods TEXT NOT NULL DEFAULT '',
                uncertainties TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                created_by TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_brief_versions_project ON brief_versions(project_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_version(row) -> BriefVersion:
    return BriefVersion(
        id=row["id"],
        project_id=row["project_id"],
        version_number=row["version_number"],
        parties=row["parties"],
        objective=row["objective"],
        perspective=row["perspective"],
        scope=row["scope"],
        periods=row["periods"],
        uncertainties=row["uncertainties"],
        created_at=row["created_at"],
        created_by=row["created_by"],
    )


def create_version(project_id: str, fields: dict[str, str], created_by: str | None) -> BriefVersion:
    """Always appends a new version - never updates a prior one. `fields`
    may supply any subset of BRIEF_FIELDS; anything omitted starts blank
    on the very first version, or carries over unchanged from the current
    version on every version after that (so editing just one field - e.g.
    a scope update partway through diligence - doesn't blank out the
    others)."""
    current = get_current_version(project_id)
    version_number = (current.version_number + 1) if current else 1

    values: dict[str, str] = {}
    for field in BRIEF_FIELDS:
        if field in fields:
            values[field] = str(fields[field] or "").strip()
        elif current is not None:
            values[field] = getattr(current, field)
        else:
            values[field] = ""

    version = BriefVersion(
        id=uuid.uuid4().hex,
        project_id=project_id,
        version_number=version_number,
        created_at=datetime.now(timezone.utc).isoformat(),
        created_by=created_by,
        **values,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO brief_versions
                (id, project_id, version_number, parties, objective, perspective, scope,
                 periods, uncertainties, created_at, created_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                version.id, version.project_id, version.version_number, version.parties,
                version.objective, version.perspective, version.scope, version.periods,
                version.uncertainties, version.created_at, version.created_by,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return version


def get_current_version(project_id: str) -> BriefVersion | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM brief_versions WHERE project_id = %s
            ORDER BY version_number DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_version(row) if row else None


def list_versions(project_id: str) -> list[BriefVersion]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM brief_versions WHERE project_id = %s ORDER BY version_number ASC",
            (project_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_version(row) for row in rows]


def get_version(project_id: str, version_id: str) -> BriefVersion | None:
    """Scoped to its own project_id so a version id can't be used to read
    a different project's brief by guessing."""
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM brief_versions WHERE project_id = %s AND id = %s",
            (project_id, version_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_version(row) if row else None
