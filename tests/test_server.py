"""Integration tests: start the real HTTP server and hit it over the network."""

import json
import sys
import threading
import unittest
import urllib.error
import urllib.request
import uuid
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import identity
import server
import store


class ServerTests(unittest.TestCase):
    httpd: ThreadingHTTPServer
    port: int
    thread: threading.Thread

    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        identity.init_identity_db()

        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def _url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def test_home_page_serves_html(self):
        with urllib.request.urlopen(self._url("/")) as res:
            self.assertEqual(res.status, 200)
            body = res.read().decode()
            self.assertIn("Deal Intelligence Lab", body)

    def test_create_and_list_project_roundtrip(self):
        payload = json.dumps({"name": "Project Falcon", "description": "Target: Falcon Industries"}).encode()
        req = urllib.request.Request(
            self._url("/api/projects"), data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req) as res:
            self.assertEqual(res.status, 201)
            created = json.loads(res.read())
            self.assertEqual(created["name"], "Project Falcon")

        with urllib.request.urlopen(self._url("/api/projects")) as res:
            projects = json.loads(res.read())
            self.assertTrue(any(p["id"] == created["id"] for p in projects))

        with urllib.request.urlopen(self._url(f"/api/projects/{created['id']}")) as res:
            fetched = json.loads(res.read())
            self.assertEqual(fetched["description"], "Target: Falcon Industries")

    def test_create_project_without_name_is_rejected(self):
        payload = json.dumps({"name": "", "description": "no name"}).encode()
        req = urllib.request.Request(
            self._url("/api/projects"), data=payload, headers={"Content-Type": "application/json"}, method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        self.assertEqual(ctx.exception.code, 400)

    def test_unknown_project_id_returns_404(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self._url("/api/projects/does-not-exist"))
        self.assertEqual(ctx.exception.code, 404)

    def test_static_asset_is_served(self):
        with urllib.request.urlopen(self._url("/style.css")) as res:
            self.assertEqual(res.status, 200)
            self.assertIn("text/css", res.headers.get("Content-Type", ""))

    def test_path_traversal_is_blocked(self):
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(self._url("/../server.py"))
        self.assertIn(ctx.exception.code, (403, 404))


if __name__ == "__main__":
    unittest.main()
