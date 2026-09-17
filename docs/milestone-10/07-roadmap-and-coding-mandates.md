# Roadmap and Coding Mandates

No calendar dates, per instructions. Each mandate is independently specified —
do not execute more than one without the founder reviewing the result of the
previous one first, even within the same numbered milestone.

---

## Milestone 9 closeout

Not new work — closing out what `01-baseline-inventory.md` found, recorded
separately from Milestone 11's new work as instructed.

- **9.1 — Reproducible-baseline confirmation.** Already done this session (isolated
  worktree at `fd59122`, 333 tests, mypy clean on 43 files) and recorded in
  `01-baseline-inventory.md`. No further action unless the founder wants it
  re-run after the four still-uncommitted files from the other session land.
- **9.2 — Targeted regressions.** Add the two missing regression tests identified
  in the baseline inventory (`adjusted_severity` null-vs-empty-string;
  workspace-summary refresh after request mutation) — blocked on Milestone 12's
  test-tooling decision for the frontend half of each, since no JS test runner
  exists yet; the backend halves can be added independently sooner.
- **9.3 — Accessibility fix.** Replace `role="button"` on `<tr>` in
  `static/workspace.js` with a real focusable, correctly-announced control
  (e.g. a `<button>` wrapping the expand affordance, or restructure the row as
  `role="row"` with a nested `role="button"` cell) — small, isolated, its own
  before/after accessibility-tree check.
- **9.4 — Verification-record identification plan.** A separately approved plan
  for what to do with the verification-only state left in the real Universal
  Logic workspace (full list of affected rows already recorded in
  `01-baseline-inventory.md`). **No cleanup happens until the founder picks an
  approach and approves it** — this is on the decision list in
  `00-executive-summary.md`.
- **9.5 — Formula-injection fix.** Neutralize `=`/`+`/`-`/`@`-leading values
  across every exported free-text field in `workspace_exports.py` — see
  `05-permissions-and-security.md`. Small, isolated, testable with a single new
  test asserting an exported cell containing `=1+1` round-trips as text, not a
  live formula.

---

## Milestone 11 — Deal-level workspace foundation

Versioned deal brief, workstreams, stable finding identity, links to existing
Milestone 9 records. **No paid AI calls, no cloud migration, anywhere in this
milestone.**

### 11.1 — First coding mandate: the narrow vertical slice

**User outcome.** A user can open an existing project, create and edit a
versioned deal brief for it, create a workstream, associate an existing
document and an existing finding with that workstream, reload the page, and see
all of it still there — proving the new deal-level persistence layer actually
persists, without touching AI, hosting, or auth.

**Dependencies.** None beyond the current committed baseline (`fd59122`).

**Scope.**
- New tables: `deal_briefs`, `deal_brief_versions`, `workstreams`,
  `deal_workspaces` (per `03-data-model.md`), plus the `deal_workspace_id`
  backfill column on the existing `workspaces` table.
- New module `deals.py` (or extend `store.py` — implementer's call, follow
  existing one-module-per-concern convention) with the usual
  dataclass/`init_*_db()`/`to_dict()` shape.
- New endpoints: create/get deal brief, create/update brief version (draft
  only — no approve step needed for this slice), create/list workstreams,
  associate a document with a workstream, associate a finding with a
  workstream.
- New minimal UI: a "Deal Brief" section and a "Workstreams" section on (or
  linked from) the existing `project.html`, following existing
  `static/*.html`/`.js` conventions exactly (per the frontend-direction call in
  `01-baseline-inventory.md`, this slice stays on the static pattern — no
  framework decision needed or made here).
- The backfill: on first read of a project that already has a Milestone 9
  workspace, create its `deal_workspace_id` link automatically (idempotent,
  same pattern as `get_or_create_workspace`).

**Exclusions.** No AI calls of any kind. No brief *approval* lifecycle (draft
editing only — approval mirrors the memo's proven pattern and is a natural
11.2, not needed to prove persistence). No workstream task/comment/submission
records yet (that's 13.x, once there's a second person to coordinate with). No
auth (single implicit local actor, same as today).

**Existing components reused.** `store.get_connection()`; the
`Workspace`/`get_or_create_workspace` pattern as the direct template for
`DealWorkspace`; `evaluations.list_findings`-equivalent read path to resolve
"an existing finding" for the association step; the existing project-ownership
check pattern (`_get_owned_workspace`-shaped) for the new endpoints.

