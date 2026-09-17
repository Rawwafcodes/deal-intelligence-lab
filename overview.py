"""Workspace/Deal overview aggregation (Task 13.3: docs/05-experience.md's
Workspace Overview / Deal Overview - "Counts derive from real records
with visible filters. No invented percent-health metrics.").

Deliberately a pure-function module: every function here takes
already-fetched real records (plain dicts, or objects with the attributes
named) and produces counts, filtered lists, or a merged, sorted feed - it
never queries the database and imports no other domain module. `server.py`
is what fetches the real Task/Mandate/finding/etc. records from their own
modules and calls into this one to summarize them, the same "compose at
the API boundary" shape this app already uses throughout (see
`_task_with_details`, `_workstream_with_assignments`). Kept this way
specifically so the counting/filtering/sorting logic - the part most
worth getting exactly right, since a wrong count here is a literal "fake
metric" - can be unit-tested with plain Python objects, no Postgres, no
HTTP server.

Every number this module produces is a real count of real rows already
persisted elsewhere, or a real, unweighted list of them - never a derived
score, percentage, or "health" rating. If a summary here cannot be
computed from real underlying records, it is omitted, not guessed.
"""

from __future__ import annotations

from typing import Any, Iterable


def count_by_status(items: Iterable[Any]) -> dict[str, int]:
    """Real counts, keyed by each item's own `.status` attribute - no
    category is invented or renamed; whatever status strings the
    underlying records actually use are what shows up here."""
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def tasks_needing_attention(task_list: Iterable[Any], limit: int = 10) -> list[Any]:
    """Tasks whose status is "submitted" or "returned" - the two states
    where a specific human action (review, or revision) is expected next.
    Most recently updated first. This is a real filter on a real field
    (docs/05's "My attention... blocked assignments"), not a synthesized
    urgency score."""
    urgent = [t for t in task_list if t.status in ("submitted", "returned")]
    urgent.sort(key=lambda t: t.updated_at, reverse=True)
    return urgent[:limit]


def findings_summary(all_findings: list[dict]) -> dict[str, Any]:
    """`all_findings`: the flat concatenation of `workspaces.list_findings()`
    across every one of a project's real reconciliation workspaces (a
    project can have more than one). Returns real counts only: how many
    findings exist at each severity, and - a real filter on the existing
    `resolution_status` field, not a new judgment this module makes -
    how many of those are still `resolution_status == "open"`
    specifically (docs/05's "material issues"). Never collapses severity
    into one "deal health" number."""
    by_severity: dict[str, int] = {}
    open_by_severity: dict[str, int] = {}
    for finding in all_findings:
        severity = finding.get("effective_severity") or "unspecified"
        by_severity[severity] = by_severity.get(severity, 0) + 1
        if finding.get("resolution_status") == "open":
            open_by_severity[severity] = open_by_severity.get(severity, 0) + 1
    return {
        "total": len(all_findings),
        "by_severity": by_severity,
        "open_by_severity": open_by_severity,
    }


def build_activity_feed(events: list[dict], limit: int = 20) -> list[dict]:
    """`events`: a list of already-tagged {"kind": ..., "at": <ISO
    timestamp>, ...} dicts from any real source (a comment, a
    review decision, a work-product submission) - this function only
    sorts them newest-first and caps the length. It never invents an
    event, and never reorders by anything other than the real timestamp
    each event already carries."""
    return sorted(events, key=lambda e: e["at"], reverse=True)[:limit]
