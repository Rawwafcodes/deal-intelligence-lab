"""M16.1: a versioned corpus of known integrity-defect cases, one family per
defect type in the fixed taxonomy below. This is a reference/benchmark
dataset - not project-scoped, not tied to any real deal's documents - used
by later M16 work (16.3's deterministic reconciler, 16.4's semantic-review
benchmarking) to justify each new rule or pipeline against known cases
before it ships, per docs/08-roadmap.md's M16 gate.

Every case is either `synthetic` (invented to illustrate a pattern) or
`authorized_real` (drawn from a real deal with explicit authorization to
reuse it outside that deal's own workspace). Per the M16.1 spec ("Do not
move confidential client content into a reusable corpus without
authority"), nothing in this module ever reads from `documents.py`/
`DATA_DIR` or any project's real files - a case's `scenario_text` is
free-standing prose stored directly in this table, never a pointer into a
real uploaded document.

Versioning mirrors the Document/DocumentVersion split (documents.py) and
SubmissionVersion (work_products.py): `case_key` is the stable identity
across edits, `version_number` increments, and superseding a case creates
a new row rather than mutating the old one - so a rule or benchmark result
that cited a specific version stays reproducible even after the case
itself is later corrected.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

import store


class DefectType(str, Enum):
    """The fixed taxonomy from docs/08-roadmap.md 16.1 / the M16 spec's own
    16.1 section. Deliberately closed (not user-extensible) - a case whose
    defect_type doesn't match one of these is almost always miscategorized
    rather than a genuinely new pattern; extending this list is a task-file
    decision, not a runtime one."""

    NUMERICAL_CONFLICT = "numerical_conflict"
    TEMPORAL_MISMATCH = "temporal_mismatch"
    UNIT_CURRENCY_MISMATCH = "unit_currency_mismatch"
    DERIVATION_DIVERGENCE = "derivation_divergence"
    ENTITY_CONFLATION = "entity_conflation"
    MODALITY_ESCALATION = "modality_escalation"
    UNSUPPORTED_ASSERTION = "unsupported_assertion"
    STALENESS = "staleness"
    LOGICAL_CONTRADICTION = "logical_contradiction"
    COMPARATOR_SPECIFICITY_MISMATCH = "comparator_specificity_mismatch"


DEFECT_TYPE_DESCRIPTIONS: dict[DefectType, str] = {
    DefectType.NUMERICAL_CONFLICT: (
        "Two sources state materially different numeric values for what should be the same fact."
    ),
    DefectType.TEMPORAL_MISMATCH: (
        "Sources disagree on a date, period, or as-of point, or apply the wrong period's figures."
    ),
    DefectType.UNIT_CURRENCY_MISMATCH: (
        "A comparison silently mixes units (e.g. thousands vs. millions) or currencies."
    ),
    DefectType.DERIVATION_DIVERGENCE: (
        "A derived figure does not follow from its own stated inputs (a sum, ratio, or formula doesn't reconcile)."
    ),
    DefectType.ENTITY_CONFLATION: (
        "Two distinct entities, instruments, or line items are treated as the same one, or vice versa."
    ),
    DefectType.MODALITY_ESCALATION: (
        "A hedged, conditional, or draft statement in a source is restated as a firm, unconditional fact."
    ),
    DefectType.UNSUPPORTED_ASSERTION: (
        "A claim is presented as sourced but no cited passage actually supports it."
    ),
    DefectType.STALENESS: (
        "A finding or assertion still cites a document version that has since been superseded."
    ),
    DefectType.LOGICAL_CONTRADICTION: (
        "Two statements cannot both be true regardless of numeric tolerance (a direct logical conflict)."
    ),
    DefectType.COMPARATOR_SPECIFICITY_MISMATCH: (
        "A comparison is drawn between a specific figure and an aggregate/rounded one that isn't the same thing."
    ),
}


@dataclass
class GoldenCase:
    id: str
    case_key: str
    version_number: int
    defect_type: DefectType
    title: str
    scenario_text: str
    expected_assertion: str
    provenance: str
    status: str
    notes: str
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "case_key": self.case_key,
            "version_number": self.version_number,
            "defect_type": self.defect_type.value,
            "title": self.title,
            "scenario_text": self.scenario_text,
            "expected_assertion": self.expected_assertion,
            "provenance": self.provenance,
            "status": self.status,
            "notes": self.notes,
            "created_at": self.created_at,
        }


_VALID_PROVENANCE = ("synthetic", "authorized_real")


def init_golden_set_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS golden_cases (
                id TEXT PRIMARY KEY,
                case_key TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                defect_type TEXT NOT NULL,
                title TEXT NOT NULL,
                scenario_text TEXT NOT NULL,
                expected_assertion TEXT NOT NULL,
                provenance TEXT NOT NULL,
                status TEXT NOT NULL,
                notes TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_golden_cases_case_key ON golden_cases(case_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_golden_cases_defect_type ON golden_cases(defect_type)")
        conn.commit()
    finally:
        conn.close()
    _seed_defaults()


def _row_to_case(row) -> GoldenCase:
    return GoldenCase(
        id=row["id"],
        case_key=row["case_key"],
        version_number=row["version_number"],
        defect_type=DefectType(row["defect_type"]),
        title=row["title"],
        scenario_text=row["scenario_text"],
        expected_assertion=row["expected_assertion"],
        provenance=row["provenance"],
        status=row["status"],
        notes=row["notes"],
        created_at=row["created_at"],
    )


def create_case(
    *,
    defect_type: DefectType,
    title: str,
    scenario_text: str,
    expected_assertion: str,
    provenance: str = "synthetic",
    notes: str = "",
) -> GoldenCase:
    if provenance not in _VALID_PROVENANCE:
        raise ValueError(f"invalid provenance: {provenance!r}")
    case = GoldenCase(
        id=uuid.uuid4().hex,
        case_key=uuid.uuid4().hex,
        version_number=1,
        defect_type=defect_type,
        title=title.strip(),
        scenario_text=scenario_text.strip(),
        expected_assertion=expected_assertion.strip(),
        provenance=provenance,
        status="active",
        notes=notes.strip(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _insert(case)
    return case


def _insert(case: GoldenCase) -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO golden_cases (
                id, case_key, version_number, defect_type, title, scenario_text,
                expected_assertion, provenance, status, notes, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                case.id,
                case.case_key,
                case.version_number,
                case.defect_type.value,
                case.title,
                case.scenario_text,
                case.expected_assertion,
                case.provenance,
                case.status,
                case.notes,
                case.created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_case(case_key: str) -> GoldenCase | None:
    """Returns the current (`status = 'active'`) version of a case family,
    or None if the case_key doesn't exist or its only versions are all
    superseded (shouldn't happen in practice - supersede_case always leaves
    exactly one active version - but callers should still handle it)."""
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM golden_cases WHERE case_key = %s AND status = 'active'", (case_key,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_case(row) if row else None


def get_case_history(case_key: str) -> list[GoldenCase]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM golden_cases WHERE case_key = %s ORDER BY version_number ASC", (case_key,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_case(row) for row in rows]


def list_cases(defect_type: DefectType | None = None, *, include_superseded: bool = False) -> list[GoldenCase]:
    conn = store.get_connection()
    try:
        clauses = []
        params: list[str] = []
        if not include_superseded:
            clauses.append("status = 'active'")
        if defect_type is not None:
            clauses.append("defect_type = %s")
            params.append(defect_type.value)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM golden_cases {where} ORDER BY defect_type ASC, created_at ASC", tuple(params)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_case(row) for row in rows]


class GoldenCaseNotFoundError(Exception):
    pass


def supersede_case(
    case_key: str,
    *,
    title: str | None = None,
    scenario_text: str | None = None,
    expected_assertion: str | None = None,
    provenance: str | None = None,
    notes: str | None = None,
) -> GoldenCase:
    """Creates a new version of an existing case family, carrying forward
    any field not explicitly overridden, and marks the prior current
    version `superseded`. Raises GoldenCaseNotFoundError if there is no
    current active version for this case_key (never silently creates a new
    family - use create_case for that)."""
    current = get_case(case_key)
    if current is None:
        raise GoldenCaseNotFoundError(case_key)
    if provenance is not None and provenance not in _VALID_PROVENANCE:
        raise ValueError(f"invalid provenance: {provenance!r}")

    new_version = GoldenCase(
        id=uuid.uuid4().hex,
        case_key=case_key,
        version_number=current.version_number + 1,
        defect_type=current.defect_type,
        title=(title if title is not None else current.title).strip(),
        scenario_text=(scenario_text if scenario_text is not None else current.scenario_text).strip(),
        expected_assertion=(
            expected_assertion if expected_assertion is not None else current.expected_assertion
        ).strip(),
        provenance=provenance if provenance is not None else current.provenance,
        status="active",
        notes=(notes if notes is not None else current.notes).strip(),
        created_at=datetime.now(timezone.utc).isoformat(),
    )

    conn = store.get_connection()
    try:
        conn.execute(
            "UPDATE golden_cases SET status = 'superseded' WHERE id = %s", (current.id,)
        )
        conn.commit()
    finally:
        conn.close()
    _insert(new_version)
    return new_version


# Synthetic seed cases: one per defect type, illustrating the pattern with
# clearly invented deal content (fictional company/figures) rather than any
# real deal's material - see this module's own docstring and the M16.1 spec's
# "do not move confidential client content into a reusable corpus without
# authority." Idempotent: only runs once, the first time this table is empty.
_SEED_CASES: list[dict] = [
    {
        "defect_type": DefectType.NUMERICAL_CONFLICT,
        "title": "Purchase price disagreement between term sheet and sources & uses",
        "scenario_text": (
            "[SYNTHETIC] Term Sheet, Section 2.1: 'Purchase Price: $50,000,000, payable in cash at closing.' "
            "Sources & Uses Workbook, cell B12 ('Total Purchase Consideration'): $52,000,000."
        ),
        "expected_assertion": (
            "The term sheet's stated purchase price ($50,000,000) conflicts with the sources & uses "
            "workbook's total purchase consideration ($52,000,000) for what both documents present as "
            "the same transaction figure."
        ),
    },
    {
        "defect_type": DefectType.TEMPORAL_MISMATCH,
        "title": "Financial statements cited for the wrong fiscal period",
        "scenario_text": (
            "[SYNTHETIC] Management Presentation, slide 4: 'FY2025 revenue grew 18% year over year to $84M.' "
            "Audited Financial Statements cover the period 'January 1, 2024 - December 31, 2024' and show "
            "revenue of $84M for that period, not FY2025."
        ),
        "expected_assertion": (
            "The management presentation attributes $84M of revenue to FY2025, but the only audited "
            "statements showing $84M actually cover FY2024 - the figure appears to have been carried "
            "forward under the wrong period label."
        ),
    },
    {
        "defect_type": DefectType.UNIT_CURRENCY_MISMATCH,
        "title": "EBITDA comparison mixes thousands and millions",
        "scenario_text": (
            "[SYNTHETIC] Target's internal model, row 22 (header: 'EBITDA ($000s)'): 4,200. "
            "Buyer's comparison memo: 'Target EBITDA of $4,200 versus peer average of $38 million' - "
            "treating the model's 4,200 (i.e., $4.2 million) as if it were already stated in whole dollars."
        ),
        "expected_assertion": (
            "The buyer's memo compares the target's EBITDA figure (4,200, expressed in thousands per the "
            "model's own header, i.e. $4.2M) directly against a peer average stated in millions, understating "
            "the target's EBITDA by roughly 1000x in the comparison."
        ),
    },
    {
        "defect_type": DefectType.DERIVATION_DIVERGENCE,
        "title": "Reported gross margin does not follow from the stated revenue and COGS",
        "scenario_text": (
            "[SYNTHETIC] Financial summary: 'Revenue: $10.0M. Cost of goods sold: $7.0M. Gross margin: 42%.' "
            "($10.0M - $7.0M) / $10.0M = 30%, not 42%."
        ),
        "expected_assertion": (
            "The stated gross margin of 42% does not follow from the same document's own revenue ($10.0M) "
            "and COGS ($7.0M) figures, which imply a 30% gross margin."
        ),
    },
    {
        "defect_type": DefectType.ENTITY_CONFLATION,
        "title": "Target's operating subsidiary and its holding company treated as one entity",
        "scenario_text": (
            "[SYNTHETIC] Diligence request list refers throughout to 'Acme Holdings LLC.' The credit "
            "agreement attached in response is signed by 'Acme Operating Co., Inc.', a wholly owned "
            "subsidiary of Acme Holdings LLC with its own separate liabilities."
        ),
        "expected_assertion": (
            "The credit agreement produced in response to a request about Acme Holdings LLC is actually "
            "an obligation of its subsidiary, Acme Operating Co., Inc. - a distinct legal entity - and "
            "should not be read as Acme Holdings LLC's own direct liability without clarification."
        ),
    },
    {
        "defect_type": DefectType.MODALITY_ESCALATION,
        "title": "A conditional letter of intent restated as a signed, binding commitment",
        "scenario_text": (
            "[SYNTHETIC] Draft Letter of Intent: 'Buyer may, subject to further diligence and financing, "
            "elect to proceed with the acquisition on substantially these terms.' Deal summary memo: "
            "'Buyer has committed to acquire the company on these terms.'"
        ),
        "expected_assertion": (
            "The deal summary memo describes the buyer as having 'committed' to the acquisition, but the "
            "underlying letter of intent is explicitly conditional and non-binding ('may elect to proceed, "
            "subject to further diligence and financing') - the memo escalates a conditional statement into "
            "a firm commitment."
        ),
    },
    {
        "defect_type": DefectType.UNSUPPORTED_ASSERTION,
        "title": "A claimed customer-concentration figure has no supporting citation",
        "scenario_text": (
            "[SYNTHETIC] Investment memo: 'No single customer represents more than 10% of revenue, per the "
            "customer ledger.' The cited customer ledger workbook contains customer names and total billings "
            "but no revenue-share or percentage-of-total column, and no row reaches any conclusion about "
            "concentration."
        ),
        "expected_assertion": (
            "The investment memo's customer-concentration claim ('no single customer represents more than "
            "10% of revenue') cites the customer ledger, but that ledger contains no percentage-of-revenue "
            "figures at all - the specific 10% claim is not actually supported by the cited source."
        ),
    },
    {
        "defect_type": DefectType.STALENESS,
        "title": "A published finding still cites a document version that has since been superseded",
        "scenario_text": (
            "[SYNTHETIC] A workspace finding cites 'Term Sheet v1, Section 2.1' for a $50,000,000 purchase "
            "price. Term Sheet v2 was uploaded two weeks later and changes Section 2.1's purchase price to "
            "$55,000,000; the finding has not been reviewed since."
        ),
        "expected_assertion": (
            "This finding's cited passage (Term Sheet v1, Section 2.1) has been superseded by Term Sheet v2, "
            "which states a different purchase price for the same clause - the finding should be reassessed "
            "against the current version before being relied on."
        ),
    },
    {
        "defect_type": DefectType.LOGICAL_CONTRADICTION,
        "title": "Exclusivity clause contradicted by a disclosed side agreement",
        "scenario_text": (
            "[SYNTHETIC] Purchase Agreement, Section 5.3: 'Seller shall not, during the Exclusivity Period, "
            "solicit, negotiate, or enter into any agreement with any third party regarding a sale of the "
            "Company.' Disclosure Schedule 5.3(a), dated during the same Exclusivity Period: 'Seller entered "
            "into a non-binding term sheet with Third Party X regarding a potential sale of the Company.'"
        ),
        "expected_assertion": (
            "The Disclosure Schedule states that the seller entered into a term sheet with a third party "
            "regarding a sale of the company during the same period the Purchase Agreement's exclusivity "
            "clause prohibits exactly that - the two documents cannot both be accurate as written, "
            "regardless of numeric tolerance."
        ),
    },
    {
        "defect_type": DefectType.COMPARATOR_SPECIFICITY_MISMATCH,
        "title": "A single quarter's growth rate compared against a full-year peer average",
        "scenario_text": (
            "[SYNTHETIC] Pitch deck: 'Target's 34% revenue growth outpaces the industry average of 12%.' "
            "The 34% figure is Q4-over-Q3 sequential growth (per the underlying financial model); the cited "
            "12% industry figure is a trailing-twelve-month year-over-year average."
        ),
        "expected_assertion": (
            "The pitch deck compares the target's single-quarter sequential growth rate (34%) directly "
            "against an industry figure that is a trailing-twelve-month year-over-year average (12%) - "
            "the two rates measure different things and are not a like-for-like comparison."
        ),
    },
]


def _seed_defaults() -> None:
    if list_cases(include_superseded=True):
        return
    for seed in _SEED_CASES:
        create_case(
            defect_type=seed["defect_type"],
            title=seed["title"],
            scenario_text=seed["scenario_text"],
            expected_assertion=seed["expected_assertion"],
            provenance="synthetic",
            notes="Seeded default golden case (Task 16.1).",
        )
