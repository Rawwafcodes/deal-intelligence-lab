"""Deal Intelligence Lab - local web server.

Run inside the project's virtual environment (see README.md):

    source venv/bin/activate
    python3 server.py

Then open http://localhost:8765 in a browser.
"""

from __future__ import annotations

import http.cookies
import json
import mimetypes
import os
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
import deal_briefs
import documents
import evaluations
import identity
import inspections
import mandates
import multipart
import pdf_inspection
import store
import tasks
import validation_cases
import validation_runs
import work_products
import workspace_exports
import workspaces
import workstreams
import xlsx_inspection
import xlsx_inspections

STATIC_DIR = Path(__file__).parent / "static"
PORT = 8765

MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
MAX_BODY_BYTES = 1_000_000

SESSION_COOKIE_NAME = "dl_session"

# Origins this local dev tool itself is served from - the static pages
# directly (127.0.0.1/localhost:8765) and the frontend/ scaffold's Vite dev
# server, which proxies /api requests server-to-server (see
# frontend/vite.config.ts) so the browser's own Origin header still reads
# as the Vite origin, not this server's. A mutating request carrying any
# other Origin is rejected (docs/06-security-and-collaboration.md: "Protect
# local mutation endpoints from cross-origin requests and CSRF; local
# binding alone is not a full defense").
_ALLOWED_ORIGINS = {
    f"http://127.0.0.1:{PORT}",
    f"http://localhost:{PORT}",
    "http://127.0.0.1:5173",
    "http://localhost:5173",
}

# Task 11.3b: dev-only identity switching (docs/06: "explicit, disabled
# outside development, loopback-only, and absent from production routes").
# This app has no production deployment (see AGENTS.md/CLAUDE.md - none is
# authorized), so there is no separate prod mode to gate against yet;
# defaulting to enabled keeps the app usable without extra setup, while
# still enforcing the loopback check unconditionally and honoring an
# explicit opt-out via this env var for whoever eventually adds one.
_DEV_AUTH_DISABLED_VALUES = {"0", "false", "no", ""}

_DOCUMENTS_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/documents$")
_DOCUMENT_DOWNLOAD_RE = re.compile(r"^/api/projects/([^/]+)/documents/([^/]+)/download$")
_DOCUMENT_INSPECT_RE = re.compile(r"^/api/projects/([^/]+)/documents/([^/]+)/inspect$")
_DOCUMENT_VERSIONS_RE = re.compile(r"^/api/projects/([^/]+)/documents/([^/]+)/versions$")
_DOCUMENT_VERSION_DOWNLOAD_RE = re.compile(
    r"^/api/projects/([^/]+)/documents/([^/]+)/versions/([^/]+)/download$"
)
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

_WORKSPACE_OPEN_RE = re.compile(r"^/api/projects/([^/]+)/cross-format-analyses/([^/]+)/workspace$")
_WORKSPACE_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/workspaces/([^/]+)$")
_WORKSPACE_FINDINGS_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/workspaces/([^/]+)/findings$")
_WORKSPACE_FINDING_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/workspaces/([^/]+)/findings/([^/]+)$")
_WORKSPACE_FINDING_DUPLICATE_RE = re.compile(
    r"^/api/projects/([^/]+)/workspaces/([^/]+)/findings/([^/]+)/duplicate$"
)
_WORKSPACE_REQUESTS_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/workspaces/([^/]+)/requests$")
_WORKSPACE_REQUEST_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/workspaces/([^/]+)/requests/([^/]+)$")
_WORKSPACE_MEMO_RE = re.compile(r"^/api/projects/([^/]+)/workspaces/([^/]+)/memo$")
_WORKSPACE_MEMO_APPROVE_RE = re.compile(r"^/api/projects/([^/]+)/workspaces/([^/]+)/memo/approve$")
_WORKSPACE_AUDIT_LOG_RE = re.compile(r"^/api/projects/([^/]+)/workspaces/([^/]+)/audit-log$")
_WORKSPACE_EXPORT_RE = re.compile(r"^/api/projects/([^/]+)/workspaces/([^/]+)/export/([a-z.]+)$")

_BRIEF_RE = re.compile(r"^/api/projects/([^/]+)/brief$")
_BRIEF_VERSIONS_RE = re.compile(r"^/api/projects/([^/]+)/brief/versions$")
_BRIEF_VERSION_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/brief/versions/([^/]+)$")

_WORKSTREAMS_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/workstreams$")
_WORKSTREAM_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/workstreams/([^/]+)$")
_WORKSTREAM_ASSIGNMENTS_RE = re.compile(r"^/api/projects/([^/]+)/workstreams/([^/]+)/assignments$")
_WORKSTREAM_ASSIGNMENT_ITEM_RE = re.compile(
    r"^/api/projects/([^/]+)/workstreams/([^/]+)/assignments/([^/]+)$"
)

_TASKS_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/tasks$")
_TASK_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/tasks/([^/]+)$")
_TASK_STATUS_RE = re.compile(r"^/api/projects/([^/]+)/tasks/([^/]+)/status$")
_TASK_ASSIGN_RE = re.compile(r"^/api/projects/([^/]+)/tasks/([^/]+)/assign$")
_TASK_COMMENTS_RE = re.compile(r"^/api/projects/([^/]+)/tasks/([^/]+)/comments$")
_TASK_WORK_PRODUCTS_RE = re.compile(r"^/api/projects/([^/]+)/tasks/([^/]+)/work-products$")
_WORK_PRODUCT_VERSIONS_RE = re.compile(r"^/api/projects/([^/]+)/work-products/([^/]+)/versions$")
_WORK_PRODUCT_VERSION_DOWNLOAD_RE = re.compile(
    r"^/api/projects/([^/]+)/work-products/([^/]+)/versions/([^/]+)/download$"
)

_MANDATE_TEMPLATES_RE = re.compile(r"^/api/mandate-templates$")
_MANDATES_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/mandates$")
_MANDATE_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/mandates/([^/]+)$")
_MANDATE_PLAN_RE = re.compile(r"^/api/projects/([^/]+)/mandates/([^/]+)/plan$")
_MANDATE_PLAN_PROPOSE_AI_RE = re.compile(r"^/api/projects/([^/]+)/mandates/([^/]+)/plan/propose-ai$")
_MANDATE_PLAN_APPROVE_RE = re.compile(r"^/api/projects/([^/]+)/mandates/([^/]+)/plan/approve$")
_MANDATE_PLAN_REJECT_RE = re.compile(r"^/api/projects/([^/]+)/mandates/([^/]+)/plan/reject$")
_MANDATE_RUNS_COLLECTION_RE = re.compile(r"^/api/projects/([^/]+)/mandates/([^/]+)/runs$")
_MANDATE_RUN_ITEM_RE = re.compile(r"^/api/projects/([^/]+)/mandates/([^/]+)/runs/([^/]+)$")
_MANDATE_RUN_RESUME_RE = re.compile(r"^/api/projects/([^/]+)/mandates/([^/]+)/runs/([^/]+)/resume$")
_MANDATE_RUN_CANCEL_RE = re.compile(r"^/api/projects/([^/]+)/mandates/([^/]+)/runs/([^/]+)/cancel$")


