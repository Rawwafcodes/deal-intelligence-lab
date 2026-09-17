"""Original document storage and inventory tracking.

Uploaded file bytes are stored outside the application repository (under
DATA_DIR, default ~/DealLabData) so confidential deal documents never end
up in git. Only metadata (filename, folder path, checksum, etc.) lives in
the application's SQLite database.

Every stored file is written under its own server-generated document id -
never under the browser-supplied filename or folder path - so a hostile
filename can never influence a filesystem path (see save_uploaded_file).
"""

from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import store

DATA_DIR = Path(os.environ.get("DEAL_LAB_DATA_DIR", str(Path.home() / "DealLabData")))

# Total bytes allowed in a single upload request (all files combined).
MAX_UPLOAD_BYTES = int(os.environ.get("DEAL_LAB_MAX_UPLOAD_BYTES", 500 * 1024 * 1024))  # 500 MB
# Maximum number of files accepted in a single upload request.
MAX_FILES_PER_UPLOAD = int(os.environ.get("DEAL_LAB_MAX_FILES_PER_UPLOAD", 200))

# Extension -> content type. SVG is deliberately excluded from images: it
# can embed <script>, so treating it as a "safe" image would undercut the
# "never execute uploaded content" requirement.
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".tif": "image/tiff",
    ".tiff": "image/tiff",
    ".webp": "image/webp",
}

_UNSAFE_PATH_CHARS = re.compile(r'[\x00-\x1f]')


@dataclass
class Document:
    """The stable parent record (Task 11.4: docs/03-domain-model.md's
    Document/DocumentVersion split). `size_bytes`/`sha256`/`uploaded_at`
    are a denormalized copy of the *current* version's own values, kept so
    every existing caller that reads `document.sha256` etc. (pdf_inspection,
    xlsx_inspection, workspace_exports, citations, this module's own
    download handler) keeps working unchanged - they always mean "the
    current version," exactly as they meant "the only version" before this
    task. `current_version_id` is `None` only transiently, never once
    `save_uploaded_file`/the startup backfill has run - a real Document
    always has at least one version."""

    id: str
    project_id: str
    original_filename: str
    relative_path: str
    extension: str
    size_bytes: int
    sha256: str
    uploaded_at: str
    version_number: int = 1
    current_version_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "original_filename": self.original_filename,
            "relative_path": self.relative_path,
            "extension": self.extension,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "uploaded_at": self.uploaded_at,
            "version_number": self.version_number,
            "current_version_id": self.current_version_id,
        }


@dataclass
class DocumentVersion:
    """An immutable, individually-addressable version of a Document.
    Every version's bytes are stored under its own id
    (`{version.id}{extension}`), never overwritten - so an old version
    stays byte-identical and independently downloadable/citeable forever
    (docs/09-acceptance.md T01), even after a newer version replaces it as
    "current" on the parent Document."""

    id: str
    document_id: str
    version_number: int
    size_bytes: int
    sha256: str
    uploaded_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "document_id": self.document_id,
            "version_number": self.version_number,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "uploaded_at": self.uploaded_at,
        }


@dataclass
class UploadResult:
    filename: str
    relative_path: str
    status: str  # "success" | "duplicate" | "unsupported_type" | "failed"
    document: Document | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        out: dict = {"filename": self.filename, "relative_path": self.relative_path, "status": self.status}
        if self.document is not None:
            out["document"] = self.document.to_dict()
        if self.error is not None:
            out["error"] = self.error
        return out


def init_documents_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                original_filename TEXT NOT NULL,
                relative_path TEXT NOT NULL DEFAULT '',
                extension TEXT NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id)")
        # Task 11.4: additive columns for Document/DocumentVersion. A
        # pre-existing document (real data included) has no version row
        # yet until _backfill_legacy_versions() below gives it one -
        # current_version_id is nullable at the schema level for exactly
        # that transient window.
        conn.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS current_version_id TEXT")
        conn.execute("ALTER TABLE documents ADD COLUMN IF NOT EXISTS version_number INTEGER NOT NULL DEFAULT 1")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS document_versions (
                id TEXT PRIMARY KEY,
                document_id TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                size_bytes INTEGER NOT NULL,
                sha256 TEXT NOT NULL,
                uploaded_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_document_versions_document ON document_versions(document_id)"
        )
        conn.commit()
    finally:
        conn.close()
    _backfill_legacy_versions()


