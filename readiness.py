"""Readiness checklist assessment (roadmap M14.4: "Readiness template:
checklist scope explicit; no claim of universal completeness"). Pure
assessment logic (no database access) - `readiness_assessments.py`
persists the record this module's outcome produces, and `mandates.py`'s
`readiness.assess_scope` capability composes the two, mirroring how
`decision_package.py`/`deliverables.py` and `integrity_review.py`/
`integrity_reviews.py` are each split.

Genuinely different in kind from every other registered capability so
far: this one makes **no external call at all** - `side_effect_class`
is `"read_only"`, the first real (non-fixture) use of that class. A
readiness checklist is exactly the kind of thing docs/workspace-shift/
docs/07-architecture.md already warns against paying for ("No paid AI to
compute basic dashboard counts") - every item here is a deterministic
read of already-persisted, already-real state, the same discipline
`workspaces._generate_memo_content` already established for the
executive memo ("Deterministic synthesis... no Anthropic call, no
free-text generation").

Scope, explicit and bounded (the roadmap's own "checklist scope
explicit; no claim of universal completeness" - this is not a company-
wide, universally-complete "is this deal done" verdict): one workspace's
own decision-readiness - does the deal have a brief and at least one
source document, does its findings register have no open critical/high
items and nothing left unreviewed, are there no open information
requests, and has *either* the classic executive memo (Milestone 9) or a
Task 14.3 decision package actually been approved. A workspace that
passes every item is "ready to sign off," not "this deal is fully
diligenced" - the module's own `SCOPE_DESCRIPTION` states this plainly
and is carried on every persisted assessment so a reader never mistakes
the narrower claim for the broader one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SCOPE_DESCRIPTION = (
    "Checks one workspace's own decision-readiness: a deal brief exists, at least one source "
    "document has been uploaded, no open critical/high finding remains, no finding is left "
    "unreviewed, no information request is still awaiting a response, and either the executive "
    "memo or a decision package for this workspace has been approved. This is not a claim that "
    "the underlying deal, transaction, or diligence effort is complete in any broader sense - "
    "only that this one checklist, scoped exactly as described here, currently passes or does not."
)

# Ordered, named, and documented - the whole point of "checklist scope
# explicit" is that nothing here is a hidden or inferred criterion.
CHECKLIST_ITEM_LABELS: dict[str, str] = {
    "has_brief": "The project has a deal brief",
    "has_documents": "At least one source document has been uploaded",
    "no_open_critical_or_high_findings": "No critical or high-severity finding remains open",
    "no_unreviewed_findings": "Every finding has been explicitly reviewed",
    "no_open_information_requests": "No information request is awaiting a response",
    "position_approved": "The executive memo or a decision package for this workspace has been approved",
}
CHECKLIST_ITEM_ORDER = tuple(CHECKLIST_ITEM_LABELS.keys())


@dataclass
class ChecklistItem:
    key: str
    label: str
    met: bool
    detail: str

    def to_dict(self) -> dict:
        return {"key": self.key, "label": self.label, "met": self.met, "detail": self.detail}


@dataclass
class ReadinessAssessment:
    ready: bool
    scope_description: str
    items: list[ChecklistItem] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ready": self.ready,
            "scope_description": self.scope_description,
            "items": [i.to_dict() for i in self.items],
        }

    @property
    def unmet_items(self) -> list[ChecklistItem]:
        return [i for i in self.items if not i.met]


def assess_readiness(
    *,
    has_brief: bool,
    has_documents: bool,
    findings: list[dict[str, Any]],
    open_request_count: int,
    memo_approved: bool,
    deliverable_approved: bool,
) -> ReadinessAssessment:
    """Pure function - every input is a plain value or a list of already-
    merged finding dicts (the same shape `workspaces.list_findings`
    returns), never a database handle or a domain object this module
    would need to import other modules to understand. `findings` is
    expected to already exclude duplicates (the caller's job, matching
    `_generate_memo_content`'s own convention)."""
    open_critical_high = [
        f for f in findings
        if (f.get("effective_severity") or "").lower() in ("critical", "high")
        and f.get("resolution_status") not in ("resolved", "accepted_risk")
    ]
    unreviewed = [f for f in findings if f.get("review_status") == "unreviewed"]

    items = [
        ChecklistItem(
            key="has_brief", label=CHECKLIST_ITEM_LABELS["has_brief"], met=has_brief,
            detail="A deal brief exists." if has_brief else "No deal brief has been recorded yet.",
        ),
        ChecklistItem(
            key="has_documents", label=CHECKLIST_ITEM_LABELS["has_documents"], met=has_documents,
            detail="At least one document is on file." if has_documents else "No document has been uploaded yet.",
        ),
        ChecklistItem(
            key="no_open_critical_or_high_findings",
            label=CHECKLIST_ITEM_LABELS["no_open_critical_or_high_findings"],
            met=not open_critical_high,
            detail=(
                "No open critical or high-severity finding." if not open_critical_high
                else f"{len(open_critical_high)} open critical/high finding(s): "
                     + "; ".join(f["title"] for f in open_critical_high)
            ),
        ),
        ChecklistItem(
            key="no_unreviewed_findings", label=CHECKLIST_ITEM_LABELS["no_unreviewed_findings"],
            met=not unreviewed,
            detail=(
                "Every finding has been reviewed." if not unreviewed
                else f"{len(unreviewed)} finding(s) not yet reviewed: " + "; ".join(f["title"] for f in unreviewed)
            ),
        ),
        ChecklistItem(
            key="no_open_information_requests", label=CHECKLIST_ITEM_LABELS["no_open_information_requests"],
            met=open_request_count == 0,
            detail=(
                "No information request is awaiting a response." if open_request_count == 0
                else f"{open_request_count} information request(s) still awaiting a response."
            ),
        ),
        ChecklistItem(
            key="position_approved", label=CHECKLIST_ITEM_LABELS["position_approved"],
            met=memo_approved or deliverable_approved,
            detail=(
                "An executive memo has been approved for this workspace." if memo_approved
                else "A decision package has been approved for this workspace." if deliverable_approved
                else "Neither an executive memo nor a decision package has been approved yet."
            ),
        ),
    ]

    return ReadinessAssessment(ready=all(i.met for i in items), scope_description=SCOPE_DESCRIPTION, items=items)
