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
    id: str
    project_id: str
    original_filename: str
    relative_path: str
    extension: str
    size_bytes: int
    sha256: str
    uploaded_at: str

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
    )


def originals_dir_for(project_id: str) -> Path:
    directory = DATA_DIR / "projects" / project_id / "originals"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def stored_file_path(document: Document) -> Path:
    return DATA_DIR / "projects" / document.project_id / "originals" / f"{document.id}{document.extension}"


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
            "SELECT * FROM documents WHERE project_id = ? AND sha256 = ? ORDER BY uploaded_at ASC LIMIT 1",
            (project_id, sha256),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_document(row) if row else None


def save_uploaded_file(project_id: str, raw_filename: str, raw_relative_path: str, data: bytes) -> UploadResult:
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

    document = Document(
        id=uuid.uuid4().hex,
        project_id=project_id,
        original_filename=filename,
        relative_path=relative_path,
        extension=extension,
        size_bytes=len(data),
        sha256=checksum,
        uploaded_at=datetime.now(timezone.utc).isoformat(),
    )

    originals_dir_for(project_id)
    try:
        stored_file_path(document).write_bytes(data)
    except OSError as exc:
        return UploadResult(filename=filename, relative_path=relative_path, status="failed", error=str(exc))

    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO documents (id, project_id, original_filename, relative_path, extension, size_bytes, sha256, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (document.id, document.project_id, document.original_filename, document.relative_path,
             document.extension, document.size_bytes, document.sha256, document.uploaded_at),
        )
        conn.commit()
    finally:
        conn.close()

    return UploadResult(filename=filename, relative_path=relative_path, status="success", document=document)


def list_documents(project_id: str) -> list[Document]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM documents WHERE project_id = ? ORDER BY uploaded_at DESC", (project_id,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_document(row) for row in rows]


def get_document(project_id: str, document_id: str) -> Document | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM documents WHERE project_id = ? AND id = ?", (project_id, document_id)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_document(row) if row else None


def delete_document(project_id: str, document_id: str) -> bool:
    document = get_document(project_id, document_id)
    if document is None:
        return False

    conn = store.get_connection()
    try:
        conn.execute("DELETE FROM documents WHERE project_id = ? AND id = ?", (project_id, document_id))
        conn.commit()
    finally:
        conn.close()

    path = stored_file_path(document)
    path.unlink(missing_ok=True)
    return True
