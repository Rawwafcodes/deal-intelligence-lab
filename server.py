"""Deal Intelligence Lab - local web server.

Run inside the project's virtual environment (see README.md):

    source venv/bin/activate
    python3 server.py

Then open http://localhost:8765 in a browser.
"""

from __future__ import annotations

import json
import mimetypes
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

import ai_client
import cross_analyses
import cross_document_analysis
import documents
import inspections
import multipart
import pdf_inspection
import store

STATIC_DIR = Path(__file__).parent / "static"
PORT = 8765

MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
MAX_BODY_BYTES = 1_000_000

_DOCUMENTS_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/documents$")
_DOCUMENT_DOWNLOAD_RE = re.compile(r"^/api/projects/([^/]+)/documents/([^/]+)/download$")
_DOCUMENT_INSPECT_RE = re.compile(r"^/api/projects/([^/]+)/documents/([^/]+)/inspect$")
_DOCUMENT_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/documents/([^/]+)$")
_INSPECTION_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/inspections/([^/]+)$")
_CROSS_ANALYSIS_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/cross-analysis$")
_CROSS_ANALYSIS_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/cross-analyses/([^/]+)$")


class Handler(BaseHTTPRequestHandler):
    server_version = "DealLab/0.1"

    def log_message(self, format: str, *args) -> None:  # quieter default logging
        pass

    # -- helpers -----------------------------------------------------

    def _send_json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_static_file(self, rel_path: str) -> None:
        candidate = (STATIC_DIR / rel_path).resolve()
        if STATIC_DIR.resolve() not in candidate.parents and candidate != STATIC_DIR.resolve():
            self._send_json(403, {"error": "forbidden"})
            return
        if not candidate.is_file():
            self._send_json(404, {"error": "not found"})
            return
        content_type, _ = mimetypes.guess_type(str(candidate))
        body = candidate.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self) -> dict | None:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > MAX_BODY_BYTES:
            return None
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def _content_disposition(self, filename: str, disposition_type: str = "attachment") -> str:
        ascii_fallback = filename.encode("ascii", "replace").decode("ascii").replace('"', "'")
        encoded = quote(filename, safe="")
        return f'{disposition_type}; filename="{ascii_fallback}"; filename*=UTF-8\'\'{encoded}'

    def _send_file_download(self, document, inline: bool = False) -> None:
        path = documents.stored_file_path(document)
        if not path.is_file():
            self._send_json(404, {"error": "stored file is missing"})
            return
        body = path.read_bytes()
        content_type = documents.ALLOWED_EXTENSIONS.get(document.extension, "application/octet-stream")
        disposition_type = "inline" if inline else "attachment"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Content-Disposition", self._content_disposition(document.original_filename, disposition_type)
        )
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _read_multipart_body(self) -> bytes | None:
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0 or length > documents.MAX_UPLOAD_BYTES:
            self.send_response(413)
            self.send_header("Content-Length", "0")
            self.end_headers()
            self.close_connection = True
            return None
        return self.rfile.read(length)

    # -- routing -------------------------------------------------------

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self._send_static_file("index.html")
            return

        if path == "/project.html":
            self._send_static_file("project.html")
            return

        if path == "/inspect.html":
            self._send_static_file("inspect.html")
            return

        if path == "/cross-analysis.html":
            self._send_static_file("cross-analysis.html")
            return

        if path == "/api/projects":
            projects = [p.to_dict() for p in store.list_projects()]
            self._send_json(200, projects)
            return

        download_match = _DOCUMENT_DOWNLOAD_RE.match(path)
        if download_match:
            project_id, document_id = download_match.groups()
            if store.get_project(project_id) is None:
                self._send_json(404, {"error": "project not found"})
                return
            document = documents.get_document(project_id, document_id)
            if document is None:
                self._send_json(404, {"error": "document not found"})
                return
            inline = parse_qs(parsed.query).get("inline", ["0"])[0] == "1"
            self._send_file_download(document, inline=inline)
            return

        inspection_match = _INSPECTION_ITEM_RE.match(path)
        if inspection_match:
            project_id, inspection_id = inspection_match.groups()
            if store.get_project(project_id) is None:
                self._send_json(404, {"error": "project not found"})
                return
            inspection = inspections.get_inspection(project_id, inspection_id)
            if inspection is None:
                self._send_json(404, {"error": "inspection not found"})
                return
            self._send_json(200, inspection.to_dict())
            return

        cross_analysis_match = _CROSS_ANALYSIS_ITEM_RE.match(path)
        if cross_analysis_match:
            project_id, cross_analysis_id = cross_analysis_match.groups()
            if store.get_project(project_id) is None:
                self._send_json(404, {"error": "project not found"})
                return
            record = cross_analyses.get_cross_analysis(project_id, cross_analysis_id)
            if record is None:
                self._send_json(404, {"error": "cross-document analysis not found"})
                return
            self._send_json(200, record.to_dict())
            return

        collection_match = _DOCUMENTS_COLLECTION_RE.match(path)
        if collection_match:
            (project_id,) = collection_match.groups()
            if store.get_project(project_id) is None:
                self._send_json(404, {"error": "project not found"})
                return
            docs = [d.to_dict() for d in documents.list_documents(project_id)]
            self._send_json(200, docs)
            return

        if path.startswith("/api/projects/"):
            project_id = path.removeprefix("/api/projects/")
            project = store.get_project(project_id)
            if project is None:
                self._send_json(404, {"error": "project not found"})
                return
            self._send_json(200, project.to_dict())
            return

        # static assets: css, js
        if path.startswith("/"):
            self._send_static_file(path.lstrip("/"))
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        path = urlparse(self.path).path

        if path == "/api/ai/test-connection":
            length = int(self.headers.get("Content-Length", 0))
            if length > 0:
                self.rfile.read(length)  # discard any body; nothing is required
            result = ai_client.test_connection()
            self._send_json(200 if result.success else 502, result.to_dict())
            return

        if path == "/api/projects":
            data = self._read_json_body()
            if data is None:
                self._send_json(400, {"error": "invalid JSON body"})
                return

            name = str(data.get("name", "")).strip()
            description = str(data.get("description", "")).strip()

            if not name:
                self._send_json(400, {"error": "name is required"})
                return
            if len(name) > MAX_NAME_LENGTH:
                self._send_json(400, {"error": f"name must be under {MAX_NAME_LENGTH} characters"})
                return
            if len(description) > MAX_DESCRIPTION_LENGTH:
                self._send_json(
                    400, {"error": f"description must be under {MAX_DESCRIPTION_LENGTH} characters"}
                )
                return

            project = store.create_project(name, description)
            self._send_json(201, project.to_dict())
            return

        collection_match = _DOCUMENTS_COLLECTION_RE.match(path)
        if collection_match:
            (project_id,) = collection_match.groups()
            self._handle_document_upload(project_id)
            return

        inspect_match = _DOCUMENT_INSPECT_RE.match(path)
        if inspect_match:
            project_id, document_id = inspect_match.groups()
            self._handle_document_inspect(project_id, document_id)
            return

        cross_analysis_match = _CROSS_ANALYSIS_COLLECTION_RE.match(path)
        if cross_analysis_match:
            (project_id,) = cross_analysis_match.groups()
            self._handle_cross_analysis(project_id)
            return

        self._send_json(404, {"error": "not found"})

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path

        item_match = _DOCUMENT_ITEM_RE.match(path)
        if item_match:
            project_id, document_id = item_match.groups()
            if store.get_project(project_id) is None:
                self._send_json(404, {"error": "project not found"})
                return
            if documents.get_document(project_id, document_id) is None:
                self._send_json(404, {"error": "document not found"})
                return

            body = self._read_json_body()
            if not body or body.get("confirm") is not True:
                self._send_json(400, {"error": "deletion requires {\"confirm\": true} in the request body"})
                return

            documents.delete_document(project_id, document_id)
            self._send_json(200, {"deleted": True})
            return

        self._send_json(404, {"error": "not found"})

    def _handle_document_upload(self, project_id: str) -> None:
        if store.get_project(project_id) is None:
            self._send_json(404, {"error": "project not found"})
            return

        content_type_header = self.headers.get("Content-Type", "")
        if not content_type_header.lower().startswith("multipart/form-data"):
            self._send_json(400, {"error": "expected multipart/form-data"})
            return

        try:
            boundary = multipart.parse_boundary(content_type_header)
        except multipart.MultipartError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        body = self._read_multipart_body()
        if body is None:
            return  # 413 already sent

        try:
            parts = multipart.parse_multipart(body, boundary)
        except multipart.MultipartError as exc:
            self._send_json(400, {"error": f"malformed upload: {exc}"})
            return

        file_parts = [p for p in parts if p.name == "files" and p.filename]
        path_parts = [p.data.decode("utf-8", errors="replace") for p in parts if p.name == "relative_paths"]

        if not file_parts:
            self._send_json(400, {"error": "no files were included in the upload"})
            return

        if len(file_parts) > documents.MAX_FILES_PER_UPLOAD:
            self._send_json(
                400,
                {"error": f"too many files in one upload (max {documents.MAX_FILES_PER_UPLOAD})"},
            )
            return

        results = []
        for index, part in enumerate(file_parts):
            raw_relative_path = path_parts[index] if index < len(path_parts) else ""
            # webkitRelativePath includes the filename itself; keep only the folder portion.
            folder_path = raw_relative_path.rsplit("/", 1)[0] if "/" in raw_relative_path else ""
            result = documents.save_uploaded_file(project_id, part.filename or "", folder_path, part.data)
            results.append(result.to_dict())

        self._send_json(200, {"results": results})

    def _handle_document_inspect(self, project_id: str, document_id: str) -> None:
        if store.get_project(project_id) is None:
            self._send_json(404, {"error": "project not found"})
            return

        document = documents.get_document(project_id, document_id)
        if document is None:
            self._send_json(404, {"error": "document not found"})
            return

        if document.extension != ".pdf":
            self._send_json(400, {"error": "only PDF documents can be inspected in this milestone"})
            return

        body = self._read_json_body()
        if not body or body.get("confirm") is not True:
            self._send_json(400, {"error": "inspection requires {\"confirm\": true} in the request body"})
            return

        outcome = pdf_inspection.inspect_document(document)
        record = inspections.create_inspection(
            project_id=project_id,
            document_id=document_id,
            document_filename=document.original_filename,
            status="success" if outcome.success else "error",
            transmitted=outcome.transmitted,
            analysis_seconds=outcome.analysis_seconds,
            model=outcome.model,
            stop_reason=outcome.stop_reason,
            input_tokens=outcome.usage["input_tokens"] if outcome.usage else None,
            output_tokens=outcome.usage["output_tokens"] if outcome.usage else None,
            error_type=outcome.error_type,
            error_message=outcome.error_message,
            segments=[s.to_dict() for s in outcome.segments] if outcome.segments else None,
        )
        self._send_json(200 if outcome.success else 502, record.to_dict())

    def _handle_cross_analysis(self, project_id: str) -> None:
        if store.get_project(project_id) is None:
            self._send_json(404, {"error": "project not found"})
            return

        body = self._read_json_body()
        if not body or body.get("confirm") is not True:
            self._send_json(
                400, {"error": "cross-document analysis requires {\"confirm\": true} in the request body"}
            )
            return

        document_ids = body.get("document_ids")
        if not isinstance(document_ids, list) or not all(isinstance(d, str) for d in document_ids):
            self._send_json(400, {"error": "document_ids must be a list of document id strings"})
            return
        if len(document_ids) != len(set(document_ids)):
            self._send_json(400, {"error": "duplicate document selected"})
            return

        selected = []
        for document_id in document_ids:
            document = documents.get_document(project_id, document_id)
            if document is None:
                self._send_json(404, {"error": f"document not found: {document_id}"})
                return
            selected.append(document)

        outcome = cross_document_analysis.run_cross_analysis(selected)
        record = cross_analyses.create_cross_analysis(
            project_id=project_id,
            document_ids=[d.id for d in selected],
            document_filenames=[d.original_filename for d in selected],
            document_checksums=[d.sha256 for d in selected],
            status="success" if outcome.success else "error",
            transmitted=outcome.transmitted,
            analysis_seconds=outcome.analysis_seconds,
            model=outcome.model,
            mandate_version=cross_document_analysis.MANDATE_VERSION,
            stop_reason=outcome.stop_reason,
            input_tokens=outcome.usage["input_tokens"] if outcome.usage else None,
            output_tokens=outcome.usage["output_tokens"] if outcome.usage else None,
            error_type=outcome.error_type,
            error_message=outcome.error_message,
            segments=[s.to_dict() for s in outcome.segments] if outcome.segments else None,
        )
        self._send_json(200 if outcome.success else 502, record.to_dict())


def main() -> None:
    store.init_db()
    documents.init_documents_db()
    inspections.init_inspections_db()
    cross_analyses.init_cross_analyses_db()
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Deal Intelligence Lab running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


if __name__ == "__main__":
    main()
