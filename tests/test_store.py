"""Tests for store.py (SQLite persistence layer)."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._original_db_path = store.DB_PATH
        store.DB_PATH = Path(self._tmpdir.name) / "test.db"
        store.init_db()

    def tearDown(self):
        store.DB_PATH = self._original_db_path
        self._tmpdir.cleanup()

    def test_create_and_get_project(self):
        created = store.create_project("Acme Merger", "Acquisition of Acme Corp")
        fetched = store.get_project(created.id)

        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Acme Merger")
        self.assertEqual(fetched.description, "Acquisition of Acme Corp")
        self.assertEqual(fetched.id, created.id)

    def test_get_missing_project_returns_none(self):
        self.assertIsNone(store.get_project("does-not-exist"))

    def test_list_projects_empty_initially(self):
        self.assertEqual(store.list_projects(), [])

    def test_list_projects_returns_newest_first(self):
        first = store.create_project("First Deal", "")
        second = store.create_project("Second Deal", "")

        projects = store.list_projects()

        self.assertEqual([p.id for p in projects], [second.id, first.id])

    def test_create_project_strips_whitespace(self):
        created = store.create_project("  Padded Name  ", "  Padded description  ")
        self.assertEqual(created.name, "Padded Name")
        self.assertEqual(created.description, "Padded description")

    def test_project_persists_across_connections(self):
        created = store.create_project("Persistent Deal", "should survive a reconnect")
        # Simulate a fresh process by opening a brand new connection.
        reloaded = store.get_project(created.id)
        self.assertIsNotNone(reloaded)
        self.assertEqual(reloaded.name, "Persistent Deal")


if __name__ == "__main__":
    unittest.main()
