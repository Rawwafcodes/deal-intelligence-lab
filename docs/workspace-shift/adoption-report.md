# Task 000 — Adoption Report

Executed by: the agent with live, direct access to the actual application
repository (this report closes the gap `STATUS.md` names as "not completed:
fresh inspection of the actual application"). Everything below was run
against the real repository in this session, not inferred from historical
reports.

**App revision**: `fd59122` ("Add a Reconciliations list to the project
page"), re-verified twice in this session (before and after the workspace-
shift v1.0.0 → v1.0.1 replacement) — unchanged both times.

**Dirty working tree, preserved exactly, not touched by this task**:
`cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
`tests/test_xlsx_inspection.py` (unrelated edits from a concurrent session —
same four files, same diff, both times checked) — plus this session's own
untracked `docs/` (the prior M10 planning package, cited by this package as
a historical source) and the untracked `frontend/`, `scripts/`,
`.claude/launch.json`, `CLAUDE.md`. Nothing here was reset, cleaned, or
overwritten.

**Package adopted**: `workspace-shift` v1.0.1, copied into
`docs/workspace-shift/` without its nested `.git` (per its own README
instruction). Its standalone copy at `~/Downloads/workspace-shift/` was
replaced in place, with its 3-commit git history preserved and verified as a
genuine continuation — `git merge-base --is-ancestor` confirmed the old
`HEAD` is an ancestor of the new one before anything was overwritten, and a
backup of the pre-replacement state was kept outside both repositories. No
root-level instruction file (`CLAUDE.md`; this repo has no `AGENTS.md`) was
touched.

## 1. Baseline: what `docs/02-existing-baseline.md` got right and where it's now stale

| Claim | Verdict |
| --- | --- |
| "333 at committed fd59122, mypy clean on 43 files" | **Confirmed**, re-run this session. |
| "Extra regression was in a dirty working tree" | **Confirmed and still true**: the working tree (334 tests) still contains one extra test belonging to the other session's still-uncommitted `tests/test_xlsx_inspection.py` edit. |
| "The inventory listed uncommitted analysis files and unused frontend work" | **Confirmed, unchanged**: same four files, same diff stat, both times checked in this session. |
| Known gaps list (position-based IDs, no identity model, no document versioning, inline long-running requests, missing frontend regressions, accessibility issue, formula-injection risk, test artifacts in the real workspace) | **All confirmed still present**, no code has changed since they were found. |
| "A genuine financing-room run reportedly produced 33 findings" | **Confirmed directly**, this session, by reading the real record: project `e32167f6062f45d999259a360c1f04f9`, analysis `0eb3026719504139917038fb88f8a5fb`, 33 AI findings. The workspace also still carries the verification-only state from that work: 34 finding rows (33 AI + 1 human), one duplicate marking, two non-default review states, one information request, one memo (draft, previously approved then reverted), 22 audit-log rows. Read-only re-check; nothing altered. |

No discrepancy found between the package's stated baseline and the live
repository. It correctly labeled everything as unverified secondhand claims
and was right to.

## 2. Workspace vs. Organization — resolving Task 000's point 6 precisely

Exact, code-level facts: module `workspaces.py`, dataclass `Workspace`,
SQLite table `workspaces` (primary key `id`, unique on
`cross_format_analysis_id` — one workspace per analysis run, not per deal),
exposed at `GET/POST /api/projects/{project}/workspaces/{workspace}` and
`static/workspace.html?project=...&workspace=...`. This is the *entire*
meaning of "workspace" in the codebase today — there is no team/tenant
concept anywhere to collide with, which is exactly why v1.0.1's `AGENTS.md`
rule (`Organization` for the new tenant boundary; this table becomes
`LegacyAnalysisWorkspace` in new code/docs; never rename it) is the correct
call. Nothing was renamed in this task — no implementation is authorized —
but confirmed as safe and necessary to enforce starting with task 11.1.

## 3. M11.3a spike — SQLite/WAL contention and recovery (executed, not just proposed)

Run against an isolated temp SQLite database using this app's own
`store.py`/`workspaces.py`/`cross_format_analyses.py` code paths (real
schema, real connection pattern) — never the real database. Full script and
raw output available on request; results below.

| Scenario | Threads × writes | Hold per write | Connect timeout | Journal mode | Lock errors |
| --- | --- | --- | --- | --- | --- |
| Realistic small-team load | 8 × 15 (120) | 20ms | 5.0s (app's actual default — `store.get_connection()` sets none, so Python's own default applies) | rollback (default) | **0** |
| Same load | 8 × 15 (120) | 20ms | 5.0s | WAL | **0** |
| Stress load | 20 × 15 (300) | 50ms | 5.0s | rollback | **20** |
| Same stress load | 20 × 15 (300) | 50ms | 5.0s | WAL | **19** |
| Raw behavior (no retry masking) | 8 × 15 (120) | 20ms | 0s | rollback | **105** |
| Raw behavior | 8 × 15 (120) | 20ms | 0s | WAL | **105** |

Plus, in the first (lighter) run: a deliberately-uncommitted, mid-transaction
connection was dropped without closing cleanly (simulating a crashed
process) — the next fresh connection's `PRAGMA integrity_check` returned
`ok` and the uncommitted write was confirmed **not** present (SQLite's own
atomicity held, no corruption, no partial write leaked). A plain file copy
of the live database (plus `-wal`/`-shm` siblings when in WAL mode) produced
a readable, correct backup.

**Findings, stated plainly:**
1. **At a realistic small-team load (a deal lead, one or two analysts, a
   worker process, ordinary edit pace), SQLite handles concurrent writes
   with zero errors**, using nothing more than Python's own default 5-second
   connect timeout — no code change needed to reach this.
2. **WAL mode does not meaningfully change write-write contention** — 19-20
   errors either way under the stress scenario, because SQLite only ever
   allows one writer at a time *regardless of journal mode*; WAL's actual
   benefit is letting readers proceed without blocking on a writer, which is
   a different problem than "two people editing findings at once."
3. **Under sustained heavier contention, even the default timeout eventually
   surfaces raw "database is locked" errors** — not corruption, not data
   loss, just a failed write that today's code does not retry.

**Recommendation for M11.3b and beyond**: stay on SQLite for local/pilot
development (matches the package's own local-first philosophy and this
spike's own evidence), but add a small, explicit bounded-retry-with-backoff
wrapper around the write path in `store.get_connection()`-based code before
building collaborative editing on top of it — cheap, directly evidenced as
necessary by finding #3, and not something to discover in front of two real
analysts editing the same finding at once. Do not adopt Postgres on the
strength of this spike; nothing here shows a real limit SQLite can't handle
for this scale.

## 4. Module-to-capability mapping (Task 000 point 6)

| Existing module | Target capability (per `examples/reconciliation-template.json`) | Change needed to register it |
| --- | --- | --- |
| `cross_format_analysis.py` (+ `cross_format_analyses.py` for persistence) | `existing_cross_format_reconciliation` | None to the module itself. A thin adapter records an `InputManifest` (pinned document versions) before calling it and writes a `Run`/`Attempt` row around the existing call — wrapping, not rewriting, exactly as `AGENTS.md` requires. |
| `evaluations.extract_findings` | Feeds `finding_observations` output of the above capability | Becomes the extraction step behind the UUID/snapshot identity model in v1.0.1's `docs/03-domain-model.md` — same parser, new persistence shape (M11.2, already scoped ahead of the mandate runtime work in the roadmap). |
| `workspaces.py` review/duplicate/request/memo logic | The shared human-review half of every mandate's output, not capability-specific | Reused directly once `FindingObservation`/`TrackedIssue` exist; this is the "one connected findings register" the package (and the prior M10 package) both require. |
| A draft-production capability (`draft_from_reviewed_findings` in the illustrative template) | Named but **does not exist yet** | Genuinely new code — nothing in Milestones 1–9 produces a narrative draft from reviewed findings today. Milestone 9's memo generation is the closest existing thing (deterministic, template-based, not AI-drafted) and is a reasonable starting point to adapt rather than building from nothing. |

No other existing analysis module (`pdf_inspection.py`, `xlsx_inspection.py`,
`cross_document_analysis.py`) needs to change to support Gate A (one
capability, through the new runtime, end to end) — they're called *by*
`cross_format_analysis.py`, not separately registered yet.

## 5. Conflicts with existing repository instructions

**None found.** `CLAUDE.md` (this repo's only root instruction file; there is
no `AGENTS.md`) asks for clarity/accessibility/professional credibility over
visual flourish, using the same two design skills v1.0.1 already expects new
UI work to consult (`docs/05-experience.md`'s UI quality gate). No conflict
with anything in the adopted package.

## 6. Risks and open items surfaced by this adoption pass

- **The verification-only state in the real Universal Logic workspace is
  still unresolved** — v1.0.1's own `AGENTS.md` rule ("never use real deal
  records as writable acceptance fixtures... Universal Logic is read-only by
  default") is a direct, correct response to exactly this mess, but doesn't
  retroactively clean it up. Still requires an explicit founder-approved
  decision before anything touches it (unchanged from the prior report).
- **Frontend decision is not literally blocking task 11.1** — 11.1 is a
  targeted closeout (bug fixes: export safety, two regressions, the
  accessibility fix) with no new permanent screen, so v1.0.1's "decide
  before new permanent screens" principle isn't violated by proceeding with
  11.1 first. It **is** a hard prerequisite for 11.3b (new workstream/brief
  UI) and should be resolved (O01) before that task is drafted.
- **`examples/reconciliation-template.json`'s `draft_from_reviewed_findings`
  capability doesn't exist** — flagged above; worth the founder knowing this
  before 12.5 ("reuse proof... using existing capabilities") is scoped, in
  case it turns out to need its own bounded task rather than being free
  reuse.

## 7. Frontend / local API / database / worker recommendation

- **Database**: SQLite, locally, through at least M13 — directly evidenced
  by §3's spike, not assumed.
- **Web/session framework**: not changed by this task (no implementation
  authorized); the prior M10 architecture package's FastAPI reasoning (the
  official Python docs' own "`http.server` is not recommended for
  production" warning) still holds and isn't contradicted by anything in
  v1.0.1 — v1.0.1 treats this as O02, open, to confirm at 11.3b.
- **Frontend**: inspect-then-decide (O01), before 11.3b specifically, not
  before 11.1. The untracked `frontend/` React/Vite/shadcn scaffold (already
  inventoried in the prior M10 baseline: working build, matches
  `style.css`'s tokens by name, zero git history, unintegrated) remains the
  concrete candidate to evaluate against the existing static-page pattern
  when that decision is actually made.
- **Worker**: local, in-process-or-sibling-process durable job runner per
  `docs/04-mandate-engine.md`'s "durable execution is local work" — no
  hosting decision needed to build this locally, consistent with D08.

## 8. Proposed decision-log additions (for founder review, not self-approved)

Added to `docs/10-decisions.md`'s "Proposed defaults" section (not to
"Established direction" — only the founder moves something there):

- **P06 (proposed)**: SQLite remains the local/pilot database through at
  least Milestone 13, on the evidence in §3; revisit only if real (not
  synthetic) usage shows sustained contention a retry-with-backoff wrapper
  doesn't absorb.
- **P07 (proposed)**: Task 11.1 proceeds without a frontend decision;
  task 11.3b may not start until O01 is resolved.

---

Next: `tasks/11.1-closeout.md`, drafted below and delivered alongside this
report, per Task 000's own deliverables. Stopping here for founder review —
no code changed, no migration applied, no real data touched, nothing
committed or pushed.
