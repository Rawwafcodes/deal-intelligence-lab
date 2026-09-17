"""Tests for overview.py (Task 13.3): pure aggregation, no database, no
HTTP - plain Python objects/dicts standing in for real records."""

import sys
import types
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import overview


def fake(status=None, updated_at=None, **extra):
    return types.SimpleNamespace(status=status, updated_at=updated_at, **extra)


class CountByStatusTests(unittest.TestCase):
    def test_counts_real_statuses_only(self):
        items = [fake(status="open"), fake(status="open"), fake(status="submitted")]
        self.assertEqual(overview.count_by_status(items), {"open": 2, "submitted": 1})

    def test_empty_list(self):
        self.assertEqual(overview.count_by_status([]), {})

    def test_never_invents_a_status_not_present(self):
        # No "cancelled" key should appear just because it's a known status
        # elsewhere in the app - only real, present statuses are counted.
        counts = overview.count_by_status([fake(status="approved")])
        self.assertEqual(counts, {"approved": 1})
        self.assertNotIn("cancelled", counts)


class TasksNeedingAttentionTests(unittest.TestCase):
    def test_filters_to_submitted_and_returned_only(self):
        items = [
            fake(status="open", updated_at="2026-01-01"),
            fake(status="submitted", updated_at="2026-01-02"),
            fake(status="returned", updated_at="2026-01-03"),
            fake(status="approved", updated_at="2026-01-04"),
            fake(status="cancelled", updated_at="2026-01-05"),
        ]
        urgent = overview.tasks_needing_attention(items)
        self.assertEqual({t.status for t in urgent}, {"submitted", "returned"})

    def test_sorted_most_recently_updated_first(self):
        items = [
            fake(status="submitted", updated_at="2026-01-01", name="oldest"),
            fake(status="returned", updated_at="2026-01-03", name="newest"),
            fake(status="submitted", updated_at="2026-01-02", name="middle"),
        ]
        urgent = overview.tasks_needing_attention(items)
        self.assertEqual([t.name for t in urgent], ["newest", "middle", "oldest"])

    def test_respects_limit(self):
        items = [fake(status="submitted", updated_at=f"2026-01-{i:02d}") for i in range(1, 6)]
        self.assertEqual(len(overview.tasks_needing_attention(items, limit=2)), 2)


class FindingsSummaryTests(unittest.TestCase):
    def test_counts_by_severity(self):
        findings = [
            {"effective_severity": "critical", "resolution_status": "open"},
            {"effective_severity": "critical", "resolution_status": "resolved"},
            {"effective_severity": "high", "resolution_status": "open"},
            {"effective_severity": "low", "resolution_status": "accepted_risk"},
        ]
        summary = overview.findings_summary(findings)
        self.assertEqual(summary["total"], 4)
        self.assertEqual(summary["by_severity"], {"critical": 2, "high": 1, "low": 1})

    def test_open_counts_are_a_real_filter_not_a_derived_score(self):
        findings = [
            {"effective_severity": "critical", "resolution_status": "open"},
            {"effective_severity": "critical", "resolution_status": "resolved"},
            {"effective_severity": "high", "resolution_status": "open"},
        ]
        summary = overview.findings_summary(findings)
        self.assertEqual(summary["open_by_severity"], {"critical": 1, "high": 1})

    def test_missing_severity_falls_back_to_unspecified_not_dropped(self):
        summary = overview.findings_summary([{"resolution_status": "open"}])
        self.assertEqual(summary["by_severity"], {"unspecified": 1})

    def test_empty_findings(self):
        summary = overview.findings_summary([])
        self.assertEqual(summary, {"total": 0, "by_severity": {}, "open_by_severity": {}})

    def test_never_produces_a_single_health_number(self):
        # Explicit guard against the exact thing docs/05 forbids: no key
        # in the output should look like a synthesized overall score.
        summary = overview.findings_summary([{"effective_severity": "critical", "resolution_status": "open"}])
        for forbidden in ("health", "score", "percent", "rating"):
            self.assertNotIn(forbidden, summary)


class ActivityFeedTests(unittest.TestCase):
    def test_sorted_newest_first(self):
        events = [
            {"kind": "comment", "at": "2026-01-01T00:00:00Z"},
            {"kind": "review_decision", "at": "2026-01-03T00:00:00Z"},
            {"kind": "submission", "at": "2026-01-02T00:00:00Z"},
        ]
        feed = overview.build_activity_feed(events)
        self.assertEqual([e["kind"] for e in feed], ["review_decision", "submission", "comment"])

    def test_respects_limit(self):
        events = [{"kind": "comment", "at": f"2026-01-{i:02d}T00:00:00Z"} for i in range(1, 30)]
        self.assertEqual(len(overview.build_activity_feed(events, limit=5)), 5)

    def test_empty_events(self):
        self.assertEqual(overview.build_activity_feed([]), [])


if __name__ == "__main__":
    unittest.main()
