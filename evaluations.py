"""Human evaluation of a validation run: extracts Claude's individual
reconciliation findings from a stored cross_format_analyses record into
stable, addressable units; stores the evaluator's ratings against them and
against each answer-key issue; and computes transparent (numerator,
denominator) metrics from those ratings. No automatic judgment of
correctness happens anywhere in this module - every rating is a value the
evaluator explicitly chose from a fixed set of labels; this module only
counts and totals what a human already decided.

Finding extraction is a plain-text parse of Claude's reply against the
known "Reconciliation Findings" bullet template that
cross_format_analysis.STRUCTURE_INSTRUCTIONS asks Claude to follow (Title /
Classification / Severity / Explanation / PDF evidence / Workbook evidence /
... one bullet per finding). It is a read-only, best-effort parse for
display and rating purposes - it never feeds back into the analysis itself
and never modifies the stored record.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import store

# -- finding extraction ------------------------------------------------------

_HEADING_RE = re.compile(r"^##\s+(.*)$")
_FINDING_START_RE = re.compile(r"^-\s+\*\*Title:\*\*\s*(.*)$")
_FIELD_RE = re.compile(r"^\*\*([^*]+):\*\*\s*(.*)$")

_FIELD_KEY_MAP = {
    "title": "title",
    "classification": "classification",
    "severity": "severity",
    "explanation": "explanation",
    "pdf evidence": "pdf_evidence",
    "workbook evidence": "workbook_evidence",
    "commercial or financial relevance": "commercial_relevance",
    "commercial/financial relevance": "commercial_relevance",
    "uncertainty": "uncertainty",
    "recommended action": "recommended_action",
}


def _segments_to_lines(segments: list[dict]) -> list[list[dict]]:
    """Mirrors reconcile.js's segmentsToLines: reconstructs the full text
    stream from ordered (text | excel_citation) parts, splitting on literal
    newlines, so headings/bullets/fields can be found by looking at whole
    lines - the same reason that page needs this same reconstruction."""
    lines: list[list[dict]] = [[]]
    for segment in segments:
        pdf_citations = segment.get("pdf_citations") or []
        for part in segment.get("parts") or []:
            if part.get("type") == "excel_citation":
                lines[-1].append({"type": "excel_citation", "citation": part.get("citation"), "pdf_citations": []})
                continue
            text = part.get("text") or ""
            chunks = text.split("\n")
            for i, chunk in enumerate(chunks):
                if i > 0:
                    lines.append([])
                if chunk:
                    lines[-1].append({"type": "text", "text": chunk, "pdf_citations": pdf_citations})
    return lines


def _line_text(pieces: list[dict]) -> str:
    return "".join(p["text"] for p in pieces if p["type"] == "text")


def _parse_finding_fields(raw_lines: list[str]) -> dict[str, str]:
    fields: dict[str, str] = {}
    current_key: str | None = None
    for line in raw_lines:
        stripped = line.strip()
        if stripped.startswith("- "):
            stripped = stripped[2:].strip()
        match = _FIELD_RE.match(stripped)
        if match:
            label = match.group(1).strip().lower()
            current_key = _FIELD_KEY_MAP.get(label, label.replace(" ", "_").replace("/", "_"))
            fields[current_key] = match.group(2).strip()
        elif current_key is not None and stripped:
            fields[current_key] = (fields.get(current_key, "") + " " + stripped).strip()
    return fields


def _citation_key(citation: dict) -> str:
    return json.dumps(citation, sort_keys=True)


# Tags every snapshot workspaces.py persists from this parser's output.
# Bump this whenever extract_findings's parsing rules change, so a stored
# snapshot's provenance is always known and legacy re-extraction (see
# migrate_finding_ids.py) can tell which parser version produced which
# index mapping.
EXTRACTION_VERSION = "v1"


def extract_findings(segments: list[dict] | None) -> list[dict]:
    """Returns an ordered list of findings parsed out of the "##
    Reconciliation Findings" section of a cross_format_analyses record's
    stored segments. Each finding's `index` is its position in this list -
    stable as long as the underlying record (which is write-once) doesn't
    change, which it never does after creation. Returns [] for a record
    with no segments (e.g. a failed run)."""
    if not segments:
        return []

    lines = _segments_to_lines(segments)
    findings: list[dict] = []
    in_findings_section = False
    current: dict[str, Any] | None = None

    def close_current() -> None:
        nonlocal current
        if current is None:
            return
        fields = _parse_finding_fields(current["raw_lines"])
        findings.append(
            {
                "index": len(findings),
                "raw_text": "\n".join(current["raw_lines"]).strip(),
                "title": fields.get("title", ""),
                "classification": fields.get("classification", ""),
                "severity": fields.get("severity", ""),
                "explanation": fields.get("explanation", ""),
                "pdf_evidence": fields.get("pdf_evidence", ""),
                "workbook_evidence": fields.get("workbook_evidence", ""),
                "commercial_relevance": fields.get("commercial_relevance", ""),
                "uncertainty": fields.get("uncertainty", ""),
                "recommended_action": fields.get("recommended_action", ""),
                "pdf_citations": current["pdf_citations"],
                "excel_citations": current["excel_citations"],
            }
        )
        current = None

    for pieces in lines:
        trimmed = _line_text(pieces).strip()
        all_text = all(p["type"] == "text" for p in pieces)

        heading_match = _HEADING_RE.match(trimmed) if all_text else None
        if heading_match:
            close_current()
            in_findings_section = heading_match.group(1).strip().lower() == "reconciliation findings"
            continue

        if not in_findings_section:
            continue

        finding_start = _FINDING_START_RE.match(trimmed) if all_text else None
        if finding_start:
            close_current()
            current = {"raw_lines": [], "pdf_citations": [], "excel_citations": []}

        if current is None:
            continue  # stray text in this section before the first finding bullet

        line_repr = []
        seen_pdf_keys = {_citation_key(c) for c in current["pdf_citations"]}
        seen_excel_keys = {_citation_key(c) for c in current["excel_citations"]}
        for p in pieces:
            if p["type"] == "text":
                line_repr.append(p["text"])
                for c in p.get("pdf_citations") or []:
                    key = _citation_key(c)
                    if key not in seen_pdf_keys:
                        seen_pdf_keys.add(key)
                        current["pdf_citations"].append(c)
            else:
                citation = p.get("citation") or {}
                line_repr.append(citation.get("raw_text", ""))
                key = _citation_key(citation)
                if key not in seen_excel_keys:
                    seen_excel_keys.add(key)
                    current["excel_citations"].append(citation)
        current["raw_lines"].append("".join(line_repr))

    close_current()
    return findings


_SEVERITY_ORDER = ["critical", "high", "medium", "low", "informational"]


def normalized_severity(raw: str) -> str | None:
    lowered = (raw or "").strip().lower()
    for level in _SEVERITY_ORDER:
        if lowered.startswith(level):
            return level
    return None


# -- evaluation storage -------------------------------------------------------

EXPECTED_ISSUE_STATUSES = {"found_completely", "found_partially", "missed", "not_applicable"}
FINDING_STATUSES = {
    "correct_material",
    "correct_immaterial",
    "partially_correct",
    "unsupported",
    "false",
    "requires_specialist",
    "not_reviewed",
}
UNEXPECTED_CLASSIFICATIONS = {
    "newly_verified_issue",
    "valid_but_immaterial",
    "unsupported",
    "false",
    "requires_investigation",
}
CHECK_VALUES = {"correct", "incorrect", "not_checked"}
SEVERITY_CHECK_VALUES = {"appropriate", "inappropriate", "not_checked"}
ACTION_CHECK_VALUES = {"useful", "not_useful", "not_checked"}
FINAL_STATUSES = {"passed", "passed_with_limitations", "failed", "incomplete_review", "not_a_blind_test"}


def default_evaluation_content() -> dict:
    return {
        "expected_issue_ratings": {},
        "finding_ratings": {},
        "unexpected_findings": {},
        "human_conclusion": "",
        "material_limitations": "",
        "recommended_improvements": "",
        "final_status": None,
    }


@dataclass
class Evaluation:
    id: str
    validation_run_id: str
    expected_issue_ratings: dict = field(default_factory=dict)
    finding_ratings: dict = field(default_factory=dict)
    unexpected_findings: dict = field(default_factory=dict)
    human_conclusion: str = ""
    material_limitations: str = ""
    recommended_improvements: str = ""
    final_status: str | None = None
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "validation_run_id": self.validation_run_id,
            "expected_issue_ratings": self.expected_issue_ratings,
            "finding_ratings": self.finding_ratings,
            "unexpected_findings": self.unexpected_findings,
            "human_conclusion": self.human_conclusion,
            "material_limitations": self.material_limitations,
            "recommended_improvements": self.recommended_improvements,
            "final_status": self.final_status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def init_evaluations_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS evaluations (
                id TEXT PRIMARY KEY,
                validation_run_id TEXT NOT NULL UNIQUE,
                expected_issue_ratings_json TEXT NOT NULL,
                finding_ratings_json TEXT NOT NULL,
                unexpected_findings_json TEXT NOT NULL,
                human_conclusion TEXT NOT NULL DEFAULT '',
                material_limitations TEXT NOT NULL DEFAULT '',
                recommended_improvements TEXT NOT NULL DEFAULT '',
                final_status TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_evaluations_run ON evaluations(validation_run_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_evaluation(row) -> Evaluation:
    return Evaluation(
        id=row["id"],
        validation_run_id=row["validation_run_id"],
        expected_issue_ratings=json.loads(row["expected_issue_ratings_json"]),
        finding_ratings=json.loads(row["finding_ratings_json"]),
        unexpected_findings=json.loads(row["unexpected_findings_json"]),
        human_conclusion=row["human_conclusion"],
        material_limitations=row["material_limitations"],
        recommended_improvements=row["recommended_improvements"],
        final_status=row["final_status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def create_evaluation(validation_run_id: str) -> Evaluation:
    now = datetime.now(timezone.utc).isoformat()
    defaults = default_evaluation_content()
    evaluation = Evaluation(
        id=uuid.uuid4().hex,
        validation_run_id=validation_run_id,
        expected_issue_ratings=defaults["expected_issue_ratings"],
        finding_ratings=defaults["finding_ratings"],
        unexpected_findings=defaults["unexpected_findings"],
        created_at=now,
        updated_at=now,
    )
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO evaluations (
                id, validation_run_id, expected_issue_ratings_json, finding_ratings_json,
                unexpected_findings_json, human_conclusion, material_limitations,
                recommended_improvements, final_status, created_at, updated_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                evaluation.id,
                evaluation.validation_run_id,
                json.dumps(evaluation.expected_issue_ratings),
                json.dumps(evaluation.finding_ratings),
                json.dumps(evaluation.unexpected_findings),
                evaluation.human_conclusion,
                evaluation.material_limitations,
                evaluation.recommended_improvements,
                evaluation.final_status,
                evaluation.created_at,
                evaluation.updated_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return evaluation


def get_evaluation(validation_run_id: str) -> Evaluation | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM evaluations WHERE validation_run_id = %s", (validation_run_id,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_evaluation(row) if row else None


class EvaluationValidationError(Exception):
    pass


def update_evaluation(validation_run_id: str, updates: dict, *, is_blind: bool) -> Evaluation:
    """Merges `updates` into the stored evaluation. The three ratings
    dictionaries (expected_issue_ratings, finding_ratings,
    unexpected_findings) are merged key-by-key so an evaluator can save one
    rating at a time without clobbering others; the remaining scalar fields
    are simply overwritten when present in `updates`.

    Rejects a `final_status` of "passed" / "passed_with_limitations" /
    "failed" for a run that was not genuinely blind (`is_blind=False`) -
    those statuses represent a legitimate blind-validation outcome and must
    never be claimed for a retrospective run; only "incomplete_review" or
    "not_a_blind_test" are accepted for one.
    """
    existing = get_evaluation(validation_run_id)
    if existing is None:
        raise ValueError("evaluation not found")

    if "expected_issue_ratings" in updates:
        for issue_id, rating in updates["expected_issue_ratings"].items():
            status = rating.get("status")
            if status is not None and status not in EXPECTED_ISSUE_STATUSES:
                raise EvaluationValidationError(f"invalid expected-issue status: {status}")
            existing.expected_issue_ratings[issue_id] = rating

    if "finding_ratings" in updates:
        for finding_index, rating in updates["finding_ratings"].items():
            status = rating.get("status")
            if status is not None and status not in FINDING_STATUSES:
                raise EvaluationValidationError(f"invalid finding status: {status}")
            for check_field, allowed in (
                ("citation_check", CHECK_VALUES),
                ("calculation_check", CHECK_VALUES),
                ("severity_check", SEVERITY_CHECK_VALUES),
                ("recommended_action_check", ACTION_CHECK_VALUES),
            ):
                value = rating.get(check_field)
                if value is not None and value not in allowed:
                    raise EvaluationValidationError(f"invalid {check_field}: {value}")
            existing.finding_ratings[finding_index] = rating

    if "unexpected_findings" in updates:
        for finding_index, rating in updates["unexpected_findings"].items():
            classification = rating.get("classification")
            if classification is not None and classification not in UNEXPECTED_CLASSIFICATIONS:
                raise EvaluationValidationError(f"invalid unexpected-finding classification: {classification}")
            existing.unexpected_findings[finding_index] = rating

    for scalar_field in ("human_conclusion", "material_limitations", "recommended_improvements"):
        if scalar_field in updates:
            setattr(existing, scalar_field, str(updates[scalar_field]))

    if "final_status" in updates:
        final_status = updates["final_status"]
        if final_status is not None:
            if final_status not in FINAL_STATUSES:
                raise EvaluationValidationError(f"invalid final_status: {final_status}")
            if not is_blind and final_status in ("passed", "passed_with_limitations", "failed"):
                raise EvaluationValidationError(
                    "a non-blind (retrospective) run cannot be marked passed/passed_with_limitations/failed; "
                    "use incomplete_review or not_a_blind_test"
                )
        existing.final_status = final_status

    existing.updated_at = datetime.now(timezone.utc).isoformat()

    conn = store.get_connection()
    try:
        conn.execute(
            """
            UPDATE evaluations SET
                expected_issue_ratings_json = %s, finding_ratings_json = %s, unexpected_findings_json = %s,
                human_conclusion = %s, material_limitations = %s, recommended_improvements = %s,
                final_status = %s, updated_at = %s
            WHERE validation_run_id = %s
            """,
            (
                json.dumps(existing.expected_issue_ratings),
                json.dumps(existing.finding_ratings),
                json.dumps(existing.unexpected_findings),
                existing.human_conclusion,
                existing.material_limitations,
                existing.recommended_improvements,
                existing.final_status,
                existing.updated_at,
                validation_run_id,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    updated = get_evaluation(validation_run_id)
    assert updated is not None
    return updated


# -- metrics -------------------------------------------------------------


def _metric(numerator: int, denominator: int, label: str, *, provisional: bool = False) -> dict:
    return {
        "numerator": numerator,
        "denominator": denominator,
        "label": label,
        "percent": round(100 * numerator / denominator, 1) if denominator else None,
        "provisional": provisional,
    }


def compute_metrics(
    *, answer_key_content: dict, findings: list[dict], evaluation: Evaluation
) -> dict[str, dict]:
    issues = answer_key_content.get("issues", [])
    ratings = evaluation.expected_issue_ratings

    def issue_rating_status(issue_id: str) -> str | None:
        r = ratings.get(issue_id)
        return r.get("status") if r else None

    applicable_issues = [i for i in issues if issue_rating_status(i["id"]) != "not_applicable"]
    excluded_not_applicable = len(issues) - len(applicable_issues)

    def recall_for(severity: str | None) -> dict:
        pool = (
            applicable_issues
            if severity is None
            else [i for i in applicable_issues if normalized_severity(i.get("expected_severity", "")) == severity]
        )
        found = sum(1 for i in pool if issue_rating_status(i["id"]) == "found_completely")
        label = f"{severity.capitalize()}-issue recall" if severity else "Overall expected-issue recall"
        return _metric(found, len(pool), label)

    fully_found = sum(1 for i in applicable_issues if issue_rating_status(i["id"]) == "found_completely")
    partially_found = sum(1 for i in applicable_issues if issue_rating_status(i["id"]) == "found_partially")
    missed = sum(1 for i in applicable_issues if issue_rating_status(i["id"]) == "missed")

    finding_ratings = evaluation.finding_ratings
    unexpected = evaluation.unexpected_findings

    def finding_status(index: int) -> str | None:
        r = finding_ratings.get(str(index))
        return r.get("status") if r else None

    def unexpected_classification(index: int) -> str | None:
        r = unexpected.get(str(index))
        return r.get("classification") if r else None

    total_findings = len(findings)

    def is_unreviewed(f: dict) -> bool:
        return finding_status(f["index"]) in (None, "not_reviewed") and unexpected_classification(f["index"]) is None

    unreviewed = [f for f in findings if is_unreviewed(f)]
    reviewed = [f for f in findings if not is_unreviewed(f)]

    correct_like = {"correct_material", "correct_immaterial", "partially_correct"}
    reviewed_correct = sum(1 for f in reviewed if finding_status(f["index"]) in correct_like)
    precision = _metric(
        reviewed_correct, len(reviewed), "Reviewed-finding precision", provisional=len(unreviewed) > 0
    )

    false_positive_count = 0
    unsupported_critical_high = 0
    for f in findings:
        status = finding_status(f["index"])
        classification = unexpected_classification(f["index"])
        is_false = status == "false" or classification == "false"
        is_unsupported = status == "unsupported" or classification == "unsupported"
        if is_false:
            false_positive_count += 1
        severity = normalized_severity(f.get("severity", ""))
        if is_unsupported and severity in ("critical", "high"):
            unsupported_critical_high += 1

    def check_metric(check_field: str, good_value: str, label: str) -> dict:
        checked = [r for r in finding_ratings.values() if r.get(check_field) in (good_value, _opposite(good_value))]
        good = sum(1 for r in checked if r.get(check_field) == good_value)
        return _metric(good, len(checked), label)

    def _opposite(value: str) -> str:
        return {"correct": "incorrect", "appropriate": "inappropriate"}.get(value, "")

    citation_accuracy = check_metric("citation_check", "correct", "Citation accuracy")
    calculation_accuracy = check_metric("calculation_check", "correct", "Calculation accuracy")
    severity_agreement = check_metric("severity_check", "appropriate", "Severity-rating agreement")

    verified_unexpected_material = sum(
        1 for f in findings if unexpected_classification(f["index"]) == "newly_verified_issue"
    )

    return {
        "critical_recall": recall_for("critical"),
        "high_recall": recall_for("high"),
        "overall_recall": recall_for(None),
        "fully_vs_partially_found": {
            "fully_found": fully_found,
            "partially_found": partially_found,
            "missed": missed,
            "applicable_total": len(applicable_issues),
            "excluded_not_applicable": excluded_not_applicable,
        },
        "reviewed_finding_precision": precision,
        "false_positive_count": {"count": false_positive_count, "total_findings": total_findings},
        "unsupported_critical_high_count": {"count": unsupported_critical_high, "total_findings": total_findings},
        "citation_accuracy": citation_accuracy,
        "calculation_accuracy": calculation_accuracy,
        "severity_agreement": severity_agreement,
        "verified_unexpected_material_findings": {"count": verified_unexpected_material},
        "unreviewed_finding_count": {"count": len(unreviewed), "total_findings": total_findings},
    }
