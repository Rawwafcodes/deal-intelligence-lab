"""Tests for answer_keys.py: versioning, locking, checksum stability, and
immutability of a locked version.
"""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import answer_keys
import store
import validation_cases


class AnswerKeyTests(unittest.TestCase):
    project: store.Project

    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        validation_cases.init_validation_cases_db()
        answer_keys.init_answer_keys_db()
        cls.project = store.create_project("Project Falcon", "answer key tests")

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def _make_case(self) -> str:
        case = validation_cases.create_validation_case(
            project_id=self.project.id,
            name=f"Case {self.id()}",
            description="",
            pdf_document_ids=["pdf1"],
            excel_document_ids=["xlsx1"],
        )
        answer_keys.create_initial_version(case.id)
        return case.id

    def test_initial_version_is_an_unlocked_draft(self):
        case_id = self._make_case()
        version = answer_keys.get_current_version(case_id)
        self.assertIsNotNone(version)
        self.assertFalse(version.is_locked)
        self.assertIsNone(version.checksum)
        self.assertEqual(version.version_number, 1)

    def test_answer_key_issue_creation_and_draft_update(self):
        case_id = self._make_case()
        version = answer_keys.get_current_version(case_id)
        content = answer_keys.empty_content()
        content["issues"].append(answer_keys.new_issue(title="Revenue conflict", expected_severity="critical"))
        content["must_not_claim"].append(answer_keys.new_must_not_claim(statement="PDF entity is the target"))
        updated = answer_keys.update_draft_content(case_id, version.id, content)
        self.assertEqual(len(updated.content["issues"]), 1)
        self.assertEqual(len(updated.content["must_not_claim"]), 1)
        self.assertEqual(updated.content["issues"][0]["title"], "Revenue conflict")

    def test_locking_stamps_timestamp_and_checksum(self):
        case_id = self._make_case()
        version = answer_keys.get_current_version(case_id)
        content = answer_keys.empty_content()
        content["issues"].append(answer_keys.new_issue(title="X"))
        answer_keys.update_draft_content(case_id, version.id, content)

        locked = answer_keys.lock_version(case_id, version.id)
        self.assertTrue(locked.is_locked)
        self.assertIsNotNone(locked.locked_at)
        self.assertIsNotNone(locked.checksum)
        self.assertEqual(len(locked.checksum), 64)  # sha256 hex digest length

    def test_checksum_is_stable_and_reproducible_from_content_alone(self):
        content_a = answer_keys.empty_content()
        content_a["issues"].append({"id": "fixed-id", "title": "X", "b_field": 2, "a_field": 1})
        content_b = answer_keys.empty_content()
        # Same logical content, different key insertion order and dict order.
        content_b["issues"].append({"id": "fixed-id", "a_field": 1, "title": "X", "b_field": 2})
        self.assertEqual(answer_keys.compute_checksum(content_a), answer_keys.compute_checksum(content_b))

    def test_checksum_changes_when_content_changes(self):
        content_a = answer_keys.empty_content()
        content_a["issues"].append(answer_keys.new_issue(title="A"))
        content_b = answer_keys.empty_content()
        content_b["issues"].append(answer_keys.new_issue(title="B"))
        self.assertNotEqual(answer_keys.compute_checksum(content_a), answer_keys.compute_checksum(content_b))

    def test_locked_version_cannot_be_silently_modified(self):
        case_id = self._make_case()
        version = answer_keys.get_current_version(case_id)
        content = answer_keys.empty_content()
        content["issues"].append(answer_keys.new_issue(title="Original"))
        answer_keys.update_draft_content(case_id, version.id, content)
        locked = answer_keys.lock_version(case_id, version.id)

        tampered = answer_keys.empty_content()
        tampered["issues"].append(answer_keys.new_issue(title="Tampered"))
        with self.assertRaises(answer_keys.AnswerKeyLockedError):
            answer_keys.update_draft_content(case_id, locked.id, tampered)

        # Confirm nothing actually changed on disk.
        reread = answer_keys.get_version(case_id, locked.id)
        self.assertEqual(reread.content["issues"][0]["title"], "Original")
        self.assertEqual(reread.checksum, locked.checksum)

    def test_locking_an_already_locked_version_is_rejected(self):
        case_id = self._make_case()
        version = answer_keys.get_current_version(case_id)
        content = answer_keys.empty_content()
        content["issues"].append(answer_keys.new_issue(title="X"))
        answer_keys.update_draft_content(case_id, version.id, content)
        answer_keys.lock_version(case_id, version.id)
        with self.assertRaises(answer_keys.AnswerKeyLockedError):
            answer_keys.lock_version(case_id, version.id)

    def test_revision_creates_new_version_without_touching_the_original(self):
        case_id = self._make_case()
        version = answer_keys.get_current_version(case_id)
        content = answer_keys.empty_content()
        content["issues"].append(answer_keys.new_issue(title="Original"))
        answer_keys.update_draft_content(case_id, version.id, content)
        locked_v1 = answer_keys.lock_version(case_id, version.id)

        revision = answer_keys.create_revision(case_id)
        self.assertEqual(revision.version_number, 2)
        self.assertFalse(revision.is_locked)
        self.assertEqual(revision.content, locked_v1.content)  # copied forward as a starting point

        # Editing the revision must never affect the original locked row.
        edited = answer_keys.empty_content()
        edited["issues"].append(answer_keys.new_issue(title="Corrected"))
        answer_keys.update_draft_content(case_id, revision.id, edited)

        original_reread = answer_keys.get_version(case_id, version.id)
        self.assertEqual(original_reread.content["issues"][0]["title"], "Original")
        self.assertEqual(original_reread.checksum, locked_v1.checksum)
        self.assertEqual(original_reread.locked_at, locked_v1.locked_at)

        versions = answer_keys.list_versions(case_id)
        self.assertEqual([v.version_number for v in versions], [1, 2])

    def test_revising_a_draft_is_rejected(self):
        case_id = self._make_case()
        # Version 1 is a draft (never locked) - revising it makes no sense.
        with self.assertRaises(answer_keys.AnswerKeyLockedError):
            answer_keys.create_revision(case_id)

    def test_get_current_version_returns_the_latest(self):
        case_id = self._make_case()
        version = answer_keys.get_current_version(case_id)
        content = answer_keys.empty_content()
        content["issues"].append(answer_keys.new_issue(title="X"))
        answer_keys.update_draft_content(case_id, version.id, content)
        answer_keys.lock_version(case_id, version.id)
        revision = answer_keys.create_revision(case_id)

        current = answer_keys.get_current_version(case_id)
        self.assertEqual(current.id, revision.id)
        self.assertEqual(current.version_number, 2)


if __name__ == "__main__":
    unittest.main()
