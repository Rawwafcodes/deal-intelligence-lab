"""Storage for Validation Lab cases: a named, project-scoped container that
groups a document selection, a private answer key (answer_keys.py), and one
or more validation runs (validation_runs.py) against Milestone 7's existing
cross-format reconciliation path.

A validation case never stores answer-key *content* itself - only the
selected document ids that a run will be executed against. Answer-key
content lives exclusively in answer_keys.py's own table, kept structurally
separate so a bug in this module can never leak it (see that module's
docstring for the full blindness design).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import store


@dataclass
class ValidationCase:
    id: str
    project_id: str
    name: str
    description: str
    pdf_document_ids: list[str]
    excel_document_ids: list[str]
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "pdf_document_ids": self.pdf_document_ids,
            "excel_document_ids": self.excel_document_ids,
            "created_at": self.created_at,
        }


def init_validation_cases_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS validation_cases (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                pdf_document_ids_json TEXT NOT NULL,
                excel_document_ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_validation_cases_project ON validation_cases(project_id)")
        conn.commit()
    finally:
        conn.close()


def _row_to_case(row) -> ValidationCase:
    return ValidationCase(
        id=row["id"],
        project_id=row["project_id"],
        name=row["name"],
        description=row["description"],
        pdf_document_ids=json.loads(row["pdf_document_ids_json"]),
        excel_document_ids=json.loads(row["excel_document_ids_json"]),
        created_at=row["created_at"],
    )


def create_validation_case(
    *, project_id: str, name: str, description: str, pdf_document_ids: list[str], excel_document_ids: list[str]
) -> ValidationCase:
    case = ValidationCase(
        id=uuid.uuid4().hex,
        project_id=project_id,
        name=name.strip(),
        description=description.strip(),
        pdf_document_ids=list(pdf_document_ids),
        excel_document_ids=list(excel_document_ids),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO validation_cases (
                id, project_id, name, description, pdf_document_ids_json, excel_document_ids_json, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                case.id,
                case.project_id,
                case.name,
                case.description,
                json.dumps(case.pdf_document_ids),
                json.dumps(case.excel_document_ids),
                case.created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return case


def list_validation_cases(project_id: str) -> list[ValidationCase]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM validation_cases WHERE project_id = %s ORDER BY created_at DESC", (project_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_case(row) for row in rows]


def get_validation_case(project_id: str, validation_case_id: str) -> ValidationCase | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM validation_cases WHERE project_id = %s AND id = %s", (project_id, validation_case_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_case(row) if row else None


def update_selected_documents(
    project_id: str, validation_case_id: str, *, pdf_document_ids: list[str], excel_document_ids: list[str]
) -> ValidationCase | None:
    """Overwrites the case's document selection. Callers must enforce that
    this is only permitted before any run has been created for the case -
    this module only knows about cases, not runs, so that check lives in
    the server handler (validation_runs.list_runs_for_case is the source of
    truth for "has this case already run")."""
    existing = get_validation_case(project_id, validation_case_id)
    if existing is None:
        return None

    conn = store.get_connection()
    try:
        conn.execute(
            "UPDATE validation_cases SET pdf_document_ids_json = %s, excel_document_ids_json = %s "
            "WHERE project_id = %s AND id = %s",
            (json.dumps(pdf_document_ids), json.dumps(excel_document_ids), project_id, validation_case_id),
        )
        conn.commit()
    finally:
        conn.close()
    return get_validation_case(project_id, validation_case_id)
