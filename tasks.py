"""Assigned tasks and comments (Task 13.1: docs/03-domain-model.md's
"Task / Comment / Request / Response | Actor, target, owner, status,
visibility, evidence").

A Task is a unit of work a deal lead assigns to someone within a Deal -
"reconcile the two sources by Friday", "draft the customer overview
section" - distinct from two things this app already has:
- `workspaces.py`'s existing Request/Response (Milestone 9): a question
  tied to one specific finding in one specific analysis workspace. A Task
  here is not attached to a finding at all - it is the general unit of
  assigned work docs/05-experience.md's Analyst journey describes
  ("Assignment -> source access -> mandate or human work -> submission
  version -> ...").
- `mandates.py`'s Mandate: an AI-executed engagement. A Task is work
  assigned to a *person*; nothing here ever calls a capability or a model.

A Task may optionally belong to a Workstream (11.4b) for grouping, but
does not require one - `workstreams.py`'s own domain rule ("assignment
does not silently grant or restrict document access") applies here
identically: this module never checks or changes anyone's access either.

Status is deliberately minimal for this task: `open -> in_progress ->
submitted` (once a WorkProduct version exists - see `work_products.py`)
or `cancelled` from either open state. `"submitted"` is never a directly
settable value via `update_status` - it is a hallmark of first submission
recorded by `mark_submitted`, called only from `work_products.py`'s
creation path (composed at the API boundary in `server.py`, not by one
module importing the other - the same "neither module depends on the
other" shape this app already uses for workstreams+identity). The
review/return/approve state machine docs/03's ReviewDecision/Approval
records implies is Task 13.2's job, not built here: a "submitted" task
has nothing yet acting on it beyond existing to be reviewed later.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import store

MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 4000
MAX_COMMENT_LENGTH = 4000

# "submitted" is reachable only via mark_submitted (see module docstring) -
# never accepted directly by update_status.
TASK_STATUSES = {"open", "in_progress", "submitted", "cancelled"}
_MANUALLY_SETTABLE_STATUSES = {"open", "in_progress", "cancelled"}


class TaskValidationError(Exception):
    pass


@dataclass
class Task:
    id: str
    project_id: str
    title: str
    description: str
    workstream_id: str | None
    assigned_to: str | None
    created_by: str | None
    status: str
    created_at: str
    updated_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "description": self.description,
            "workstream_id": self.workstream_id,
            "assigned_to": self.assigned_to,
            "created_by": self.created_by,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Comment:
    id: str
    task_id: str
    author_id: str | None
    body: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "author_id": self.author_id,
            "body": self.body,
            "created_at": self.created_at,
        }


def init_tasks_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                workstream_id TEXT,
                assigned_to TEXT,
                created_by TEXT,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_comments (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                author_id TEXT,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_task_comments_task ON task_comments(task_id)")
        conn.commit()
    finally:
        conn.close()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_task(row) -> Task:
    return Task(
        row["id"], row["project_id"], row["title"], row["description"], row["workstream_id"],
        row["assigned_to"], row["created_by"], row["status"], row["created_at"], row["updated_at"],
    )


def _row_to_comment(row) -> Comment:
    return Comment(row["id"], row["task_id"], row["author_id"], row["body"], row["created_at"])


def create_task(
    project_id: str, title: str, description: str = "", workstream_id: str | None = None,
    assigned_to: str | None = None, created_by: str | None = None,
) -> Task:
    title = title.strip()
    description = description.strip()
    if not title:
        raise TaskValidationError("title is required")
    if len(title) > MAX_TITLE_LENGTH:
        raise TaskValidationError(f"title must be under {MAX_TITLE_LENGTH} characters")
    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise TaskValidationError(f"description must be under {MAX_DESCRIPTION_LENGTH} characters")

    now = _now()
    task = Task(
        id=uuid.uuid4().hex, project_id=project_id, title=title, description=description,
        workstream_id=workstream_id, assigned_to=assigned_to, created_by=created_by,
        status="open", created_at=now, updated_at=now,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO tasks (id, project_id, title, description, workstream_id, assigned_to,
                                created_by, status, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (task.id, task.project_id, task.title, task.description, task.workstream_id,
             task.assigned_to, task.created_by, task.status, task.created_at, task.updated_at),
        )
        conn.commit()
    finally:
        conn.close()
    return task


def list_tasks(project_id: str) -> list[Task]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM tasks WHERE project_id = %s ORDER BY created_at DESC", (project_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_task(r) for r in rows]


def get_task(project_id: str, task_id: str) -> Task | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM tasks WHERE project_id = %s AND id = %s", (project_id, task_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_task(row) if row else None


def _set_task(task_id: str, **fields) -> None:
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    conn = store.get_connection()
    try:
        conn.execute(f"UPDATE tasks SET {set_clause} WHERE id = %s", (*fields.values(), task_id))
        conn.commit()
    finally:
        conn.close()


def update_status(project_id: str, task_id: str, status: str) -> Task:
    task = get_task(project_id, task_id)
    if task is None:
        raise ValueError("task not found")
    if status not in _MANUALLY_SETTABLE_STATUSES:
        raise TaskValidationError(
            f"status must be one of {sorted(_MANUALLY_SETTABLE_STATUSES)} "
            "('submitted' is set automatically by a work-product submission, not directly)"
        )
    _set_task(task_id, status=status)
    updated = get_task(project_id, task_id)
    assert updated is not None
    return updated


def mark_submitted(project_id: str, task_id: str) -> Task | None:
    """Called only from the work-product submission path (composed at the
    API boundary in server.py, not imported by work_products.py - see
    module docstring). A cancelled task staying cancelled despite a late
    submission is deliberate: cancelling a task is a human decision this
    function does not second-guess."""
    task = get_task(project_id, task_id)
    if task is None or task.status == "cancelled":
        return task
    _set_task(task_id, status="submitted")
    return get_task(project_id, task_id)


def assign(project_id: str, task_id: str, assigned_to: str | None) -> Task:
    task = get_task(project_id, task_id)
    if task is None:
        raise ValueError("task not found")
    _set_task(task_id, assigned_to=assigned_to)
    updated = get_task(project_id, task_id)
    assert updated is not None
    return updated


def add_comment(task_id: str, author_id: str | None, body: str) -> Comment:
    body = body.strip()
    if not body:
        raise TaskValidationError("comment body is required")
    if len(body) > MAX_COMMENT_LENGTH:
        raise TaskValidationError(f"comment must be under {MAX_COMMENT_LENGTH} characters")

    comment = Comment(id=uuid.uuid4().hex, task_id=task_id, author_id=author_id, body=body, created_at=_now())
    conn = store.get_connection()
    try:
        conn.execute(
            "INSERT INTO task_comments (id, task_id, author_id, body, created_at) VALUES (%s, %s, %s, %s, %s)",
            (comment.id, comment.task_id, comment.author_id, comment.body, comment.created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return comment


def list_comments(task_id: str) -> list[Comment]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM task_comments WHERE task_id = %s ORDER BY created_at ASC", (task_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_comment(r) for r in rows]
