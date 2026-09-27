"""Centralized deal-role authorization policy (M17 security closeout,
Task 17.14 - see docs/workspace-shift/tasks/17.14-authorization-
closeout.md and docs/workspace-shift/docs/10-decisions.md D16).

Before this task, every project-scoped route in server.py gated on
`identity.has_deal_access` alone (via `_authorized_project`/
`_get_owned_workspace`) - "is this caller an active member of this
deal at all", with no role distinction. A handful of individually
sensitive routes (grant/revoke membership, review-work-product,
integrity-candidate decisions, trigger configuration) additionally
inlined their own `identity.get_deal_role(...) in (...)` check. Both
patterns are still correct for what they check; neither expresses a
single, auditable policy, and nothing gated the many routes an
`external_executive` should never reach at all (Findings, Documents,
Work, Assertions, Readiness, Reassessments, Triggers, Mandates).

This module is the single place that answers "can this deal role do
this?" - a plain, dependency-free function of `(role, capability)`,
with no I/O and no knowledge of HTTP, so it is trivially unit-testable
against every role/capability pair without a server or a database (see
`tests/test_authz.py`). `server.py`'s `_require_capability` is the only
caller that touches identity.py/HTTP at all; everything else in this
module is pure.

Capability naming intentionally covers more ground than the founder's
own required documentation matrix's 17 named rows - a handful of
capabilities (`VIEW_REQUESTS`, `RESPOND_AS_EXTERNAL`, `VIEW_MANDATES`,
`VIEW_DECISION_PACKAGES`, `VIEW_ASSERTIONS`, `MANAGE_ASSERTIONS`,
`VIEW_TRIGGERS`) exist because the real route surface needed a finer
grain than the 17 rows alone would express (e.g. "view requests" and
"respond to requests as an external participant" are different
questions with different answers for `external_executive`). Every one
of the 17 required rows maps onto exactly one capability below; see
`docs/workspace-shift/docs/06-security-and-collaboration.md`'s matrix
table for the full row-by-row mapping and the object-level filters
(request status, deliverable status) that a boolean capability alone
cannot express.
"""

from __future__ import annotations

# -- capabilities -----------------------------------------------------------
# Plain strings, not an Enum: server.py passes these as literals at each call
# site, and a plain string keeps `tests/test_authz.py`'s table-driven tests
# and any future "explain this decision" logging trivial to read.

VIEW_DEAL = "view_deal"
VIEW_INTERNAL_DOCUMENTS = "view_internal_documents"
DOWNLOAD_DOCUMENTS = "download_documents"
VIEW_FINDINGS = "view_findings"
MANAGE_FINDINGS = "manage_findings"
VIEW_REQUESTS = "view_requests"
CREATE_REQUESTS = "create_requests"
RESPOND_AS_EXTERNAL = "respond_as_external"
VIEW_MANDATES = "view_mandates"
CREATE_MANDATES = "create_mandates"
EXECUTE_MANDATES = "execute_mandates"
VIEW_WORK_PRODUCTS = "view_work_products"
SUBMIT_WORK = "submit_work"
REVIEW_WORK = "review_work"
VIEW_DECISION_PACKAGES = "view_decision_packages"
APPROVE_PUBLISH = "approve_publish"
VIEW_INTERNAL_ACTIVITY = "view_internal_activity"
VIEW_READINESS = "view_readiness"
VIEW_REASSESSMENTS = "view_reassessments"
REQUEST_REASSESSMENT = "request_reassessment"
VIEW_ASSERTIONS = "view_assertions"
MANAGE_ASSERTIONS = "manage_assertions"
VIEW_TRIGGERS = "view_triggers"
CONFIGURE_TRIGGERS = "configure_triggers"
MANAGE_MEMBERSHIP = "manage_membership"