def _backfill_legacy_versions() -> None:
    """Additive, idempotent: gives every document created before this task
    (real data included) a version 1 row - without moving any file on
    disk. The version's id is set equal to its parent document's id, so
    stored_file_path() (which resolves via current_version_id) keeps
    pointing at the exact file that was already on disk at
    `{document.id}{extension}` - zero bytes moved, zero risk to real
    stored originals."""
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT id, size_bytes, sha256, uploaded_at FROM documents WHERE current_version_id IS NULL"
        ).fetchall()
        for row in rows:
            conn.execute(
                """
                INSERT INTO document_versions (id, document_id, version_number, size_bytes, sha256, uploaded_at)
                VALUES (%s, %s, 1, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (row["id"], row["id"], row["size_bytes"], row["sha256"], row["uploaded_at"]),
            )
            conn.execute("UPDATE documents SET current_version_id = %s WHERE id = %s", (row["id"], row["id"]))
        conn.commit()
    finally:
        conn.close()


def _row_to_document(row) -> Document:
    return Document(
        id=row["id"],
        project_id=row["project_id"],
        original_filename=row["original_filename"],
        relative_path=row["relative_path"],
        extension=row["extension"],
        size_bytes=row["size_bytes"],
        sha256=row["sha256"],
        uploaded_at=row["uploaded_at"],
        version_number=row["version_number"],
        current_version_id=row["current_version_id"],
    )


def originals_dir_for(project_id: str) -> Path:
    directory = DATA_DIR / "projects" / project_id / "originals"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def stored_file_path(document: Document) -> Path:
    """Resolves to the document's *current* version's bytes. Every
    existing caller (pdf_inspection, xlsx_inspection, workspace_exports,
    the download handler) keeps working unchanged: for a document that
    has only ever had one version, `current_version_id == document.id`
    (see _backfill_legacy_versions/save_uploaded_file), so this resolves
    to exactly the path it always did."""
    version_id = document.current_version_id or document.id
    return _version_file_path(document.project_id, version_id, document.extension)


def _version_file_path(project_id: str, version_id: str, extension: str) -> Path:
    return DATA_DIR / "projects" / project_id / "originals" / f"{version_id}{extension}"


def version_file_path(document: Document, version: DocumentVersion) -> Path:
    """Public counterpart to stored_file_path(), for reaching a specific
    historical version rather than always the current one."""
    return _version_file_path(document.project_id, version.id, document.extension)


def sanitize_relative_path(raw: str) -> str:
    """Keep only a display-safe folder path; never used to build filesystem paths."""
    raw = _UNSAFE_PATH_CHARS.sub("", raw).strip().strip("/")
    parts = [p for p in raw.split("/") if p not in ("", ".", "..")]
    return "/".join(parts)


def sanitize_original_filename(raw: str) -> str:
    """Basename only, control characters stripped; used for display and the download header."""
    raw = raw.replace("\\", "/")
    basename = raw.rsplit("/", 1)[-1]
    basename = _UNSAFE_PATH_CHARS.sub("", basename).strip()
    return basename or "unnamed"


def find_duplicate(project_id: str, sha256: str) -> Document | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE project_id = %s AND sha256 = %s ORDER BY uploaded_at ASC LIMIT 1",
            (project_id, sha256),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_document(row) if row else None


def save_uploaded_file(project_id: str, raw_filename: str, raw_relative_path: str, data: bytes) -> UploadResult:
    """Always creates a brand-new, independent Document - unchanged from
    before Task 11.4, including for a filename that happens to match an
    existing document's. Replacing a specific document's content is a
    separate, explicit action a caller takes on that document
    (add_version, below), never an inferred side effect of an ordinary
    upload - inferring it from a name collision would have been a
    surprising, silent behavior change for exactly the same-named-but-
    unrelated-files pattern several existing test fixtures (and,
    plausibly, real users re-using a common filename like "notes.txt")
    already rely on."""
    filename = sanitize_original_filename(raw_filename)
    relative_path = sanitize_relative_path(raw_relative_path)
    extension = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        return UploadResult(filename=filename, relative_path=relative_path, status="unsupported_type",
                             error=f"'{extension or 'no extension'}' is not a supported file type")

    checksum = hashlib.sha256(data).hexdigest()

    existing = find_duplicate(project_id, checksum)
    if existing is not None:
        return UploadResult(filename=filename, relative_path=relative_path, status="duplicate",
                             document=existing, error="identical file already uploaded to this project")

    uploaded_at = datetime.now(timezone.utc).isoformat()
    document = Document(
        id=uuid.uuid4().hex,
        project_id=project_id,
        original_filename=filename,
        relative_path=relative_path,
        extension=extension,
        size_bytes=len(data),
        sha256=checksum,
        uploaded_at=uploaded_at,
        version_number=1,
        current_version_id=None,
    )
    document.current_version_id = document.id  # version 1 always reuses the document's own id

    originals_dir_for(project_id)
    try:
        stored_file_path(document).write_bytes(data)
    except OSError as exc:
        return UploadResult(filename=filename, relative_path=relative_path, status="failed", error=str(exc))

    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO documents (id, project_id, original_filename, relative_path, extension, size_bytes,
                                    sha256, uploaded_at, current_version_id, version_number)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
            """,
            (document.id, document.project_id, document.original_filename, document.relative_path,
             document.extension, document.size_bytes, document.sha256, document.uploaded_at, document.id),
        )
        conn.execute(
            """
            INSERT INTO document_versions (id, document_id, version_number, size_bytes, sha256, uploaded_at)
            VALUES (%s, %s, 1, %s, %s, %s)
            """,
            (document.id, document.id, document.size_bytes, document.sha256, document.uploaded_at),
        )
        conn.commit()
    finally:
        conn.close()

    return UploadResult(filename=filename, relative_path=relative_path, status="success", document=document)


