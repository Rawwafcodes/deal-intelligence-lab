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
import answer_keys
import cross_analyses
import cross_document_analysis
import cross_format_analyses
import cross_format_analysis
import documents
import evaluations
import inspections
import multipart
import pdf_inspection
import store
import validation_cases
import validation_runs
import xlsx_inspection
import xlsx_inspections

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
_XLSX_INSPECT_RE = re.compile(r"^/api/projects/([^/]+)/documents/([^/]+)/inspect-workbook$")
_XLSX_INSPECTION_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/workbook-inspections/([^/]+)$")
_RECONCILIATION_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/reconciliation$")
_RECONCILIATION_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/reconciliations/([^/]+)$")
_CROSS_FORMAT_ANALYSES_LIST_RE = re.compile(r"^/api/projects/([^/]+)/cross-format-analyses$")

_VALIDATION_CASES_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/validation-cases$")
_VALIDATION_CASE_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/validation-cases/([^/]+)$")
_VALIDATION_CASE_DOCUMENTS_RE = re.compile(r"^/api/projects/([^/]+)/validation-cases/([^/]+)/documents$")
_ANSWER_KEY_RE = re.compile(r"^/api/projects/([^/]+)/validation-cases/([^/]+)/answer-key$")
_ANSWER_KEY_LOCK_RE = re.compile(r"^/api/projects/([^/]+)/validation-cases/([^/]+)/answer-key/lock$")
_ANSWER_KEY_REVISE_RE = re.compile(r"^/api/projects/([^/]+)/validation-cases/([^/]+)/answer-key/revise$")
_VALIDATION_RUNS_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/validation-cases/([^/]+)/runs$")
_VALIDATION_RUN_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/validation-cases/([^/]+)/runs/([^/]+)$")
_VALIDATION_EVALUATION_RE = re.compile(
    r"^/api/projects/([^/]+)/validation-cases/([^/]+)/runs/([^/]+)/evaluation$"
)
_VALIDATION_REPORT_RE = re.compile(r"^/api/projects/([^/]+)/validation-cases/([^/]+)/runs/([^/]+)/report$")


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

        if path == "/workbook-inspect.html":
            self._send_static_file("workbook-inspect.html")
            return

        if path == "/reconcile.html":
            self._send_static_file("reconcile.html")
            return

        if path == "/validation.html":
            self._send_static_file("validation.html")
            return

        if path == "/validation-case.html":
            self._send_static_file("validation-case.html")
            return

        if path == "/validation-evaluation.html":
            self._send_static_file("validation-evaluation.html")
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

        xlsx_inspection_match = _XLSX_INSPECTION_ITEM_RE.match(path)
        if xlsx_inspection_match:
            project_id, xlsx_inspection_id = xlsx_inspection_match.groups()
            if store.get_project(project_id) is None:
                self._send_json(404, {"error": "project not found"})
                return
            xlsx_record = xlsx_inspections.get_xlsx_inspection(project_id, xlsx_inspection_id)
            if xlsx_record is None:
                self._send_json(404, {"error": "workbook inspection not found"})
                return
            self._send_json(200, xlsx_record.to_dict())
            return

        reconciliation_match = _RECONCILIATION_ITEM_RE.match(path)
        if reconciliation_match:
            project_id, reconciliation_id = reconciliation_match.groups()
            if store.get_project(project_id) is None:
                self._send_json(404, {"error": "project not found"})
                return
            reconciliation_record = cross_format_analyses.get_cross_format_analysis(project_id, reconciliation_id)
            if reconciliation_record is None:
                self._send_json(404, {"error": "reconciliation not found"})
                return
            self._send_json(200, reconciliation_record.to_dict())
            return

        cross_format_list_match = _CROSS_FORMAT_ANALYSES_LIST_RE.match(path)
        if cross_format_list_match:
            (project_id,) = cross_format_list_match.groups()
            if store.get_project(project_id) is None:
                self._send_json(404, {"error": "project not found"})
                return
            records = cross_format_analyses.list_cross_format_analyses(project_id)
            self._send_json(200, [r.to_dict() for r in records])
            return

        evaluation_match = _VALIDATION_EVALUATION_RE.match(path)
        if evaluation_match:
            project_id, validation_case_id, run_id = evaluation_match.groups()
            self._handle_get_evaluation(project_id, validation_case_id, run_id)
            return

        report_match = _VALIDATION_REPORT_RE.match(path)
        if report_match:
            project_id, validation_case_id, run_id = report_match.groups()
            self._handle_get_report(project_id, validation_case_id, run_id)
            return

        validation_run_item_match = _VALIDATION_RUN_ITEM_RE.match(path)
        if validation_run_item_match:
            project_id, validation_case_id, run_id = validation_run_item_match.groups()
            case = self._get_owned_validation_case(project_id, validation_case_id)
            if case is None:
                return
            run = validation_runs.get_run(validation_case_id, run_id)
            if run is None:
                self._send_json(404, {"error": "validation run not found"})
                return
            self._send_json(200, run.to_dict())
            return

        validation_runs_collection_match = _VALIDATION_RUNS_COLLECTION_RE.match(path)
        if validation_runs_collection_match:
            project_id, validation_case_id = validation_runs_collection_match.groups()
            case = self._get_owned_validation_case(project_id, validation_case_id)
            if case is None:
                return
            runs = validation_runs.list_runs_for_case(validation_case_id)
            self._send_json(200, [r.to_dict() for r in runs])
            return

        answer_key_match = _ANSWER_KEY_RE.match(path)
        if answer_key_match:
            project_id, validation_case_id = answer_key_match.groups()
            self._handle_get_answer_key(project_id, validation_case_id)
            return

        validation_case_item_match = _VALIDATION_CASE_ITEM_RE.match(path)
        if validation_case_item_match:
            project_id, validation_case_id = validation_case_item_match.groups()
            self._handle_get_validation_case(project_id, validation_case_id)
            return

        validation_cases_collection_match = _VALIDATION_CASES_COLLECTION_RE.match(path)
        if validation_cases_collection_match:
            (project_id,) = validation_cases_collection_match.groups()
            if store.get_project(project_id) is None:
                self._send_json(404, {"error": "project not found"})
                return
            cases = validation_cases.list_validation_cases(project_id)
            self._send_json(200, [c.to_dict() for c in cases])
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

        xlsx_inspect_match = _XLSX_INSPECT_RE.match(path)
        if xlsx_inspect_match:
            project_id, document_id = xlsx_inspect_match.groups()
            self._handle_workbook_inspect(project_id, document_id)
            return

        reconciliation_match = _RECONCILIATION_COLLECTION_RE.match(path)
        if reconciliation_match:
            (project_id,) = reconciliation_match.groups()
            self._handle_reconciliation(project_id)
            return

        validation_cases_collection_match = _VALIDATION_CASES_COLLECTION_RE.match(path)
        if validation_cases_collection_match:
            (project_id,) = validation_cases_collection_match.groups()
            self._handle_create_validation_case(project_id)
            return

        validation_case_documents_match = _VALIDATION_CASE_DOCUMENTS_RE.match(path)
        if validation_case_documents_match:
            project_id, validation_case_id = validation_case_documents_match.groups()
            self._handle_update_validation_case_documents(project_id, validation_case_id)
            return

        answer_key_lock_match = _ANSWER_KEY_LOCK_RE.match(path)
        if answer_key_lock_match:
            project_id, validation_case_id = answer_key_lock_match.groups()
            self._handle_lock_answer_key(project_id, validation_case_id)
            return

        answer_key_revise_match = _ANSWER_KEY_REVISE_RE.match(path)
        if answer_key_revise_match:
            project_id, validation_case_id = answer_key_revise_match.groups()
            self._handle_revise_answer_key(project_id, validation_case_id)
            return

        answer_key_match = _ANSWER_KEY_RE.match(path)
        if answer_key_match:
            project_id, validation_case_id = answer_key_match.groups()
            self._handle_update_answer_key(project_id, validation_case_id)
            return

        validation_runs_collection_match = _VALIDATION_RUNS_COLLECTION_RE.match(path)
        if validation_runs_collection_match:
            project_id, validation_case_id = validation_runs_collection_match.groups()
            self._handle_start_validation_run(project_id, validation_case_id)
            return

        evaluation_match = _VALIDATION_EVALUATION_RE.match(path)
        if evaluation_match:
            project_id, validation_case_id, run_id = evaluation_match.groups()
            self._handle_update_evaluation(project_id, validation_case_id, run_id)
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

    def _handle_workbook_inspect(self, project_id: str, document_id: str) -> None:
        if store.get_project(project_id) is None:
            self._send_json(404, {"error": "project not found"})
            return

        document = documents.get_document(project_id, document_id)
        if document is None:
            self._send_json(404, {"error": "document not found"})
            return

        if document.extension not in (".xlsx", ".xls"):
            self._send_json(400, {"error": "only .xlsx or .xls documents can be inspected with this action"})
            return

        body = self._read_json_body()
        if not body or body.get("confirm") is not True:
            self._send_json(
                400, {"error": "workbook inspection requires {\"confirm\": true} in the request body"}
            )
            return

        outcome = xlsx_inspection.inspect_workbook(document)
        record = xlsx_inspections.create_xlsx_inspection(
            project_id=project_id,
            document_id=document_id,
            document_filename=document.original_filename,
            document_checksum=document.sha256,
            status="success" if outcome.success else "error",
            transmitted=outcome.transmitted,
            remote_cleanup_attempted=outcome.remote_cleanup_attempted,
            remote_cleanup_succeeded=outcome.remote_cleanup_succeeded,
            verification_available=outcome.verification_available,
            verification_unavailable_reason=outcome.verification_unavailable_reason,
            analysis_seconds=outcome.analysis_seconds,
            model=outcome.model,
            mandate_version=xlsx_inspection.MANDATE_VERSION,
            stop_reason=outcome.stop_reason,
            input_tokens=outcome.usage["input_tokens"] if outcome.usage else None,
            output_tokens=outcome.usage["output_tokens"] if outcome.usage else None,
            code_execution_requests=outcome.usage.get("code_execution_requests") if outcome.usage else None,
            error_type=outcome.error_type,
            error_message=outcome.error_message,
            segments=[s.to_dict() for s in outcome.segments] if outcome.segments else None,
            tool_trace=outcome.tool_trace,
        )
        self._send_json(200 if outcome.success else 502, record.to_dict())

    def _handle_reconciliation(self, project_id: str) -> None:
        if store.get_project(project_id) is None:
            self._send_json(404, {"error": "project not found"})
            return

        body = self._read_json_body()
        if not body or body.get("confirm") is not True:
            self._send_json(
                400, {"error": "reconciliation requires {\"confirm\": true} in the request body"}
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

        outcome = cross_format_analysis.run_cross_format_analysis(selected)

        pdf_docs = [d for d in selected if d.extension == ".pdf"]
        excel_docs = [d for d in selected if d.extension in (".xlsx", ".xls")]

        record = cross_format_analyses.create_cross_format_analysis(
            project_id=project_id,
            pdf_document_ids=[d.id for d in pdf_docs],
            pdf_document_filenames=[d.original_filename for d in pdf_docs],
            pdf_document_checksums=[d.sha256 for d in pdf_docs],
            excel_document_ids=[d.id for d in excel_docs],
            excel_document_filenames=[d.original_filename for d in excel_docs],
            excel_document_checksums=[d.sha256 for d in excel_docs],
            status="success" if outcome.success else "error",
            transmitted=outcome.transmitted,
            analysis_seconds=outcome.analysis_seconds,
            model=outcome.model,
            mandate_version=cross_format_analysis.MANDATE_VERSION,
            stop_reason=outcome.stop_reason,
            input_tokens=outcome.usage["input_tokens"] if outcome.usage else None,
            output_tokens=outcome.usage["output_tokens"] if outcome.usage else None,
            code_execution_requests=outcome.usage.get("code_execution_requests") if outcome.usage else None,
            error_type=outcome.error_type,
            error_message=outcome.error_message,
            segments=[s.to_dict() for s in outcome.segments] if outcome.segments else None,
            tool_trace=outcome.tool_trace,
            excel_cleanup=[c.to_dict() for c in outcome.excel_cleanup] if outcome.excel_cleanup else None,
            excel_verification=[v.to_dict() for v in outcome.excel_verification] if outcome.excel_verification else None,
        )
        self._send_json(200 if outcome.success else 502, record.to_dict())

    # -- Validation Lab (Milestone 8) --------------------------------------

    def _get_owned_validation_case(self, project_id: str, validation_case_id: str):
        """Project-isolation + existence check shared by every validation
        endpoint. Sends the 404 response itself and returns None when the
        project or case doesn't exist (or the case belongs to a different
        project) - callers should `if case is None: return`."""
        if store.get_project(project_id) is None:
            self._send_json(404, {"error": "project not found"})
            return None
        case = validation_cases.get_validation_case(project_id, validation_case_id)
        if case is None:
            self._send_json(404, {"error": "validation case not found"})
            return None
        return case

    def _answer_key_response_dict(self, validation_case_id: str) -> dict | None:
        """Implements the blindness-preserving reveal rule: an unlocked
        draft is always visible (the user is still writing it), but once
        locked, content is withheld from this general endpoint until at
        least one validation run has actually been executed against that
        *exact* locked version - never merely because the case exists or a
        run against some other version happened."""
        version = answer_keys.get_current_version(validation_case_id)
        if version is None:
            return None
        revealed = True
        if version.is_locked:
            runs = validation_runs.list_runs_for_case(validation_case_id)
            revealed = any(r.answer_key_version_id == version.id for r in runs)
        out = version.to_dict(include_content=revealed)
        out["content_hidden"] = not revealed
        return out

    def _handle_create_validation_case(self, project_id: str) -> None:
        if store.get_project(project_id) is None:
            self._send_json(404, {"error": "project not found"})
            return

        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return

        name = str(data.get("name", "")).strip()
        description = str(data.get("description", "")).strip()
        pdf_ids = data.get("pdf_document_ids")
        excel_ids = data.get("excel_document_ids")

        if not name:
            self._send_json(400, {"error": "name is required"})
            return
        if not isinstance(pdf_ids, list) or not all(isinstance(d, str) for d in pdf_ids):
            self._send_json(400, {"error": "pdf_document_ids must be a list of document id strings"})
            return
        if not isinstance(excel_ids, list) or not all(isinstance(d, str) for d in excel_ids):
            self._send_json(400, {"error": "excel_document_ids must be a list of document id strings"})
            return
        combined = pdf_ids + excel_ids
        if len(combined) != len(set(combined)):
            self._send_json(400, {"error": "duplicate document selected"})
            return
        if len(pdf_ids) < 1 or len(excel_ids) < 1:
            self._send_json(400, {"error": "select at least one PDF and one Excel workbook"})
            return

        for document_id in pdf_ids:
            document = documents.get_document(project_id, document_id)
            if document is None:
                self._send_json(404, {"error": f"document not found: {document_id}"})
                return
            if document.extension != ".pdf":
                self._send_json(400, {"error": f"document is not a PDF: {document_id}"})
                return
        for document_id in excel_ids:
            document = documents.get_document(project_id, document_id)
            if document is None:
                self._send_json(404, {"error": f"document not found: {document_id}"})
                return
            if document.extension not in (".xlsx", ".xls"):
                self._send_json(400, {"error": f"document is not an Excel workbook: {document_id}"})
                return

        case = validation_cases.create_validation_case(
            project_id=project_id,
            name=name,
            description=description,
            pdf_document_ids=pdf_ids,
            excel_document_ids=excel_ids,
        )
        answer_keys.create_initial_version(case.id)
        self._send_json(201, case.to_dict())

    def _handle_get_validation_case(self, project_id: str, validation_case_id: str) -> None:
        case = self._get_owned_validation_case(project_id, validation_case_id)
        if case is None:
            return
        answer_key = self._answer_key_response_dict(validation_case_id)
        runs = validation_runs.list_runs_for_case(validation_case_id)
        self._send_json(
            200, {"case": case.to_dict(), "answer_key": answer_key, "runs": [r.to_dict() for r in runs]}
        )

    def _handle_update_validation_case_documents(self, project_id: str, validation_case_id: str) -> None:
        case = self._get_owned_validation_case(project_id, validation_case_id)
        if case is None:
            return
        if validation_runs.list_runs_for_case(validation_case_id):
            self._send_json(409, {"error": "documents cannot be changed once a run exists for this case"})
            return

        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        pdf_ids = data.get("pdf_document_ids")
        excel_ids = data.get("excel_document_ids")
        if not isinstance(pdf_ids, list) or not all(isinstance(d, str) for d in pdf_ids):
            self._send_json(400, {"error": "pdf_document_ids must be a list of document id strings"})
            return
        if not isinstance(excel_ids, list) or not all(isinstance(d, str) for d in excel_ids):
            self._send_json(400, {"error": "excel_document_ids must be a list of document id strings"})
            return
        combined = pdf_ids + excel_ids
        if len(combined) != len(set(combined)):
            self._send_json(400, {"error": "duplicate document selected"})
            return
        if len(pdf_ids) < 1 or len(excel_ids) < 1:
            self._send_json(400, {"error": "select at least one PDF and one Excel workbook"})
            return

        for document_id in pdf_ids:
            document = documents.get_document(project_id, document_id)
            if document is None or document.extension != ".pdf":
                self._send_json(400, {"error": f"invalid PDF selection: {document_id}"})
                return
        for document_id in excel_ids:
            document = documents.get_document(project_id, document_id)
            if document is None or document.extension not in (".xlsx", ".xls"):
                self._send_json(400, {"error": f"invalid Excel selection: {document_id}"})
                return

        updated = validation_cases.update_selected_documents(
            project_id, validation_case_id, pdf_document_ids=pdf_ids, excel_document_ids=excel_ids
        )
        assert updated is not None
        self._send_json(200, updated.to_dict())

    def _handle_get_answer_key(self, project_id: str, validation_case_id: str) -> None:
        case = self._get_owned_validation_case(project_id, validation_case_id)
        if case is None:
            return
        out = self._answer_key_response_dict(validation_case_id)
        if out is None:
            self._send_json(404, {"error": "answer key not found"})
            return
        self._send_json(200, out)

    def _handle_update_answer_key(self, project_id: str, validation_case_id: str) -> None:
        case = self._get_owned_validation_case(project_id, validation_case_id)
        if case is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        content = data.get("content")
        if (
            not isinstance(content, dict)
            or not isinstance(content.get("issues"), list)
            or not isinstance(content.get("must_not_claim"), list)
        ):
            self._send_json(400, {"error": "content must include 'issues' and 'must_not_claim' lists"})
            return

        version = answer_keys.get_current_version(validation_case_id)
        if version is None:
            self._send_json(404, {"error": "answer key not found"})
            return
        try:
            updated = answer_keys.update_draft_content(validation_case_id, version.id, content)
        except answer_keys.AnswerKeyLockedError as exc:
            self._send_json(409, {"error": str(exc)})
            return
        self._send_json(200, updated.to_dict(include_content=True))

    def _handle_lock_answer_key(self, project_id: str, validation_case_id: str) -> None:
        case = self._get_owned_validation_case(project_id, validation_case_id)
        if case is None:
            return
        body = self._read_json_body()
        if not body or body.get("confirm") is not True:
            self._send_json(400, {"error": "locking requires {\"confirm\": true} in the request body"})
            return

        version = answer_keys.get_current_version(validation_case_id)
        if version is None:
            self._send_json(404, {"error": "answer key not found"})
            return
        if version.is_locked:
            self._send_json(409, {"error": "this answer-key version is already locked"})
            return
        if not version.content.get("issues") and not version.content.get("must_not_claim"):
            self._send_json(400, {"error": "add at least one expected issue or must-not-claim item before locking"})
            return

        try:
            locked = answer_keys.lock_version(validation_case_id, version.id)
        except answer_keys.AnswerKeyLockedError as exc:
            self._send_json(409, {"error": str(exc)})
            return
        self._send_json(200, locked.to_dict(include_content=True))

    def _handle_revise_answer_key(self, project_id: str, validation_case_id: str) -> None:
        case = self._get_owned_validation_case(project_id, validation_case_id)
        if case is None:
            return
        body = self._read_json_body()
        if not body or body.get("confirm") is not True:
            self._send_json(400, {"error": "revising requires {\"confirm\": true} in the request body"})
            return
        try:
            revision = answer_keys.create_revision(validation_case_id)
        except (ValueError, answer_keys.AnswerKeyLockedError) as exc:
            self._send_json(409, {"error": str(exc)})
            return
        self._send_json(201, revision.to_dict(include_content=True))

    def _handle_start_validation_run(self, project_id: str, validation_case_id: str) -> None:
        case = self._get_owned_validation_case(project_id, validation_case_id)
        if case is None:
            return
        body = self._read_json_body()
        if not body or body.get("confirm") is not True:
            self._send_json(400, {"error": "starting a run requires {\"confirm\": true} in the request body"})
            return

        mode = body.get("mode", "new")
        if mode not in ("new", "existing"):
            self._send_json(400, {"error": "mode must be 'new' or 'existing'"})
            return

        if mode == "existing":
            analysis_id = body.get("cross_format_analysis_id")
            if not isinstance(analysis_id, str) or not analysis_id:
                self._send_json(400, {"error": "cross_format_analysis_id is required for mode 'existing'"})
                return
            analysis = cross_format_analyses.get_cross_format_analysis(project_id, analysis_id)
            if analysis is None:
                self._send_json(404, {"error": "cross-format analysis not found in this project"})
                return
            try:
                run = validation_runs.attach_existing_analysis(validation_case_id, analysis)
            except validation_runs.ValidationRunError as exc:
                self._send_json(400, {"error": str(exc)})
                return
            evaluations.create_evaluation(run.id)
            self._send_json(201, run.to_dict())
            return

        selected = []
        for document_id in case.pdf_document_ids + case.excel_document_ids:
            document = documents.get_document(project_id, document_id)
            if document is None:
                self._send_json(404, {"error": f"selected document no longer exists: {document_id}"})
                return
            selected.append(document)

        try:
            run, outcome = validation_runs.start_new_run(validation_case_id, selected)
        except validation_runs.ValidationRunError as exc:
            self._send_json(400, {"error": str(exc)})
            return

        evaluations.create_evaluation(run.id)
        self._send_json(200 if outcome.success else 502, run.to_dict())

    def _handle_get_evaluation(self, project_id: str, validation_case_id: str, run_id: str) -> None:
        case = self._get_owned_validation_case(project_id, validation_case_id)
        if case is None:
            return
        run = validation_runs.get_run(validation_case_id, run_id)
        if run is None:
            self._send_json(404, {"error": "validation run not found"})
            return
        evaluation = evaluations.get_evaluation(run.id)
        if evaluation is None:
            self._send_json(404, {"error": "evaluation not found"})
            return
        self._send_json(200, evaluation.to_dict())

    def _handle_update_evaluation(self, project_id: str, validation_case_id: str, run_id: str) -> None:
        case = self._get_owned_validation_case(project_id, validation_case_id)
        if case is None:
            return
        run = validation_runs.get_run(validation_case_id, run_id)
        if run is None:
            self._send_json(404, {"error": "validation run not found"})
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        try:
            updated = evaluations.update_evaluation(run.id, data, is_blind=run.is_blind)
        except evaluations.EvaluationValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        self._send_json(200, updated.to_dict())

    def _handle_get_report(self, project_id: str, validation_case_id: str, run_id: str) -> None:
        case = self._get_owned_validation_case(project_id, validation_case_id)
        if case is None:
            return
        run = validation_runs.get_run(validation_case_id, run_id)
        if run is None:
            self._send_json(404, {"error": "validation run not found"})
            return
        analysis = cross_format_analyses.get_cross_format_analysis(project_id, run.cross_format_analysis_id)
        if analysis is None:
            self._send_json(404, {"error": "linked analysis not found"})
            return
        evaluation = evaluations.get_evaluation(run.id)
        if evaluation is None:
            self._send_json(404, {"error": "evaluation not found"})
            return
        answer_key_version = answer_keys.get_version(validation_case_id, run.answer_key_version_id)
        if answer_key_version is None:
            self._send_json(404, {"error": "answer key version not found"})
            return

        # The run this report describes is already complete, so revealing
        # the exact locked answer-key version it was checked against here
        # is precisely "reveal the answer key only after analysis has
        # completed" - not a bypass of that rule.
        findings = evaluations.extract_findings(analysis.segments)
        metrics = evaluations.compute_metrics(
            answer_key_content=answer_key_version.content, findings=findings, evaluation=evaluation
        )
        self._send_json(
            200,
            {
                "case": case.to_dict(),
                "run": run.to_dict(),
                "analysis": analysis.to_dict(),
                "answer_key": answer_key_version.to_dict(include_content=True),
                "findings": findings,
                "evaluation": evaluation.to_dict(),
                "metrics": metrics,
            },
        )


def main() -> None:
    store.init_db()
    documents.init_documents_db()
    inspections.init_inspections_db()
    cross_analyses.init_cross_analyses_db()
    xlsx_inspections.init_xlsx_inspections_db()
    cross_format_analyses.init_cross_format_analyses_db()
    validation_cases.init_validation_cases_db()
    answer_keys.init_answer_keys_db()
    validation_runs.init_validation_runs_db()
    evaluations.init_evaluations_db()
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