ALL_CAPABILITIES: tuple[str, ...] = (
    VIEW_DEAL,
    VIEW_INTERNAL_DOCUMENTS,
    DOWNLOAD_DOCUMENTS,
    VIEW_FINDINGS,
    MANAGE_FINDINGS,
    VIEW_REQUESTS,
    CREATE_REQUESTS,
    RESPOND_AS_EXTERNAL,
    VIEW_MANDATES,
    CREATE_MANDATES,
    EXECUTE_MANDATES,
    VIEW_WORK_PRODUCTS,
    SUBMIT_WORK,
    REVIEW_WORK,
    VIEW_DECISION_PACKAGES,
    APPROVE_PUBLISH,
    VIEW_INTERNAL_ACTIVITY,
    VIEW_READINESS,
    VIEW_REASSESSMENTS,
    REQUEST_REASSESSMENT,
    VIEW_ASSERTIONS,
    MANAGE_ASSERTIONS,
    VIEW_TRIGGERS,
    CONFIGURE_TRIGGERS,
    MANAGE_MEMBERSHIP,
)

# -- the matrix ---------------------------------------------------------------
# One row per deal role (identity.DEAL_ROLES), one column per capability.
# `deal_lead` is deliberately spelled out in full rather than "all True" -
# an auditor should be able to read this table without cross-referencing
# identity.DEAL_ROLES's own definition.
#
# Every False for `external_executive` traces to the founder's own
# "May not access by default" list (2026-09-27 authorization closeout
# directive); every True for `external_executive` traces to its "May
# access only" list. `reviewer`/`analyst` differences trace to the same
# directive's per-role "May"/"May not" lists, preserving every already-
# implemented narrower-than-the-table gate (e.g. only `deal_lead` may
# actually approve a decision package today - docs/06's own "Approve
# decision package: No/Recommend/Yes/Explicit grant only" row, unchanged
# by this task) rather than widening it just because the new role
# description says "reviewer... may approve... where current domain
# rules support it".

_MATRIX: dict[str, dict[str, bool]] = {
    "deal_lead": {c: True for c in ALL_CAPABILITIES},
    "reviewer": {
        VIEW_DEAL: True,
        VIEW_INTERNAL_DOCUMENTS: True,
        DOWNLOAD_DOCUMENTS: True,
        VIEW_FINDINGS: True,
        MANAGE_FINDINGS: True,
        VIEW_REQUESTS: True,
        CREATE_REQUESTS: True,
        RESPOND_AS_EXTERNAL: False,
        VIEW_MANDATES: True,
        CREATE_MANDATES: True,
        EXECUTE_MANDATES: True,
        VIEW_WORK_PRODUCTS: True,
        SUBMIT_WORK: True,
        REVIEW_WORK: True,
        VIEW_DECISION_PACKAGES: True,
        # Reviewer's "recommend" role has no dedicated approval endpoint
        # yet (disclosed since Task 14.3/17.10) - the new directive's own
        # "where current domain rules support it" qualifier means this
        # stays False, not widened.
        APPROVE_PUBLISH: False,
        VIEW_INTERNAL_ACTIVITY: True,
        VIEW_READINESS: True,
        VIEW_REASSESSMENTS: True,
        REQUEST_REASSESSMENT: True,
        VIEW_ASSERTIONS: True,
        MANAGE_ASSERTIONS: True,
        VIEW_TRIGGERS: True,
        CONFIGURE_TRIGGERS: True,
        MANAGE_MEMBERSHIP: False,
    },
    "analyst": {
        VIEW_DEAL: True,
        VIEW_INTERNAL_DOCUMENTS: True,
        DOWNLOAD_DOCUMENTS: True,
        VIEW_FINDINGS: True,
        MANAGE_FINDINGS: True,
        VIEW_REQUESTS: True,
        CREATE_REQUESTS: True,
        RESPOND_AS_EXTERNAL: False,
        VIEW_MANDATES: True,
        CREATE_MANDATES: True,
        EXECUTE_MANDATES: True,
        VIEW_WORK_PRODUCTS: True,
        SUBMIT_WORK: True,
        REVIEW_WORK: False,
        VIEW_DECISION_PACKAGES: True,
        APPROVE_PUBLISH: False,
        VIEW_INTERNAL_ACTIVITY: True,
        VIEW_READINESS: True,
        VIEW_REASSESSMENTS: True,
        REQUEST_REASSESSMENT: True,
        VIEW_ASSERTIONS: True,
        MANAGE_ASSERTIONS: True,
        VIEW_TRIGGERS: True,
        CONFIGURE_TRIGGERS: False,
        MANAGE_MEMBERSHIP: False,
    },
    "external_executive": {
        VIEW_DEAL: True,
        VIEW_INTERNAL_DOCUMENTS: False,
        DOWNLOAD_DOCUMENTS: False,
        VIEW_FINDINGS: False,
        MANAGE_FINDINGS: False,
        # Object-filtered by the caller (server.py): only requests whose
        # status is already "sent" or "answered" - see
        # `visible_request_statuses_for`.
        VIEW_REQUESTS: True,
        CREATE_REQUESTS: False,
        RESPOND_AS_EXTERNAL: True,
        VIEW_MANDATES: False,
        CREATE_MANDATES: False,
        EXECUTE_MANDATES: False,
        VIEW_WORK_PRODUCTS: False,
        SUBMIT_WORK: False,
        REVIEW_WORK: False,
        # Object-filtered by the caller: only deliverable versions whose
        # status is "approved" - see `visible_deliverable_statuses_for`.
        VIEW_DECISION_PACKAGES: True,
        APPROVE_PUBLISH: False,
        VIEW_INTERNAL_ACTIVITY: False,
        VIEW_READINESS: False,
        VIEW_REASSESSMENTS: False,
        REQUEST_REASSESSMENT: False,
        VIEW_ASSERTIONS: False,
        MANAGE_ASSERTIONS: False,
        VIEW_TRIGGERS: False,
        CONFIGURE_TRIGGERS: False,
        MANAGE_MEMBERSHIP: False,
    },
}


