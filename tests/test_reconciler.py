"""Tests for reconciler.py (Task 16.3): the deterministic reconciler's
first rule, numerical_conflict_same_label_v1.
"""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import golden_set
import reconciler
import store
from reconciler import NumericFact


class ReconcilerRuleTests(unittest.TestCase):
    """Tests of the rule's own arithmetic and preconditions. The
    within-tolerance/different-label/different-unit cases return None
    before any database access; the rest exercise the full persisted path,
    so this class still needs an isolated schema like every other
    store-backed test."""

    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        reconciler.init_reconciler_db()
        cls.project = store.create_project("Project Falcon", "reconciler rule tests")

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def test_flags_a_conflict_beyond_tolerance(self):
        a = NumericFact("Purchase Price", 50_000_000, "USD", "document", "doc-1")
        b = NumericFact("purchase price", 52_000_000, "usd", "document", "doc-2")
        result = reconciler.evaluate_numeric_conflict(self.project.id, a, b)
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.relative_difference, (52_000_000 - 50_000_000) / 52_000_000)

    def test_within_tolerance_is_not_flagged(self):
        a = NumericFact("Revenue", 100.0, "USD", "document", "doc-3")
        b = NumericFact("Revenue", 100.3, "USD", "document", "doc-4")  # 0.3% difference
        self.assertIsNone(reconciler.evaluate_numeric_conflict(self.project.id, a, b))

    def test_different_labels_are_not_compared(self):
        a = NumericFact("Revenue", 100.0, "USD", "document", "doc-5")
        b = NumericFact("EBITDA", 40.0, "USD", "document", "doc-6")
        self.assertIsNone(reconciler.evaluate_numeric_conflict(self.project.id, a, b))

    def test_different_units_are_not_compared(self):
        # Deliberate precondition: a unit mismatch is a different, not-yet-built rule.
        a = NumericFact("EBITDA", 4200, "USD thousands", "document", "doc-7")
        b = NumericFact("EBITDA", 38_000_000, "USD", "document", "doc-8")
        self.assertIsNone(reconciler.evaluate_numeric_conflict(self.project.id, a, b))

    def test_label_and_unit_normalization_ignores_case_and_whitespace(self):
        a = NumericFact("  Purchase   Price ", 50.0, " USD ", "document", "doc-9")
        b = NumericFact("purchase price", 55.0, "usd", "document", "doc-10")
        self.assertIsNotNone(reconciler.evaluate_numeric_conflict(self.project.id, a, b))

    def test_unitless_facts_are_comparable(self):
        a = NumericFact("Growth rate", 34.0, None, "document", "doc-11")
        b = NumericFact("Growth rate", 12.0, None, "document", "doc-12")
        self.assertIsNotNone(reconciler.evaluate_numeric_conflict(self.project.id, a, b))


class ReconcilerPersistenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        reconciler.init_reconciler_db()
        cls.project = store.create_project("Project Falcon", "reconciler tests")

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def test_evaluate_persists_a_finding(self):
        a = NumericFact("Purchase Price", 50_000_000, "USD", "document", "doc-1")
        b = NumericFact("Purchase Price", 52_000_000, "USD", "document", "doc-2")
        finding = reconciler.evaluate_numeric_conflict(self.project.id, a, b)

        self.assertEqual(finding.status, "open")
        self.assertEqual(finding.rule_id, reconciler.NUMERICAL_CONFLICT_SAME_LABEL_V1)
        self.assertEqual(finding.defect_type, golden_set.DefectType.NUMERICAL_CONFLICT)
        self.assertEqual(finding.tier, "challenge")

        fetched = reconciler.get_finding(finding.id)
        self.assertEqual(fetched.id, finding.id)

    def test_evaluate_is_idempotent_for_the_same_source_pair(self):
        a = NumericFact("Total Consideration", 10.0, "USD", "document", "doc-a")
        b = NumericFact("Total Consideration", 20.0, "USD", "document", "doc-b")
        first = reconciler.evaluate_numeric_conflict(self.project.id, a, b)
        second = reconciler.evaluate_numeric_conflict(self.project.id, a, b)
        self.assertEqual(first.id, second.id)

        # Order of arguments shouldn't matter either - facts are canonically sorted.
        third = reconciler.evaluate_numeric_conflict(self.project.id, b, a)
        self.assertEqual(first.id, third.id)

        matches = [f for f in reconciler.list_findings(self.project.id) if f.id == first.id]
        self.assertEqual(len(matches), 1)

    def test_dismiss_requires_a_reason(self):
        a = NumericFact("Headcount", 100.0, None, "document", "doc-x")
        b = NumericFact("Headcount", 120.0, None, "document", "doc-y")
        finding = reconciler.evaluate_numeric_conflict(self.project.id, a, b)
        with self.assertRaises(reconciler.ReconcilerError):
            reconciler.dismiss_finding(finding.id, dismissed_by="reviewer@local.dev", reason="  ")

    def test_dismiss_is_permanent_across_re_evaluation(self):
        a = NumericFact("Backlog", 5.0, "M", "document", "doc-p")
        b = NumericFact("Backlog", 5.2, "M", "document", "doc-q")  # 3.8% diff, above tolerance
        finding = reconciler.evaluate_numeric_conflict(self.project.id, a, b)
        dismissed = reconciler.dismiss_finding(
            finding.id, dismissed_by="reviewer@local.dev", reason="Rounding difference confirmed benign."
        )
        self.assertEqual(dismissed.status, "dismissed")
        self.assertEqual(dismissed.dismissed_by, "reviewer@local.dev")

        re_evaluated = reconciler.evaluate_numeric_conflict(self.project.id, a, b)
        self.assertEqual(re_evaluated.id, finding.id)
        self.assertEqual(re_evaluated.status, "dismissed")  # not silently reopened

    def test_dismiss_unknown_finding_raises(self):
        with self.assertRaises(reconciler.FindingNotFoundError):
            reconciler.dismiss_finding(uuid.uuid4().hex, dismissed_by="x", reason="doesn't exist")

    def test_list_findings_scoped_to_project_and_filters(self):
        a = NumericFact("Deferred Revenue", 1.0, "M", "document", "doc-m")
        b = NumericFact("Deferred Revenue", 2.0, "M", "document", "doc-n")
        finding = reconciler.evaluate_numeric_conflict(self.project.id, a, b)

        other_project = store.create_project("Project Osprey", "a different project")
        self.assertEqual(reconciler.list_findings(other_project.id), [])

        by_rule = reconciler.list_findings(self.project.id, rule_id=reconciler.NUMERICAL_CONFLICT_SAME_LABEL_V1)
        self.assertIn(finding.id, [f.id for f in by_rule])

        by_status = reconciler.list_findings(self.project.id, status="open")
        self.assertIn(finding.id, [f.id for f in by_status])


class ReconcilerGoldenSetRegressionTests(unittest.TestCase):
    """Task 16.3's own regression-fixture requirement: this rule must be
    justified by, and stay in sync with, Task 16.1's golden set. Since
    golden_set cases are free-standing prose (not structured facts - see
    golden_set.py's own docstring on why), this doesn't parse the case
    automatically; it hand-authors NumericFacts matching the golden case's
    own numbers, and separately asserts the golden case's prose still
    contains those same figures, so the two can't silently drift apart."""

    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        golden_set.init_golden_set_db()
        reconciler.init_reconciler_db()
        cls.project = store.create_project("Project Regression", "golden set regression")

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def test_numerical_conflict_golden_case_is_flagged(self):
        cases = golden_set.list_cases(golden_set.DefectType.NUMERICAL_CONFLICT)
        self.assertEqual(len(cases), 1)
        case = cases[0]
        self.assertIn("$50,000,000", case.scenario_text)
        self.assertIn("$52,000,000", case.scenario_text)

        term_sheet_price = NumericFact("Purchase Price", 50_000_000, "USD", "document", "term-sheet")
        workbook_price = NumericFact("Purchase Price", 52_000_000, "USD", "document", "sources-and-uses")
        finding = reconciler.evaluate_numeric_conflict(self.project.id, term_sheet_price, workbook_price)

        self.assertIsNotNone(finding)
        self.assertEqual(finding.defect_type, case.defect_type)

    def test_other_golden_cases_have_no_numeric_facts_to_reconcile_yet(self):
        # Honest disclosure, made executable: every other seeded defect type
        # is prose-only today - this rule only ever fires when a caller has
        # already extracted and labeled NumericFacts, which nothing in this
        # codebase does automatically yet (see this task's Exclusions).
        non_numerical_cases = golden_set.list_cases()
        for case in non_numerical_cases:
            if case.defect_type != golden_set.DefectType.NUMERICAL_CONFLICT:
                self.assertNotIn("NumericFact", case.scenario_text)


if __name__ == "__main__":
    unittest.main()