def add_version(project_id: str, document_id: str, data: bytes) -> UploadResult:
    """Explicitly replaces a specific, already-known document's content
    with a new immutable version - the only way a new version is ever
    created (see save_uploaded_file's docstring for why this is kept
    separate from ordinary upload). The document's own identity
    (original_filename, relative_path, id) never changes; only its
    current bytes/hash/size and version_number do. The previous version's
    file is never touched - only a fresh file, under the new version's
    own id, is written, so it stays independently downloadable/citeable
    (docs/09-acceptance.md T01)."""
    document = get_document(project_id, document_id)
    if document is None:
        return UploadResult(filename="", relative_path="", status="failed", error="document not found")

    checksum = hashlib.sha256(data).hexdigest()
    if checksum == document.sha256:
        return UploadResult(
            filename=document.original_filename, relative_path=document.relative_path, status="duplicate",
            document=document, error="identical to the current version",
        )

    new_version_id = uuid.uuid4().hex
    version_number = document.version_number + 1
    uploaded_at = datetime.now(timezone.utc).isoformat()

    originals_dir_for(project_id)
    try:
        _version_file_path(project_id, new_version_id, document.extension).write_bytes(data)
    except OSError as exc:
        return UploadResult(
            filename=document.original_filename, relative_path=document.relative_path,
            status="failed", error=str(exc),
        )

    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO document_versions (id, document_id, version_number, size_bytes, sha256, uploaded_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (new_version_id, document.id, version_number, len(data), checksum, uploaded_at),
        )
        conn.execute(
            """
            UPDATE documents
            SET current_version_id = %s, version_number = %s, size_bytes = %s, sha256 = %s, uploaded_at = %s
            WHERE id = %s
            """,
            (new_version_id, version_number, len(data), checksum, uploaded_at, document.id),
        )
        conn.commit()
    finally:
        conn.close()

    updated = get_document(document.project_id, document.id)
    assert updated is not None
    return UploadResult(
        filename=updated.original_filename, relative_path=updated.relative_path,
        status="new_version", document=updated,
    )


def list_versions(document_id: str) -> list[DocumentVersion]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            """
            SELECT id, document_id, version_number, size_bytes, sha256, uploaded_at
            FROM document_versions WHERE document_id = %s ORDER BY version_number ASC
            """,
            (document_id,),
        ).fetchall()
    finally:
        conn.close()
    return [
        DocumentVersion(r["id"], r["document_id"], r["version_number"], r["size_bytes"], r["sha256"], r["uploaded_at"])
        for r in rows
    ]


def get_version(document_id: str, version_id: str) -> DocumentVersion | None:
    """Scoped to `document_id` so a version id can never be used to reach
    a different document's file by guessing."""
    conn = store.get_connection()
    try:
        row = conn.execute(
            """
            SELECT id, document_id, version_number, size_bytes, sha256, uploaded_at
            FROM document_versions WHERE document_id = %s AND id = %s
            """,
            (document_id, version_id),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    return DocumentVersion(row["id"], row["document_id"], row["version_number"], row["size_bytes"], row["sha256"], row["uploaded_at"])


def list_documents(project_id: str) -> list[Document]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM documents WHERE project_id = %s ORDER BY uploaded_at DESC", (project_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_document(row) for row in rows]


def get_document(project_id: str, document_id: str) -> Document | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE project_id = %s AND id = %s", (project_id, document_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_document(row) if row else None


def delete_document(project_id: str, document_id: str) -> bool:
    document = get_document(project_id, document_id)
    if document is None:
        return False

    versions = list_versions(document_id)

    conn = store.get_connection()
    try:
        conn.execute("DELETE FROM document_versions WHERE document_id = %s", (document_id,))
        conn.execute("DELETE FROM documents WHERE project_id = %s AND id = %s", (project_id, document_id))
        conn.commit()
    finally:
        conn.close()

    for version in versions:
        _version_file_path(project_id, version.id, document.extension).unlink(missing_ok=True)
    return True
