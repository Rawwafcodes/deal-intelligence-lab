"""Tests for validation_cases.py: case creation, listing, and document
selection updates.
"""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import store
import validation_cases


class ValidationCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        validation_cases.init_validation_cases_db()
        cls.project = store.create_project("Project Falcon", "validation case tests")
        cls.other_project = store.create_project("Project Osprey", "a different project")

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def test_create_and_get_case(self):
        case = validation_cases.create_validation_case(
            project_id=self.project.id,
            name="Falcon deal",
            description="a completed deal",
            pdf_document_ids=["pdf-1"],
            excel_document_ids=["xlsx-1"],
        )
        fetched = validation_cases.get_validation_case(self.project.id, case.id)
        self.assertEqual(fetched.id, case.id)
        self.assertEqual(fetched.name, "Falcon deal")

    def test_list_cases_scoped_to_project(self):
        validation_cases.create_validation_case(
            project_id=self.project.id, name="A", description="", pdf_document_ids=["p"], excel_document_ids=["x"]
        )
        validation_cases.create_validation_case(
            project_id=self.other_project.id,
            name="B",
            description="",
            pdf_document_ids=["p"],
            excel_document_ids=["x"],
        )
        cases = validation_cases.list_validation_cases(self.project.id)
        self.assertTrue(all(c.project_id == self.project.id for c in cases))
        self.assertNotIn("B", [c.name for c in cases])

    def test_get_case_from_wrong_project_returns_none(self):
        case = validation_cases.create_validation_case(
            project_id=self.project.id, name="A", description="", pdf_document_ids=["p"], excel_document_ids=["x"]
        )
        self.assertIsNone(validation_cases.get_validation_case(self.other_project.id, case.id))

    def test_update_selected_documents(self):
        case = validation_cases.create_validation_case(
            project_id=self.project.id, name="A", description="", pdf_document_ids=["p1"], excel_document_ids=["x1"]
        )
        updated = validation_cases.update_selected_documents(
            self.project.id, case.id, pdf_document_ids=["p1", "p2"], excel_document_ids=["x1"]
        )
        self.assertEqual(updated.pdf_document_ids, ["p1", "p2"])

    def test_update_selected_documents_wrong_project_returns_none(self):
        case = validation_cases.create_validation_case(
            project_id=self.project.id, name="A", description="", pdf_document_ids=["p1"], excel_document_ids=["x1"]
        )
        result = validation_cases.update_selected_documents(
            self.other_project.id, case.id, pdf_document_ids=["p1"], excel_document_ids=["x1"]
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
