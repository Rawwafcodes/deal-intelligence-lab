"""M16.2: the evidence assertion ledger.

Promotes a *proven* M14.2 Integrity Review candidate - one a human has
already accepted (integrity_reviews.py's own `decision == "accepted"`,
the same event that publishes it as a real shared finding) - into a
separate, versioned ledger record. Per docs/10-decisions.md's I05 ("Persist
only material assertion snapshots actually used in real M14.2 reviews;
promote them into a reusable ledger (M16.2) only after validation - no
universal claim-store schema built ahead of evidence"), this module never
invents assertions of its own and never promotes a pending or rejected
candidate - it only re-records, in a stable and versioned form, an
assertion the M14.2 pipeline already produced and a human already
confirmed.

Per the M16.2 spec's own explicit requirement ("Never require all prose or
judgments to become rigid subject-predicate-object triples"), the
assertion's own wording is always kept as free text (`assertion_text`) -
`normalized_fields` is an optional, freeform dict for whatever structured
facts a caller chooses to attach (an amount, a date, a currency code), not
a mandated schema every assertion must fit.

Versioning follows the same stable-key-plus-incrementing-version pattern
as golden_set.py/documents.py: `entry_key` is the ledger record's stable
identity (per the spec, "separate from content hashes" - it is a fresh
uuid, never derived from the assertion's own text, so a later correction
to the wording doesn't change what identifies "the same claim").
Confirming or disputing an entry creates a new version rather than
mutating the old one, so a decision made against a specific version stays
reproducible.

M16.5 ("Incremental evaluation... Cache only when source/version/prompt/
model identity makes reuse valid and auditable") is implemented here by
reuse, not new machinery: `promote_candidate` records each source
document/version pair as a real Task-15.1 leaf dependency edge
(`version_dependencies.record_dependencies`), keyed on the entry's own
stable `entry_key` - so the exact same, already-proven
`mark_superseded` staleness mechanism every other dependent in this app
already relies on picks up an assertion ledger entry automatically the
moment one of its source documents gets a new version, with zero new
schema. `is_stale`/`get_staleness` read that same flag back;
`is_extraction_current`/`is_reusable` add the spec's other required
axis (prompt/model identity, which `version_dependencies.py` has no
concept of) as a pure comparison against caller-supplied "what's current
now" values. Per the spec's own "Full reassessment remains an explicit
mandate," nothing here ever re-runs an extraction automatically - this
module only ever answers "is this entry still trustworthy," never "let
me go get you a fresh one."
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any

import integrity_reviews
import store
import version_dependencies

MODALITIES = ("firm", "conditional", "uncertain")
VERIFICATION_STATUSES = ("confirmed", "disputed")


class AssertionLedgerError(Exception):
    pass


class AlreadyPromotedError(AssertionLedgerError):
    pass


class CandidateNotPromotableError(AssertionLedgerError):
    pass


class LedgerEntryNotFoundError(AssertionLedgerError):
    pass


@dataclass
class AssertionLedgerEntry:
    id: str
    entry_key: str
    version_number: int
    status: str  # "active" | "superseded"
    project_id: str
    source_review_id: str
    source_candidate_id: str
    target_work_product_id: str
    target_version_id: str
    source_document_ids: list[str]
    source_version_ids: list[str]
    assertion_text: str
    language: str
    pdf_citations: list[dict[str, Any]]
    excel_citations: list[dict[str, Any]]
    normalized_fields: dict[str, Any] | None
    modality: str
    verification_status: str
    confirmed_by: str | None
    confirmed_at: str | None
    disputed_by: str | None
    disputed_at: str | None
    dispute_reason: str
    extraction_model: str
    extraction_prompt_version: str
    published_finding_id: str | None
    created_at: str

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "entry_key": self.entry_key,
            "version_number": self.version_number,
            "status": self.status,
            "project_id": self.project_id,
            "source_review_id": self.source_review_id,
            "source_candidate_id": self.source_candidate_id,
            "target_work_product_id": self.target_work_product_id,
            "target_version_id": self.target_version_id,
            "source_document_ids": self.source_document_ids,
            "source_version_ids": self.source_version_ids,
            "assertion_text": self.assertion_text,
            "language": self.language,
            "pdf_citations": self.pdf_citations,
            "excel_citations": self.excel_citations,
            "normalized_fields": self.normalized_fields,
            "modality": self.modality,
            "verification_status": self.verification_status,
            "confirmed_by": self.confirmed_by,
            "confirmed_at": self.confirmed_at,
            "disputed_by": self.disputed_by,
            "disputed_at": self.disputed_at,
            "dispute_reason": self.dispute_reason,
            "extraction_model": self.extraction_model,
            "extraction_prompt_version": self.extraction_prompt_version,
            "published_finding_id": self.published_finding_id,
            "created_at": self.created_at,
        }


def init_assertion_ledger_db() -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS assertion_ledger_entries (
                id TEXT PRIMARY KEY,
                entry_key TEXT NOT NULL,
                version_number INTEGER NOT NULL,
                status TEXT NOT NULL,
                project_id TEXT NOT NULL,
                source_review_id TEXT NOT NULL,
                source_candidate_id TEXT NOT NULL,
                target_work_product_id TEXT NOT NULL,
                target_version_id TEXT NOT NULL,
                source_document_ids_json TEXT NOT NULL,
                source_version_ids_json TEXT NOT NULL,
                assertion_text TEXT NOT NULL,
                language TEXT NOT NULL DEFAULT 'en',
                pdf_citations_json TEXT NOT NULL DEFAULT '[]',
                excel_citations_json TEXT NOT NULL DEFAULT '[]',
                normalized_fields_json TEXT,
                modality TEXT NOT NULL,
                verification_status TEXT NOT NULL,
                confirmed_by TEXT,
                confirmed_at TEXT,
                disputed_by TEXT,
                disputed_at TEXT,
                dispute_reason TEXT NOT NULL DEFAULT '',
                extraction_model TEXT NOT NULL,
                extraction_prompt_version TEXT NOT NULL,
                published_finding_id TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assertion_ledger_entry_key ON assertion_ledger_entries(entry_key)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assertion_ledger_project ON assertion_ledger_entries(project_id)"
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_assertion_ledger_candidate "
            "ON assertion_ledger_entries(source_candidate_id)"
        )
        conn.commit()
    finally:
        conn.close()


def _row_to_entry(row) -> AssertionLedgerEntry:
    return AssertionLedgerEntry(
        id=row["id"],
        entry_key=row["entry_key"],
        version_number=row["version_number"],
        status=row["status"],
        project_id=row["project_id"],
        source_review_id=row["source_review_id"],
        source_candidate_id=row["source_candidate_id"],
        target_work_product_id=row["target_work_product_id"],
        target_version_id=row["target_version_id"],
        source_document_ids=json.loads(row["source_document_ids_json"]),
        source_version_ids=json.loads(row["source_version_ids_json"]),
        assertion_text=row["assertion_text"],
        language=row["language"],
        pdf_citations=json.loads(row["pdf_citations_json"]),
        excel_citations=json.loads(row["excel_citations_json"]),
        normalized_fields=json.loads(row["normalized_fields_json"]) if row["normalized_fields_json"] else None,
        modality=row["modality"],
        verification_status=row["verification_status"],
        confirmed_by=row["confirmed_by"],
        confirmed_at=row["confirmed_at"],
        disputed_by=row["disputed_by"],
        disputed_at=row["disputed_at"],
        dispute_reason=row["dispute_reason"],
        extraction_model=row["extraction_model"],
        extraction_prompt_version=row["extraction_prompt_version"],
        published_finding_id=row["published_finding_id"],
        created_at=row["created_at"],
    )


def _insert(entry: AssertionLedgerEntry) -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO assertion_ledger_entries (
                id, entry_key, version_number, status, project_id, source_review_id, source_candidate_id,
                target_work_product_id, target_version_id, source_document_ids_json, source_version_ids_json,
                assertion_text, language, pdf_citations_json, excel_citations_json, normalized_fields_json,
                modality, verification_status, confirmed_by, confirmed_at, disputed_by, disputed_at,
                dispute_reason, extraction_model, extraction_prompt_version, published_finding_id, created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entry.id, entry.entry_key, entry.version_number, entry.status, entry.project_id,
                entry.source_review_id, entry.source_candidate_id, entry.target_work_product_id,
                entry.target_version_id, json.dumps(entry.source_document_ids),
                json.dumps(entry.source_version_ids), entry.assertion_text, entry.language,
                json.dumps(entry.pdf_citations), json.dumps(entry.excel_citations),
                json.dumps(entry.normalized_fields) if entry.normalized_fields is not None else None,
                entry.modality, entry.verification_status, entry.confirmed_by, entry.confirmed_at,
                entry.disputed_by, entry.disputed_at, entry.dispute_reason, entry.extraction_model,
                entry.extraction_prompt_version, entry.published_finding_id, entry.created_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def get_entry(entry_key: str) -> AssertionLedgerEntry | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM assertion_ledger_entries WHERE entry_key = %s AND status = 'active'", (entry_key,)
        ).fetchone()
    finally:
        conn.close()
    return _row_to_entry(row) if row else None


def get_entry_history(entry_key: str) -> list[AssertionLedgerEntry]:
    conn = store.get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM assertion_ledger_entries WHERE entry_key = %s ORDER BY version_number ASC", (entry_key,)
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_entry(r) for r in rows]


def get_entry_by_candidate(source_candidate_id: str) -> AssertionLedgerEntry | None:
    conn = store.get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM assertion_ledger_entries WHERE source_candidate_id = %s AND status = 'active'",
            (source_candidate_id,),
        ).fetchone()
    finally:
        conn.close()
    return _row_to_entry(row) if row else None


def list_entries(
    project_id: str,
    *,
    target_work_product_id: str | None = None,
    verification_status: str | None = None,
    include_superseded: bool = False,
) -> list[AssertionLedgerEntry]:
    conn = store.get_connection()
    try:
        clauses = ["project_id = %s"]
        params: list[str] = [project_id]
        if not include_superseded:
            clauses.append("status = 'active'")
        if target_work_product_id is not None:
            clauses.append("target_work_product_id = %s")
            params.append(target_work_product_id)
        if verification_status is not None:
            clauses.append("verification_status = %s")
            params.append(verification_status)
        rows = conn.execute(
            f"SELECT * FROM assertion_ledger_entries WHERE {' AND '.join(clauses)} ORDER BY created_at ASC",
            tuple(params),
        ).fetchall()
    finally:
        conn.close()
    return [_row_to_entry(r) for r in rows]


def promote_candidate(
    project_id: str,
    review_id: str,
    candidate_id: str,
    *,
    modality: str = "firm",
    normalized_fields: dict[str, Any] | None = None,
    language: str = "en",
) -> AssertionLedgerEntry:
    """Promotes one already-accepted M14.2 candidate into a new ledger
    entry family (version 1). Requires `decision == "accepted"` - the same
    human act that publishes the candidate as a real shared finding - so
    every ledger entry traces back to an assertion a human has actually
    confirmed, never a raw, undecided model proposal (I05). Raises
    AlreadyPromotedError if this exact candidate already has an active
    ledger entry, rather than silently creating a duplicate family.

    `modality` classification is not attempted automatically here - that
    is semantic-review work (M16.4), not this task's. It defaults to
    "firm" and must be explicitly overridden by the caller when a
    candidate's own content (e.g. its `uncertainty` field) suggests
    otherwise.
    """
    if modality not in MODALITIES:
        raise ValueError(f"invalid modality: {modality!r}")

    review = integrity_reviews.get_integrity_review(project_id, review_id)
    if review is None:
        raise AssertionLedgerError(f"integrity review not found: {review_id!r}")
    candidate = integrity_reviews.get_candidate(review_id, candidate_id)
    if candidate is None:
        raise AssertionLedgerError(f"candidate not found: {candidate_id!r}")
    if candidate.decision != "accepted":
        raise CandidateNotPromotableError(
            f"candidate {candidate_id!r} has decision {candidate.decision!r}, not 'accepted' - "
            "only a human-accepted candidate may be promoted into the ledger"
        )
    if get_entry_by_candidate(candidate_id) is not None:
        raise AlreadyPromotedError(f"candidate {candidate_id!r} is already promoted")

    now = datetime.now(timezone.utc).isoformat()
    entry = AssertionLedgerEntry(
        id=uuid.uuid4().hex,
        entry_key=uuid.uuid4().hex,
        version_number=1,
        status="active",
        project_id=project_id,
        source_review_id=review_id,
        source_candidate_id=candidate_id,
        target_work_product_id=review.target_work_product_id,
        target_version_id=review.target_version_id,
        source_document_ids=list(review.source_document_ids),
        source_version_ids=list(review.source_version_ids),
        assertion_text=candidate.assertion,
        language=language,
        pdf_citations=list(candidate.pdf_citations),
        excel_citations=list(candidate.excel_citations),
        normalized_fields=normalized_fields,
        modality=modality,
        verification_status="confirmed",
        confirmed_by=candidate.decided_by,
        confirmed_at=candidate.decided_at,
        disputed_by=None,
        disputed_at=None,
        dispute_reason="",
        extraction_model=review.model,
        extraction_prompt_version=review.review_template_version,
        published_finding_id=candidate.published_finding_id,
        created_at=now,
    )
    _insert(entry)

    # Task 16.5: leaf dependency edges, one per source document version
    # actually consumed - keyed on the entry's own stable entry_key (not
    # this specific version's row id), so staleness persists correctly
    # across a later dispute_entry/confirm_entry version bump.
    version_dependencies.record_dependencies(
        "assertion_ledger_entry", entry.entry_key,
        [("document", doc_id, ver_id) for doc_id, ver_id in zip(entry.source_document_ids, entry.source_version_ids)],
    )
    return entry


def _retire_and_insert(current: AssertionLedgerEntry, new_version: AssertionLedgerEntry) -> None:
    conn = store.get_connection()
    try:
        conn.execute(
            "UPDATE assertion_ledger_entries SET status = 'superseded' WHERE id = %s", (current.id,)
        )
        conn.commit()
    finally:
        conn.close()
    _insert(new_version)


def dispute_entry(entry_key: str, *, disputed_by: str, reason: str) -> AssertionLedgerEntry:
    """Records a human dispute against a currently-confirmed ledger entry -
    a later reviewer or reassessment concluding the assertion is wrong,
    stale, or no longer supported. A reason is required, the same
    "no unexplained negative decision" rule reviews.py's own
    `record_decision` enforces for a return."""
    reason = reason.strip()
    if not reason:
        raise AssertionLedgerError("a reason is required when disputing a ledger entry")
    current = get_entry(entry_key)
    if current is None:
        raise LedgerEntryNotFoundError(entry_key)

    now = datetime.now(timezone.utc).isoformat()
    new_version = replace(
        current,
        id=uuid.uuid4().hex,
        version_number=current.version_number + 1,
        status="active",
        verification_status="disputed",
        disputed_by=disputed_by,
        disputed_at=now,
        dispute_reason=reason,
        created_at=now,
    )
    _retire_and_insert(current, new_version)
    return new_version


def confirm_entry(entry_key: str, *, confirmed_by: str) -> AssertionLedgerEntry:
    """Re-confirms an entry - most commonly after a prior dispute is
    resolved in the assertion's favor. Clears the prior dispute fields on
    the new current version; the disputed version itself remains fully
    readable via get_entry_history."""
    current = get_entry(entry_key)
    if current is None:
        raise LedgerEntryNotFoundError(entry_key)

    now = datetime.now(timezone.utc).isoformat()
    new_version = replace(
        current,
        id=uuid.uuid4().hex,
        version_number=current.version_number + 1,
        status="active",
        verification_status="confirmed",
        confirmed_by=confirmed_by,
        confirmed_at=now,
        disputed_by=None,
        disputed_at=None,
        dispute_reason="",
        created_at=now,
    )
    _retire_and_insert(current, new_version)
    return new_version


def get_staleness(entry_key: str) -> version_dependencies.StalenessFlag | None:
    """Task 16.5: reads back the same Task-15.1 staleness mechanism every
    other dependent in this app uses - `promote_candidate` registered
    this entry's own source document versions as leaf dependency edges,
    so this reflects a real, already-computed flag, not a fresh check."""
    return version_dependencies.get_staleness("assertion_ledger_entry", entry_key)


def is_stale(entry_key: str) -> bool:
    return get_staleness(entry_key) is not None


def is_extraction_current(entry: AssertionLedgerEntry, *, current_model: str, current_prompt_version: str) -> bool:
    """The M16.5 spec's other required cache-validity axis
    (prompt/model identity), which version_dependencies.py has no
    concept of - a pure comparison against caller-supplied "what's
    current now" values, so this module never has to import
    integrity_review.py's executor just to answer this."""
    return entry.extraction_model == current_model and entry.extraction_prompt_version == current_prompt_version


def is_reusable(entry: AssertionLedgerEntry, *, current_model: str, current_prompt_version: str) -> bool:
    """True only when BOTH of the M16.5 spec's required conditions hold:
    the entry's recorded sources are still current (no staleness flag)
    AND it was produced by a model/prompt version the caller still
    considers current. False for either reason means "don't silently
    reuse this" - a stale source calls for a real reassessment (the
    existing M15.2 flow, for whatever depends on it); a prompt/model
    mismatch means this entry doesn't represent what the current
    pipeline would produce even though none of its own sources changed,
    which calls for a fresh promotion, not force-trusting an old one.
    Never triggers either path itself - detection only, per the spec's
    own "full reassessment remains an explicit mandate.\""""
    return not is_stale(entry.entry_key) and is_extraction_current(
        entry, current_model=current_model, current_prompt_version=current_prompt_version
    )


def list_stale_entries(project_id: str) -> list[AssertionLedgerEntry]:
    """The M16.5 spec's own "reevaluate only changed assertions" query
    surface: which of this project's current ledger entries actually
    need attention, rather than a caller having to re-check everything."""
    return [entry for entry in list_entries(project_id) if is_stale(entry.entry_key)]
