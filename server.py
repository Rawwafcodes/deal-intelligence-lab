"""Deal Intelligence Lab - local web server.

Standard-library only: no pip install required. Run with:

    python3 server.py

Then open http://localhost:8765 in a browser.
"""

from __future__ import annotations

import json
import mimetypes
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import store

STATIC_DIR = Path(__file__).parent / "static"
PORT = 8765

MAX_NAME_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
MAX_BODY_BYTES = 1_000_000


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

    # -- routing -------------------------------------------------------

    def do_GET(self) -> None:
        path = urlparse(self.path).path

        if path == "/":
            self._send_static_file("index.html")
            return

        if path == "/project.html":
            self._send_static_file("project.html")
            return

        if path == "/api/projects":
            projects = [p.to_dict() for p in store.list_projects()]
            self._send_json(200, projects)
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

        self._send_json(404, {"error": "not found"})


def main() -> None:
    store.init_db()
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
