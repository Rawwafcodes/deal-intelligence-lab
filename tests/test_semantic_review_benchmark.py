"""Tests for semantic_review_benchmark.py (Task 16.4): the harness that
builds real records/PDFs for the "current strong-model review" benchmark
leg. Never calls the network - `integrity_review.run_integrity_review`
itself is exercised only under the script's own `--confirm` flag, run
manually and documented in tasks/16.4-semantic-review-benchmark.md, per
this codebase's standing "no real Anthropic requests from any automated
test" convention.
"""

import shutil
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import documents
import golden_set
import semantic_review_benchmark as benchmark
import store
import tasks
import work_products


@unittest.skipUnless(shutil.which("cupsfilter"), "cupsfilter not available on this system")
class SemanticReviewBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        documents.init_documents_db()
        work_products.init_work_products_db()
        tasks.init_tasks_db()
        golden_set.init_golden_set_db()

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def setUp(self):
        # A fresh project per test: cupsfilter's output is byte-identical
        # for identical input text, so building the same BenchmarkCase
        # twice on one shared project would trip documents.py's own
        # duplicate-content detection (by sha256) on the second attempt.
        self.project = store.create_project(f"Benchmark Test Project {uuid.uuid4().hex[:8]}", "test fixture")

    def test_text_to_pdf_produces_valid_pdf_bytes(self):
        pdf_bytes = benchmark._text_to_pdf_bytes("Hello from Task 16.4's benchmark harness test.")
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        self.assertGreater(len(pdf_bytes), 100)

    def test_exactly_three_cases_defined(self):
        self.assertEqual(len(benchmark.CASES), 3)
        self.assertEqual(len(benchmark.CASES), len({c.defect_type for c in benchmark.CASES}))

    def test_every_case_has_a_matching_golden_set_case(self):
        # The spec requires every rule/benchmark to be justified by the golden
        # set - confirms each benchmarked defect type actually has a seeded
        # golden case, not just a plausible-sounding label.
        for case in benchmark.CASES:
            golden_cases = golden_set.list_cases(case.defect_type)
            self.assertEqual(len(golden_cases), 1, f"expected exactly one golden case for {case.defect_type}")

    def test_build_case_records_creates_real_pdf_submission_and_source(self):
        for case in benchmark.CASES:
            with self.subTest(case=case.defect_type.value):
                target, source = benchmark.build_case_records(self.project.id, "test@local.dev", case)

                self.assertEqual(target.work_product.project_id, self.project.id)
                self.assertEqual(target.work_product.extension, ".pdf")
                wp_path = work_products.version_file_path(target.work_product, target.version)
                self.assertTrue(wp_path.is_file())
                self.assertTrue(wp_path.read_bytes().startswith(b"%PDF"))

                self.assertEqual(source.document.project_id, self.project.id)
                self.assertEqual(source.document.extension, ".pdf")
                doc_path = documents.version_file_path(source.document, source.version)
                self.assertTrue(doc_path.is_file())
                self.assertTrue(doc_path.read_bytes().startswith(b"%PDF"))

    def test_validate_selection_accepts_the_built_records(self):
        # Confirms the harness's output actually satisfies
        # integrity_review.py's own local pre-flight checks - i.e. this
        # would be accepted as a real review request, not just structurally
        # similar to one.
        import integrity_review

        for case in benchmark.CASES:
            with self.subTest(case=case.defect_type.value):
                target, source = benchmark.build_case_records(self.project.id, "test@local.dev", case)
                error = integrity_review.validate_selection(target, [source], [])
                self.assertIsNone(error)


if __name__ == "__main__":
    unittest.main()
