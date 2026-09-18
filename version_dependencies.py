"""Version dependency tracking and staleness propagation (roadmap M15.1:
docs/workspace-shift/integrations/workspace-integrity-integration-v1.0.0/
06-m15-change-awareness.md's own "Dependency tracking" section). A
freestanding module (only `store` imported) so any layer of this app -
`documents.py`/`work_products.py` at the version-creation end,
`mandates.py`'s capability executors and `reviews.py` at the
dependent-creation end - can record or query a dependency without a
circular import.

Two kinds of edge, distinguished by whether `pinned_version_id` is set:

- **Leaf edges** (`pinned_version_id` set): a dependent was built from an
  exact version of a real, independently-versioned container - a
  `Document` or `WorkProduct`. Staleness here is a genuine version
  mismatch: `mark_superseded(container_type, container_id, new_version_id)`
  (called from `documents.add_version`/`work_products.add_version` the
  moment a new version is created) flags every leaf edge whose pinned
  version no longer matches.
- **Cascade edges** (`pinned_version_id` is `None`): a dependent was
  built from another *dependent* that has no version concept of its own
  (e.g. a decision package built from a workspace's current findings).
  These always propagate once their source is itself marked stale,
  regardless of any version comparison - there is no version to compare.

`mark_superseded` walks both kinds together, breadth-first, from the one
real trigger (a new version appearing) outward through however many
hops the real dependency graph has - satisfying the spec's whole
relationship chain (DocumentVersion/SubmissionVersion -> assertion/
evidence snapshot -> finding/challenge -> review decision/request/memo
conclusion; SubmissionVersion -> approval decision) with one generic
mechanism instead of a hand-written propagation function per
relationship. No AI call is made anywhere in this module - the spec's
own "No AI call is required for staleness propagation," literally true
here, not merely uncontradicted.

Marking never mutates the dependent item's own historical content -
only this module's own side table records that it may now be stale, with
a plain-English reason. Reassessing (deciding whether the stale item's
conclusion still holds) is M15.2's own separate, explicitly authorized
job - out of this task's scope.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Sequence

import store


@dataclass
class StalenessFlag:
    dependent_type: str
    dependent_id: str
    reason: str
    superseded_source_type: str
    superseded_source_id: str
    superseded_version_id: str
    first_marked_at: str
    last_marked_at: str

    def to_dict(self) -> dict:
        return {
            "dependent_type": self.dependent_type,
            "dependent_id": self.dependent_id,
            "reason": self.reason,
            "superseded_source_type": self.superseded_source_type,
            "superseded_source_id": self.superseded_source_id,
            "superseded_version_id": self.superseded_version_id,
            "first_marked_at": self.first_marked_at,
            "last_marked_at": self.last_marked_at,
        }


def init_version_dependencies_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS dependency_edges (
                id TEXT PRIMARY KEY,
                dependent_type TEXT NOT NULL,
                dependent_id TEXT NOT NULL,
                source_type TEXT NOT NULL,
                source_id TEXT NOT NULL,
                pinned_version_id TEXT,
                created_at TEXT NOT NULL,
                UNIQUE (dependent_type, dependent_id, source_type, source_id)
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dependency_edges_source ON dependency_edges(source_type, source_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_dependency_edges_dependent "
            "ON dependency_edges(dependent_type, dependent_id)"
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS staleness_flags (
                dependent_type TEXT NOT NULL,
                dependent_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                superseded_source_type TEXT NOT NULL,
                superseded_source_id TEXT NOT NULL,
                superseded_version_id TEXT NOT NULL,
                first_marked_at TEXT NOT NULL,
                last_marked_at TEXT NOT NULL,
                PRIMARY KEY (dependent_type, dependent_id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def record_dependency(
    dependent_type: str, dependent_id: str, source_type: str, source_id: str,
    pinned_version_id: str | None = None,
) -> None:
    """Idempotent - recording the same edge twice (e.g. an idempotent
    workspace re-open) is a no-op, never a duplicate row or an error.

    Self-healing: if `source_type`/`source_id` is already flagged stale
    at the moment this edge is recorded (e.g. a decision package freshly
    built from a workspace that was already stale), the new dependent
    inherits that staleness immediately - the invariant "everything
    currently depending on a stale item is itself stale" holds at every
    point in time, not only at the instant a version first changes."""
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO dependency_edges (id, dependent_type, dependent_id, source_type, source_id,
                                           pinned_version_id, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (dependent_type, dependent_id, source_type, source_id) DO NOTHING
            """,
            (
                uuid.uuid4().hex, dependent_type, dependent_id, source_type, source_id, pinned_version_id,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        existing_flag = conn.execute(
            "SELECT * FROM staleness_flags WHERE dependent_type = %s AND dependent_id = %s",
            (source_type, source_id),
        ).fetchone()
        if existing_flag is not None:
            now = datetime.now(timezone.utc).isoformat()
            reason = f"Depends on {source_type} {source_id}, which is stale: {existing_flag['reason']}"
            _upsert_stale(
                conn, dependent_type, dependent_id, reason, existing_flag["superseded_source_type"],
                existing_flag["superseded_source_id"], existing_flag["superseded_version_id"], now,
            )
        conn.commit()
    finally:
        conn.close()


def record_dependencies(
    dependent_type: str, dependent_id: str, edges: Sequence[tuple[str, str, str | None]],
) -> None:
    """Convenience batch form of `record_dependency` - `edges` is a list
    of `(source_type, source_id, pinned_version_id)` tuples."""
    for source_type, source_id, pinned_version_id in edges:
        record_dependency(dependent_type, dependent_id, source_type, source_id, pinned_version_id)


def get_pinned_version(dependent_type: str, dependent_id: str, source_type: str, source_id: str) -> str | None:
    """Task 15.2: looks up the exact version a dependent was pinned to
    for one specific source - the "old" version a targeted reassessment
    needs to fetch, given only the dependent (a workspace) and the
    source container a staleness flag already names."""
    conn = store.get_connection()
    try:
        row = conn.execute(
            """
            SELECT pinned_version_id FROM dependency_edges
            WHERE dependent_type = %s AND dependent_id = %s AND source_type = %s AND source_id = %s
            """,
            (dependent_type, dependent_id, source_type, source_id),
        ).fetchone()
    finally:
        conn.close()
    return row["pinned_version_id"] if row else None


def get_staleness(dependent_type: str, dependent_id: str) -> StalenessFlag | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM staleness_flags WHERE dependent_type = %s AND dependent_id = %s",
            (dependent_type, dependent_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return StalenessFlag(
        dependent_type=row["dependent_type"], dependent_id=row["dependent_id"], reason=row["reason"],
        superseded_source_type=row["superseded_source_type"], superseded_source_id=row["superseded_source_id"],
        superseded_version_id=row["superseded_version_id"], first_marked_at=row["first_marked_at"],
        last_marked_at=row["last_marked_at"],
    )


def _upsert_stale(
    conn, dependent_type: str, dependent_id: str, reason: str, source_type: str, source_id: str,
    version_id: str, now: str,
) -> None:
    conn.execute(
        """
        INSERT INTO staleness_flags (dependent_type, dependent_id, reason, superseded_source_type,
                                      superseded_source_id, superseded_version_id, first_marked_at, last_marked_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (dependent_type, dependent_id) DO UPDATE SET
            reason = EXCLUDED.reason,
            superseded_source_type = EXCLUDED.superseded_source_type,
            superseded_source_id = EXCLUDED.superseded_source_id,
            superseded_version_id = EXCLUDED.superseded_version_id,
            last_marked_at = EXCLUDED.last_marked_at
        """,
        (dependent_type, dependent_id, reason, source_type, source_id, version_id, now, now),
    )


def mark_superseded(source_type: str, source_id: str, new_version_id: str) -> list[StalenessFlag]:
    """Called the moment a new version appears (from `documents.
    add_version`/`work_products.add_version`) - `source_type`/`source_id`
    identify the *container* (a Document or WorkProduct id, not a
    version id), `new_version_id` is the version just created. Every
    dependent with a leaf edge pinned to an older version of this
    container is marked stale, then the same marking cascades outward
    through every cascade edge sourced on a now-stale dependent, breadth-
    first, until nothing new is found. Returns every newly- or
    re-marked StalenessFlag, in the order discovered."""
    now = datetime.now(timezone.utc).isoformat()
    conn = store.get_connection()
    try:
        direct_rows = conn.execute(
            """
            SELECT dependent_type, dependent_id, pinned_version_id FROM dependency_edges
            WHERE source_type = %s AND source_id = %s
              AND pinned_version_id IS NOT NULL AND pinned_version_id != %s
            """,
            (source_type, source_id, new_version_id),
        ).fetchall()

        queue: list[tuple[str, str, str]] = [
            (
                row["dependent_type"], row["dependent_id"],
                f"Depends on {source_type} {source_id} at version {row['pinned_version_id']}, "
                f"which has been superseded by version {new_version_id}.",
            )
            for row in direct_rows
        ]

        visited: set[tuple[str, str]] = set()
        results: list[StalenessFlag] = []
        while queue:
            dependent_type, dependent_id, reason = queue.pop(0)
            key = (dependent_type, dependent_id)
            if key in visited:
                continue
            visited.add(key)

            _upsert_stale(conn, dependent_type, dependent_id, reason, source_type, source_id, new_version_id, now)
            # Read back through the same connection/transaction, not via
            # get_staleness() - that function opens its own connection,
            # which under Postgres's default read-committed isolation
            # would not yet see this same transaction's own uncommitted
            # write.
            row = conn.execute(
                "SELECT * FROM staleness_flags WHERE dependent_type = %s AND dependent_id = %s",
                (dependent_type, dependent_id),
            ).fetchone()
            assert row is not None
            results.append(
                StalenessFlag(
                    dependent_type=row["dependent_type"], dependent_id=row["dependent_id"], reason=row["reason"],
                    superseded_source_type=row["superseded_source_type"],
                    superseded_source_id=row["superseded_source_id"],
                    superseded_version_id=row["superseded_version_id"], first_marked_at=row["first_marked_at"],
                    last_marked_at=row["last_marked_at"],
                )
            )

            cascade_rows = conn.execute(
                "SELECT dependent_type, dependent_id FROM dependency_edges WHERE source_type = %s AND source_id = %s",
                (dependent_type, dependent_id),
            ).fetchall()
            for crow in cascade_rows:
                if (crow["dependent_type"], crow["dependent_id"]) in visited:
                    continue
                queue.append(
                    (
                        crow["dependent_type"], crow["dependent_id"],
                        f"Depends on {dependent_type} {dependent_id}, which is stale: {reason}",
                    )
                )
        conn.commit()
        return results
    finally:
        conn.close()


def clear_staleness(dependent_type: str, dependent_id: str) -> None:
    """Task 15.2: removes exactly this one dependent's own staleness flag
    - called once a human has acknowledged every item of a targeted
    reassessment addressing it (reassessments.py's own
    `all_items_acknowledged`). Deliberately does not cascade: a
    deliverable or other dependent that had inherited staleness from this
    one is left flagged - clearing it would silently declare something
    reassessed that nobody actually looked at. A no-op if nothing is
    flagged (idempotent, safe to call defensively)."""
    conn = store.get_connection()
    try:
        conn.execute(
            "DELETE FROM staleness_flags WHERE dependent_type = %s AND dependent_id = %s",
            (dependent_type, dependent_id),
        )
        conn.commit()
    finally:
        conn.close()