**Data/API/UI changes.** Additive only — no existing table's schema changes
shape (only the new nullable `deal_workspace_id` column is added to
`workspaces`), no existing endpoint's request/response shape changes, no
existing static page's current behavior changes except the new section being
appended.

**Tests and browser acceptance scenario.**
- Unit tests: brief/version CRUD, workstream CRUD, document/finding
  association, backfill idempotency (calling it twice doesn't create two deal
  workspaces for one project — same idempotency test shape as
  `test_reopening_is_idempotent_and_does_not_duplicate_findings` in
  `tests/test_workspaces.py`).
- HTTP integration tests: same real-server-thread-plus-temp-DB pattern as
  `tests/test_workspace_endpoints.py`; forged-ID and cross-project rejection
  tests for every new endpoint, matching the existing convention exactly.
- Browser acceptance (against the real Universal Logic project specifically,
  read-only beyond the new records this mandate itself creates): open
  `project.html?id=e32167f6062f45d999259a360c1f04f9`, create a brief version,
  create a workstream, associate the existing Milestone 9 workspace's `ai-0`
  finding and one existing document with it, **reload the page**, confirm
  everything is still there, and confirm the existing Milestone 9
  `/workspace.html` view for that project is completely unaffected (same 33+1
  findings, same review state, same URL).

**Migration and rollback.** New tables only (`CREATE TABLE IF NOT EXISTS`,
matching every existing `init_*_db()`); rollback is dropping the new tables and
the new nullable column — no existing data is ever rewritten, only backfilled
additively.

**Paid AI / cloud approval.** Not applicable — none used.

**Evidence needed to claim completion.** Test output (count of new tests, all
passing, full suite still green), mypy clean, and screenshots/transcript of the
browser acceptance scenario above including the reload step.

### 11.2 — Stable finding identity

Implements the fingerprint-based identity design in `03-data-model.md` in full:
`extraction_version` on `evaluations.py`, fingerprint computation, the
match/orphan/new-finding read-time logic, and the one-time backfill for the
real Universal Logic workspace's existing 34 rows. **Tests**: extract the same
segments twice and assert identical fingerprints; feed a hand-modified parser
output (simulating a future parser change) through the matcher and assert
existing review state follows the matching content and any content with no
match is flagged `orphaned`, never silently reattached to whatever now sits at
the same position. **Browser acceptance**: confirm the real workspace's
existing review state (the "J. Chen accepted `ai-0`" edit from Milestone 9's
verification) survives the backfill with the same fingerprint-derived identity,
read-only beyond the backfill write itself.

### 11.3 — Brief and workstream approval lifecycle

Extends 11.1's draft-only brief with the memo's proven
approve/edit-reverts-to-draft pattern, reused near-verbatim from
`workspaces.approve_memo`/`update_memo`.

---

## Milestone 12 — Shared staging foundation

Authentication, memberships, permissions, hosting, private storage, database
migration, background jobs. Split into independently verifiable mandates,
synthetic data only, staging environment only (per
`06-architecture-and-infrastructure.md`).

- **12.1 — Auth + organization + user + membership**, synthetic accounts only,
  in staging. Data/API changes per `03-data-model.md`'s `Organization`/`User`/
  `DealMembership`. Acceptance: create two synthetic users, confirm each can
  only see deals they're a member of.
- **12.2 — Permission-matrix enforcement**, per `05-permissions-and-security.md`,
  applied to every existing Milestone 9/11 endpoint. Acceptance: for each role,
  a scripted pass/fail check against every endpoint in the matrix (authorized
  action succeeds, unauthorized action is rejected server-side, not just
  hidden in the UI).
- **12.3 — Database migration to Postgres**, staging only, synthetic data,
  schema-equivalent to the SQLite baseline (same `init_*_db()`-derived shapes,
  translated). Acceptance: full test suite passes against staging Postgres,
  not just SQLite.
- **12.4 — Private object storage**, staging only, synthetic documents.
  Acceptance: upload/download round-trip with per-request membership
  re-checked, confirmed a non-member's request is rejected.
- **12.5 — Web framework migration** (`http.server` → FastAPI), route-shape
  preserving, staging first. Acceptance: existing test suite's HTTP-level
  tests pass unmodified in shape (same URLs, same status codes, same JSON
  shapes) against the new framework.
