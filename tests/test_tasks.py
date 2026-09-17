"""Tests for tasks.py (Task 13.1: Task / Comment)."""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import identity
import store
import tasks
import workstreams


class TaskTests(unittest.TestCase):
    def setUp(self):
        self._schema = f"test_{uuid.uuid4().hex}"
        self._original_schema = store.SCHEMA
        store.ensure_schema(self._schema)
        store.SCHEMA = self._schema
        store.init_db()
        identity.init_identity_db()
        workstreams.init_workstreams_db()
        tasks.init_tasks_db()
        self.project = store.create_project("Acme Merger", "")
        self.other_project = store.create_project("Other Deal", "")

    def tearDown(self):
        store.SCHEMA = self._original_schema
        store.drop_schema(self._schema)

    # -- creation / listing -----------------------------------------------

    def test_create_and_list_task(self):
        task = tasks.create_task(self.project.id, "Reconcile the two sources", "Compare PDF vs Excel",
                                  created_by="u1")
        self.assertEqual(task.status, "open")
        self.assertIsNone(task.assigned_to)
        self.assertIsNone(task.workstream_id)
        listed = tasks.list_tasks(self.project.id)
        self.assertEqual([t.id for t in listed], [task.id])

    def test_blank_title_is_rejected(self):
        with self.assertRaises(tasks.TaskValidationError):
            tasks.create_task(self.project.id, "   ")

    def test_title_too_long_is_rejected(self):
        with self.assertRaises(tasks.TaskValidationError):
            tasks.create_task(self.project.id, "x" * (tasks.MAX_TITLE_LENGTH + 1))

    def test_tasks_are_isolated_per_project(self):
        tasks.create_task(self.project.id, "Acme's task")
        self.assertEqual(tasks.list_tasks(self.other_project.id), [])

    def test_create_with_workstream_and_assignee(self):
        workstream = workstreams.create_workstream(self.project.id, "Financial diligence", "")
        task = tasks.create_task(
            self.project.id, "Reconcile", workstream_id=workstream.id, assigned_to="u2", created_by="u1"
        )
        self.assertEqual(task.workstream_id, workstream.id)
        self.assertEqual(task.assigned_to, "u2")

    # -- status transitions -------------------------------------------------

    def test_update_status_to_in_progress_and_cancelled(self):
        task = tasks.create_task(self.project.id, "Draft the memo")
        updated = tasks.update_status(self.project.id, task.id, "in_progress")
        self.assertEqual(updated.status, "in_progress")
        cancelled = tasks.update_status(self.project.id, task.id, "cancelled")
        self.assertEqual(cancelled.status, "cancelled")

    def test_submitted_is_not_directly_settable(self):
        task = tasks.create_task(self.project.id, "Draft the memo")
        with self.assertRaises(tasks.TaskValidationError):
            tasks.update_status(self.project.id, task.id, "submitted")

    def test_invalid_status_is_rejected(self):
        task = tasks.create_task(self.project.id, "Draft the memo")
        with self.assertRaises(tasks.TaskValidationError):
            tasks.update_status(self.project.id, task.id, "bogus")

    def test_update_status_unknown_task(self):
        with self.assertRaises(ValueError):
            tasks.update_status(self.project.id, "not-a-real-task", "in_progress")

    def test_mark_submitted_flips_status(self):
        task = tasks.create_task(self.project.id, "Draft the memo")
        submitted = tasks.mark_submitted(self.project.id, task.id)
        assert submitted is not None
        self.assertEqual(submitted.status, "submitted")

    def test_mark_submitted_does_not_revive_a_cancelled_task(self):
        task = tasks.create_task(self.project.id, "Draft the memo")
        tasks.update_status(self.project.id, task.id, "cancelled")
        result = tasks.mark_submitted(self.project.id, task.id)
        assert result is not None
        self.assertEqual(result.status, "cancelled")

    def test_mark_submitted_unknown_task_returns_none(self):
        self.assertIsNone(tasks.mark_submitted(self.project.id, "not-a-real-task"))

    # -- assignment -----------------------------------------------------

    def test_assign_and_reassign(self):
        task = tasks.create_task(self.project.id, "Draft the memo")
        assigned = tasks.assign(self.project.id, task.id, "u1")
        self.assertEqual(assigned.assigned_to, "u1")
        reassigned = tasks.assign(self.project.id, task.id, "u2")
        self.assertEqual(reassigned.assigned_to, "u2")
        unassigned = tasks.assign(self.project.id, task.id, None)
        self.assertIsNone(unassigned.assigned_to)

    def test_assign_unknown_task(self):
        with self.assertRaises(ValueError):
            tasks.assign(self.project.id, "not-a-real-task", "u1")

    # -- comments -----------------------------------------------------------

    def test_add_and_list_comments_in_order(self):
        task = tasks.create_task(self.project.id, "Draft the memo")
        tasks.add_comment(task.id, "u1", "Started drafting.")
        tasks.add_comment(task.id, "u2", "Looks good so far.")
        comments = tasks.list_comments(task.id)
        self.assertEqual([c.body for c in comments], ["Started drafting.", "Looks good so far."])
        self.assertEqual(comments[0].author_id, "u1")

    def test_blank_comment_is_rejected(self):
        task = tasks.create_task(self.project.id, "Draft the memo")
        with self.assertRaises(tasks.TaskValidationError):
            tasks.add_comment(task.id, "u1", "   ")

    def test_comments_are_isolated_per_task(self):
        task_a = tasks.create_task(self.project.id, "Task A")
        task_b = tasks.create_task(self.project.id, "Task B")
        tasks.add_comment(task_a.id, "u1", "On task A.")
        self.assertEqual(tasks.list_comments(task_b.id), [])


if __name__ == "__main__":
    unittest.main()
