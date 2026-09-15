"""SQLite-backed storage for projects. No external dependencies."""

from __future__ import annotations

import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "deal_lab.db"


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


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


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
            "INSERT INTO projects (id, name, description, created_at) VALUES (?, ?, ?, ?)",
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
            "SELECT id, name, description, created_at FROM projects WHERE id = ?",
            (project_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return Project(row["id"], row["name"], row["description"], row["created_at"])
