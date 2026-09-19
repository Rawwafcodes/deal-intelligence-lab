"""M16.3: the deterministic reconciler.

Per the M16.3 spec ("Implement rules one at a time, each justified by the
golden set... Start with the least ambiguous checks"), this module
implements exactly one rule, `numerical_conflict_same_label_v1`, and
nothing else - the spec is explicit that later rules are separate,
individually-justified additions, not a batch.

Deliberate scope boundary, chosen specifically to keep this first rule
genuinely unambiguous: it operates on `NumericFact` values that are
*already labeled* as representing the same real-world quantity by
whoever supplies them (a human, or an upstream capability) - it never
parses prose, never decides which two numbers from two documents
correspond to the same fact, and never converts between units or
currencies. Those are all real, harder problems (semantic linking is
M16.4's "semantic review" territory; unit/currency conversion is its own
separate, not-yet-built rule - see RULES["numerical_conflict_same_label_v1"]
.preconditions). Given two facts already labeled as the same quantity in
the same unit, whether their values agree within tolerance is pure
arithmetic - the actual "least ambiguous" core of the numerical_conflict
defect type.

Per the spec's "Do not claim zero false positives without measured
evidence": this module makes no such claim. The rule's own arithmetic is
exact given correct inputs; whether real upstream labeling is itself
reliable, and whether 0.5% is the right tolerance, are both unmeasured -
see this task's own completion evidence for the full disclosure.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import golden_set
import store

TIERS = ("block", "challenge", "review_queue")


@dataclass(frozen=True)
class NumericFact:
    """A single already-extracted, already-labeled numeric claim from one
    source. Producing this (deciding what the label should be, and that
    two facts from two different sources claim the same thing) is
    deliberately left to the caller - a human, or an upstream capability
    like M14.2's own review - not this module."""

    label: str
    value: float
    unit: str | None
    source_type: str
    source_id: str
    locator: dict[str, Any] | None = None

    def normalized_label(self) -> str:
        return " ".join(self.label.strip().lower().split())

    def normalized_unit(self) -> str | None:
        return " ".join(self.unit.strip().lower().split()) if self.unit else None

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "value": self.value,
            "unit": self.unit,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "locator": self.locator,
        }

    @staticmethod
    def from_dict(data: dict) -> "NumericFact":
        return NumericFact(
            label=data["label"], value=data["value"], unit=data["unit"],
            source_type=data["source_type"], source_id=data["source_id"], locator=data.get("locator"),
        )


@dataclass(frozen=True)
class RuleDefinition:
    """The M16.3 spec's own six required properties per rule, made
    inspectable in code rather than left only as prose in a task file."""

    rule_id: str
    defect_type: golden_set.DefectType
    description: str
    preconditions: str
    normalization_assumptions: str
    tolerance: str
    tier: str
    evidence_presentation: str
    dismissal_policy: str


NUMERICAL_CONFLICT_SAME_LABEL_V1 = "numerical_conflict_same_label_v1"

RULES: dict[str, RuleDefinition] = {
    NUMERICAL_CONFLICT_SAME_LABEL_V1: RuleDefinition(
        rule_id=NUMERICAL_CONFLICT_SAME_LABEL_V1,
        defect_type=golden_set.DefectType.NUMERICAL_CONFLICT,
        description=(
            "Flags two numeric facts that both claim to represent the same real-world quantity "
            "(identical normalized label and unit) but disagree beyond tolerance."
        ),
        preconditions=(
            "Both facts must already be labeled, by whoever supplies them, as representing the same "
            "real-world quantity (normalized label match) and the same unit (normalized unit match, or "
            "both unitless). This rule never decides which two facts correspond to each other and never "
            "converts between units or currencies - both are deliberately out of scope (a unit/currency "
            "mismatch is the separate, not-yet-built unit_currency_mismatch rule)."
        ),
        normalization_assumptions=(
            "Label: whitespace-collapsed, case-folded exact match. Unit: whitespace-collapsed, "
            "case-folded exact match, or both None. No fuzzy or semantic label matching of any kind."
        ),
        tolerance=(
            "Relative difference > 0.5% of the larger absolute value (default; overridable per call via "
            "`relative_tolerance`). Chosen as a conservative starting default, not validated against any "
            "measured real-case false-positive/negative rate - see this rule's own disclosed limitation."
        ),
        tier="challenge",
        evidence_presentation=(
            "Both facts' label/value/unit/source/locator, plus the computed relative difference, shown "
            "verbatim - never a summarized or reworded version of either source."
        ),
        dismissal_policy=(
            "A human may dismiss a finding by supplying a non-empty reason (dismiss_finding); an empty "
            "reason is rejected. Dismissal does not expire - re-evaluating the same two sources again "
            "returns the same, still-dismissed finding rather than reopening it."
        ),
    ),
}


