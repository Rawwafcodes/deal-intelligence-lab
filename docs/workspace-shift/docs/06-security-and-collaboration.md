# Collaboration and security

## Local identity
Build identities, scoped memberships and server-side authorization locally.
Development user switching is explicit, disabled outside development, loopback-only,
and absent from production routes. Store actor in a server-validated session;
do not trust a free-text owner or arbitrary user header.
Browser profiles test distinct sessions. Organization admins do not automatically gain
client-deal content rights merely by administering accounts.

## Proposed first permissions (superseded - see "Final authorization matrix" below)
**Status: historical.** This table was the pre-implementation proposal
from Task 000 ("confirm in task 000"). Task 17.14 (the M17 security
closeout, 2026-09-27) is that confirmation - it replaced plain deal-
membership gating with a centralized, capability-based policy
(`authz.py`) enforced on every route, superseding the table below.
Kept here, unmodified, as the historical record the founder's own D06
requires ("historical evidence... must remain stable") - use the final
matrix, not this one, for current behavior.

| Action | Analyst | Reviewer | Deal lead | External executive |
| --- | --- | --- | --- | --- |
| Read internal deal work | If deal member | If deal member | If deal member | Shared approved subset |
| Create mandate | Within granted capability/budget | Same | Yes within workspace policy | No by default |
| Submit work | Own/assigned | Own/assigned | Yes | No |
| Comment/respond | Authorized records | Authorized records | Yes | Shared requests only |
| Recommend finding disposition | Yes | Yes | Yes | No |
| Approve submissions | No | Assigned reviewer | Yes | No by default |
| Close material issue/accept risk | No | Recommend | Yes | No by default |
| Approve decision package | No | Recommend | Yes | Explicit grant only |
| Change access | No | No | Authorized deal management | No |

## Final authorization matrix (Task 17.14, M17 security closeout, 2026-09-27)

**Status: implemented fact.** Every cell below is enforced by
`authz.py`'s `_MATRIX` and independently re-checked by `server.py` on
its own matching route - never only by the React frontend, which
consumes the same matrix (via `GET .../overview`'s `role`/
`capabilities` fields) purely as a usability aid to hide/disable what a
role cannot do. See `authz.py`'s own module docstring for the full
capability list (more granular than this table's 17 required rows -
several rows below map onto more than one `authz.py` capability where
the real route surface needed a finer grain, e.g. "respond to requests"
covers both `CREATE_REQUESTS` (internal) and `RESPOND_AS_EXTERNAL`).

Legend: **Allowed** (unconditional) / **Denied** / **Conditional**
(depends on the specific object's own state, not just the caller's
role) / **Own-object** (restricted to something the caller authored or
is assigned) / **Shared-only** (restricted to material another human
already marked explicitly approved/sent).

| Permission | Analyst | Reviewer | Deal lead | External executive |
| --- | --- | --- | --- | --- |
| View deal | Allowed | Allowed | Allowed | Allowed (restricted-shaped: brief + approved deliverables + sent/answered requests only, via `_deal_overview_restricted`) |
| View internal documents | Allowed | Allowed | Allowed | Denied |
| Download documents | Allowed | Allowed | Allowed | Denied |
| View findings | Allowed | Allowed | Allowed | Denied |
| Create/update findings | Allowed | Allowed | Allowed | Denied |
| Create requests | Allowed | Allowed | Allowed | Denied |
| Respond to requests | Allowed (full edit) | Allowed (full edit) | Allowed (full edit) | **Shared-only + own-field**: only requests already `sent`/`answered` (`authz.request_visible_to`), and only the `management_response` field - never status, assignment, or the other internal-only fields |
| Create mandates | Allowed | Allowed | Allowed | Denied |
| Execute mandates | Allowed | Allowed | Allowed | Denied |
| View work products | Allowed | Allowed | Allowed | Denied |
| Submit work | Allowed | Allowed | Allowed | Denied |
| Review/return work | Denied | Allowed | Allowed | Denied |
| Approve/publish | Denied | Denied (still "recommend"-tier - no dedicated endpoint, unchanged since Task 14.3) | Allowed | Denied |
| View internal activity | Allowed | Allowed | Allowed | Denied (the restricted overview's own omission of `activity`/`tasks`/`mandates` is this row's real effect, not a separate check) |
| Configure triggers | Denied | Allowed | Allowed | Denied |
| Request reassessment | Allowed | Allowed | Allowed | Denied |
| Manage membership | Denied | Denied | Allowed | Denied |

Two rows the 17 required by the founder's directive don't name, added
because the real route surface needed them and because leaving them
undocumented would defeat "easy to audit":
- **View/manage decision packages**: Allowed (all statuses) for
  analyst/reviewer/deal_lead; **Conditional** for external_executive -
  only deliverable versions whose status is `approved`
  (`authz.deliverable_visible_to`), matching "explicitly approved or
  published decision packages/deliverables".
- **View assertions / manage assertions**: Allowed for analyst/
  reviewer/deal_lead; Denied for external_executive.

Job title does not confer rights. Membership, content visibility, responsibility and
approval power are distinct. Revocation stops reads, downloads, event streams and new
tool fetches. Previously transmitted provider content cannot be recalled by revocation;
record exposure and stop pending work as policy requires.

## Access enforcement
Apply checks to APIs, downloads, search, aggregates, comments, exports, jobs, citations
and AI source retrieval. Cross-workspace/deal references are rejected.
Do not leak inaccessible filenames or issue counts through overview summaries.
Attaching a private deal document to a workspace record must not widen access.
Validation answer keys are evaluator-only and never accessible to AI, including
planner context, tools, search, summaries and logging.

## Untrusted inputs
Source content is data, not authority. Restrict model tools, network/host access,
destinations and actions. Validate proposed actions server-side. Citation validity
does not defend against injected instructions. Maintain adversarial fixtures.
Render model/user text safely. Protect local mutation endpoints from cross-origin
requests and CSRF; local binding alone is not a full defense.

## Exports
Write free text as literal spreadsheet text without changing legitimate numeric/formula
fields created by the application. Test suspicious prefixes/whitespace and round-trip
cell types. Escape HTML; never export secrets or internal paths.

## Retention
Preserve cited versions by default, but do not promise indefinite retention.
Deletion policy must reconcile user obligations and evidence history. If authorized
purging removes bytes, retain a non-sensitive tombstone and indicate unavailable evidence.
Provider cleanup attempt/status is recorded; Files API deletion is not a blanket
guarantee of immediate erasure from all provider systems. Reverify terms before pilot.

## Spending and approvals
Paid execution and external transmissions require scoped approval. Templates cannot
self-authorize larger budgets. Approval applies to an exact plan/version and content
scope. Internal draft creation is distinguishable from published findings and approved
deliverables. No external messages/sends in the first implementation.