class Handler(BaseHTTPRequestHandler):
    server_version = "DealLab/0.1"

    # Set by _resolve_identity() at the top of every do_GET/do_POST/
    # do_DELETE, before any route runs.
    current_user_id: str
    _new_session_token: str | None

    def log_message(self, format: str, *args) -> None:  # quieter default logging
        pass

    # -- identity and authorization -----------------------------------

    def _client_is_loopback(self) -> bool:
        return self.client_address[0] in ("127.0.0.1", "::1")

    def _dev_auth_enabled(self) -> bool:
        raw = os.environ.get("DEAL_LAB_DEV_AUTH", "1").strip().lower()
        return raw not in _DEV_AUTH_DISABLED_VALUES and self._client_is_loopback()

    def _get_session_cookie_token(self) -> str | None:
        header = self.headers.get("Cookie")
        if not header:
            return None
        jar: http.cookies.SimpleCookie = http.cookies.SimpleCookie()
        try:
            jar.load(header)
        except Exception:
            return None
        morsel = jar.get(SESSION_COOKIE_NAME)
        return morsel.value if morsel else None

    def _resolve_identity(self) -> None:
        """Resolves the caller's identity for this request. A valid
        session cookie wins; otherwise this transparently mints a session
        for the bootstrap default identity (see identity.py's module
        docstring) rather than rejecting the request, so the existing
        static pages - which have no login UI - keep working unchanged.
        Explicitly switching identity (POST /api/dev/session) is what
        actually exercises differentiated access."""
        self._new_session_token = None
        token = self._get_session_cookie_token()
        if token:
            session = identity.get_session(token)
            if session is not None:
                self.current_user_id = session.user_id
                return
        new_session = identity.create_session(identity.get_default_user_id())
        self.current_user_id = new_session.user_id
        self._new_session_token = new_session.token

    def _check_origin_for_mutation(self) -> bool:
        """CSRF mitigation for mutating requests (docs/06: local binding
        alone is not a full defense). Only rejects when an Origin header
        is present and doesn't match one of this app's own dev origins -
        a request with no Origin header at all (plain same-origin script,
        curl, tests) is unaffected."""
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        return origin in _ALLOWED_ORIGINS

    def _authorized_project(self, project_id: str) -> "store.Project | None":
        """Existence + membership check shared by every project-scoped
        route. Sends 404 and returns None either when the project doesn't
        exist or when the caller has no active deal membership on it -
        deliberately the same response either way, so a denied caller
        can't distinguish 'not yours' from 'doesn't exist'
        (docs/06-security-and-collaboration.md)."""
        project = store.get_project(project_id)
        if project is None or not identity.has_deal_access(project_id, self.current_user_id):
            self._send_json(404, {"error": "project not found"})
            return None
        return project

    # -- identity endpoints (Task 11.3b) --------------------------------

    def _session_dict(self, user_id: str) -> dict:
        user = identity.get_user(user_id)
        assert user is not None
        memberships = identity.list_organization_memberships_for_user(user_id)
        organizations = []
        for membership in memberships:
            org = identity.get_organization(membership.organization_id)
            if org is not None:
                organizations.append({"organization": org.to_dict(), "role": membership.role})
        return {"user": user.to_dict(), "organizations": organizations}

    def _handle_get_session(self) -> None:
        self._send_json(200, self._session_dict(self.current_user_id))

    # -- workstreams (Task 11.4) -----------------------------------------

    def _assignments_with_users(self, workstream_id: str) -> list[dict]:
        """Every active assignment, each carrying the assignee's own
        display info inline (a plain composition of workstreams.py +
        identity.py at the API boundary - neither module depends on the
        other) so the frontend never needs a second round trip per row."""
        out = []
        for assignment in workstreams.list_active_assignments(workstream_id):
            user = identity.get_user(assignment.user_id)
            row = assignment.to_dict()
            row["user"] = user.to_dict() if user is not None else None
            out.append(row)
        return out

    def _workstream_with_assignments(self, workstream: workstreams.Workstream) -> dict:
        out = workstream.to_dict()
        out["assignments"] = self._assignments_with_users(workstream.id)
        return out

    # -- tasks and work-product submissions (Task 13.1) --------------------

    def _comments_with_authors(self, task_id: str) -> list[dict]:
        out = []
        for comment in tasks.list_comments(task_id):
            author = identity.get_user(comment.author_id) if comment.author_id else None
            row = comment.to_dict()
            row["author"] = author.to_dict() if author is not None else None
            out.append(row)
        return out

    def _task_with_details(self, task: tasks.Task) -> dict:
        """A task's own record plus its comments (each carrying the
        author's display info inline) and work products (each carrying
        its own version list) - a plain composition of tasks.py +
        work_products.py + identity.py at the API boundary, the same
        "neither module depends on the other" shape _workstream_with_
        assignments already uses, so the frontend never needs a
        round trip per row."""
        out = task.to_dict()
        out["assigned_user"] = None
        if task.assigned_to:
            user = identity.get_user(task.assigned_to)
            out["assigned_user"] = user.to_dict() if user is not None else None
        out["workstream"] = None
        if task.workstream_id:
            workstream = workstreams.get_workstream(task.project_id, task.workstream_id)
            out["workstream"] = workstream.to_dict() if workstream is not None else None
        out["comments"] = self._comments_with_authors(task.id)
        work_product_list = []
        for work_product in work_products.list_work_products(task.id):
            row = work_product.to_dict()
            row["versions"] = [v.to_dict() for v in work_products.list_versions(work_product.id)]
            work_product_list.append(row)
        out["work_products"] = work_product_list
        return out

    # -- mandates (Task 12.1) --------------------------------------------

    def _mandate_with_plans(self, mandate: mandates.Mandate) -> dict:
        out = mandate.to_dict()
        out["plans"] = [p.to_dict() for p in mandates.list_plans(mandate.id)]
        out["runs"] = [self._run_with_attempts(r) for r in mandates.list_runs(mandate.id)]
        return out

    def _run_with_attempts(self, run: mandates.Run) -> dict:
        out = run.to_dict()
        out["attempts"] = [a.to_dict() for a in mandates.list_attempts(run.id)]
        return out

    def _handle_list_dev_identities(self) -> None:
        """Dev-only: lists every seeded identity with its org memberships,
        for the frontend's identity switcher. Absent (404) unless dev auth
        is enabled and the request is from loopback - see docs/06-
        security-and-collaboration.md."""
        if not self._dev_auth_enabled():
            self._send_json(404, {"error": "not found"})
            return
        identities = []
        for user in identity.list_users():
            memberships = identity.list_organization_memberships_for_user(user.id)
            organizations = []
            for membership in memberships:
                org = identity.get_organization(membership.organization_id)
                if org is not None:
                    organizations.append({"organization": org.to_dict(), "role": membership.role})
            identities.append({"user": user.to_dict(), "organizations": organizations})
        self._send_json(200, identities)

    def _handle_dev_session_login(self) -> None:
        if not self._dev_auth_enabled():
            self._send_json(404, {"error": "not found"})
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        user_id = data.get("user_id")
        if not isinstance(user_id, str) or identity.get_user(user_id) is None:
            self._send_json(400, {"error": "user_id must be an existing user id"})
            return
        new_session = identity.create_session(user_id)
        self._new_session_token = new_session.token
        self._send_json(200, self._session_dict(user_id))

    def _handle_dev_session_clear(self) -> None:
        if not self._dev_auth_enabled():
            self._send_json(404, {"error": "not found"})
            return
        token = self._get_session_cookie_token()
        if token:
            identity.delete_session(token)
        self._new_session_token = None
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        body = json.dumps({"cleared": True}).encode("utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header(
            "Set-Cookie", f"{SESSION_COOKIE_NAME}=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0"
        )
        self.end_headers()
        self.wfile.write(body)

    # -- helpers -----------------------------------------------------

    def _apply_session_cookie(self) -> None:
        if self._new_session_token:
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE_NAME}={self._new_session_token}; HttpOnly; SameSite=Strict; Path=/",
            )

    def _send_json(self, status: int, payload) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self._apply_session_cookie()
        self.end_headers()
        self.wfile.write(body)

    def _send_binary(self, status: int, data: bytes, content_type: str, filename: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        if filename:
            self.send_header("Content-Disposition", self._content_disposition(filename, "attachment"))
            self.send_header("X-Content-Type-Options", "nosniff")
        self._apply_session_cookie()
        self.end_headers()
        self.wfile.write(data)

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
        self._apply_session_cookie()
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
        self._send_stored_file(
            documents.stored_file_path(document), document.original_filename, document.extension, inline
        )

    def _send_stored_file(self, path: Path, download_filename: str, extension: str, inline: bool = False) -> None:
        if not path.is_file():
            self._send_json(404, {"error": "stored file is missing"})
            return
        body = path.read_bytes()
        content_type = documents.ALLOWED_EXTENSIONS.get(extension, "application/octet-stream")
        disposition_type = "inline" if inline else "attachment"
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Content-Disposition", self._content_disposition(download_filename, disposition_type))
        self.send_header("X-Content-Type-Options", "nosniff")
        self._apply_session_cookie()
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
        self._resolve_identity()
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/session":
            self._handle_get_session()
            return

        if path == "/api/dev/identities":
            self._handle_list_dev_identities()
            return

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

        if path == "/workspace.html":
            self._send_static_file("workspace.html")
            return

        if path == "/api/projects":
            accessible = identity.list_accessible_project_ids(self.current_user_id)
            projects = [p.to_dict() for p in store.list_projects() if p.id in accessible]
            self._send_json(200, projects)
            return

        download_match = _DOCUMENT_DOWNLOAD_RE.match(path)
        if download_match:
            project_id, document_id = download_match.groups()
            if self._authorized_project(project_id) is None:
                return
            document = documents.get_document(project_id, document_id)
            if document is None:
                self._send_json(404, {"error": "document not found"})
                return
            inline = parse_qs(parsed.query).get("inline", ["0"])[0] == "1"
            self._send_file_download(document, inline=inline)
            return

        version_download_match = _DOCUMENT_VERSION_DOWNLOAD_RE.match(path)
        if version_download_match:
            project_id, document_id, version_id = version_download_match.groups()
            if self._authorized_project(project_id) is None:
                return
            document = documents.get_document(project_id, document_id)
            if document is None:
                self._send_json(404, {"error": "document not found"})
                return
            version = documents.get_version(document_id, version_id)
            if version is None:
                self._send_json(404, {"error": "document version not found"})
                return
            inline = parse_qs(parsed.query).get("inline", ["0"])[0] == "1"
            version_path = documents.version_file_path(document, version)
            self._send_stored_file(version_path, document.original_filename, document.extension, inline=inline)
            return

        versions_match = _DOCUMENT_VERSIONS_RE.match(path)
        if versions_match:
            project_id, document_id = versions_match.groups()
            if self._authorized_project(project_id) is None:
                return
            if documents.get_document(project_id, document_id) is None:
                self._send_json(404, {"error": "document not found"})
                return
            versions = documents.list_versions(document_id)
            self._send_json(200, [v.to_dict() for v in versions])
            return

        inspection_match = _INSPECTION_ITEM_RE.match(path)
        if inspection_match:
            project_id, inspection_id = inspection_match.groups()
            if self._authorized_project(project_id) is None:
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
            if self._authorized_project(project_id) is None:
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
            if self._authorized_project(project_id) is None:
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
            if self._authorized_project(project_id) is None:
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
            if self._authorized_project(project_id) is None:
                return
            records = cross_format_analyses.list_cross_format_analyses(project_id)
            self._send_json(200, [r.to_dict() for r in records])
            return

        workspace_export_match = _WORKSPACE_EXPORT_RE.match(path)
        if workspace_export_match:
            project_id, workspace_id, export_name = workspace_export_match.groups()
            self._handle_workspace_export(project_id, workspace_id, export_name)
            return

        workspace_audit_log_match = _WORKSPACE_AUDIT_LOG_RE.match(path)
        if workspace_audit_log_match:
            project_id, workspace_id = workspace_audit_log_match.groups()
            workspace = self._get_owned_workspace(project_id, workspace_id)
            if workspace is None:
                return
            events = workspaces.list_audit_log(workspace_id)
            self._send_json(200, [e.to_dict() for e in events])
            return

        workspace_memo_match = _WORKSPACE_MEMO_RE.match(path)
        if workspace_memo_match:
            project_id, workspace_id = workspace_memo_match.groups()
            self._handle_get_memo(project_id, workspace_id)
            return

        workspace_requests_match = _WORKSPACE_REQUESTS_COLLECTION_RE.match(path)
        if workspace_requests_match:
            project_id, workspace_id = workspace_requests_match.groups()
            workspace = self._get_owned_workspace(project_id, workspace_id)
            if workspace is None:
                return
            requests = workspaces.list_requests(workspace_id)
            self._send_json(200, [r.to_dict() for r in requests])
            return

        workspace_item_match = _WORKSPACE_ITEM_RE.match(path)
        if workspace_item_match:
            project_id, workspace_id = workspace_item_match.groups()
            self._handle_get_workspace(project_id, workspace_id)
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
            if self._authorized_project(project_id) is None:
                return
            cases = validation_cases.list_validation_cases(project_id)
            self._send_json(200, [c.to_dict() for c in cases])
            return

        collection_match = _DOCUMENTS_COLLECTION_RE.match(path)
        if collection_match:
            (project_id,) = collection_match.groups()
            if self._authorized_project(project_id) is None:
                return
            docs = [d.to_dict() for d in documents.list_documents(project_id)]
            self._send_json(200, docs)
            return

        brief_versions_match = _BRIEF_VERSIONS_RE.match(path)
        if brief_versions_match:
            (project_id,) = brief_versions_match.groups()
            if self._authorized_project(project_id) is None:
                return
            brief_versions = deal_briefs.list_versions(project_id)
            self._send_json(200, [v.to_dict() for v in brief_versions])
            return

        brief_version_item_match = _BRIEF_VERSION_ITEM_RE.match(path)
        if brief_version_item_match:
            project_id, version_id = brief_version_item_match.groups()
            if self._authorized_project(project_id) is None:
                return
            brief_version = deal_briefs.get_version(project_id, version_id)
            if brief_version is None:
                self._send_json(404, {"error": "brief version not found"})
                return
            self._send_json(200, brief_version.to_dict())
            return

        brief_match = _BRIEF_RE.match(path)
        if brief_match:
            (project_id,) = brief_match.groups()
            if self._authorized_project(project_id) is None:
                return
            current = deal_briefs.get_current_version(project_id)
            self._send_json(200, current.to_dict() if current else None)
            return

        workstream_assignments_match = _WORKSTREAM_ASSIGNMENTS_RE.match(path)
        if workstream_assignments_match:
            project_id, workstream_id = workstream_assignments_match.groups()
            if self._authorized_project(project_id) is None:
                return
            if workstreams.get_workstream(project_id, workstream_id) is None:
                self._send_json(404, {"error": "workstream not found"})
                return
            self._send_json(200, self._assignments_with_users(workstream_id))
            return

        workstream_item_match = _WORKSTREAM_ITEM_RE.match(path)
        if workstream_item_match:
            project_id, workstream_id = workstream_item_match.groups()
            if self._authorized_project(project_id) is None:
                return
            workstream = workstreams.get_workstream(project_id, workstream_id)
            if workstream is None:
                self._send_json(404, {"error": "workstream not found"})
                return
            self._send_json(200, self._workstream_with_assignments(workstream))
            return

        workstreams_collection_match = _WORKSTREAMS_COLLECTION_RE.match(path)
        if workstreams_collection_match:
            (project_id,) = workstreams_collection_match.groups()
            if self._authorized_project(project_id) is None:
                return
            out = [self._workstream_with_assignments(w) for w in workstreams.list_workstreams(project_id)]
            self._send_json(200, out)
            return

        work_product_version_download_match = _WORK_PRODUCT_VERSION_DOWNLOAD_RE.match(path)
        if work_product_version_download_match:
            project_id, work_product_id, version_id = work_product_version_download_match.groups()
            if self._authorized_project(project_id) is None:
                return
            work_product = work_products.get_work_product(project_id, work_product_id)
            if work_product is None:
                self._send_json(404, {"error": "work product not found"})
                return
            submission_version = work_products.get_version(work_product_id, version_id)
            if submission_version is None:
                self._send_json(404, {"error": "work product version not found"})
                return
            version_path = work_products.version_file_path(work_product, submission_version)
            self._send_stored_file(version_path, work_product.original_filename, work_product.extension)
            return

        work_product_versions_match = _WORK_PRODUCT_VERSIONS_RE.match(path)
        if work_product_versions_match:
            project_id, work_product_id = work_product_versions_match.groups()
            if self._authorized_project(project_id) is None:
                return
            work_product = work_products.get_work_product(project_id, work_product_id)
            if work_product is None:
                self._send_json(404, {"error": "work product not found"})
                return
            self._send_json(200, [v.to_dict() for v in work_products.list_versions(work_product_id)])
            return

        task_item_match = _TASK_ITEM_RE.match(path)
        if task_item_match:
            project_id, task_id = task_item_match.groups()
            if self._authorized_project(project_id) is None:
                return
            task = tasks.get_task(project_id, task_id)
            if task is None:
                self._send_json(404, {"error": "task not found"})
                return
            self._send_json(200, self._task_with_details(task))
            return

        tasks_collection_match = _TASKS_COLLECTION_RE.match(path)
        if tasks_collection_match:
            (project_id,) = tasks_collection_match.groups()
            if self._authorized_project(project_id) is None:
                return
            out = [self._task_with_details(t) for t in tasks.list_tasks(project_id)]
            self._send_json(200, out)
            return

        if _MANDATE_TEMPLATES_RE.match(path):
            self._send_json(200, [t.to_dict() for t in mandates.list_templates()])
            return

        mandate_run_item_match = _MANDATE_RUN_ITEM_RE.match(path)
        if mandate_run_item_match:
            project_id, mandate_id, run_id = mandate_run_item_match.groups()
            if self._authorized_project(project_id) is None:
                return
            mandate_run = mandates.get_run(mandate_id, run_id)
            if mandate_run is None:
                self._send_json(404, {"error": "run not found"})
                return
            self._send_json(200, self._run_with_attempts(mandate_run))
            return

        mandate_runs_collection_match = _MANDATE_RUNS_COLLECTION_RE.match(path)
        if mandate_runs_collection_match:
            project_id, mandate_id = mandate_runs_collection_match.groups()
            if self._authorized_project(project_id) is None:
                return
            if mandates.get_mandate(project_id, mandate_id) is None:
                self._send_json(404, {"error": "mandate not found"})
                return
            out = [self._run_with_attempts(r) for r in mandates.list_runs(mandate_id)]
            self._send_json(200, out)
            return

        mandate_item_match = _MANDATE_ITEM_RE.match(path)
        if mandate_item_match:
            project_id, mandate_id = mandate_item_match.groups()
            if self._authorized_project(project_id) is None:
                return
            mandate = mandates.get_mandate(project_id, mandate_id)
            if mandate is None:
                self._send_json(404, {"error": "mandate not found"})
                return
            self._send_json(200, self._mandate_with_plans(mandate))
            return

        mandates_collection_match = _MANDATES_COLLECTION_RE.match(path)
        if mandates_collection_match:
            (project_id,) = mandates_collection_match.groups()
            if self._authorized_project(project_id) is None:
                return
            out = [m.to_dict() for m in mandates.list_mandates(project_id)]
            self._send_json(200, out)
            return

        if path.startswith("/api/projects/"):
            project_id = path.removeprefix("/api/projects/")
            project = self._authorized_project(project_id)
            if project is None:
                return
            self._send_json(200, project.to_dict())
            return

        # static assets: css, js
        if path.startswith("/"):
            self._send_static_file(path.lstrip("/"))
            return

        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        self._resolve_identity()
        path = urlparse(self.path).path

        if not self._check_origin_for_mutation():
            self._send_json(403, {"error": "cross-origin request rejected"})
            return

        if path == "/api/dev/session":
            self._handle_dev_session_login()
            return

        if path == "/api/dev/session/clear":
            self._handle_dev_session_clear()
            return

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
            organization_id = data.get("organization_id")

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

            caller_orgs = identity.list_organization_memberships_for_user(self.current_user_id)
            if organization_id is not None:
                if not isinstance(organization_id, str) or organization_id not in {m.organization_id for m in caller_orgs}:
                    self._send_json(400, {"error": "organization_id must be one of the caller's own organizations"})
                    return
            elif caller_orgs:
                organization_id = caller_orgs[0].organization_id
            else:
                self._send_json(400, {"error": "caller has no organization to create this project in"})
                return

            project = store.create_project(name, description)
            identity.assign_project_organization(project.id, organization_id)
            identity.add_deal_membership(project.id, self.current_user_id, "deal_lead")
            self._send_json(201, project.to_dict())
            return

        collection_match = _DOCUMENTS_COLLECTION_RE.match(path)
        if collection_match:
            (project_id,) = collection_match.groups()
            self._handle_document_upload(project_id)
            return

        new_version_match = _DOCUMENT_VERSIONS_RE.match(path)
        if new_version_match:
            project_id, document_id = new_version_match.groups()
            self._handle_add_document_version(project_id, document_id)
            return

        brief_match = _BRIEF_RE.match(path)
        if brief_match:
            (project_id,) = brief_match.groups()
            self._handle_create_brief_version(project_id)
            return

        workstreams_collection_match = _WORKSTREAMS_COLLECTION_RE.match(path)
        if workstreams_collection_match:
            (project_id,) = workstreams_collection_match.groups()
            self._handle_create_workstream(project_id)
            return

        workstream_assignments_match = _WORKSTREAM_ASSIGNMENTS_RE.match(path)
        if workstream_assignments_match:
            project_id, workstream_id = workstream_assignments_match.groups()
            self._handle_create_assignment(project_id, workstream_id)
            return

        task_work_products_match = _TASK_WORK_PRODUCTS_RE.match(path)
        if task_work_products_match:
            project_id, task_id = task_work_products_match.groups()
            self._handle_create_work_product(project_id, task_id)
            return

        work_product_versions_match = _WORK_PRODUCT_VERSIONS_RE.match(path)
        if work_product_versions_match:
            project_id, work_product_id = work_product_versions_match.groups()
            self._handle_add_work_product_version(project_id, work_product_id)
            return

        task_comments_match = _TASK_COMMENTS_RE.match(path)
        if task_comments_match:
            project_id, task_id = task_comments_match.groups()
            self._handle_add_task_comment(project_id, task_id)
            return

        task_assign_match = _TASK_ASSIGN_RE.match(path)
        if task_assign_match:
            project_id, task_id = task_assign_match.groups()
            self._handle_assign_task(project_id, task_id)
            return

        task_status_match = _TASK_STATUS_RE.match(path)
        if task_status_match:
            project_id, task_id = task_status_match.groups()
            self._handle_update_task_status(project_id, task_id)
            return

        tasks_collection_match = _TASKS_COLLECTION_RE.match(path)
        if tasks_collection_match:
            (project_id,) = tasks_collection_match.groups()
            self._handle_create_task(project_id)
            return

        mandate_run_cancel_match = _MANDATE_RUN_CANCEL_RE.match(path)
        if mandate_run_cancel_match:
            project_id, mandate_id, run_id = mandate_run_cancel_match.groups()
            self._handle_cancel_run(project_id, mandate_id, run_id)
            return

        mandate_run_resume_match = _MANDATE_RUN_RESUME_RE.match(path)
        if mandate_run_resume_match:
            project_id, mandate_id, run_id = mandate_run_resume_match.groups()
            self._handle_resume_run(project_id, mandate_id, run_id)
            return

        mandate_runs_collection_match = _MANDATE_RUNS_COLLECTION_RE.match(path)
        if mandate_runs_collection_match:
            project_id, mandate_id = mandate_runs_collection_match.groups()
            self._handle_start_run(project_id, mandate_id)
            return

        mandate_plan_reject_match = _MANDATE_PLAN_REJECT_RE.match(path)
        if mandate_plan_reject_match:
            project_id, mandate_id = mandate_plan_reject_match.groups()
            self._handle_reject_plan(project_id, mandate_id)
            return

        mandate_plan_approve_match = _MANDATE_PLAN_APPROVE_RE.match(path)
        if mandate_plan_approve_match:
            project_id, mandate_id = mandate_plan_approve_match.groups()
            self._handle_approve_plan(project_id, mandate_id)
            return

        mandate_plan_propose_ai_match = _MANDATE_PLAN_PROPOSE_AI_RE.match(path)
        if mandate_plan_propose_ai_match:
            project_id, mandate_id = mandate_plan_propose_ai_match.groups()
            self._handle_propose_plan_llm(project_id, mandate_id)
            return

        mandate_plan_match = _MANDATE_PLAN_RE.match(path)
        if mandate_plan_match:
            project_id, mandate_id = mandate_plan_match.groups()
            self._handle_propose_plan(project_id, mandate_id)
            return

        mandates_collection_match = _MANDATES_COLLECTION_RE.match(path)
        if mandates_collection_match:
            (project_id,) = mandates_collection_match.groups()
            self._handle_create_mandate(project_id)
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

        workspace_open_match = _WORKSPACE_OPEN_RE.match(path)
        if workspace_open_match:
            project_id, analysis_id = workspace_open_match.groups()
            self._handle_open_workspace(project_id, analysis_id)
            return

        workspace_finding_duplicate_match = _WORKSPACE_FINDING_DUPLICATE_RE.match(path)
        if workspace_finding_duplicate_match:
            project_id, workspace_id, finding_id = workspace_finding_duplicate_match.groups()
            self._handle_set_duplicate(project_id, workspace_id, finding_id)
            return

        workspace_finding_item_match = _WORKSPACE_FINDING_ITEM_RE.match(path)
        if workspace_finding_item_match:
            project_id, workspace_id, finding_id = workspace_finding_item_match.groups()
            self._handle_update_finding(project_id, workspace_id, finding_id)
            return

        workspace_findings_collection_match = _WORKSPACE_FINDINGS_COLLECTION_RE.match(path)
        if workspace_findings_collection_match:
            project_id, workspace_id = workspace_findings_collection_match.groups()
            self._handle_create_human_finding(project_id, workspace_id)
            return

        workspace_request_item_match = _WORKSPACE_REQUEST_ITEM_RE.match(path)
        if workspace_request_item_match:
            project_id, workspace_id, request_id = workspace_request_item_match.groups()
            self._handle_update_request(project_id, workspace_id, request_id)
            return

        workspace_requests_collection_match = _WORKSPACE_REQUESTS_COLLECTION_RE.match(path)
        if workspace_requests_collection_match:
            project_id, workspace_id = workspace_requests_collection_match.groups()
            self._handle_create_request(project_id, workspace_id)
            return

        workspace_memo_approve_match = _WORKSPACE_MEMO_APPROVE_RE.match(path)
        if workspace_memo_approve_match:
            project_id, workspace_id = workspace_memo_approve_match.groups()
            self._handle_approve_memo(project_id, workspace_id)
            return

        workspace_memo_match = _WORKSPACE_MEMO_RE.match(path)
        if workspace_memo_match:
            project_id, workspace_id = workspace_memo_match.groups()
            self._handle_update_memo(project_id, workspace_id)
            return

        self._send_json(404, {"error": "not found"})

    def do_DELETE(self) -> None:
        self._resolve_identity()
        path = urlparse(self.path).path

        if not self._check_origin_for_mutation():
            self._send_json(403, {"error": "cross-origin request rejected"})
            return

        item_match = _DOCUMENT_ITEM_RE.match(path)
        if item_match:
            project_id, document_id = item_match.groups()
            if self._authorized_project(project_id) is None:
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

        workspace_finding_item_match = _WORKSPACE_FINDING_ITEM_RE.match(path)
        if workspace_finding_item_match:
            project_id, workspace_id, finding_id = workspace_finding_item_match.groups()
            self._handle_delete_human_finding(project_id, workspace_id, finding_id)
            return

        assignment_item_match = _WORKSTREAM_ASSIGNMENT_ITEM_RE.match(path)
        if assignment_item_match:
            project_id, workstream_id, user_id = assignment_item_match.groups()
            if self._authorized_project(project_id) is None:
                return
            if workstreams.get_workstream(project_id, workstream_id) is None:
                self._send_json(404, {"error": "workstream not found"})
                return
            revoked = workstreams.revoke_assignment(workstream_id, user_id)
            if not revoked:
                self._send_json(404, {"error": "active assignment not found"})
                return
            self._send_json(200, {"revoked": True})
            return

        workstream_item_match = _WORKSTREAM_ITEM_RE.match(path)
        if workstream_item_match:
            project_id, workstream_id = workstream_item_match.groups()
            if self._authorized_project(project_id) is None:
                return
            body = self._read_json_body()
            if not body or body.get("confirm") is not True:
                self._send_json(400, {"error": "deletion requires {\"confirm\": true} in the request body"})
                return
            if not workstreams.delete_workstream(project_id, workstream_id):
                self._send_json(404, {"error": "workstream not found"})
                return
            self._send_json(200, {"deleted": True})
            return

        self._send_json(404, {"error": "not found"})

    def _handle_document_upload(self, project_id: str) -> None:
        if self._authorized_project(project_id) is None:
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

    def _handle_add_document_version(self, project_id: str, document_id: str) -> None:
        """Task 11.4: explicitly replaces one already-known document's
        content with a new immutable version - a deliberately separate,
        single-file action from the bulk upload endpoint (see
        documents.save_uploaded_file's docstring for why the two are not
        merged)."""
        if self._authorized_project(project_id) is None:
            return
        if documents.get_document(project_id, document_id) is None:
            self._send_json(404, {"error": "document not found"})
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

        file_parts = [p for p in parts if p.name == "file" and p.filename]
        if not file_parts:
            self._send_json(400, {"error": "no file was included in the upload"})
            return

        result = documents.add_version(project_id, document_id, file_parts[0].data)
        status_code = {"new_version": 201, "duplicate": 409, "failed": 500}.get(result.status, 500)
        self._send_json(status_code, result.to_dict())

    # -- deal brief (Task 11.4) -------------------------------------------

    def _handle_create_brief_version(self, project_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        fields = {k: v for k, v in data.items() if k in deal_briefs.BRIEF_FIELDS}
        if not fields:
            self._send_json(400, {"error": f"body must include at least one of {deal_briefs.BRIEF_FIELDS}"})
            return
        version = deal_briefs.create_version(project_id, fields, created_by=self.current_user_id)
        self._send_json(201, version.to_dict())

    # -- workstreams (Task 11.4) ------------------------------------------

    def _handle_create_workstream(self, project_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        try:
            workstream = workstreams.create_workstream(
                project_id, str(data.get("name", "")), str(data.get("description", ""))
            )
        except workstreams.WorkstreamValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(201, self._workstream_with_assignments(workstream))

    def _handle_create_assignment(self, project_id: str, workstream_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        if workstreams.get_workstream(project_id, workstream_id) is None:
            self._send_json(404, {"error": "workstream not found"})
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        user_id = data.get("user_id")
        if not isinstance(user_id, str) or identity.get_user(user_id) is None:
            self._send_json(400, {"error": "user_id must be an existing user id"})
            return
        try:
            workstreams.assign(workstream_id, user_id, str(data.get("role_label", "")))
        except workstreams.WorkstreamValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(201, self._assignments_with_users(workstream_id))

    # -- tasks and work-product submissions (Task 13.1) --------------------

    def _handle_create_task(self, project_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        workstream_id = data.get("workstream_id")
        if workstream_id is not None:
            if not isinstance(workstream_id, str) or workstreams.get_workstream(project_id, workstream_id) is None:
                self._send_json(400, {"error": "workstream_id must be an existing workstream in this project"})
                return
        assigned_to = data.get("assigned_to")
        if assigned_to is not None:
            if not isinstance(assigned_to, str) or identity.get_user(assigned_to) is None:
                self._send_json(400, {"error": "assigned_to must be an existing user id"})
                return
        try:
            task = tasks.create_task(
                project_id, str(data.get("title", "")), str(data.get("description", "")),
                workstream_id=workstream_id, assigned_to=assigned_to, created_by=self.current_user_id,
            )
        except tasks.TaskValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(201, self._task_with_details(task))

    def _handle_update_task_status(self, project_id: str, task_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        status = data.get("status")
        if not isinstance(status, str):
            self._send_json(400, {"error": "status is required"})
            return
        try:
            task = tasks.update_status(project_id, task_id, status)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except tasks.TaskValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, self._task_with_details(task))

    def _handle_assign_task(self, project_id: str, task_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        assigned_to = data.get("assigned_to")
        if assigned_to is not None:
            if not isinstance(assigned_to, str) or identity.get_user(assigned_to) is None:
                self._send_json(400, {"error": "assigned_to must be an existing user id, or null to unassign"})
                return
        try:
            task = tasks.assign(project_id, task_id, assigned_to)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        self._send_json(200, self._task_with_details(task))

    def _handle_add_task_comment(self, project_id: str, task_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        if tasks.get_task(project_id, task_id) is None:
            self._send_json(404, {"error": "task not found"})
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        try:
            tasks.add_comment(task_id, self.current_user_id, str(data.get("body", "")))
        except tasks.TaskValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(201, self._comments_with_authors(task_id))

    def _handle_create_work_product(self, project_id: str, task_id: str) -> None:
        """Task 13.1: creates a brand-new WorkProduct and its first
        SubmissionVersion in one call - the upload-time equivalent of
        documents.save_uploaded_file, and subject to the identical rule:
        a second submission against the same task is a second, independent
        WorkProduct, never inferred as a new version of an existing one
        (see work_products.create_work_product's own docstring). Marking
        the task "submitted" is composed here, at the API boundary,
        exactly like _assignments_with_users composes workstreams.py with
        identity.py - work_products.py itself never imports tasks.py."""
        if self._authorized_project(project_id) is None:
            return
        task = tasks.get_task(project_id, task_id)
        if task is None:
            self._send_json(404, {"error": "task not found"})
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

        file_parts = [p for p in parts if p.name == "file" and p.filename]
        if not file_parts:
            self._send_json(400, {"error": "no file was included in the upload"})
            return
        title_parts = [p.data.decode("utf-8", errors="replace") for p in parts if p.name == "title"]
        title = title_parts[0] if title_parts else ""

        result = work_products.create_work_product(
            project_id, task_id, title, file_parts[0].filename or "", file_parts[0].data,
            created_by=self.current_user_id,
        )
        if result.status != "success":
            status_code = {"unsupported_type": 400, "failed": 500}.get(result.status, 500)
            self._send_json(status_code, result.to_dict())
            return
        tasks.mark_submitted(project_id, task_id)
        self._send_json(201, result.to_dict())

    def _handle_add_work_product_version(self, project_id: str, work_product_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        work_product = work_products.get_work_product(project_id, work_product_id)
        if work_product is None:
            self._send_json(404, {"error": "work product not found"})
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

        file_parts = [p for p in parts if p.name == "file" and p.filename]
        if not file_parts:
            self._send_json(400, {"error": "no file was included in the upload"})
            return

        result = work_products.add_version(
            project_id, work_product_id, file_parts[0].data, uploaded_by=self.current_user_id
        )
        status_code = {"new_version": 201, "duplicate": 409, "failed": 500}.get(result.status, 500)
        if result.status == "new_version":
            tasks.mark_submitted(project_id, work_product.task_id)
        self._send_json(status_code, result.to_dict())

    # -- mandates (Task 12.1) --------------------------------------------

    def _handle_create_mandate(self, project_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        try:
            mandate = mandates.create_mandate(
                project_id, str(data.get("objective", "")), created_by=self.current_user_id
            )
        except mandates.MandateValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(201, self._mandate_with_plans(mandate))

    def _handle_propose_plan(self, project_id: str, mandate_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        template_key = data.get("template_key")
        if not isinstance(template_key, str):
            self._send_json(400, {"error": "template_key is required"})
            return
        stage_inputs = data.get("stage_inputs")
        if stage_inputs is not None and not isinstance(stage_inputs, dict):
            self._send_json(400, {"error": "stage_inputs must be an object keyed by stage id"})
            return
        try:
            plan = mandates.propose_plan(project_id, mandate_id, template_key, stage_inputs=stage_inputs)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except (mandates.MandateValidationError, mandates.PlanValidationError) as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(201, plan.to_dict())

    def _handle_propose_plan_llm(self, project_id: str, mandate_id: str) -> None:
        # Task 12.4: a real model proposes template + (for a capability
        # that needs one) a source document selection - see
        # mandates.propose_plan_llm's own docstring for the two independent
        # verification layers this goes through before anything is
        # persisted. Optional `feedback`: a human's requested change to a
        # prior proposal (docs/04: "AI can request adaptation... Record a
        # new plan revision") - always produces a brand new PlanRevision,
        # never mutates one already on record.
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body() or {}
        feedback = data.get("feedback")
        if feedback is not None and not isinstance(feedback, str):
            self._send_json(400, {"error": "feedback must be a string"})
            return
        try:
            result = mandates.propose_plan_llm(project_id, mandate_id, feedback=feedback)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except mandates.MandateValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        if result.status == "error":
            # The planning call itself failed (missing key, rate limit, a
            # malformed reply...) - a provider-side failure, not a plan
            # decision, so this mirrors _handle_reconciliation's own
            # success-vs-provider-error status code split (200 vs 502).
            self._send_json(502, result.to_dict())
            return
        if result.status == "unsupported":
            # A considered "no confident plan" outcome, not an error - 200,
            # same as any other successful call that simply has nothing to
            # approve yet. No PlanRevision was created.
            self._send_json(200, result.to_dict())
            return
        self._send_json(201, result.to_dict())

    def _handle_approve_plan(self, project_id: str, mandate_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        plan_id = data.get("plan_id")
        if not isinstance(plan_id, str):
            self._send_json(400, {"error": "plan_id is required"})
            return
        try:
            plan = mandates.approve_plan(project_id, mandate_id, plan_id, approved_by=self.current_user_id)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except mandates.MandateValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, plan.to_dict())

    def _handle_reject_plan(self, project_id: str, mandate_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        plan_id = data.get("plan_id")
        if not isinstance(plan_id, str):
            self._send_json(400, {"error": "plan_id is required"})
            return
        try:
            plan = mandates.reject_plan(project_id, mandate_id, plan_id)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except mandates.MandateValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, plan.to_dict())

    def _handle_start_run(self, project_id: str, mandate_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        # Task 12.2: an optional per-run budget_limit - the minimal ledger
        # is enforced against whatever is passed here (or unlimited, if
        # omitted). No body at all is valid (budget is optional), so an
        # empty/unparsable body is treated as "no budget_limit", not a 400.
        data = self._read_json_body() or {}
        budget_limit_raw = data.get("budget_limit")
        budget_limit: float | None = None
        if budget_limit_raw is not None:
            if isinstance(budget_limit_raw, bool) or not isinstance(budget_limit_raw, (int, float)):
                self._send_json(400, {"error": "budget_limit must be a number"})
                return
            budget_limit = float(budget_limit_raw)
        try:
            run = mandates.execute_run(project_id, mandate_id, budget_limit=budget_limit)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except mandates.MandateValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        # 202, not 201: the run is persisted and accepted for processing,
        # not completed - Task 12.2 moved execution off this request
        # entirely, onto the durable Worker (see mandates.py).
        self._send_json(202, self._run_with_attempts(run))

    def _handle_resume_run(self, project_id: str, mandate_id: str, run_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        stage_id = data.get("stage_id")
        if not isinstance(stage_id, str):
            self._send_json(400, {"error": "stage_id is required"})
            return
        try:
            run = mandates.resume_run(project_id, mandate_id, run_id, stage_id, str(data.get("decision", "")))
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except mandates.MandateValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, self._run_with_attempts(run))

    def _handle_cancel_run(self, project_id: str, mandate_id: str, run_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        try:
            run = mandates.cancel_run(project_id, mandate_id, run_id)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except mandates.MandateValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, self._run_with_attempts(run))

    def _handle_document_inspect(self, project_id: str, document_id: str) -> None:
        if self._authorized_project(project_id) is None:
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
        if self._authorized_project(project_id) is None:
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
        if self._authorized_project(project_id) is None:
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
        if self._authorized_project(project_id) is None:
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
        if self._authorized_project(project_id) is None:
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
        if self._authorized_project(project_id) is None:
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


    # -- Deal Workspace (Milestone 9) ---------------------------------------

    def _get_owned_workspace(self, project_id: str, workspace_id: str) -> workspaces.Workspace | None:
        """Project-isolation + existence check shared by every workspace
        endpoint, same shape as _get_owned_validation_case."""
        if self._authorized_project(project_id) is None:
            return None
        workspace = workspaces.get_workspace(project_id, workspace_id)
        if workspace is None:
            self._send_json(404, {"error": "workspace not found"})
            return None
        return workspace

    def _get_workspace_analysis(
        self, workspace: workspaces.Workspace
    ) -> cross_format_analyses.CrossFormatAnalysis | None:
        analysis = cross_format_analyses.get_cross_format_analysis(
            workspace.project_id, workspace.cross_format_analysis_id
        )
        if analysis is None:
            self._send_json(404, {"error": "the analysis linked to this workspace no longer exists"})
            return None
        return analysis

    def _handle_open_workspace(self, project_id: str, analysis_id: str) -> None:
        if self._authorized_project(project_id) is None:
            return
        analysis = cross_format_analyses.get_cross_format_analysis(project_id, analysis_id)
        if analysis is None:
            self._send_json(404, {"error": "cross-format analysis not found"})
            return
        if analysis.status != "success":
            self._send_json(
                400, {"error": "a deal workspace can only be opened from a completed (successful) reconciliation"}
            )
            return
        workspace, created = workspaces.get_or_create_workspace(project_id, analysis)
        self._send_json(201 if created else 200, workspace.to_dict())

    def _handle_get_workspace(self, project_id: str, workspace_id: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        analysis = self._get_workspace_analysis(workspace)
        if analysis is None:
            return
        findings = workspaces.list_findings(workspace, analysis)
        request_list = workspaces.list_requests(workspace_id)
        summary = workspaces.compute_summary(workspace, analysis, request_list)
        self._send_json(
            200,
            {
                "workspace": workspace.to_dict(),
                "analysis": analysis.to_dict(),
                "findings": findings,
                "summary": summary,
            },
        )

    def _handle_update_finding(self, project_id: str, workspace_id: str, finding_id: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        analysis = self._get_workspace_analysis(workspace)
        if analysis is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        expected_revision = data.get("revision")
        if expected_revision is not None and not isinstance(expected_revision, int):
            self._send_json(400, {"error": "revision must be an integer"})
            return
        try:
            workspaces.update_finding_workflow(workspace_id, finding_id, data, expected_revision=expected_revision)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except workspaces.FindingRevisionConflictError as exc:
            self._send_json(409, {"error": str(exc), "current": exc.current})
            return
        except workspaces.WorkspaceValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, workspaces.get_finding(workspace, analysis, finding_id))

    def _handle_create_human_finding(self, project_id: str, workspace_id: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        analysis = self._get_workspace_analysis(workspace)
        if analysis is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return

        evidence_document_ids = data.get("evidence_document_ids") or []
        if not isinstance(evidence_document_ids, list):
            self._send_json(400, {"error": "evidence_document_ids must be a list of document id strings"})
            return
        for document_id in evidence_document_ids:
            if not isinstance(document_id, str) or documents.get_document(project_id, document_id) is None:
                self._send_json(400, {"error": f"evidence document not found in this project: {document_id}"})
                return

        try:
            created = workspaces.create_human_finding(workspace_id, data)
        except workspaces.WorkspaceValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(201, workspaces.get_finding(workspace, analysis, created["id"]))

    def _handle_delete_human_finding(self, project_id: str, workspace_id: str, finding_id: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        body = self._read_json_body()
        if not body or body.get("confirm") is not True:
            self._send_json(400, {"error": "deletion requires {\"confirm\": true} in the request body"})
            return
        try:
            workspaces.delete_human_finding(workspace_id, finding_id)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except workspaces.WorkspaceValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, {"deleted": True})

    def _handle_set_duplicate(self, project_id: str, workspace_id: str, finding_id: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        analysis = self._get_workspace_analysis(workspace)
        if analysis is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        duplicate_of = data.get("duplicate_of")
        if duplicate_of is not None and not isinstance(duplicate_of, str):
            self._send_json(400, {"error": "duplicate_of must be a string finding id or null"})
            return
        marked_by = str(data.get("marked_by", "") or "").strip()
        if duplicate_of and not marked_by:
            self._send_json(400, {"error": "marked_by is required when marking a duplicate"})
            return
        try:
            workspaces.set_duplicate(workspace_id, finding_id, duplicate_of, marked_by)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except workspaces.WorkspaceValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, workspaces.get_finding(workspace, analysis, finding_id))

    def _handle_create_request(self, project_id: str, workspace_id: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        try:
            request = workspaces.create_request(workspace_id, data)
        except workspaces.WorkspaceValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(201, request.to_dict())

    def _handle_update_request(self, project_id: str, workspace_id: str, request_id: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        try:
            request = workspaces.update_request(workspace_id, request_id, data)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except workspaces.WorkspaceValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, request.to_dict())

    def _handle_get_memo(self, project_id: str, workspace_id: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        analysis = self._get_workspace_analysis(workspace)
        if analysis is None:
            return
        memo = workspaces.get_or_create_memo(workspace, analysis)
        self._send_json(200, memo.to_dict())

    def _handle_update_memo(self, project_id: str, workspace_id: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        analysis = self._get_workspace_analysis(workspace)
        if analysis is None:
            return
        workspaces.get_or_create_memo(workspace, analysis)  # ensure one exists before updating it
        data = self._read_json_body()
        if data is None:
            self._send_json(400, {"error": "invalid JSON body"})
            return
        try:
            memo = workspaces.update_memo(workspace_id, data)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except workspaces.WorkspaceValidationError as exc:
            self._send_json(400, {"error": str(exc)})
            return
        self._send_json(200, memo.to_dict())

    def _handle_approve_memo(self, project_id: str, workspace_id: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        body = self._read_json_body()
        if not body or body.get("confirm") is not True:
            self._send_json(400, {"error": "approval requires {\"confirm\": true} in the request body"})
            return
        approver = str(body.get("approver", "")).strip()
        if not approver:
            self._send_json(400, {"error": "an approver name is required to approve the memo"})
            return
        try:
            memo = workspaces.approve_memo(workspace_id, approver)
        except ValueError as exc:
            self._send_json(404, {"error": str(exc)})
            return
        except workspaces.WorkspaceValidationError as exc:
            self._send_json(409, {"error": str(exc)})
            return
        self._send_json(200, memo.to_dict())

    def _handle_workspace_export(self, project_id: str, workspace_id: str, export_name: str) -> None:
        workspace = self._get_owned_workspace(project_id, workspace_id)
        if workspace is None:
            return
        project = store.get_project(project_id)
        assert project is not None
        analysis = self._get_workspace_analysis(workspace)
        if analysis is None:
            return

        if export_name == "findings.xlsx":
            findings = workspaces.list_findings(workspace, analysis)
            data = workspace_exports.build_findings_workbook(project, analysis, workspace, findings)
            self._send_binary(
                200, data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "findings-register.xlsx",
            )
            workspaces.log_export(workspace_id, export_name)
            return

        if export_name == "requests.xlsx":
            request_list = workspaces.list_requests(workspace_id)
            data = workspace_exports.build_requests_workbook(project, analysis, workspace, request_list)
            self._send_binary(
                200, data, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "information-requests.xlsx",
            )
            workspaces.log_export(workspace_id, export_name)
            return

        if export_name == "memo.html":
            memo = workspaces.get_or_create_memo(workspace, analysis)
            html = workspace_exports.build_memo_html(project, analysis, workspace, memo)
            self._send_binary(200, html.encode("utf-8"), "text/html; charset=utf-8")
            workspaces.log_export(workspace_id, export_name)
            return

        if export_name == "package.html":
            findings = workspaces.list_findings(workspace, analysis)
            request_list = workspaces.list_requests(workspace_id)
            memo = workspaces.get_or_create_memo(workspace, analysis)
            html = workspace_exports.build_package_html(project, analysis, workspace, findings, request_list, memo)
            self._send_binary(200, html.encode("utf-8"), "text/html; charset=utf-8")
            workspaces.log_export(workspace_id, export_name)
            return

        self._send_json(404, {"error": f"unknown export: {export_name}"})


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
    workspaces.init_workspaces_db()
    identity.init_identity_db()
    deal_briefs.init_deal_briefs_db()
    workstreams.init_workstreams_db()
    tasks.init_tasks_db()
    work_products.init_work_products_db()
    mandates.init_mandates_db()
    # Task 12.2: the durable local worker - a real background thread,
    # independent of any HTTP request, that executes queued/resumed
    # mandate runs (see mandates.py's own module docstring and Worker
    # class). Poll interval is configurable so a real, observable "kill
    # the server after a run is accepted but before the worker has polled"
    # window can be demonstrated live without touching production defaults.
    mandate_worker = mandates.Worker(
        poll_interval=float(os.environ.get("DEAL_LAB_MANDATE_WORKER_POLL_SECONDS", "0.5"))
    )
    mandate_worker.start()
    httpd = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Deal Intelligence Lab running at http://localhost:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        mandate_worker.stop()
        httpd.server_close()


if __name__ == "__main__":
    main()