class ReconcilerError(Exception):
    pass


class FindingNotFoundError(ReconcilerError):
    pass


@dataclass
class ReconcilerFinding:
    id: str
    project_id: str
    rule_id: str
    defect_type: golden_set.DefectType
    tier: str
    status: str  # "open" | "dismissed"
    summary: str
    fact_a: NumericFact
    fact_b: NumericFact
    relative_difference: float
    dismissed_by: str | None
    dismissed_at: str | None
    dismissal_reason: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "rule_id": self.rule_id,
            "defect_type": self.defect_type.value,
            "tier": self.tier,
            "status": self.status,
            "summary": self.summary,
            "fact_a": self.fact_a.to_dict(),
            "fact_b": self.fact_b.to_dict(),
            "relative_difference": self.relative_difference,
            "dismissed_by": self.dismissed_by,
            "dismissed_at": self.dismissed_at,
            "dismissal_reason": self.dismissal_reason,
            "created_at": self.created_at,
        }


def init_reconciler_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS reconciler_findings (
                id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                defect_type TEXT NOT NULL,
                tier TEXT NOT NULL,
                status TEXT NOT NULL,
                summary TEXT NOT NULL,
                fact_a_json TEXT NOT NULL,
                fact_b_json TEXT NOT NULL,
                fact_a_source_type TEXT NOT NULL,
                fact_a_source_id TEXT NOT NULL,
                fact_b_source_type TEXT NOT NULL,
                fact_b_source_id TEXT NOT NULL,
                relative_difference REAL NOT NULL,
                dismissed_by TEXT,
                dismissed_at TEXT,
                dismissal_reason TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_reconciler_findings_project ON reconciler_findings(project_id)"
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_reconciler_findings_pair ON reconciler_findings(
                project_id, rule_id, fact_a_source_type, fact_a_source_id, fact_b_source_type, fact_b_source_id
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_finding(row) -> ReconcilerFinding:
    return ReconcilerFinding(
        id=row["id"],
        project_id=row["project_id"],
        rule_id=row["rule_id"],
        defect_type=golden_set.DefectType(row["defect_type"]),
        tier=row["tier"],
        status=row["status"],
        summary=row["summary"],
        fact_a=NumericFact.from_dict(json.loads(row["fact_a_json"])),
        fact_b=NumericFact.from_dict(json.loads(row["fact_b_json"])),
        relative_difference=row["relative_difference"],
        dismissed_by=row["dismissed_by"],
        dismissed_at=row["dismissed_at"],
        dismissal_reason=row["dismissal_reason"],
        created_at=row["created_at"],
    )


def _insert(finding: ReconcilerFinding) -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO reconciler_findings (
                id, project_id, rule_id, defect_type, tier, status, summary, fact_a_json, fact_b_json,
                fact_a_source_type, fact_a_source_id, fact_b_source_type, fact_b_source_id,
                relative_difference, dismissed_by, dismissed_at, dismissal_reason, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                finding.id, finding.project_id, finding.rule_id, finding.defect_type.value, finding.tier,
                finding.status, finding.summary, json.dumps(finding.fact_a.to_dict()),
                json.dumps(finding.fact_b.to_dict()), finding.fact_a.source_type, finding.fact_a.source_id,
                finding.fact_b.source_type, finding.fact_b.source_id, finding.relative_difference,
                finding.dismissed_by, finding.dismissed_at, finding.dismissal_reason, finding.created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _find_existing(
    project_id: str, rule_id: str, fact_a: NumericFact, fact_b: NumericFact
) -> ReconcilerFinding | None:
    """Idempotency check keyed on the *pair of sources*, not their current
    values - re-evaluating the same two sources again returns the
    existing finding (open or dismissed) unchanged rather than creating a
    duplicate or silently refreshing its snapshot. Refreshing an existing
    finding when its underlying facts later change is a follow-on
    concern, not attempted here (see this task's disclosed limitations)."""
    conn = store.get_connection()
    try:
        row = conn.execute(
            """
            SELECT * FROM reconciler_findings
            WHERE project_id = %s AND rule_id = %s
              AND fact_a_source_type = %s AND fact_a_source_id = %s
              AND fact_b_source_type = %s AND fact_b_source_id = %s
            """,
            (project_id, rule_id, fact_a.source_type, fact_a.source_id, fact_b.source_type, fact_b.source_id),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_finding(row) if row else None


def evaluate_numeric_conflict(
    project_id: str, fact_a: NumericFact, fact_b: NumericFact, *, relative_tolerance: float = 0.005,
) -> ReconcilerFinding | None:
    """Applies `numerical_conflict_same_label_v1` to exactly one pair of
    facts. Returns None if the rule's preconditions aren't met (different
    normalized label, or different normalized unit - not this rule's
    concern) or the values agree within tolerance; returns the finding
    (freshly created, or the existing one if this exact pair was already
    evaluated) otherwise."""
    if fact_a.normalized_label() != fact_b.normalized_label():
        return None
    if fact_a.normalized_unit() != fact_b.normalized_unit():
        return None

    denom = max(abs(fact_a.value), abs(fact_b.value))
    relative_difference = (abs(fact_a.value - fact_b.value) / denom) if denom else 0.0
    if relative_difference <= relative_tolerance:
        return None

    ordered_a, ordered_b = sorted([fact_a, fact_b], key=lambda f: (f.source_type, f.source_id))

    existing = _find_existing(project_id, NUMERICAL_CONFLICT_SAME_LABEL_V1, ordered_a, ordered_b)
    if existing is not None:
        return existing

    def _fmt(fact: NumericFact) -> str:
        unit_suffix = f" {fact.unit}" if fact.unit else ""
        return f"{fact.value:,g}{unit_suffix}"

    summary = (
        f"'{fact_a.label}' is reported as {_fmt(fact_a)} by {fact_a.source_type} {fact_a.source_id}, "
        f"but as {_fmt(fact_b)} by {fact_b.source_type} {fact_b.source_id} - "
        f"a {relative_difference:.1%} difference."
    )
    finding = ReconcilerFinding(
        id=uuid.uuid4().hex,
        project_id=project_id,
        rule_id=NUMERICAL_CONFLICT_SAME_LABEL_V1,
        defect_type=RULES[NUMERICAL_CONFLICT_SAME_LABEL_V1].defect_type,
        tier=RULES[NUMERICAL_CONFLICT_SAME_LABEL_V1].tier,
        status="open",
        summary=summary,
        fact_a=ordered_a,
        fact_b=ordered_b,
        relative_difference=relative_difference,
        dismissed_by=None,
        dismissed_at=None,
        dismissal_reason="",
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _insert(finding)
    return finding


def get_finding(finding_id: str) -> ReconcilerFinding | None:
    conn = store.get_connection()
    try:
        row = conn.execute("SELECT * FROM reconciler_findings WHERE id = %s", (finding_id,)).fetchone()
    finally:
        conn.close()
    return _row_to_finding(row) if row else None


def list_findings(
    project_id: str, *, rule_id: str | None = None, status: str | None = None
) -> list[ReconcilerFinding]:
    conn = store.get_connection()
    try:
        clauses = ["project_id = %s"]
        params: list[str] = [project_id]
        if rule_id is not None:
            clauses.append("rule_id = %s")
            params.append(rule_id)
        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        rows = conn.execute(
            f"SELECT * FROM reconciler_findings WHERE {' AND '.join(clauses)} ORDER BY created_at ASC",
            tuple(params),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_finding(r) for r in rows]


def dismiss_finding(finding_id: str, *, dismissed_by: str, reason: str) -> ReconcilerFinding:
    reason = reason.strip()
    if not reason:
        raise ReconcilerError("a reason is required when dismissing a reconciler finding")
    existing = get_finding(finding_id)
    if existing is None:
        raise FindingNotFoundError(finding_id)

    now = datetime.now(timezone.utc).isoformat()
    conn = store.get_connection()
    try:
        conn.execute(
            """
            UPDATE reconciler_findings
            SET status = 'dismissed', dismissed_by = %s, dismissed_at = %s, dismissal_reason = %s
            WHERE id = %s
            """,
            (dismissed_by, now, reason, finding_id),
        )
        conn.commit()
    finally:
        conn.close()
    updated = get_finding(finding_id)
    assert updated is not None
    return updated
