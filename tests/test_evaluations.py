"""Tests for evaluations.py: finding extraction from a stored
cross_format_analyses record, evaluation rating storage/validation, and
metrics computation.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import answer_keys
import evaluations
import store


def _text_segment(text: str, pdf_citations=None) -> dict:
    return {
        "parts": [{"type": "text", "text": text}],
        "pdf_citations": pdf_citations or [],
    }


def _excel_citation_part(sheet="Model", ref="B3", kind="value", document_id="xlsx-1", raw_text=None):
    raw = raw_text or f"('Workbook 1'!'{sheet}'!{ref} [{kind}])"
    return {
        "type": "excel_citation",
        "citation": {
            "workbook_label": "Workbook 1",
            "document_id": document_id,
            "document_filename": "model.xlsx",
            "sheet": sheet,
            "ref": ref,
            "kind": kind,
            "exists": True,
            "raw_text": raw,
        },
    }


SAMPLE_FINDINGS_TEXT = (
    "## Executive Conclusion\n"
    "A brief summary.\n\n"
    "## Sources Reviewed\n"
    "- **Filename:** im.pdf\n"
    "**Type:** pdf\n\n"
    "## Reconciliation Findings\n"
    "- **Title:** Revenue mismatch\n"
    "**Classification:** cross-source conflict\n"
    "**Severity:** critical\n"
    "**Explanation:** the figures differ.\n"
    "**PDF evidence:** the IM says $12m.\n"
    "**Workbook evidence:** the model says $10m.\n"
    "**Commercial or financial relevance:** matters a lot.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended action:** ask the seller.\n\n"
    "- **Title:** Unsupported growth rate\n"
    "**Classification:** unsupported model assumption\n"
    "**Severity:** high\n"
    "**Explanation:** no support found.\n"
    "**PDF evidence:** No PDF evidence located\n"
    "**Workbook evidence:** hardcoded 18%.\n"
    "**Commercial or financial relevance:** inflates forecast.\n"
    "**Uncertainty:** fully supported by citations\n"
    "**Recommended action:** ask for derivation.\n\n"
    "## Unresolved Questions\n"
    "- Which figure is correct?\n\n"
    "## Analysis Limitations\n"
    "None material.\n"
)


class FindingExtractionTests(unittest.TestCase):
    def test_extracts_each_finding_with_labeled_fields(self):
        segments = [_text_segment(SAMPLE_FINDINGS_TEXT)]
        findings = evaluations.extract_findings(segments)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0]["title"], "Revenue mismatch")
        self.assertEqual(findings[0]["classification"], "cross-source conflict")
        self.assertEqual(findings[0]["severity"], "critical")
        self.assertEqual(findings[1]["title"], "Unsupported growth rate")
        self.assertEqual(findings[1]["severity"], "high")

    def test_finding_indices_are_stable_and_ordered(self):
        segments = [_text_segment(SAMPLE_FINDINGS_TEXT)]
        findings = evaluations.extract_findings(segments)
        self.assertEqual([f["index"] for f in findings], [0, 1])

    def test_excel_citation_within_a_finding_is_attached(self):
        text_before = (
            "## Reconciliation Findings\n"
            "- **Title:** Revenue mismatch\n"
            "**Workbook evidence:** "
        )
        segments = [
            {
                "parts": [{"type": "text", "text": text_before}, _excel_citation_part()],
                "pdf_citations": [],
            }
        ]
        findings = evaluations.extract_findings(segments)
        self.assertEqual(len(findings), 1)
        self.assertEqual(len(findings[0]["excel_citations"]), 1)
        self.assertEqual(findings[0]["excel_citations"][0]["ref"], "B3")

    def test_pdf_citation_attached_to_its_block_is_collected(self):
        pdf_citation = {
            "cited_text": "Revenue is $12m",
            "document_id": "pdf-1",
            "document_title": "im.pdf",
            "start_page": 3,
            "end_page": 3,
        }
        segments = [
            _text_segment("## Reconciliation Findings\n"),
            _text_segment("- **Title:** X\n**PDF evidence:** cited here\n", pdf_citations=[pdf_citation]),
        ]
        findings = evaluations.extract_findings(segments)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]["pdf_citations"], [pdf_citation])

    def test_no_findings_section_yields_empty_list(self):
        segments = [_text_segment("## Executive Conclusion\nEverything looks fine.\n")]
        self.assertEqual(evaluations.extract_findings(segments), [])

    def test_empty_segments_yields_empty_list(self):
        self.assertEqual(evaluations.extract_findings(None), [])
        self.assertEqual(evaluations.extract_findings([]), [])

    def test_normalized_severity(self):
        self.assertEqual(evaluations.normalized_severity("Critical"), "critical")
        self.assertEqual(evaluations.normalized_severity("high"), "high")
        self.assertEqual(evaluations.normalized_severity("nonsense"), None)


class EvaluationStorageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._original_db_path = store.DB_PATH
        store.DB_PATH = Path(cls._tmpdir.name) / "test.db"
        store.init_db()
        evaluations.init_evaluations_db()

    @classmethod
    def tearDownClass(cls):
        store.DB_PATH = cls._original_db_path
        cls._tmpdir.cleanup()

    def test_create_and_get_evaluation_defaults(self):
        ev = evaluations.create_evaluation("run-1")
        self.assertEqual(ev.expected_issue_ratings, {})
        self.assertIsNone(ev.final_status)
        fetched = evaluations.get_evaluation("run-1")
        self.assertEqual(fetched.id, ev.id)

    def test_finding_can_be_manually_classified(self):
        evaluations.create_evaluation("run-2")
        updated = evaluations.update_evaluation(
            "run-2",
            {"finding_ratings": {"0": {"status": "correct_material", "citation_check": "correct"}}},
            is_blind=True,
        )
        self.assertEqual(updated.finding_ratings["0"]["status"], "correct_material")

    def test_expected_issue_can_be_mapped_to_multiple_findings(self):
        evaluations.create_evaluation("run-3")
        updated = evaluations.update_evaluation(
            "run-3",
            {"expected_issue_ratings": {"issue-a": {"status": "found_completely", "linked_finding_indices": [0, 2, 5]}}},
            is_blind=True,
        )
        self.assertEqual(updated.expected_issue_ratings["issue-a"]["linked_finding_indices"], [0, 2, 5])

    def test_unexpected_finding_can_be_classified(self):
        evaluations.create_evaluation("run-4")
        updated = evaluations.update_evaluation(
            "run-4", {"unexpected_findings": {"3": {"classification": "newly_verified_issue"}}}, is_blind=True
        )
        self.assertEqual(updated.unexpected_findings["3"]["classification"], "newly_verified_issue")

    def test_invalid_finding_status_is_rejected(self):
        evaluations.create_evaluation("run-5")
        with self.assertRaises(evaluations.EvaluationValidationError):
            evaluations.update_evaluation("run-5", {"finding_ratings": {"0": {"status": "definitely_correct"}}}, is_blind=True)

    def test_ratings_merge_without_clobbering_other_keys(self):
        evaluations.create_evaluation("run-6")
        evaluations.update_evaluation("run-6", {"finding_ratings": {"0": {"status": "correct_material"}}}, is_blind=True)
        updated = evaluations.update_evaluation("run-6", {"finding_ratings": {"1": {"status": "false"}}}, is_blind=True)
        self.assertIn("0", updated.finding_ratings)
        self.assertIn("1", updated.finding_ratings)

    def test_human_conclusion_and_final_status_can_be_saved(self):
        evaluations.create_evaluation("run-7")
        updated = evaluations.update_evaluation(
            "run-7",
            {"human_conclusion": "Looks solid.", "final_status": "passed"},
            is_blind=True,
        )
        self.assertEqual(updated.human_conclusion, "Looks solid.")
        self.assertEqual(updated.final_status, "passed")

    def test_non_blind_run_cannot_be_marked_passed(self):
        evaluations.create_evaluation("run-8")
        with self.assertRaises(evaluations.EvaluationValidationError):
            evaluations.update_evaluation("run-8", {"final_status": "passed"}, is_blind=False)
        with self.assertRaises(evaluations.EvaluationValidationError):
            evaluations.update_evaluation("run-8", {"final_status": "failed"}, is_blind=False)

    def test_non_blind_run_can_be_marked_not_a_blind_test(self):
        evaluations.create_evaluation("run-9")
        updated = evaluations.update_evaluation("run-9", {"final_status": "not_a_blind_test"}, is_blind=False)
        self.assertEqual(updated.final_status, "not_a_blind_test")

    def test_non_blind_run_can_be_marked_incomplete_review(self):
        evaluations.create_evaluation("run-10")
        updated = evaluations.update_evaluation("run-10", {"final_status": "incomplete_review"}, is_blind=False)
        self.assertEqual(updated.final_status, "incomplete_review")

    def test_invalid_final_status_is_rejected(self):
        evaluations.create_evaluation("run-11")
        with self.assertRaises(evaluations.EvaluationValidationError):
            evaluations.update_evaluation("run-11", {"final_status": "looks_good"}, is_blind=True)

    def test_evaluation_persists_across_reconnect(self):
        evaluations.create_evaluation("run-12")
        evaluations.update_evaluation("run-12", {"human_conclusion": "durable"}, is_blind=True)
        # Simulate a fresh process: re-run schema init (idempotent) and
        # fetch through a brand-new sqlite connection.
        evaluations.init_evaluations_db()
        refetched = evaluations.get_evaluation("run-12")
        self.assertEqual(refetched.human_conclusion, "durable")


class MetricsTests(unittest.TestCase):
    def _content_with_issues(self, *severities):
        content = answer_keys.empty_content()
        for sev in severities:
            content["issues"].append(answer_keys.new_issue(title=f"Issue {sev}", expected_severity=sev))
        return content

    def _findings(self, n, severities=None):
        severities = severities or ["medium"] * n
        return [{"index": i, "severity": severities[i], "title": f"F{i}"} for i in range(n)]

    def test_metrics_use_correct_denominators(self):
        content = self._content_with_issues("critical", "critical", "high")
        ids = [i["id"] for i in content["issues"]]
        ev = evaluations.Evaluation(id="e", validation_run_id="r")
        ev.expected_issue_ratings = {
            ids[0]: {"status": "found_completely"},
            ids[1]: {"status": "missed"},
            ids[2]: {"status": "found_partially"},
        }
        findings = self._findings(0)
        metrics = evaluations.compute_metrics(answer_key_content=content, findings=findings, evaluation=ev)
        self.assertEqual(metrics["critical_recall"]["numerator"], 1)
        self.assertEqual(metrics["critical_recall"]["denominator"], 2)
        self.assertEqual(metrics["high_recall"]["numerator"], 0)
        self.assertEqual(metrics["high_recall"]["denominator"], 1)
        self.assertEqual(metrics["overall_recall"]["numerator"], 1)
        self.assertEqual(metrics["overall_recall"]["denominator"], 3)

    def test_not_applicable_issues_excluded_from_denominator(self):
        content = self._content_with_issues("high", "high")
        ids = [i["id"] for i in content["issues"]]
        ev = evaluations.Evaluation(id="e", validation_run_id="r")
        ev.expected_issue_ratings = {
            ids[0]: {"status": "found_completely"},
            ids[1]: {"status": "not_applicable"},
        }
        metrics = evaluations.compute_metrics(answer_key_content=content, findings=[], evaluation=ev)
        self.assertEqual(metrics["high_recall"]["denominator"], 1)
        self.assertEqual(metrics["fully_vs_partially_found"]["excluded_not_applicable"], 1)

    def test_unreviewed_findings_keep_precision_provisional(self):
        findings = self._findings(3)
        ev = evaluations.Evaluation(id="e", validation_run_id="r")
        ev.finding_ratings = {"0": {"status": "correct_material"}}
        metrics = evaluations.compute_metrics(
            answer_key_content=answer_keys.empty_content(), findings=findings, evaluation=ev
        )
        self.assertTrue(metrics["reviewed_finding_precision"]["provisional"])
        self.assertEqual(metrics["unreviewed_finding_count"]["count"], 2)

    def test_fully_reviewed_findings_are_not_provisional(self):
        findings = self._findings(2)
        ev = evaluations.Evaluation(id="e", validation_run_id="r")
        ev.finding_ratings = {"0": {"status": "correct_material"}, "1": {"status": "false"}}
        metrics = evaluations.compute_metrics(
            answer_key_content=answer_keys.empty_content(), findings=findings, evaluation=ev
        )
        self.assertFalse(metrics["reviewed_finding_precision"]["provisional"])
        self.assertEqual(metrics["reviewed_finding_precision"]["numerator"], 1)
        self.assertEqual(metrics["reviewed_finding_precision"]["denominator"], 2)

    def test_unexpected_finding_marked_unreviewed_by_default(self):
        findings = self._findings(1)
        ev = evaluations.Evaluation(id="e", validation_run_id="r")
        metrics = evaluations.compute_metrics(
            answer_key_content=answer_keys.empty_content(), findings=findings, evaluation=ev
        )
        self.assertEqual(metrics["unreviewed_finding_count"]["count"], 1)

    def test_unexpected_finding_classification_counts_toward_reviewed(self):
        findings = self._findings(1)
        ev = evaluations.Evaluation(id="e", validation_run_id="r")
        ev.unexpected_findings = {"0": {"classification": "newly_verified_issue"}}
        metrics = evaluations.compute_metrics(
            answer_key_content=answer_keys.empty_content(), findings=findings, evaluation=ev
        )
        self.assertEqual(metrics["unreviewed_finding_count"]["count"], 0)
        self.assertEqual(metrics["verified_unexpected_material_findings"]["count"], 1)

    def test_unsupported_critical_or_high_finding_counted(self):
        findings = self._findings(2, severities=["critical", "low"])
        ev = evaluations.Evaluation(id="e", validation_run_id="r")
        ev.finding_ratings = {"0": {"status": "unsupported"}, "1": {"status": "unsupported"}}
        metrics = evaluations.compute_metrics(
            answer_key_content=answer_keys.empty_content(), findings=findings, evaluation=ev
        )
        self.assertEqual(metrics["unsupported_critical_high_count"]["count"], 1)

    def test_citation_and_calculation_accuracy(self):
        ev = evaluations.Evaluation(id="e", validation_run_id="r")
        ev.finding_ratings = {
            "0": {"citation_check": "correct", "calculation_check": "correct"},
            "1": {"citation_check": "incorrect", "calculation_check": "not_checked"},
        }
        metrics = evaluations.compute_metrics(
            answer_key_content=answer_keys.empty_content(), findings=self._findings(2), evaluation=ev
        )
        self.assertEqual(metrics["citation_accuracy"]["numerator"], 1)
        self.assertEqual(metrics["citation_accuracy"]["denominator"], 2)
        self.assertEqual(metrics["calculation_accuracy"]["numerator"], 1)
        self.assertEqual(metrics["calculation_accuracy"]["denominator"], 1)


if __name__ == "__main__":
    unittest.main()
