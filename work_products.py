"""Work-product submissions (Task 13.1: docs/03-domain-model.md's
"WorkProduct / SubmissionVersion | Analyst-produced output and immutable
submitted versions").

Deliberately mirrors documents.py's Document/DocumentVersion split -
stable parent, every version's bytes stored under their own generated id,
never overwritten - the exact "stable parent, immutable history" shape
Task 11.4 already proved (including the same fix that task made: adding a
version is always an explicit action against an already-known parent id,
never inferred from a filename collision - see documents.save_uploaded_
file's own docstring for why that inference broke real test fixtures).

Kept as its own module/table rather than reusing documents.py's table
directly, per docs/03's explicit separate naming: a WorkProduct is
analyst-authored output submitted against an assigned Task (tasks.py),
not deal source evidence a human uploaded as diligence material - the two
have different future lifecycles (a WorkProduct will eventually carry
review/return/approval state, Task 13.2's job; a Document never will) even
though today's storage mechanics are identical. Reuses documents.py's own
`ALLOWED_EXTENSIONS`/`sanitize_original_filename` rather than
re-declaring them - the set of acceptable file types is one fact, not two.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import documents
import store
import version_dependencies

DATA_DIR = documents.DATA_DIR


@dataclass
class WorkProduct:
    """The stable parent record - same "denormalized current version"
    shape as documents.Document, for the same reason: every existing kind
    of caller (a download route, a version-history listing) can read
    `work_product.sha256` etc. and always mean "the current version.\""""

    id: str
    project_id: str
    task_id: str
    title: str
    original_filename: str
    extension: str
    size_bytes: int
    sha256: str
    uploaded_at: str
    created_by: str | None
    version_number: int = 1
    current_version_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "title": self.title,
            "original_filename": self.original_filename,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "uploaded_at": self.uploaded_at,
            "created_by": self.created_by,
            "version_number": self.version_number,
            "current_version_id": self.current_version_id,
        }


@dataclass
class SubmissionVersion:
    id: str
    work_product_id: str
    version_number: int
    size_bytes: int
    sha256: str
    uploaded_at: str
    uploaded_by: str | None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "work_product_id": self.work_product_id,
            "version_number": self.version_number,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "uploaded_at": self.uploaded_at,
            "uploaded_by": self.uploaded_by,
        }


@dataclass
class SubmissionResult:
    title: str
    status: str  # "success" | "new_version" | "unsupported_type" | "duplicate" | "failed"
    work_product: WorkProduct | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        out: dict = {"title": self.title, "status": self.status}
        if self.work_product is not None:
            out["work_product"] = self.work_product.to_dict()
        if self.error is not None:
            out["error"] = self.error
        return out


