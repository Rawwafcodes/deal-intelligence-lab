# Data Model

Conventions carried forward from the existing codebase because they've proven out
over nine milestones: one module per concern, a dataclass + `init_*_db()` +
`to_dict()` per record type, `uuid.uuid4().hex` primary keys, ISO-8601 UTC timestamp
strings, immutable-by-convention audit rows. This document specifies the *records
and relationships*; which physical database engine they live on is
`06-architecture-and-infrastructure.md`'s decision, not this one — the shapes below
work on SQLite or Postgres unchanged.

## Why identity stability gets its own section first

This is the most consequential correctness question in the whole plan, so it's
addressed before the record list, not buried inside it.

**The problem, confirmed by direct inspection** (see `01-baseline-inventory.md`, gap
#1): `evaluations.extract_findings()` assigns each finding's `index` as its raw
position in the parser's output (`"index": len(findings)`), and
`workspaces.py` stores that position, permanently, as the finding's entire identity
(`f"ai-{index}"`). AI content is correctly never copied into storage — it's
re-derived from the immutable `segments` blob on every read — but that means the
*only* thing binding a human's review ("Accepted, owner J. Chen, severity
downgraded to High") to a specific finding is trusting that re-running the parser
today produces the same *n*-th item it produced when the workspace was created. A
parser improvement — fixing a mis-parsed bullet, splitting a merged finding, editing
the extraction to skip a spuriously-captured header line — silently and permanently
reattaches every stored review to a *different* finding, the next time anyone opens
that workspace. There is currently no way to even detect this happened.

**The fix: content-addressed identity, not positional identity, with explicit drift
handling.**

1. At extraction time, compute a stable fingerprint for each finding — a SHA-256
   hash over a normalized version of its `raw_text` (the exact bullet block the
   parser captured, whitespace-collapsed). This is deterministic for identical
   input and independent of *where* in the list the finding happens to fall.
2. A finding's public identity becomes `{run_id}:{fingerprint}`, not
   `{run_id}:{index}`. `run_id` scopes it to the specific run that produced it
   (never two different runs sharing an identity by coincidence); the fingerprint
   scopes it to its actual content.
3. Every extraction is tagged with an `extraction_version` — an integer bumped
   whenever `evaluations.py`'s parsing logic changes in any way that could alter
   what gets extracted or how a fingerprint is computed. This mirrors a pattern the
   codebase already uses and trusts (`cross_format_analysis.MANDATE_VERSION`,
   `xlsx_inspection.MANDATE_VERSION` — bumped whenever prompt text changes
   materially, exactly so stored records stay traceable to what produced them).
4. On read, re-run the parser at the *current* `extraction_version`, compute
   fingerprints for the fresh output, and match against stored review rows by
   fingerprint. Three outcomes, all explicit:
   - **Fingerprint matches a stored row exactly** → normal path, review state
     applies as before.
   - **A fresh finding has no matching stored row** → it's new; materialize a fresh,
     unreviewed row for it (this already happens today for a workspace's very first
     read — no change in behavior for the common case).
   - **A stored row's fingerprint matches no fresh finding** → the underlying
     content this review was about is gone from the current extraction. **Never**
     silently drop the review state and **never** silently reattach it to
     whatever's now sitting at the same position. Mark the row `orphaned:
     extraction_version_mismatch`, keep every field on it (title, review status,
     notes, audit history) exactly as it was, surface it in the UI as "needs
     re-linking," and require a human to either confirm a specific new finding is
     the same one (recording that confirmation as its own audit event) or
     explicitly accept that it no longer applies.
5. Migration for already-existing Milestone 9 workspaces (like the real Universal
   Logic one): on first read under the new scheme, compute fingerprints for the
   *current* parser's output against the *currently stored* `ai-{index}` rows using
   position as a one-time best-effort bridge (today's parser hasn't changed, so
   position-based matching is still correct *right now* — the fix is about
   preventing this from silently breaking on the *next* parser change, not claiming
   today's data is already wrong). Store the computed fingerprint onto each existing
   row as part of this one-time backfill. From that point on, identity is
   fingerprint-based going forward.

This is scoped as its own early coding mandate in the roadmap (part of Milestone
11), not bundled into a larger change, specifically so it can be verified in
isolation: extract the same segments twice, confirm identical fingerprints; hand-edit
a copy of the parser to reorder its output, confirm review state follows content, not
position, and confirm a genuinely-removed finding is flagged rather than silently
reassigned.

## Records

For each: what it is, whether it already exists (and where), what changes.

### Organization / team
**New.** A deal belongs to exactly one organization. Minimal fields: id, name,
created_at. Exists purely so Milestone 12's permission model has a top-level
isolation boundary (see `05-permissions-and-security.md`) — a single-organization
deployment (the likely Milestone 13 pilot shape) just has one row here.

### User and deal membership
**New.** `User`: id, email, display name, created_at — no password field in this
schema; Milestone 12 decides the auth mechanism (see architecture doc) and this
table only needs to reference whatever identity that mechanism issues.
`DealMembership`: (deal_id, user_id, role, added_at, removed_at nullable) — role is
one of `deal_lead` / `analyst` / `read_only_reviewer` (the permission matrix in
`05-permissions-and-security.md`). `removed_at` (not a hard delete) is required by
the assignment's "member removal and access revocation" concern — a removed
member's own audit-trail rows must survive their removal.

### Deal
**Extends `store.Project`.** Reuse the existing table and add columns rather than
create a parallel concept — a `Project` already is "a place documents and analyses
belong to"; a `Deal` is that same thing with an organization, membership, and a
brief attached. Add: `organization_id`, `status` (e.g. `active` / `closed` /
`archived`).

### Deal brief and brief version
**New.** `DealBrief`: id, deal_id. `DealBriefVersion`: id, brief_id, version_number,
content (structured: counterparty, transaction type, target description, key dates
— free text is fine for v1, structure can tighten later), author_user_id,
created_at. Versioned from the start, matching the memo's proven
edit/approve/version pattern from Milestone 9 — a brief is exactly "who and what the
transaction concerns," never evidence, never auto-verified (per the assignment's
explicit distinction: *"a user-entered statement is context, not automatically
verified evidence"*).

### Workstream
**New.** id, deal_id, name, description, created_by, created_at. A configurable
grouping, not a hardcoded enum of five specialist areas — matches the assignment's
explicit instruction not to claim full-coverage review methods exist.

### Source document and immutable document version
**Extends `documents.py`.** Today's `Document` row becomes the *parent* record
(filename lineage, project/deal association); add `DocumentVersion`: id,
document_id, version_number, storage_path_or_key, sha256, size_bytes, uploaded_by,
uploaded_at, superseded_at (nullable). Every citation, every analysis input
manifest (below), and every export references a specific `document_version_id`,
never a bare `document_id` — this is what makes "revisit affected conclusions when
evidence changes" (workflow step 10) possible: a new version doesn't retroactively
change what an old finding cited.

### Work product and immutable submission version
**New.** `WorkProduct`: id, deal_id, workstream_id, title, owner_user_id. 
`Submission`: id, work_product_id, version_number, storage_path_or_key, sha256,
submitted_by, submitted_at. Deliberately mirrors `DocumentVersion`'s shape —
submissions are evidence-like in that they're immutable once made and get reviewed
against sources, but they are analyst *output*, never treated as deal-room evidence
themselves (the assignment's explicit distinction between source material and work
product).

### Mandate and mandate version
**Extends the existing `MANDATE_VERSION` convention**, made a first-class,
queryable record instead of a bumped module constant. `Mandate`: id, kind
(`investigation` | `submission_review`), name. `MandateVersion`: id, mandate_id,
version_number, prompt_text, structure_instructions, created_at. Every analysis run
(below) records exactly which `mandate_version_id` it used — today this is a bare
version-number string on the analysis row; this makes the actual prompt text
retrievable for any historical run, which matters once the mandate text itself
starts changing across a live deal's lifetime.

### Analysis job/run and input manifest
**Extends `cross_format_analyses` / `xlsx_inspections` / `cross_analyses` /
`inspections`.** These four existing tables collapse into one `AnalysisRun`
concept: id, deal_id, mandate_version_id, kind (`investigation` |
`submission_review`), status, triggered_by_user_id, started_at, completed_at,
model, stop_reason, input_tokens, output_tokens, cost_usd (new — see background-job
requirements), segments (immutable raw output, unchanged), extraction_version. A
new `AnalysisRunInput` table replaces the current flat
`pdf_document_ids_json`/`excel_document_ids_json` columns: (run_id,
document_version_id **or** submission_id, role) — an explicit manifest of exactly
which *version* of which document or submission a run consumed, which is required
for "every run must record exactly which document, brief, mandate and submission
versions it used" and for change-aware reassessment (a new document version
invalidates only the runs whose manifest references the version it replaced).

### Finding observation and tracked issue
**Extends `workspace_findings`**, split into two layers to satisfy "findings from
separate runs must remain distinct source observations... linking related findings
into one tracked issue must preserve their origins":
- `FindingObservation` — what exists today, scoped per-run: fingerprint-based
  identity (above), origin (`ai` | `human`), the content fields, evidence/citations,
  `analysis_run_id`.
- `TrackedIssue` — new, deal-scoped: id, deal_id, title, status. A tracked issue
  points at one or more `FindingObservation`s through a join table
  (`tracked_issue_observations`: tracked_issue_id, observation_id, is_canonical,
  linked_by_user_id, linked_at). This *is* Milestone 9's duplicate-marking model,
  generalized: today `duplicate_of` only links two AI-origin observations within one
  workspace; a `TrackedIssue` links any number of observations from *any* run
  (investigation or submission-review, this month or last), across the whole deal,
  the same way — nothing merges or deletes, linking always requires the explicit
  human action the assignment demands, and un-linking is always possible without
  destroying the observations.

### Review decision
**Extends the review-status fields on `workspace_findings`**, made its own
append-only table rather than mutable columns, so decision *history* survives a
later decision: id, target_type (`finding_observation` | `tracked_issue` |
`submission`), target_id, decision_type (`review_status` | `severity_adjustment` |
`resolution_status` | `closure_approval` | `residual_risk_accepted`), value, actor
user_id, rationale text, evidence_version_ids (nullable, references the specific
document/submission versions the decision relied on), created_at. This is what
makes "when evidence changes, retain historical approval but flag its applicability
for reassessment" possible — the old `ReviewDecision` row is never edited or
deleted; a new row records the reassessment, and both remain visible in order.

### Task / comment
**New.** `Task`: id, deal_id, workstream_id (nullable), title, assigned_to_user_id,
status, related_finding_or_issue_id (nullable), created_by, created_at.
`Comment`: id, deal_id, target_type, target_id, body, author_user_id, created_at.
Generic enough to attach to a finding, a tracked issue, a submission, or a task
itself.

### Information request / response
**Extends `workspace_requests`** almost unchanged — already deal-shaped, not
analysis-shaped, in its current form. Add `deal_id` (currently implicit via
`workspace_id`), and split the assignment's distinct "response received / evidence
received / evidence reviewed" states into the same `ReviewDecision` table above
(target_type = `information_request`) rather than duplicating a second bespoke
status enum.

### Memo version and approval
**Extends `workspace_memos`** almost unchanged — the generate/edit/approve/
edit-reverts-to-draft lifecycle already works exactly as specified. Change: make it
explicitly versioned (`MemoVersion`, version_number, superseded_at) and deal-scoped
instead of analysis-workspace-scoped, so a deal can carry an approved memo forward
across many investigation and submission-review runs, with history of every prior
approved version retained.

### Audit event
**Extends `workspace_audit_log`** directly — already generic enough
(workspace_id/event_type/entity_type/entity_id/detail_json). Change: `deal_id`
instead of `workspace_id` as the scope key, and add `actor_user_id` (today's local
single-user app has no actor to record).

## Deal-level workspace compatibility with existing Milestone 9 records

The assignment requires this get special attention because Milestone 9 creates one
workspace per analysis. The approach:

- A `Deal` (extended `Project`) gains at most one **deal workspace** — a thin new
  record, not a rebuild of what exists: id, deal_id, created_at.
- Every existing per-analysis `Workspace` (Milestone 9's `workspaces` table) gains a
  nullable `deal_workspace_id` foreign key. **Existing rows are backfilled, not
  reinterpreted**: for each existing `Workspace`, create (or attach to) the one deal
  workspace for its project, and set the foreign key. No existing `workspace_id`
  changes, no existing URL (`/workspace.html?project=...&workspace=...`) breaks —
  it keeps rendering the exact same per-run view it does today.
- `TrackedIssue` and the deal-lead overview both query *across* every
  `FindingObservation` whose run belongs to the deal workspace, regardless of which
  per-analysis `Workspace` originally held it — this is what "one connected findings
  experience, not separate competing registers" means concretely: a new deal-level
  view is additive, and the existing per-analysis view keeps working unmodified for
  anyone who still has that link.
- The real Universal Logic workspace goes through exactly this backfill in
  Milestone 11's first coding mandate's acceptance check (open the existing project,
  confirm its Milestone 9 workspace and all 33+1 findings are still reachable
  exactly as before, *and* now also visible from the new deal-level view) —
  read-only verification, no data mutated beyond adding the new foreign-key/backfill
  rows themselves.

## What already exists vs. what's genuinely new — summary table

| Record | Status |
| --- | --- |
| Organization/team | New |
| User, deal membership | New |
| Deal | Extends `store.Project` |
| Deal brief, brief version | New |
| Workstream | New |
| Source document | Extends `documents.Document` |
| Document version | New |
| Work product | New |
| Submission version | New |
| Mandate, mandate version | New table; extends the existing `MANDATE_VERSION` convention |
| Analysis run | Extends/unifies `cross_format_analyses`/`xlsx_inspections`/`cross_analyses`/`inspections` |
| Analysis run input manifest | New |
| Finding observation | Extends `workspace_findings`, fingerprint identity instead of index |
| Tracked issue | New; generalizes Milestone 9's duplicate-marking |
| Review decision | New; makes today's mutable status columns append-only history |
| Task, comment | New |
| Information request/response | Extends `workspace_requests` |
| Memo version, approval | Extends `workspace_memos` |
| Audit event | Extends `workspace_audit_log` |