- **12.6 — Background job infrastructure**: job table, worker process, status
  polling, the full list from `06-architecture-and-infrastructure.md`
  (timeouts, cancellation, bounded retries, duplicate protection, interruption
  recovery, per-run cost tracking, spending limit). Acceptance: a
  deliberately-killed worker mid-run leaves the run `interrupted`, not
  silently retried, and a human action is required to proceed — verified by
  killing the worker process mid-test.
- **12.7 — Formula-injection fix** (carried from 9.5 if not already done) and
  **role="button" accessibility fix** (carried from 9.3 if not already done),
  verified once more in the new framework.

Each of 12.1–12.7 gets its own PR-sized change and its own acceptance check —
explicitly not one giant infrastructure change.

---

## Milestone 13 — Two-person workflow

Analyst and lead coordinate tasks, comments, versioned submissions, and human
approvals — in staging, with real (synthetic-data) multi-user behavior.

- **13.1 — Task and comment records**, attachable to a finding/tracked
  issue/submission, per `03-data-model.md`.
- **13.2 — Work product and submission-version upload**, no AI review yet —
  proves the upload/versioning mechanics alone first.
- **13.3 — Review-decision timeline UI** (the click-through in
  `04-workspace-experience.md`'s "how an issue is closed") — human-only
  actions (response received / evidence received / evidence reviewed /
  closure approved / residual risk accepted), no AI involvement yet.

**Acceptance for the whole milestone**: two separate synthetic accounts (one
`deal_lead`, one `analyst`), verifying both authorized behavior (the analyst
can submit and comment; the lead can close and approve) and unauthorized
behavior (the analyst cannot close an issue or approve a memo — server-side
rejection, not just a hidden button) end-to-end in a real browser session per
account.

---

## Milestone 14 — Submission intelligence

AI reviews submitted work against selected source versions and contributes
evidence-linked observations to the shared register. **First paid AI calls in
this roadmap since Milestone 9 — requires explicit founder approval before
running, per the authorization boundaries.**

- **14.1 — Submission-review mandate**, a new `MandateVersion`, built by
  adapting `cross_format_analysis.py`'s prompt-construction pattern (not its
  document-vs-document reconciliation framing) to a submission-vs-sources
  framing, output categorized into the five-way taxonomy from
  `02-product-direction.md`/`04-workspace-experience.md`.
- **14.2 — Wire it into the connected findings register**, tagged by
  originating run, per `04-workspace-experience.md`.

**Test data**: independently reviewed cases with a known-correct expected
categorization for each claim (mirroring the Validation Lab's proven
blind-test discipline) — **never** the Validation Lab's own private answer
keys, and never running submission-review against a `ValidationCase`'s
documents at all (the isolation boundary from
`05-permissions-and-security.md` applies here specifically).

---

## Milestone 15 — Change-aware oversight and private-pilot gate

Identify changed source versions, flag affected work, support targeted
reassessment, deal-lead overview. **This milestone ends with the private-pilot
approval gate, not an automatic transition into it.**

- **15.1 — New-document-version trigger and confirmation flow**
  ("approve analysis of a new document version," an explicit action, never
  automatic).
- **15.2 — Reassessment flagging**, per `04-workspace-experience.md`'s
  "outdated conclusion" click-through: walk `AnalysisRunInput` rows referencing
  a superseded version, flag the affected findings/memo versions
  non-destructively.
- **15.3 — Deal-lead Overview page**, the six-list layout from
  `04-workspace-experience.md`, built last (once every underlying signal it
  displays already exists from 11–15.2) rather than first, so it's assembling
  real data instead of being built ahead of what it's supposed to show.
- **15.4 — Document-format support review**: confirm which formats the first
  workflow actually needs are genuinely supported end-to-end (not just present
  in `documents.ALLOWED_EXTENSIONS`) before claiming that support anywhere in
  the product — the assignment is explicit not to quietly advertise support
  the engine lacks.
- **15.5 — Private-pilot gate review**: explicit, separate sign-off on
  permissions (12.2's checks re-verified), recovery behavior (12.6's
  interruption handling re-verified under a real, not synthetic, failure
  injection), data handling (the open items listed in
  `06-architecture-and-infrastructure.md`'s regions/backups/logs section,
  resolved by then), review quality (14.1's categorization accuracy against
  the independently-reviewed test cases), and usability (a full walkthrough of
  the ten-step workflow from `02-product-direction.md`, two real accounts, no
  scripted shortcuts) — **before**, not after, any real deal document is
  migrated anywhere.