def init_work_products_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS work_products (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                title TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                created_by TEXT,
                version_number INTEGER NOT NULL DEFAULT 1,
                current_version_id TEXT
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_work_products_task ON work_products(task_id)")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS submission_versions (
                id TEXT PRIMARY KEY,
                work_product_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                uploaded_at TEXT NOT NULL,
                uploaded_by TEXT
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_submission_versions_work_product ON submission_versions(work_product_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_work_product(row) -> WorkProduct:
    return WorkProduct(
        id=row["id"], project_id=row["project_id"], task_id=row["task_id"], title=row["title"],
        original_filename=row["original_filename"], extension=row["extension"], size_bytes=row["size_bytes"],
        sha256=row["sha256"], uploaded_at=row["uploaded_at"], created_by=row["created_by"],
        version_number=row["version_number"], current_version_id=row["current_version_id"],
    )


def _row_to_version(row) -> SubmissionVersion:
    return SubmissionVersion(
        row["id"], row["work_product_id"], row["version_number"], row["size_bytes"], row["sha256"],
        row["uploaded_at"], row["uploaded_by"],
    )


def _version_file_path(project_id: str, version_id: str, extension: str) -> Path:
    directory = DATA_DIR / "projects" / project_id / "work_products"
    directory.mkdir(parents=True, exist_ok=True)
    return directory / f"{version_id}{extension}"


def stored_file_path(work_product: WorkProduct) -> Path:
    version_id = work_product.current_version_id or work_product.id
    return _version_file_path(work_product.project_id, version_id, work_product.extension)


def version_file_path(work_product: WorkProduct, version: SubmissionVersion) -> Path:
    return _version_file_path(work_product.project_id, version.id, work_product.extension)


def create_work_product(
    project_id: str, task_id: str, raw_title: str, raw_filename: str, data: bytes, created_by: str | None,
) -> SubmissionResult:
    """Always creates a brand-new WorkProduct - mirrors documents.
    save_uploaded_file's own "never infer versioning" rule exactly: a
    second submission against the same task is a second, independent
    WorkProduct unless the caller explicitly calls add_version against a
    known work_product_id."""
    title = raw_title.strip() or documents.sanitize_original_filename(raw_filename)
    filename = documents.sanitize_original_filename(raw_filename)
    extension = Path(filename).suffix.lower()

    if extension not in documents.ALLOWED_EXTENSIONS:
        return SubmissionResult(title=title, status="unsupported_type",
                                 error=f"'{extension or 'no extension'}' is not a supported file type")

    checksum = hashlib.sha256(data).hexdigest()
    uploaded_at = datetime.now(timezone.utc).isoformat()
    work_product = WorkProduct(
        id=uuid.uuid4().hex, project_id=project_id, task_id=task_id, title=title,
        original_filename=filename, extension=extension, size_bytes=len(data), sha256=checksum,
        uploaded_at=uploaded_at, created_by=created_by, version_number=1, current_version_id=None,
    )
    work_product.current_version_id = work_product.id  # version 1 reuses the parent's own id

    try:
        _version_file_path(project_id, work_product.id, extension).write_bytes(data)
    except OSError as exc:
        return SubmissionResult(title=title, status="failed", error=str(exc))

    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO work_products (id, project_id, task_id, title, original_filename, extension,
                                        size_bytes, sha256, uploaded_at, created_by, version_number,
                                        current_version_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)
            """,
            (work_product.id, work_product.project_id, work_product.task_id, work_product.title,
             work_product.original_filename, work_product.extension, work_product.size_bytes,
             work_product.sha256, work_product.uploaded_at, work_product.created_by, work_product.id),
        )
        conn.execute(
            """
            INSERT INTO submission_versions (id, work_product_id, version_number, size_bytes, sha256,
                                              uploaded_at, uploaded_by)
            VALUES (%s, %s, 1, %s, %s, %s, %s)
            """,
            (work_product.id, work_product.id, work_product.size_bytes, work_product.sha256,
             work_product.uploaded_at, work_product.created_by),
        )
        conn.commit()
    finally:
        conn.close()

    return SubmissionResult(title=title, status="success", work_product=work_product)


def add_version(project_id: str, work_product_id: str, data: bytes, uploaded_by: str | None) -> SubmissionResult:
    """Explicitly replaces a specific, already-known work product's
    current content with a new immutable version - never inferred, same
    as documents.add_version. The previous version's own file is never
    touched, so it stays independently downloadable forever."""
    work_product = get_work_product(project_id, work_product_id)
    if work_product is None:
        return SubmissionResult(title="", status="failed", error="work product not found")

    checksum = hashlib.sha256(data).hexdigest()
    if checksum == work_product.sha256:
        return SubmissionResult(
            title=work_product.title, status="duplicate", work_product=work_product,
            error="identical to the current version",
        )

    new_version_id = uuid.uuid4().hex
    version_number = work_product.version_number + 1
    uploaded_at = datetime.now(timezone.utc).isoformat()

    try:
        _version_file_path(project_id, new_version_id, work_product.extension).write_bytes(data)
    except OSError as exc:
        return SubmissionResult(title=work_product.title, status="failed", error=str(exc))

    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO submission_versions (id, work_product_id, version_number, size_bytes, sha256,
                                              uploaded_at, uploaded_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (new_version_id, work_product.id, version_number, len(data), checksum, uploaded_at, uploaded_by),
        )
        conn.execute(
            """
            UPDATE work_products
            SET current_version_id = %s, version_number = %s, size_bytes = %s, sha256 = %s, uploaded_at = %s
            WHERE id = %s
            """,
            (new_version_id, version_number, len(data), checksum, uploaded_at, work_product.id),
        )
        conn.commit()
    finally:
        conn.close()

    updated = get_work_product(project_id, work_product.id)
    assert updated is not None

    # Task 15.1: propagate potential staleness the moment a new version
    # exists - see documents.add_version's own matching comment.
    version_dependencies.mark_superseded("work_product", work_product.id, new_version_id)

    return SubmissionResult(title=updated.title, status="new_version", work_product=updated)


def list_work_products(task_id: str) -> list[WorkProduct]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM work_products WHERE task_id = %s ORDER BY uploaded_at ASC", (task_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_work_product(r) for r in rows]


def get_work_product(project_id: str, work_product_id: str) -> WorkProduct | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM work_products WHERE project_id = %s AND id = %s", (project_id, work_product_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_work_product(row) if row else None


def list_versions(work_product_id: str) -> list[SubmissionVersion]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM submission_versions WHERE work_product_id = %s ORDER BY version_number ASC",
            (work_product_id,),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_version(r) for r in rows]


def get_version(work_product_id: str, version_id: str) -> SubmissionVersion | None:
    """Scoped to `work_product_id` so a version id can never be used to
    reach a different work product's file by guessing - same reasoning as
    documents.get_version."""
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM submission_versions WHERE work_product_id = %s AND id = %s",
            (work_product_id, version_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_version(row) if row else None
