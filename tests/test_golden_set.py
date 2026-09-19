"""Tests for golden_set.py (Task 16.1): the versioned taxonomy corpus of
known integrity-defect cases.
"""

import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import golden_set
import store
from golden_set import DefectType, GoldenCaseNotFoundError


class GoldenSetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._schema = f"test_{uuid.uuid4().hex}"
        cls._original_schema = store.SCHEMA
        store.ensure_schema(cls._schema)
        store.SCHEMA = cls._schema
        store.init_db()
        golden_set.init_golden_set_db()

    @classmethod
    def tearDownClass(cls):
        store.SCHEMA = cls._original_schema
        store.drop_schema(cls._schema)

    def test_seeding_covers_every_defect_type_exactly_once(self):
        cases = golden_set.list_cases()
        seeded_types = [case.defect_type for case in cases if "Seeded default golden case" in case.notes]
        self.assertEqual(sorted(t.value for t in seeded_types), sorted(t.value for t in DefectType))
        self.assertEqual(len(seeded_types), len(set(seeded_types)))

    def test_seeding_is_idempotent(self):
        before = len(golden_set.list_cases(include_superseded=True))
        golden_set.init_golden_set_db()
        after = len(golden_set.list_cases(include_superseded=True))
        self.assertEqual(before, after)

    def test_seeded_cases_are_all_synthetic(self):
        for case in golden_set.list_cases():
            if "Seeded default golden case" in case.notes:
                self.assertEqual(case.provenance, "synthetic")
                self.assertIn("[SYNTHETIC]", case.scenario_text)

    def test_create_case_starts_at_version_one_and_active(self):
        case = golden_set.create_case(
            defect_type=DefectType.NUMERICAL_CONFLICT,
            title="A new hand-authored case",
            scenario_text="Some scenario text.",
            expected_assertion="Some expected assertion.",
        )
        self.assertEqual(case.version_number, 1)
        self.assertEqual(case.status, "active")
        fetched = golden_set.get_case(case.case_key)
        self.assertEqual(fetched.id, case.id)

    def test_create_case_rejects_invalid_provenance(self):
        with self.assertRaises(ValueError):
            golden_set.create_case(
                defect_type=DefectType.STALENESS,
                title="Bad provenance",
                scenario_text="x",
                expected_assertion="y",
                provenance="hearsay",
            )

    def test_supersede_creates_new_version_and_retires_old_one(self):
        original = golden_set.create_case(
            defect_type=DefectType.TEMPORAL_MISMATCH,
            title="Original title",
            scenario_text="Original scenario.",
            expected_assertion="Original assertion.",
        )
        updated = golden_set.supersede_case(
            original.case_key, expected_assertion="A corrected assertion."
        )

        self.assertEqual(updated.version_number, 2)
        self.assertEqual(updated.status, "active")
        self.assertEqual(updated.title, "Original title")  # carried forward, not overridden
        self.assertEqual(updated.expected_assertion, "A corrected assertion.")

        current = golden_set.get_case(original.case_key)
        self.assertEqual(current.id, updated.id)

        history = golden_set.get_case_history(original.case_key)
        self.assertEqual([c.version_number for c in history], [1, 2])
        self.assertEqual(history[0].status, "superseded")
        self.assertEqual(history[1].status, "active")
        # The superseded version's own content is untouched - still readable.
        self.assertEqual(history[0].expected_assertion, "Original assertion.")

    def test_supersede_unknown_case_key_raises(self):
        with self.assertRaises(GoldenCaseNotFoundError):
            golden_set.supersede_case(uuid.uuid4().hex, title="doesn't exist")

    def test_list_cases_excludes_superseded_by_default(self):
        original = golden_set.create_case(
            defect_type=DefectType.ENTITY_CONFLATION,
            title="Will be superseded",
            scenario_text="x",
            expected_assertion="y",
        )
        golden_set.supersede_case(original.case_key, title="Corrected")

        active_ids = {c.id for c in golden_set.list_cases(DefectType.ENTITY_CONFLATION)}
        self.assertNotIn(original.id, active_ids)

        all_ids = {
            c.id for c in golden_set.list_cases(DefectType.ENTITY_CONFLATION, include_superseded=True)
        }
        self.assertIn(original.id, all_ids)

    def test_list_cases_filters_by_defect_type(self):
        for case in golden_set.list_cases(DefectType.LOGICAL_CONTRADICTION):
            self.assertEqual(case.defect_type, DefectType.LOGICAL_CONTRADICTION)

    def test_defect_type_descriptions_cover_every_type(self):
        self.assertEqual(set(golden_set.DEFECT_TYPE_DESCRIPTIONS.keys()), set(DefectType))
        for description in golden_set.DEFECT_TYPE_DESCRIPTIONS.values():
            self.assertTrue(description.strip())


if __name__ == "__main__":
    unittest.main()
