"""PostgreSQL-backed storage for projects (Task 11.3a: moved off SQLite -
see docs/workspace-shift/docs/10-decisions.md and POSTGRES.md). Connects
over a local Unix socket to a project-local Postgres instance; no network
exposure, no password.

`_ConnectionWrapper` is a thin compatibility shim: every other module in
this codebase was written against sqlite3.Connection's `conn.execute(sql,
params).fetchone()/.fetchall()` shorthand (sqlite3 lets you execute directly
on a connection; psycopg2 requires an explicit cursor). Rather than touch
every one of those call sites, `get_connection()` returns a connection that
still supports `.execute(...)` directly, so the rest of the codebase's SQL
call sites are unchanged except for the `?` -> `%s` placeholder syntax.
`cursor_factory=RealDictCursor` at the connection level means `row["column"]`
access (originally set up via sqlite3.Row) also keeps working everywhere,
unchanged.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import cast

import psycopg2
import psycopg2.extras

PG_HOST = os.environ.get("DEAL_LAB_PG_HOST", str(Path(__file__).parent / "pgsocket"))
PG_PORT = int(os.environ.get("DEAL_LAB_PG_PORT", "5544"))
PG_DBNAME = os.environ.get("DEAL_LAB_PG_DBNAME", "deal_lab")
PG_USER = os.environ.get("DEAL_LAB_PG_USER", os.environ.get("USER", "postgres"))

# The active schema. get_connection() re-reads this on every call, exactly
# like the pre-11.3a DB_PATH global did for the SQLite file path - tests
# isolate themselves by monkeypatching this one module global to a fresh
# per-test/per-class schema name (see ensure_schema/drop_schema) instead of
# pointing at a fresh temp file.
SCHEMA = "public"


class _ConnectionWrapper:
    """See module docstring: makes a psycopg2 connection support the same
    `execute(...)` shorthand every caller in this codebase already uses."""

    def __init__(self, conn: "psycopg2.extensions.connection") -> None:
        self._conn = conn

    def execute(self, sql: str, params: tuple = ()) -> "psycopg2.extras.RealDictCursor":
        # Typed as RealDictCursor (not the generic cursor) so mypy resolves
        # fetchone()/fetchall() to RealDictRow, which supports row["column"]
        # access - the connection's cursor_factory makes this the real
        # runtime type of every cursor this creates.
        cur = cast(psycopg2.extras.RealDictCursor, self._conn.cursor())
        cur.execute(sql, params)
        return cur

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()

    def close(self) -> None:
        self._conn.close()


@dataclass
class Project:
    id: str
    name: str
    description: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "created_at": self.created_at,
        }


def get_connection() -> _ConnectionWrapper:
    conn = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_DBNAME,
        user=PG_USER,
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
    with conn.cursor() as cur:
        cur.execute(f'SET search_path TO "{SCHEMA}", public')
    return _ConnectionWrapper(conn)


def _admin_connection() -> "psycopg2.extensions.connection":
    """A plain (non-wrapped, no search_path set) connection for schema-level
    admin operations - creating/dropping the schema itself, not tables."""
    return psycopg2.connect(host=PG_HOST, port=PG_PORT, dbname=PG_DBNAME, user=PG_USER)


def ensure_schema(schema: str) -> None:
    """Creates a Postgres schema if it doesn't already exist - the
    per-test-class/per-test isolation unit, replacing the old "point
    DB_PATH at a fresh temp sqlite file" pattern."""
    conn = _admin_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
        conn.commit()
    finally:
        conn.close()


def drop_schema(schema: str) -> None:
    if schema == "public":
        return  # never drop the real app's schema
    conn = _admin_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    conn = get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def create_project(name: str, description: str) -> Project:
    project = Project(
        id=uuid.uuid4().hex,
        name=name.strip(),
        description=description.strip(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at) VALUES (%s, %s, %s, %s)",
            (project.id, project.name, project.description, project.created_at),
        )
        conn.commit()
    finally:
        conn.close()
    return project


def list_projects() -> list[Project]:
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, name, description, created_at FROM projects ORDER BY created_at DESC"
        ).fetchall()
    finally:
        conn.close()
    return [Project(row["id"], row["name"], row["description"], row["created_at"]) for row in rows]


def get_project(project_id: str) -> Project | None:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, name, description, created_at FROM projects WHERE id = %s",
            (project_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return Project(row["id"], row["name"], row["description"], row["created_at"])