def has_capability(role: str | None, capability: str) -> bool:
    """The one function every authorization decision in this app should
    ultimately reduce to. `role=None` (no active deal membership at all)
    is always denied - `_authorized_project`'s existence+membership
    check runs before this and already 404s that case, but this
    function stays safe to call directly too, per "deny by default"."""
    if role is None:
        return False
    row = _MATRIX.get(role)
    if row is None:
        return False
    if capability not in row:
        raise ValueError(f"unknown capability: {capability!r}")
    return row[capability]


def capabilities_for(role: str | None) -> dict[str, bool]:
    """Every capability this role has, as a flat dict - what server.py
    hands to the frontend (Task 17.14's "expose the authenticated user's
    effective deal role and allowed capabilities") so the React app
    never re-derives the policy client-side."""
    if role is None or role not in _MATRIX:
        return {c: False for c in ALL_CAPABILITIES}
    return dict(_MATRIX[role])


# -- object-level filters -----------------------------------------------------
# A boolean capability answers "can this role reach this endpoint at all".
# These two answer the narrower "which specific objects" question the
# founder's directive requires for external_executive ("restricted to
# explicitly approved/shared material") - expressed entirely in terms of
# fields the existing data model (workspaces.REQUEST_STATUSES,
# deliverables.DELIVERABLE_STATUSES) already has, per the directive's own
# instruction not to add a new sharing subsystem.

# A request only becomes visible to an external participant once the deal
# team has actually sent it outward - "draft" is still internal-only
# drafting, matching REQUEST_STATUSES's own set exactly.
EXTERNAL_VISIBLE_REQUEST_STATUSES: frozenset[str] = frozenset({"sent", "answered"})

# A deliverable version only becomes visible to an external participant once
# it is the one a deal_lead actually approved - "draft"/"superseded" are
# internal drafting/history, matching DELIVERABLE_STATUSES's own set exactly.
EXTERNAL_VISIBLE_DELIVERABLE_STATUSES: frozenset[str] = frozenset({"approved"})


def request_visible_to(role: str | None, status: str) -> bool:
    """Whether a WorkspaceRequest in this status is visible to this role.
    Internal roles (VIEW_REQUESTS with no object restriction) see every
    request regardless of status; external_executive sees only ones
    already sent outward."""
    if not has_capability(role, VIEW_REQUESTS):
        return False
    if role == "external_executive":
        return status in EXTERNAL_VISIBLE_REQUEST_STATUSES
    return True


def deliverable_visible_to(role: str | None, status: str) -> bool:
    """Whether a DeliverableVersion in this status is visible to this
    role. Internal roles see every version (draft included, for their
    own review); external_executive sees only the currently approved
    one(s)."""
    if not has_capability(role, VIEW_DECISION_PACKAGES):
        return False
    if role == "external_executive":
        return status in EXTERNAL_VISIBLE_DELIVERABLE_STATUSES
    return True
