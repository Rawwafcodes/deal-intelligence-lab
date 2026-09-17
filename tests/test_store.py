"""Tests for store.py (Task 11.3a: PostgreSQL persistence layer)."""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import store


class StoreTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

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
