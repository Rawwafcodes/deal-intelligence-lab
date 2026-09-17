"""Workstreams and assignments (Task 11.4: docs/03-domain-model.md's
"Workstream / Assignment | Configurable grouping and named
responsibilities").

A Workstream is a configurable grouping within one Deal (e.g. "Financial
diligence", "Legal", "Commercial") - a named area of responsibility, not a
fixed taxonomy this app enforces. An Assignment names who is responsible
for a workstream and in what capacity (a free-text role label, not one of
docs/06-security-and-collaboration.md's DealMembership roles - a
workstream lead and a deal-level analyst/reviewer/deal_lead role are
different concepts that happen to both use the word "role").

Critically or otherwise: "WorkstreamAssignment assigns responsibility; it
does not silently grant or restrict document access" (domain model, verbatim).
This module never checks or changes anyone's access - identity.py's
DealMembership (Task 11.3b) remains the only access-control gate. Assigning
someone to a workstream who has no deal membership is allowed (a possible
data-entry error, not this module's concern to prevent) and grants them
nothing beyond appearing in that workstream's roster.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import store

MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 2000
MAX_ROLE_LABEL_LENGTH = 100


class WorkstreamValidationError(Exception):
    pass


@dataclass
class Workstream:
    id: str
    project_id: str
    name: str
    description: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
        }


@dataclass
class WorkstreamAssignment:
    id: str
    workstream_id: str
    user_id: str
    role_label: str
    created_at: str
    revoked_at: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "workstream_id": self.workstream_id,
            "user_id": self.user_id,
            "role_label": self.role_label,
            "created_at": self.created_at,
            "revoked_at": self.revoked_at,
        }


def init_workstreams_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workstreams (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_workstreams_project ON workstreams(project_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS workstream_assignments (
                id TEXT PRIMARY KEY,
                workstream_id TEXT NOT NULL,
                user_id TEXT NOT NULL,
                role_label TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                revoked_at TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_workstream_assignments_workstream ON workstream_assignments(workstream_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_workstream(row) -> Workstream:
    return Workstream(row["id"], row["project_id"], row["name"], row["description"], row["created_at"])


def _row_to_assignment(row) -> WorkstreamAssignment:
    return WorkstreamAssignment(
        row["id"], row["workstream_id"], row["user_id"], row["role_label"], row["created_at"], row["revoked_at"]
    )


def create_workstream(project_id: str, name: str, description: str) -> Workstream:
    name = name.strip()
    description = description.strip()
    if not name:
        raise WorkstreamValidationError("name is required")
    if len(name) > MAX_NAME_LENGTH:
        raise WorkstreamValidationError(f"name must be under {MAX_NAME_LENGTH} characters")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise WorkstreamValidationError(f"description must be under {MAX_DESCRIPTION_LENGTH} characters")

    workstream = Workstream(
        id=uuid.uuid4().hex, project_id=project_id, name=name, description=description,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    conn = store.get_connection()
    try:
        conn.execute(
            "INSERT INTO workstreams (id, project_id, name, description, created_at) VALUES (%s, %s, %s, %s, %s)",
            (workstream.id, workstream.project_id, workstream.name, workstream.description, workstream.created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return workstream


def list_workstreams(project_id: str) -> list[Workstream]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM workstreams WHERE project_id = %s ORDER BY created_at ASC", (project_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_workstream(row) for row in rows]


def get_workstream(project_id: str, workstream_id: str) -> Workstream | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM workstreams WHERE project_id = %s AND id = %s", (project_id, workstream_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_workstream(row) if row else None


def delete_workstream(project_id: str, workstream_id: str) -> bool:
    if get_workstream(project_id, workstream_id) is None:
        return False
    conn = store.get_connection()
    try:
        conn.execute("DELETE FROM workstream_assignments WHERE workstream_id = %s", (workstream_id,))
        conn.execute("DELETE FROM workstreams WHERE project_id = %s AND id = %s", (project_id, workstream_id))
        conn.commit()
    finally:
        conn.close()
    return True


def assign(workstream_id: str, user_id: str, role_label: str) -> WorkstreamAssignment:
    """Grants (or re-activates, updating the role label) a workstream
    assignment. Never deletes a prior row - same "revocation preserves
    history" shape as identity.py's DealMembership (Task 11.3b)."""
    role_label = role_label.strip()
    if len(role_label) > MAX_ROLE_LABEL_LENGTH:
        raise WorkstreamValidationError(f"role label must be under {MAX_ROLE_LABEL_LENGTH} characters")

    conn = store.get_connection()
    try:
        existing = conn.execute(
            """
            SELECT id FROM workstream_assignments
            WHERE workstream_id = %s AND user_id = %s AND revoked_at IS NULL
            """,
            (workstream_id, user_id),
        ).fetchone()
        now = datetime.now(timezone.utc).isoformat()
        if existing:
            conn.execute(
                "UPDATE workstream_assignments SET role_label = %s WHERE id = %s",
                (role_label, existing["id"]),
            )
            assignment_id = existing["id"]
            created_at = now
        else:
            assignment_id = uuid.uuid4().hex
            created_at = now
            conn.execute(
                """
                INSERT INTO workstream_assignments (id, workstream_id, user_id, role_label, created_at, revoked_at)
                VALUES (%s, %s, %s, %s, %s, NULL)
                """,
                (assignment_id, workstream_id, user_id, role_label, created_at),
            )
        conn.commit()
    finally:
        conn.close()
    return WorkstreamAssignment(assignment_id, workstream_id, user_id, role_label, created_at, None)


def revoke_assignment(workstream_id: str, user_id: str) -> bool:
    conn = store.get_connection()
    try:
        row = conn.execute(
            """
            UPDATE workstream_assignments SET revoked_at = %s
            WHERE workstream_id = %s AND user_id = %s AND revoked_at IS NULL
            RETURNING id
            """,
            (datetime.now(timezone.utc).isoformat(), workstream_id, user_id),
        ).fetchone()
        conn.commit()
    finally:
        conn.close()
    return row is not None


def list_assignments(workstream_id: str) -> list[WorkstreamAssignment]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM workstream_assignments WHERE workstream_id = %s ORDER BY created_at ASC",
            (workstream_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_assignment(row) for row in rows]


def list_active_assignments(workstream_id: str) -> list[WorkstreamAssignment]:
    return [a for a in list_assignments(workstream_id) if a.revoked_at is None]
