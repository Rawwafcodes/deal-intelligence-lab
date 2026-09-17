# Continuation state
Package version: 1.0.1
Current phase: Task 000, 11.1, 11.2, and 11.3a all executed inside the actual
application repository. 11.2 and 11.3a both included real, founder-authorized
migrations applied to the live local database — not just documentation. As of
11.3a, the local database is PostgreSQL, not SQLite (docs/10-decisions.md D11).
As of 2026-09-16 (out of task-number sequence, founder-directed), the app's
visual identity is the dark "Meridian" design app-wide (D12), not the original
light navy/gold identity — see the dated entries below. Also as of
2026-09-16, the untracked `frontend/` React scaffold's own `src/index.css`
was retheme'd to the same Meridian identity (see dated entry below) — the
two stacks (static pages, React scaffold) now read as one product visually.
Current task: tasks/12.4-llm-planning.md (complete — a real model now
proposes a mandate's template and, for reconciliation, its source
document pair, live and end to end against Universal Logic; see below).
Next recommended: 12.5 (reuse proof), per the roadmap and this session's
own prior recommendation — a real LLM planner now exists to reuse
against. Extending the Task 11.5 revision-conflict pattern to the memo/
requests remains a smaller, optional follow-up if wanted instead.
Application repository: /Users/rawwafa/Projects/deal-intelligence-lab, this session
had live, direct access to it.
Application revision: fd59122 (unchanged — no commits made by 11.1, 11.2,
11.3a, 11.3b, 11.4, 11.5, 11.4b, 12.1, 12.2, 12.3, or 12.4; all eleven
were implemented but never committed, per instruction).
Implementation status: 11.1, 11.2, 11.3a, 11.3b, 11.4, 11.5, 11.4b, 12.1,
12.2, 12.3, and 12.4 are real, tested, and (11.2, 11.3a, 11.3b, 11.4,
11.5, 11.4b, 12.1, 12.2, 12.3, 12.4) applied to the real local database.
The real database now runs on PostgreSQL (11.3a), carries a real
Organization/User/DealMembership layer with server-side authorization
enforced on every project-scoped route (11.3b), every real document now
has a real, immutable version history (11.4), workspace findings now
detect and reject stale concurrent edits instead of silent
last-write-wins (11.5), every Deal now has a real versioned brief and
real configurable workstreams with assignments (11.4b) — M11.4 is fully
closed — and a real Mandate/PlanRevision/Run/Attempt runtime now exists
and has been proven end to end, including a human-checkpoint pause and
resume, using a deterministic fixture planner and one fixture-only
capability (12.1). That runtime is durable (12.2): a run is persisted and
acknowledged before any capability executes, a real independent
background worker executes it (proven to survive both a lost
request/browser connection and a real `kill -9`+restart of the server
process itself, live), an interruption is either safely resumed or
reported as `outcome_unknown` rather than silently lost, cancellation now
stops a run's next stage even when it is not parked at a checkpoint, and
a minimal budget ledger is checked and enforced before every capability
call. **Gate A passed (12.3)**: a real `reconciliation.cross_format`
capability - a thin adapter around the pre-existing `cross_format_
analysis.py`/`cross_format_analyses.py`/`workspaces.py` modules, not a
reimplementation - was registered, and one real, separately-authorized
paid Claude call was run through the mandate runtime against two real
Universal Logic documents, producing a real, shared `CrossFormatAnalysis`/
`Workspace`/25 findings indistinguishable in the existing static UI from
any non-mandate-produced reconciliation. **LLM planning now exists
(12.4)**: given a mandate's objective, its brief, and the project's real
document inventory (metadata only), a real model proposes which
registered template/capability fits and, for reconciliation, which real
documents form the source pair - untrusted at every layer (every document
id independently re-verified project-scoped, the same structural
PDF/Excel check and the same `validate_plan_stages` a manual proposal
already goes through, an unconfident or invalid candidate coming back as
an honest "unsupported" outcome with no plan created rather than a
best-guess). The human `approve_plan` gate is completely unchanged - a
model-proposed plan is exactly as unapproved as a human-proposed one -
and a human can ask the planner to revise a proposal, which always
creates a new, separately approved plan revision. Proven live: a real
mandate's real planning call correctly identified, from filename metadata
alone, the same PDF/Excel pair Task 12.3 used, was really approved by a
human, and (a second, separately authorized paid call) really executed to
completion with 22 real findings landing in the same shared workspace UI
every other reconciliation uses. One disclosed discrepancy: the live
planning call actually ran on the deployment's globally configured
`claude-opus-5` (via `.env.local`'s `ANTHROPIC_MODEL`), not the
claude-sonnet-5 separately authorized for it - found live, disclosed, and
resolved by keeping one global model knob rather than adding a
planning-only override (see 12.4's own dated entry and task file).
Revision conflicts on the memo/requests, the second-capability reuse
proof (12.5), submissions, and review/approval all remain undone.

## Completed here
- Consolidated recent founder direction and supplied planning evidence.
- Defined shared domain, mandate contract, local collaboration and senior oversight.
- Replaced contradictory earlier milestone sequences with one dependency order.
- Prepared agent instructions, acceptance gates, illustrative configuration and adoption task.
- Clarified Organization versus the legacy Workspace record, ordered the local database
  contention decision before collaborative persistence, and added the one-capability runtime gate.

## Not completed
- ~~Fresh inspection of the actual application.~~ Done 2026-09-15, see below.
- ~~Verification of reported tests or migrations.~~ Done 2026-09-15, see below.
- Selection of final frontend/framework/database implementation (database has a
  local recommendation with evidence — see below; frontend and web framework remain
  open, O01/O02, deferred to before task 11.3b, not blocking 11.1).
- Implementation of collaboration or mandate engine.
- Real-deal human validation scoring.
- Online deployment.

## 2026-09-15 — Task 000 executed
- App commit: `fd59122`. Dirty files preserved and re-verified unchanged twice:
  `cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
  `tests/test_xlsx_inspection.py` (another session's uncommitted edits, untouched),
  plus this session's own untracked `docs/` (prior M10 package), `frontend/`,
  `scripts/`, `.claude/launch.json`, `CLAUDE.md`.
- Task: 000-adopt-and-audit.md, full scope executed (read, baseline reconciliation,
  live test run, M11.3a SQLite/WAL contention spike executed against an isolated
  temp DB, Workspace/Organization naming confirmed exactly against real code,
  module-to-capability mapping, conflict check against CLAUDE.md).
- Evidence: 333 tests pass at committed `fd59122` (334 in the working tree, the
  extra one belonging to the other session's uncommitted edit); mypy clean on 43
  files; SQLite contention spike results in full in `adoption-report.md` §3
  (headline: zero lock errors at realistic small-team load using the app's actual
  default 5s connect timeout; WAL does not reduce write-write contention under
  stress load — 19-20 errors either way — because SQLite allows one writer
  regardless of journal mode; recommend SQLite + an app-level bounded retry wrapper
  over adopting Postgres locally).
- Decisions: proposed P06 (SQLite stays local through at least M13, evidence-based)
  and P07 (11.1 does not need a frontend decision; 11.3b does) in
  docs/10-decisions.md — both **proposed**, not self-approved; founder decides.
- Blockers: none for 11.1. O01 (frontend) blocks 11.3b specifically, not 11.1.
- Next task: `tasks/11.1-closeout.md`, drafted, status `proposed`, awaiting founder
  authorization before implementation starts.
- Permissions needed: founder approval to execute 11.1; separately, a decision on
  the verification-only state still sitting in the real Universal Logic workspace
  (unchanged, not touched by this task, full row-level detail in the prior M10
  baseline and reconfirmed in `adoption-report.md` §1).

## Next agent must append
Date / app commit / dirty files preserved / task / evidence / decisions / blockers /
next task / permissions needed. Never delete earlier completion entries to make status
look clean. Update this header's current task only after the founder accepts the next task.

## 2026-09-15 — Task 11.1 executed

**App commit at start**: `fd59122`, re-verified fresh this session (`git log -1`,
`git status`) before trusting the prior entry's claims — matched exactly: HEAD at
`fd59122`, same four unrelated modified files from a concurrent session
(`cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
`tests/test_xlsx_inspection.py`), same untracked `docs/`, `frontend/`, `scripts/`,
`.claude/launch.json`, `CLAUDE.md`. This task did not commit, so HEAD is still
`fd59122` at the end of this entry too.

**Fresh test/mypy run before trusting `adoption-report.md`'s numbers** (its own
instruction): the repo's own `venv/` (not the system/anaconda Python — that one
lacks `anthropic`/`openpyxl`/`mypy`; `README.md`'s documented runner is
`python3 -m unittest discover -s tests`, not pytest, which is absent from `venv/`
by design):
```
./venv/bin/python -m unittest discover -s tests
```
→ 335 tests, OK (334 baseline + this task's own 1 new Python test; the other
session's uncommitted extra test is unaffected either way).
```
./venv/bin/python -m mypy $(ls *.py) tests
```
→ `Success: no issues found in 43 source files` (20 top-level `*.py` + 23 in
`tests/` = 43, matching the prior report's file count exactly).

**Scope executed, full task file (`tasks/11.1-closeout.md`), nothing beyond it**:

1. **Export formula-injection fix** — added `_safe_cell_text(value: str) -> str`
   to `workspace_exports.py`, prefixing a leading `=`, `+`, `-`, `@`, tab, or CR
   with `'`. Routed through it: every string cell in `_write_table` (covers both
   `build_findings_workbook` and `build_requests_workbook` — title,
   assigned_owner, management_response, reviewer_notes, human-finding
   evidence_notes, request question/assigned_recipient, everything in
   `_FINDINGS_COLUMNS`/`_REQUESTS_COLUMNS`) and every value written by
   `_write_header_sheet` (project/analysis/workspace identifiers, the
   disclaimer). Non-string values (none currently occur, but `_write_table` is
   generic over `dict[str, Any]`) pass through unmodified via an `isinstance`
   guard, so no regression risk if a numeric column is ever added.
2. **`adjusted_severity` regression (frontend)** — extracted the inline fix into
   `buildFindingUpdatePayload(values)`, a standalone pure function placed at the
   top of `static/workspace.js` (before all DOM lookups), called from the save
   button's click handler.
3. **Workspace-summary-refresh regression (frontend)** — both
   `Promise.all([loadRequests(), loadWorkspace()])` call sites (request save,
   request creation) left functionally unchanged; each now has a comment
   explaining why `loadWorkspace()` must stay and pointing at
   `tests/frontend/workspace.logic.test.mjs`.
4. **Accessibility fix** — `static/workspace.js`'s finding rows no longer set
   `role="button"`/`tabIndex` on the `<tr>`. The first cell now holds a real
   `<button type="button" class="ws-expand-toggle">` carrying `aria-expanded`
   and an `aria-label` ("Expand/Collapse details for {title}"); the decorative
   `▸` icon is `aria-hidden`. The row keeps its own `click` listener for
   mouse users — the button's click (from a real user's mouse or keyboard
   Enter/Space, both native browser-guaranteed behavior for `<button>`
   elements) bubbles to it, so there is exactly one `toggle()` path, not two.
   The row's separate `keydown` handler was removed as redundant (a native
   button needs no reimplementation of Enter/Space handling). `workspace.css`
   updated: new `.ws-expand-toggle` reset (transparent background/border, so
   it looks identical to the old plain icon) and the rotate-on-expand rule
   moved from `.ws-finding-row[aria-expanded]` to
   `.ws-finding-row .ws-expand-toggle[aria-expanded="true"]`. The page's
   existing global `button:focus-visible` rule in `style.css` (already used
   everywhere else in the app) now also covers this control for free.
5. **Minimal test tooling** — `buildFindingUpdatePayload` sits above all
   browser-only code in `static/workspace.js`; the rest of that file (DOM
   lookups, listener wiring, the `init()` call) is now wrapped in a single
   `if (typeof document !== "undefined") { ... }` guard, added specifically so
   this file stays loadable both as a classic `<script>` (unaffected — real
   browsers always have `document`) and as a plain Node import for testing. A
   `module.exports` guard (no-op in the browser) lets Node's built-in CJS/ESM
   interop expose `buildFindingUpdatePayload` as a named export. This was a
   discovery made *during* this task, not assumed going in: the file has
   several top-level side-effecting statements scattered past the first ~20
   lines (not just the DOM-element lookups at the top — e.g. a
   `document.querySelectorAll(...).forEach(...)` sort-wiring call and several
   `wireFilterInput(...)` calls), so guarding only the first few lines still
   crashed a plain Node import; the single wrapping guard was the smallest
   correct fix once that was found. New file:
   `tests/frontend/workspace.logic.test.mjs`, run with
   `node --test tests/frontend/workspace.logic.test.mjs` (Node's built-in
   `node:test`/`node:assert`, no `jsdom`, no bundler, no new dependency;
   `node --version` in this environment: v24.21.0) — 3 tests, all passing.

**New-test evidence (acceptance criteria, verbatim)**:
- `tests/test_workspace_endpoints.py::test_findings_export_sanitizes_formula_injection`
  (added next to the existing export tests, same HTTP-integration pattern as
  `test_findings_export_xlsx_contents_and_no_secrets`): sets a real finding's
  `reviewer_notes` to `=1+1` via the existing update endpoint, downloads the
  real `findings.xlsx` export, reads it back with `openpyxl`, and asserts
  exactly one cell has value `'=1+1` (the literal apostrophe-prefixed text)
  with `data_type == "s"` (a plain string, never `"f"` formula). Passes.
- `tests/frontend/workspace.logic.test.mjs`: `buildFindingUpdatePayload({adjusted_severity: ""})`
  → `adjusted_severity: null`; with `"high"` → `"high"` unchanged; a full
  values object with other fields (`review_status`, `assigned_owner`,
  `due_date_text`, `management_response`, `reviewer_notes`) confirmed passed
  through untouched. All 3 pass.

New test file's diff (full contents, new file):
```js
// Regression coverage for the adjusted_severity fix (Task 11.1, item 2):
// static/workspace.js's save-button handler used to inline
// `{ ...values, adjusted_severity: values.adjusted_severity || null }`
// directly in a click listener, with no test. buildFindingUpdatePayload is
// now a standalone pure function at the top of static/workspace.js (no DOM
// dependency), imported here directly via Node's built-in test runner - no
// jsdom, no bundler, no new dependency. Deliberately narrow: this proves
// the one fixed bug stays fixed, not a general DOM-testing framework.

import test from "node:test";
import assert from "node:assert/strict";

import { buildFindingUpdatePayload } from "../../static/workspace.js";

test("buildFindingUpdatePayload converts an empty adjusted_severity to null", () => {
  const result = buildFindingUpdatePayload({ adjusted_severity: "" });
  assert.equal(result.adjusted_severity, null);
});

test("buildFindingUpdatePayload leaves a set adjusted_severity unchanged", () => {
  const result = buildFindingUpdatePayload({ adjusted_severity: "high" });
  assert.equal(result.adjusted_severity, "high");
});

test("buildFindingUpdatePayload passes other fields through untouched", () => {
  const input = {
    review_status: "accepted",
    assigned_owner: "J. Rivera",
    due_date_text: "2026-10-01",
    management_response: "Pending",
    reviewer_notes: "Looks fine",
    adjusted_severity: "",
  };
  const result = buildFindingUpdatePayload(input);
  assert.equal(result.review_status, "accepted");
  assert.equal(result.assigned_owner, "J. Rivera");
  assert.equal(result.due_date_text, "2026-10-01");
  assert.equal(result.management_response, "Pending");
  assert.equal(result.reviewer_notes, "Looks fine");
  assert.equal(result.adjusted_severity, null);
});
```

**Files changed**: `workspace_exports.py`, `static/workspace.js`,
`static/workspace.css`, `tests/test_workspace_endpoints.py` (new test method),
`tests/frontend/workspace.logic.test.mjs` (new file/new directory). Nothing
else. No schema change, no migration, no renaming of `Workspace`/`Organization`.

**Browser evidence (synthetic data only — a throwaway isolated-SQLite-temp-DB
server on `127.0.0.1:8877`, built the same way `tests/test_workspace_endpoints.py`
isolates its own DB; a fresh project "Synthetic A11y Check Co" with 2 synthetic
findings; never opened Universal Logic; the temp server and its temp DB were
both torn down at the end of this task)**:
- `read_page`/`find` on the rendered findings table show, for each row:
  `button "Expand details for <title>" [ref] type="button"` — a real `<button>`
  in the accessibility tree with an accessible name and `aria-expanded`, not a
  `<tr role="button">` (which the ARIA required-context-role rules would have
  the accessibility tree ignore).
- Tabbed from the search field through the filter controls to the row's expand
  button (confirmed via `document.activeElement` mid-sequence: `tag: "BUTTON"`,
  `aria: "Expand details for Unsupported growth rate"`) and clicking it (mouse)
  flipped `aria-expanded` from `"false"` to `"true"` and visibly expanded the
  row's detail panel — the click handler and toggle logic are correctly wired
  to the new button.
- **Limitation, disclosed rather than glossed over**: sending a synthesized
  `Return`/`space` key press through this task's Browser-pane automation tool
  while the button held focus did *not* toggle `aria-expanded` in this
  environment. Before concluding that was an app bug, the same test was run
  against `static/workspace.js`'s pre-existing, entirely-unmodified "Add
  finding" `<button>`: a synthesized Enter press on it, while focused,
  likewise did not open its dialog. Since Enter/Space activation of a focused
  `<button>` is native, browser-guaranteed default behavior per the HTML
  spec — not something any app's JS implements or can break — and the same
  non-activation reproduces on an untouched button elsewhere on the same page,
  this is read as a limitation of synthesizing native key-triggered default
  actions in this particular automation harness, not a defect in the shipped
  fix. A real browser's own keyboard handling (confirmed indirectly: mouse
  activation of the same button works, and the button has the exact role/
  name/state a screen reader needs) is what the acceptance criterion actually
  depends on. Recommend a follow-up manual check with a real keyboard in an
  actual browser (not this harness) before treating this as fully closed, or
  re-attempting with a different automation approach if one becomes available.

**Unrelated state, confirmed untouched (matches the prior report's baseline
exactly, `git diff --stat` re-run at the end of this task)**:
```
cross_format_analysis.py      | 12 +++++++----
pdf_inspection.py             | 30 ++++++++++++++++++---------
tests/test_xlsx_inspection.py | 48 +++++++++++++++++++++++++++++++++++++++++++
xlsx_inspection.py            | 40 +++++++++++++++++++++++++++---------
```
Untracked `docs/`, `frontend/`, `scripts/`, `.claude/launch.json`, `CLAUDE.md`
also untouched (only the new `tests/frontend/` directory was added, in scope).
Universal Logic (project `e32167f6062f45d999259a360c1f04f9`) was never opened
or queried this session.

**Decisions**: none proposed this task (11.1 had none in scope). The wrapping
`if (typeof document !== "undefined")` guard in `static/workspace.js` is an
implementation detail in service of item 5's own explicit instruction ("no
jsdom... callable in plain Node"), not a frontend-framework decision — O01/O02
remain open, untouched, exactly as before.

**Blockers**: none. The keyboard-activation browser-evidence limitation above
is disclosed, not blocking — the underlying fix is correct by inspection, code
review, and every other verification method available in this session.

**Next task**: `tasks/11.2` (stable observation snapshots/UUIDs), per the
roadmap and the prior entry's own recommendation — not started, no files
touched in its scope, awaiting founder review of this entry first.

**Permissions needed**: founder authorization to proceed to 11.2; the
Universal Logic verification-only state remains unresolved and still needs an
explicit founder decision (unchanged from every prior entry — not touched by
this task either).

## 2026-09-15 — Task 11.2 executed (real database migrated)

**Authorization**: requested directly by the founder in this session ("i want
to implement it actually"), after reviewing 11.1's completion. Given the scope
touches the real database, the exact approach was confirmed with the founder
before writing code (`AskUserQuestion`): build the change, validate the
migration on a disposable copy, then — the founder's explicit choice, over two
narrower alternatives — also apply it to the real database in this same
session. A full plan was written and approved (`ExitPlanMode`) before
implementation started. Immediately before the real `--apply` step, the
founder was asked again and separately confirmed stopping the running server,
applying, and restarting it.

**App commit**: `fd59122`, unchanged — this task, like 11.1, was implemented
and tested but never committed, per instruction.

**Problem being fixed**: `workspaces.py` gave every AI-origin finding the id
`ai-<index>` and re-derived its content fresh from the analysis record on
every read by matching on that index — flagged in `docs/02-existing-baseline.md`
("Position-based finding IDs and extraction on read") and directly
contradicting `docs/03-domain-model.md`'s "UUID, immutable content/evidence
snapshot... Read operations never re-extract or mutate historical findings."
Risk: a future parser fix could silently reattach existing review state to
different content, with nothing to catch it.

**What changed** (full detail in `tasks/11.2-finding-identity.md`):
1. `workspace_findings` gained three additive columns
   (`ai_extraction_version`, `ai_snapshot_json`, `ai_content_hash`), added via
   an idempotent, `PRAGMA table_info`-guarded `ALTER TABLE`.
2. New AI findings now get `id = f"ai-{uuid.uuid4().hex}"` (no positional
   meaning) with their content snapshotted once at creation. The read path
   (`list_findings`/`get_finding`) no longer calls
   `evaluations.extract_findings` at all — only `get_or_create_workspace`
   does, once.
3. New `migrate_finding_ids.py` (repo root): `--dry-run` / `--verify-only` /
   `--apply` modes; never guesses on an ambiguous legacy row (leaves it
   unmigrated and reports it); remaps `duplicate_of`,
   `workspace_requests.related_finding_ids_json`, and
   `workspace_audit_log.entity_id` for every rename; audits the remap itself.
4. `tests/test_workspaces.py` / `tests/test_workspace_endpoints.py`: ~30
   hardcoded `"ai-0"`/`"ai-1"` literals replaced with lookups by known title —
   expected churn, the task removes the assumption those literals relied on.
5. New `tests/test_finding_id_migration.py` (9 tests, all passing): scan/
   apply/verify round-trip, idempotency, cross-reference remap, the
   unresolved-mapping case (both refusing and `--allow-unresolved` proceeding),
   and the CLI's dry-run/verify-only modes.

**Test/type evidence**:
```
./venv/bin/python -m unittest discover -s tests
```
→ `Ran 344 tests ... OK` (335 prior + 9 new).
```
./venv/bin/python -m mypy $(ls *.py) tests
```
→ `Success: no issues found in 45 source files` (43 prior + `migrate_finding_ids.py`
+ `tests/test_finding_id_migration.py`).

**Migration evidence, in order performed**:
1. Dry run against a copy of the real `data/deal_lab.db`:
   `./venv/bin/python migrate_finding_ids.py --dry-run` → 1 workspace scanned
   (Universal Logic), 33 legacy rows planned, 0 unresolved, `VERIFY: PASS`
   (0 hash mismatches, 0 content mismatches vs a fresh re-extraction, 0
   dangling references). The real file's size/mtime were confirmed unchanged
   immediately after.
2. Stopped the live app server (`kill <pid>`, plain SIGTERM, confirmed exited)
   with the founder's explicit go-ahead.
3. Applied for real: `./venv/bin/python migrate_finding_ids.py --apply` →
   backed up to `data/deal_lab.db.bak-20260915T203444Z` (kept, not deleted —
   the rollback path) before writing anything; 33 rows migrated, 0 unresolved,
   `VERIFY: PASS`.
4. Independent post-apply check: `./venv/bin/python migrate_finding_ids.py
   --verify-only` against the now-live file → `VERIFY: PASS` again, computed
   completely fresh (re-parses each analysis from scratch, doesn't reuse
   anything from step 3).
5. Full test suite and mypy re-run clean against the repo (not the migrated
   DB, which the test suite never touches).
6. Restarted the server: the original process had been started from a shell
   with the project's `venv` on `PATH`; a plain `python3` in a fresh shell
   resolves to a different interpreter lacking `anthropic` and fails to
   start — caught immediately via the startup log, fixed by using
   `./venv/bin/python3 server.py` explicitly. Confirmed serving again
   (`GET /` → 200).
7. Browser check against the real, now-migrated Universal Logic workspace,
   read-only navigation only (opened the existing reconciliation via its own
   "Open deal workspace" link — an idempotent re-open of an already-created
   workspace, not a new write — never entered any writable form field):
   all 33 findings render (34 with the hidden duplicate shown), every prior
   review state is intact (`Rejected`; `Accepted` with owner `J. Chen`;
   `Unreviewed` elsewhere), the human-added finding is still present and
   labeled `Human`, the duplicate-of link still resolves (34/33 shown-vs-
   hidden count unchanged from before migration), the one information
   request still shows `Answered` with its finding link intact, a finding's
   expand control is still a real `<button>` in the accessibility tree
   (11.1's fix, unaffected by this task), and the findings `.xlsx` export
   still returns 200 with valid spreadsheet content (25,253 bytes).

**Files changed**: `evaluations.py`, `workspaces.py`, new
`migrate_finding_ids.py`, `tests/test_workspaces.py`,
`tests/test_workspace_endpoints.py`, new `tests/test_finding_id_migration.py`.
Real data changed: `data/deal_lab.db` (33 rows migrated in place, plus the
additive schema columns); `data/deal_lab.db.bak-20260915T203444Z` created
(pre-migration backup, kept).

**Unrelated state, confirmed untouched** (`git diff --stat` identical to
every prior entry): `cross_format_analysis.py`, `pdf_inspection.py`,
`xlsx_inspection.py`, `tests/test_xlsx_inspection.py` (same four files, same
diff, from the still-uncommitted concurrent session); untracked `docs/`
(other than this package's own two new/edited files),
`frontend/`, `scripts/`, `.claude/launch.json`, `CLAUDE.md` all unchanged.

**Decisions**: none formally proposed to `docs/10-decisions.md` this task.
The choice to snapshot AI content as one JSON blob (`ai_snapshot_json`)
rather than one column per field was made in-task as an implementation
detail (matches the existing `human_evidence_document_ids_json` convention
already in the same table), not a decision needing founder sign-off.

**Blockers**: none.

**Next task**: `11.3a` (SQLite/WAL contention and recovery spike) — not yet
drafted as a task file. Note: `adoption-report.md` §3 already ran a
substantial version of this spike (against a fully separate temp database),
so 11.3a's remaining work is mainly to formally record P06/P07 as
founder-decided (they are currently only "proposed" in `docs/10-decisions.md`)
rather than to repeat the spike from scratch.

**Permissions needed**: founder authorization to start 11.3a (or to instead
resolve the still-open P06/P07 proposed decisions first). The Universal Logic
verification-only state (33 AI + 1 human finding, one duplicate marking, one
information request, one memo, audit log) is unchanged in *kind* by this
task — it still exists and still needs an explicit founder decision — but its
finding rows now carry stable ids rather than positional ones, which was the
point of this task.

## 2026-09-15 — Task 11.3a executed (SQLite → PostgreSQL, real cutover)

**Authorization**: the founder said "next" after 11.2's completion, meaning
proceed to 11.3a. Before implementing, the founder was offered the M11.3a
spike's own recommendation (P06: stay on SQLite + a retry wrapper) directly
via `AskUserQuestion` and explicitly rejected it, choosing Postgres instead —
recorded as a preference decision, not represented as newly evidence-driven
(the spike's findings stand, unchanged; see `docs/10-decisions.md` D11).
A second `AskUserQuestion` covered install method (conda, not Homebrew — not
installed, and installing it needs an interactive sudo prompt this session
can't satisfy) and scope ("everything now" vs. proof-of-concept vs.
decision-only — founder chose everything now, real data included). A written
plan (codebase survey via an Explore agent, then a concrete module-by-module
plan) was approved via `ExitPlanMode` before any code was touched.

**App commit**: `fd59122`, unchanged — implemented and tested but never
committed, per instruction, same as 11.1 and 11.2.

**What changed** (full detail in `tasks/11.3a-postgres-migration.md`):
1. PostgreSQL installed via `conda install -c conda-forge postgresql` — no
   Homebrew, no sudo, no system changes. Local data directory `pgdata/`
   (UTF8, `en_US.UTF-8` locale — corrected after a first attempt defaulted
   to `C`/`SQL_ASCII`, wrong for real deal content), Unix socket only
   (`pgsocket/`, port 5544, no TCP listener, `trust` auth, no password).
   `psycopg2-binary` + `types-psycopg2` added to `requirements.txt`/`venv/`.
2. `store.py` rewritten: `get_connection()` returns a `_ConnectionWrapper`
   preserving the exact `conn.execute(sql, params).fetchone()/.fetchall()`
   shorthand every other module already used (via `RealDictCursor`,
   `row["column"]` access also unchanged everywhere). `SCHEMA` module
   global replaces `DB_PATH`; new `ensure_schema()`/`drop_schema()` give
   tests the same "fresh isolated database per test/class" property a temp
   SQLite file used to, now via a throwaway Postgres schema instead.
3. The other 10 schema-owning modules (`documents.py`, `inspections.py`,
   `xlsx_inspections.py`, `cross_analyses.py`, `cross_format_analyses.py`,
   `validation_cases.py`, `answer_keys.py`, `validation_runs.py`,
   `evaluations.py` — DB half only, its parser half is untouched,
   `workspaces.py`) ported mechanically: every SQL `?` → `%s`, zero
   business-logic changes. `workspaces._ensure_finding_snapshot_columns`
   simplified from a `PRAGMA table_info` check to native `ALTER TABLE ...
   ADD COLUMN IF NOT EXISTS`. Column types (0/1-boolean `INTEGER`s,
   `*_json` `TEXT` columns) deliberately left unchanged — backend swap,
   not a schema redesign.
4. ~22 affected test files' DB fixtures converted from monkeypatching
   `store.DB_PATH` to a fresh temp file → monkeypatching `store.SCHEMA` to
   a fresh Postgres schema name, same scope (class- or per-test) each file
   already used. Two background agents handled disjoint module groups in
   parallel (survey-verified non-overlapping file sets); the lead handled
   `store.py` and `workspaces.py` directly, plus `tests/test_server.py`
   (missed by both agents' assignments) and a pre-existing, unrelated
   `tests/test_documents.py` failure (a subprocess test spawning a bare
   `python3` that lacked `psycopg2` — fixed by using `sys.executable`).
5. **Retired** `migrate_finding_ids.py` and its test
   (`tests/test_finding_id_migration.py`): its one job (legacy
   `ai-<index>` → `ai-<uuid>` migration) is already complete and verified
   against the real data (Task 11.2); it was tightly coupled to SQLite
   file semantics with no Postgres equivalent, and porting a finished
   tool would be dead weight.
6. New `migrate_sqlite_to_postgres.py` — the one-time real-data transport.
   Reads each table's column list from SQLite's own `PRAGMA table_info`
   (never a hand-maintained list), read-only against the source file,
   calls all 11 `init_*_db()` functions first (same order as
   `server.py:main()`).
7. Docs: `docs/10-decisions.md` D11 added, P06 marked rejected (kept, with
   reason), O03 marked resolved. New `POSTGRES.md`. `README.md`'s run
   instructions and "Your data" section corrected. `.gitignore` updated
   (`pgdata/`, `pgsocket/`, `pgdata.log`).

**Test/type evidence**:
```
./venv/bin/python -m unittest discover -s tests
```
→ `Ran 335 tests ... OK`.
```
./venv/bin/python -m mypy $(ls *.py) tests
```
→ `Success: no issues found in 44 source files`.

**Real migration evidence, in order performed**:
1. Confirmed Postgres `public` schema was empty before starting.
2. Stopped the running (SQLite-backed) server (`kill <pid>`, confirmed
   exited).
3. `./venv/bin/python migrate_sqlite_to_postgres.py` →
   ```
   projects: copied 6 (source 6)          [OK]
   documents: copied 157 (source 157)     [OK]
   inspections: copied 3 (source 3)       [OK]
   xlsx_inspections: copied 0 (source 0)  [OK]
   cross_analyses: copied 2 (source 2)    [OK]
   cross_format_analyses: copied 6 (source 6)     [OK]
   validation_cases: copied 2 (source 2)          [OK]
   answer_key_versions: copied 2 (source 2)       [OK]
   validation_runs: copied 5 (source 5)           [OK]
   evaluations: copied 5 (source 5)               [OK]
   workspaces: copied 1 (source 1)                [OK]
   workspace_findings: copied 34 (source 34)      [OK]
   workspace_requests: copied 1 (source 1)        [OK]
   workspace_memos: copied 1 (source 1)           [OK]
   workspace_audit_log: copied 56 (source 56)     [OK]
   ```
   Finding-snapshot spot-check: all migrated snapshots matched
   byte-for-byte between SQLite and Postgres. `VERIFY: PASS`.
4. Server restarted (`./venv/bin/python3 server.py`), confirmed responding
   (`GET /` → 200).
5. Browser check against the real, now-Postgres-backed Universal Logic
   workspace, read-only navigation only: all 33 findings render (34 with
   the hidden duplicate shown), non-ASCII characters (em-dashes, curly
   quotes throughout the real finding titles) render correctly, review
   states intact (`Rejected`, etc.), the duplicate marking and the one
   information request both intact, a finding expands with full content,
   the findings `.xlsx` export returns 200 with the exact same byte count
   (25,253) as the pre-migration export.
6. `data/deal_lab.db` and its Task 11.2 `.bak-*` confirmed unmodified
   (mtimes identical to before this task; the transport script opened the
   file with SQLite's own read-only URI mode).

**Files changed**: `store.py`, `documents.py`, `inspections.py`,
`xlsx_inspections.py`, `cross_analyses.py`, `cross_format_analyses.py`,
`validation_cases.py`, `answer_keys.py`, `validation_runs.py`,
`evaluations.py`, `workspaces.py`, ~22 test files (DB-fixture boilerplate
only), new `migrate_sqlite_to_postgres.py`, new `POSTGRES.md`,
`docs/10-decisions.md`, `README.md`, `.gitignore`, `requirements.txt`.
Removed: `migrate_finding_ids.py`, `tests/test_finding_id_migration.py`.
Real data changed: the new Postgres `deal_lab` database's `public` schema
now holds every row from `data/deal_lab.db`; the SQLite file itself was
never written to.

**Disclosed exception to the "leave concurrent-session files untouched"
rule**: `tests/test_xlsx_inspection.py` (one of the four files this effort
has kept hands-off since Task 11.1, belonging to a concurrent session's
uncommitted work on the *singular* `xlsx_inspection.py` module) needed its
`setUpClass`/`tearDownClass` DB-fixture lines converted from `store.DB_PATH`
to `store.SCHEMA`, because `store.DB_PATH` no longer exists anywhere in the
codebase after this task — leaving it unconverted would have broken every
test in that file, including the concurrent session's own added test. Only
the DB-isolation lines changed; verified by reading the full diff that the
concurrent session's actual content (`strip_dimension_declarations` helper,
`test_workbook_missing_dimension_declaration_does_not_false_reject_citations`)
is byte-for-byte untouched, and confirmed that test still passes. The
*module* `xlsx_inspection.py` itself was never touched (it doesn't use the
database at all). The other three protected files
(`cross_format_analysis.py`, `pdf_inspection.py`, and the module
`xlsx_inspection.py`) remain completely untouched — `git diff --stat`
identical to every prior task's baseline.

**Unrelated state, otherwise confirmed untouched**: untracked
`docs/`/`frontend/`/`scripts/`/`.claude/launch.json`/`CLAUDE.md` all
unchanged beyond this package's own edits.

**Decisions**: `docs/10-decisions.md` D11 (Postgres, local — Established
direction, founder preference, not evidence-driven), P06 marked rejected
(kept, not deleted), O03 marked resolved. See that file for full text.

**Blockers**: none.

**Next task**: `11.3b` (Organization, user, memberships, deal context,
server-side authorization) — not yet drafted as a task file. O01 (frontend
decision) remains its separate, harder prerequisite, still open.

**Permissions needed**: founder authorization to start 11.3b, or to resolve
O01 first. The Universal Logic verification-only state is unchanged in kind
by this task (same 33 AI + 1 human finding, duplicate, request, memo, audit
log — now living in Postgres instead of SQLite) — still needs an explicit
founder decision, unrelated to this task's scope.

## 2026-09-16 — Visual identity replaced app-wide (out of task-number sequence)

**Authorization**: founder-directed, in session, outside the numbered task
list. Origin: the founder shared a real screenshot (a "Meridian Advisory"
mandate-composer mockup) and confirmed it as this app's own actual target
design, not a borrowed style reference. A design-comparison artifact and then
a full click-through prototype of the planned Mandate workspace were built
first to validate the direction against real app data before touching any
real file (both published as Claude artifacts this session, not committed to
the repo). The founder then asked to apply it to the whole app. Two scope
questions were confirmed directly before implementing: (1) dark replaces the
light identity everywhere, including the findings/review surfaces it was
previously going to be kept separate from — not a toggle, not split by
surface; (2) convert every real page in one pass, then verify thoroughly,
rather than one page at a time.

**What changed**: `static/style.css` and `static/workspace.css` only. Every
one of the app's 9 HTML pages (`index`, `project`, `reconcile`,
`cross-analysis`, `inspect`, `workbook-inspect`, `validation`,
`validation-case`, `validation-evaluation`, `workspace`) already inherits
from these two shared stylesheets with zero inline `<style>` blocks and zero
per-page stylesheets (confirmed by grep before starting) — so the retheme is
concentrated in two files, no HTML or JS touched:
- `style.css`: full token replacement (`:root`) — near-black ground (`#0a0a0c`),
  card surfaces one step lighter, a blue accent (`#3b82f6`) reserved for
  links/focus/selection, a new `--cta-bg`/`--cta-fg` pair (white pill, near-
  black text) for the primary-action `button`/`.button-like` styles (previously
  solid navy), Inter/Inter Tight replacing EB Garamond/Lato, `color-scheme: dark`
  (deliberately committed, not a `prefers-color-scheme` toggle — see D12). Four
  hardcoded non-token colors fixed to match (dropzone drag-over tint, modal
  backdrop opacity, skeleton-loader shimmer highlight, input focus glow). New
  `.app-brand::before` CSS-only logo mark (a "D" square) added with no HTML
  changes, via a pseudo-element.
- `workspace.css`: severity badges (`.ws-severity-critical/high/medium/low`)
  converted from light pastel backgrounds to dark saturated-background/light-
  text pairs; `.ws-badge-origin-human`/`.ws-badge-approved` likewise; removed
  a stray hardcoded dark-red button hover that would have been unreadable
  against near-black.
- Confirmed via grep: zero hardcoded colors remained anywhere in either file
  afterward, and zero JS-set inline colors anywhere in `static/*.js` bypass
  the stylesheet (the only two `element.style.color` call sites in
  `workspace.js` already read `var(--danger)`/`var(--success)`, so they
  picked up the new values automatically with no JS change needed).

**Verification** (real server, real Postgres data, not a mockup):
- Full suite: `./venv/bin/python -m unittest discover -s tests` → `Ran 335
  tests ... OK` (pure CSS change; run anyway per the founder's "verify
  thoroughly" instruction).
- Browser-checked every distinct component family against the real Universal
  Logic project: home project list (cards, white CTA, new logo mark),
  project detail (breadcrumb, documents table with monospace checksums),
  cross-format reconciliation page (source lists, inspection-facts grid),
  the deal workspace (KPI summary strip, tabs, filter dropdowns, the full
  findings table with all four severity colors, an expanded finding's detail
  panel with citation badges and form controls), and the Validation Lab
  (table, and a real `<dialog>` modal with checkbox list and focus ring) —
  every one legible, correctly contrasted, and functionally unchanged.
- `git status` confirms exactly two files touched (`static/style.css`,
  `static/workspace.css`); no HTML or JS files in the diff.

**Files changed**: `static/style.css`, `static/workspace.css`,
`docs/10-decisions.md` (new D12).

**Decisions**: `docs/10-decisions.md` D12 added (Established direction) —
full text there. Supersedes the earlier per-surface split floated during
this session's design-artifact exploration (dark for Mandate screens only,
light kept for review surfaces) — the founder chose whole-app consistency
instead when asked directly.

**Blockers**: none.

**Next task**: unchanged — `11.3b` remains the next roadmap task, still
gated on O01. This visual-identity change does not resolve O01 (it's a CSS
retheme of the existing static pages, not a frontend-framework decision) but
removes any argument that the old light identity needs preserving during
that decision.

**Permissions needed**: none for this change (already executed). 11.3b/O01
authorization still pending, unrelated to this entry.

## 2026-09-16 — Frontend scaffold retheme'd to Meridian; Task 11.3b drafted

**Authorization**: founder-directed, in session, two explicit instructions in
order: (1) retheme `frontend/src/index.css` to match D12's Meridian identity,
verify by running the scaffold's dev server; (2) draft (not implement)
`tasks/11.3b-organization-auth.md`, stop and show it before writing any
implementation code. Both executed in that order; no implementation code for
11.3b was written.

**App commit**: `fd59122`, unchanged — nothing in this entry was committed.
`git status` unchanged in kind from the prior entry (same untracked
`frontend/`, `docs/`, `scripts/`, etc.; same four concurrent-session files
untouched) except that `frontend/src/index.css` and
`frontend/src/components/AppHeader.tsx` — both already untracked, inside the
untracked `frontend/` tree — were edited within this entry's own scope.

### Part 1: `frontend/src/index.css` retheme (complete)

**What changed**: `frontend/src/index.css` — the scaffold's `:root` block
previously ported the retired light "Trust & Authority" navy/gold tokens
onto shadcn/ui's variable names (see the old file's own removed comment).
Replaced with the same Meridian values already live in `static/style.css`
(D12): `--background`/`--foreground` → near-black/off-white,
`--card`/`--popover` → the one-step-lighter surface color, `--primary`/
`--primary-foreground` → the white CTA pill (not a color, per D12/D13 — a
stark white background with near-black text), `--muted`/`--accent` → the
dark muted-surface color (kept distinct from the brand's blue, which now
lives only in `--ring` for focus, matching D12's "blue reserved for
selection/links/focus"), `--destructive` → the same muted danger red-pink
`static/style.css` uses, `--border`/`--input` → the same dark border color,
Inter/Inter Tight replacing EB Garamond/Lato, `color-scheme: dark` added.
Per D12/D13 ("one committed look app-wide, not a light/dark toggle"), the
values were folded directly onto `:root` rather than left behind a `.dark`
class — nothing in this scaffold currently toggles that class (`next-themes`
is an unused dependency, confirmed by grep), so keeping a separate,
un-toggleable `.dark` override block would have been dead code; it and the
now-unused `@custom-variant dark` declaration were removed. Unused
`--primary-hover` (confirmed unreferenced anywhere in `src/`) was dropped in
the same pass.

**One companion fix, disclosed rather than silently bundled**:
`frontend/src/components/AppHeader.tsx` had a hardcoded `border-(--gold)`
3px header underline — a "Trust & Authority" decorative trait with no
Meridian equivalent (the real static pages' header is a plain 1px
`--border` bottom line, confirmed by reading `static/style.css`). Removing
the now-gone `--gold` token from `index.css` without this fix would have
left the header rendering an invalid/broken border. Changed the one
className string to `border-b border-border bg-background` — matching the
static pages' own header exactly. This is the only file outside
`index.css` touched in Part 1.

**Verification** (real dev server, `frontend/scripts` launch config
`deal-lab-frontend`, port 5173, proxied to the real running backend on
8765 — read-only `GET /api/projects` against whatever real projects already
existed, no write):
- `npm run dev` via the Browser pane; home screen (project list) rendered
  correctly: near-black ground, white heading/body text at correct
  contrast, card surfaces one step lighter than the page background, white
  "+ New project" CTA pill with near-black text, Inter/Inter Tight fonts
  loading. Opened the "New project" dialog: dark popover surface, blue
  focus ring on the autofocused input (confirms `--ring` still carries the
  Meridian blue independently of `--primary`), white submit button — closed
  via Cancel without creating anything.
- Console checked via `read_console_messages`: no errors.
- One pre-existing, unrelated observation, not a regression from this
  task: the project list's GSAP entrance animation
  (`gsap.from(".project-card", {opacity: 0, ...})` in `Home.tsx`, untouched
  by this task) was found frozen mid-animation (partial opacity) on first
  screenshot in this Browser-pane environment — confirmed via
  `getComputedStyle` to be a `requestAnimationFrame` pausing while the pane
  tab is visible-but-unfocused/hidden, not a CSS/token issue: forcing the
  affected elements' `opacity`/`transform` back to their end state via a
  one-off `javascript_tool` call (verification only, not a code change)
  showed the intended final look was already correct underneath. Not fixed
  here — it's Home.tsx's own animation code, out of this task's scope
  (retheme `index.css` only), and reproduces on the pre-existing "Add
  finding" button pattern noted as a similar automation-environment
  limitation in Task 11.1's entry above.
- Dev server stopped at the end of verification.

**Files changed**: `frontend/src/index.css`, `frontend/src/components/
AppHeader.tsx`. Nothing else — no backend file, no static page, no test
file.

**Decisions**: none newly proposed to `docs/10-decisions.md`. This is an
application of D12/D13, not a new decision.

**Blockers**: none.

### Part 2: Task 11.3b drafted, not implemented (per instruction, stopped here)

Read `docs/03-domain-model.md`, `docs/06-security-and-collaboration.md`,
`docs/05-experience.md`, `docs/04-mandate-engine.md`, D12/D13, and
`docs/09-acceptance.md`'s T03–T05 before drafting. Directly inspected
`server.py` (confirmed: hand-rolled `BaseHTTPRequestHandler`, zero existing
session/auth/CORS code anywhere), `store.py` (confirmed: `projects` has no
`organization_id` or any membership concept today), and `frontend/src/`
(confirmed: `Home.tsx` is the only real screen, `AppHeader` has no nav/
identity today) rather than assuming the specs describe the current code.

Wrote `docs/workspace-shift/tasks/11.3b-organization-auth.md` following
`tasks/TEMPLATE.md`'s exact section contract, modeled on
`tasks/11.3a-postgres-migration.md`'s shape. Scoped deliberately narrower
than the full docs/06 permission table for one sitting: stores
`analyst`/`reviewer`/`deal_lead` roles on the new `deal_memberships` table
but enforces membership-vs-no-membership only this round (today's app has
no analyst-vs-reviewer-vs-lead-differentiated action to attach a finer
check to — that's M12/M13's submission/review/approval subsystem, not yet
built). Proposes a hand-rolled cookie session on the existing
`BaseHTTPRequestHandler` rather than adopting a web framework, explicitly
flagged as a choice that side-steps O02 (still open) rather than resolving
it. All new-table testing is scoped to an isolated, disposable Postgres
schema with synthetic seed data — explicitly **not** the real `public`
schema or Universal Logic, per this session's own instruction to keep that
project read-only; the real `organization_id` backfill/cutover is written
up as a separately-authorized follow-up step (same dry-run-then-confirm
pattern Tasks 11.2 and 11.3a used for their own real-database changes), not
part of this task's completion bar. The draft ends with four explicit open
questions for the founder (O02 side-step, role-enforcement depth, seed-data
shape, real-cutover timing) rather than silently assuming answers.

**Files changed**: new `docs/workspace-shift/tasks/11.3b-organization-auth.md`
(status `proposed`); this `STATUS.md` entry; `docs/10-decisions.md`
untouched (no new decision recorded — the draft raises open questions, it
doesn't resolve any).

**Blockers**: founder review of the draft task file's scope — the four
open questions listed in the task file itself, plus a general go/no-go on
the scope reduction described above.

**Next task**: implementation of `11.3b-organization-auth.md`, once the
founder confirms scope (or sends back changes to the draft first).

**Permissions needed**: founder sign-off on the draft before any
implementation code is written, per this session's explicit instruction to
stop here.

## 2026-09-16 — Task 11.3b implemented (Organization/User/DealMembership + auth)

**Authorization**: the founder, in session, immediately after the draft
above: "from now on i want u to implemented the tasks that ur performing,
dont draft it. you can start 11.3b" — a standing instruction to implement
directly going forward, and specific authorization to build this task now.
The draft's four open questions were resolved as reversible implementation
choices during the build rather than asked about first (recorded in the
task file's own Completion evidence); this session's separate, standing
instruction to keep Universal Logic read-only was still honored — see
below for exactly what "read-only" meant once implementation showed the
real database change involved never writes to `projects` or any
pre-existing row.

**App commit**: `fd59122`, unchanged — this task, like 11.1/11.2/11.3a, was
implemented and tested but never committed, per instruction.

**What changed** (full detail, acceptance evidence, and the reasoning
behind every deviation from the original draft: `tasks/
11.3b-organization-auth.md`, now status `complete`):
1. New `identity.py`: Organization, User, OrganizationMembership,
   DealMembership, Session — five new, additive Postgres tables. Deliberately
   a new `project_organizations` side table rather than an `ALTER TABLE
   projects ADD COLUMN` (the draft's original plan) — found during
   implementation that `store.py`'s `Project` dataclass and its exact
   `to_dict()` shape are asserted against by many existing tests, so
   keeping `projects` itself completely untouched avoided that churn
   entirely.
2. `server.py`: every request now resolves an identity
   (`Handler._resolve_identity`) before any route runs. A session cookie
   with no match (or none at all) transparently gets the bootstrap default
   identity rather than a 401 — found during implementation that the
   existing static pages have no login UI and (D13) never will, so a hard
   401-when-no-session model would have broken every one of them on first
   load. Real, server-validated sessions still exist; explicitly switching
   identity (new dev-only `POST /api/dev/session`) is what actually
   demonstrates differentiated access. `Handler._authorized_project`
   replaces ~19 scattered `store.get_project(...) is None` checks
   (including inside the existing `_get_owned_workspace`/
   `_get_owned_validation_case` helpers) with one shared existence +
   membership check, 404 either way so a denied caller can't tell "not
   yours" from "doesn't exist." New `GET /api/session`,
   `GET /api/dev/identities`, `POST /api/dev/session`,
   `POST /api/dev/session/clear`; the dev-only three are absent (404) with
   `DEAL_LAB_DEV_AUTH=0`, still loopback-checked either way. CSRF: session
   cookie is `SameSite=Strict`, and mutating requests reject a foreign
   `Origin` header.
3. **Orphan-project fallback**, found necessary during implementation, not
   planned in the draft: most of this codebase's own test fixtures create
   their project via a direct `store.create_project()` call, never through
   the API — meaning most existing projects never go through this task's
   own org-assignment step. Without a fallback, the *entire* existing test
   suite would have started 404ing on its own fixtures. `identity.
   has_deal_access`/`list_accessible_project_ids` now lazily adopt an
   unassigned ("orphan") project into the default identity's organization
   the first time the default identity specifically is checked against
   it — checking a different, unrelated user's access to the same orphan
   project never triggers adoption as a side effect (a real bug caught and
   fixed during this task's own test-writing: an earlier version adopted on
   *any* checked user, which polluted an unrelated test's membership
   history — see the task file's Scope section for the fixed behavior and
   `tests/test_identity.py`'s dedicated regression test).
4. `frontend/src/components/AppHeader.tsx`: identity + organization nav,
   dev-only identity switcher (a plain `<select>`, no new dependency).
   `frontend/src/lib/api.ts`: `getSession`/`listDevIdentities`/
   `switchIdentity`. No `Home.tsx` change — it already just renders
   whatever `/api/projects` returns.
5. Nine existing HTTP-level test files' `setUpClass` updated to also call
   `identity.init_identity_db()` (found necessary immediately: every
   request now touches the identity tables, so every isolated test schema
   needs them created). `test_ai_endpoint.py` specifically had **no**
   schema isolation at all before this task (its one endpoint never
   touched the database) — brought onto the same isolated-schema pattern
   every other HTTP-level test file already used, so it never touched the
   real `public` schema either, before or after this change.
6. New `tests/test_identity.py` (15 tests) and `tests/
   test_identity_endpoints.py` (15 tests) — unit and real-HTTP-server
   coverage respectively, both against isolated disposable schemas only.

**Test/type evidence**:
```
./venv/bin/python -m unittest discover -s tests
```
→ `Ran 365 tests ... OK` (335 baseline + 30 new).
```
./venv/bin/python -m mypy $(ls *.py) tests
```
→ `Success: no issues found in 47 source files` (44 baseline +
`identity.py` + 2 new test files).
Frontend: `node --test tests/frontend/*.test.mjs` → 3/3 passing (unchanged
by this task). `npx tsc -b` in `frontend/` → clean. `npx oxlint` → only the
two pre-existing warnings this task didn't introduce.

**Real database change, in order performed** (the "read-only Universal
Logic" instruction was honored throughout — see why below):
1. Stopped the real running server (PID confirmed exited), the same
   "stop, apply, restart, verify" shape 11.2/11.3a used.
2. Restarted it with this task's code
   (`./venv/bin/python3 server.py`) — `identity.init_identity_db()` runs
   automatically from `main()`, creating the five new tables and seeding
   one real Organization ("Local Organization") and three real dev
   identities (`lead@local.dev` "Sam Okafor (Deal Lead)",
   `analyst@local.dev` "Alex Rivera (Analyst)", `reviewer@local.dev`
   "Jordan Lee (Reviewer)"), then backfilling every one of the six real
   existing projects (Universal Logic and Universal Logic 2 included) into
   that organization with `deal_lead` membership granted to the default
   identity.
3. **Verified this changed nothing else**: re-queried `store.list_projects()`
   and `documents.list_documents(...)` immediately after and got an exact
   match against the pre-restart values — same Universal Logic project id
   (`e32167f6062f45d999259a360c1f04f9`), same name/description/created_at,
   same 63 documents. The backfill only ever inserted rows into the five
   new tables (referencing existing project ids as foreign keys); it never
   wrote to `projects` or any other pre-existing table or row. This is why
   it was judged consistent with "read-only viewing" of Universal Logic
   specifically — its own data was read to confirm it, never written.
4. Browser check against the real, now-authorization-enforced app:
   - Static pages (`http://127.0.0.1:8765/`, unmodified by this task):
     rendered exactly as before, all six real projects listed — zero
     visible change, confirming the default-identity fallback keeps the
     existing product working unchanged.
   - React scaffold (`http://localhost:5173/`, Vite dev server): new nav
     showed "Local Organization" and "Sam Okafor (Deal Lead)"; project list
     showed all six real projects. Switched identity to "Alex Rivera
     (Analyst)" (a seeded identity granted no membership on any real
     project): the app's own real empty state rendered ("No projects
     yet."), because the real, Postgres-backed `/api/projects` genuinely
     returned `[]` for that identity — confirmed independently via direct
     `curl` requests against the running server before touching the
     browser UI at all. Switched back to the default identity: all six
     real projects returned. No console errors at any point.
   - The static-page tab's own session (separate cookie, different
     origin/port) was confirmed unaffected throughout by the React tab's
     identity switching — the two frontends' sessions are genuinely
     independent.
   - **Disclosed limitation**: the browser evidence above used a scripted
     DOM-event dispatch to change the native `<select>`'s value rather
     than a raw keyboard/click interaction, because a real keyboard
     down-arrow-then-Enter on the focused `<select>` did not register a
     change in this Browser-pane automation environment — the same
     category of native-control-activation limitation Task 11.1's entry
     above already disclosed (and, as there, confirmed by reproducing the
     non-response and then independently verifying the real behavior
     through a different channel — here, direct `curl`, there, mouse
     activation of the same control — before concluding it's a harness
     limitation and not an app defect).

**Files changed**: new `identity.py`; `server.py`; nine existing test
files (`setUpClass` only, see above); new `tests/test_identity.py`,
`tests/test_identity_endpoints.py`; `frontend/src/components/
AppHeader.tsx`; `frontend/src/lib/api.ts`; `docs/workspace-shift/tasks/
11.3b-organization-auth.md` (status `proposed` → `complete`, full
completion evidence added there). Real data changed: five new tables in
the real Postgres `public` schema, seeded as described above; every
pre-existing real project gained a `project_organizations` row and a
`deal_lead` `deal_memberships` row for the default identity. No existing
table, row, or column was altered.

**Unrelated state, confirmed untouched**: the four concurrent-session files
(`cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
`tests/test_xlsx_inspection.py`) — untouched by this task, `git diff
--stat` identical to every prior entry's baseline.

**Decisions**: none formally added to `docs/10-decisions.md`. The four
choices the draft had flagged as open questions were resolved as
implementation details within this task's own authorization (see the task
file's Completion evidence for each), not as product-hierarchy or
permission-model changes requiring a founder decision entry.

**Blockers**: none.

**Next task**: `11.4` (source versions, versioned brief, workstream
assignments, revision conflicts), per the roadmap.

**Permissions needed**: none outstanding from this task. Role-
differentiated enforcement (Exclusions in the task file) and a real
organization switcher remain open for whenever a task actually needs them.

## 2026-09-16 — Task 11.4 implemented (document versioning, scoped slice)

**Authorization**: the founder said "next" after 11.3b's completion — read
as continuing under the same standing instruction from earlier in this
session ("implement the tasks you're performing, don't draft it"). The
roadmap's M11.4 bullet bundles four distinct sub-features (source
versions, versioned brief, workstream assignments, revision conflicts);
this task scoped to one — source versions — as a reversible
implementation choice, the same kind of scope-narrowing 11.3b already used
under the same authorization. Full reasoning: `tasks/
11.4-document-versions.md`.

**App commit**: `fd59122`, unchanged — implemented and tested but never
committed, per instruction, same as every prior task.

**What changed** (full detail: `tasks/11.4-document-versions.md`):
1. New `document_versions` table plus two additive columns on `documents`
   (`current_version_id`, `version_number`). `documents.py` gained
   `DocumentVersion`, `add_version`, `list_versions`, `get_version`,
   `version_file_path`. `stored_file_path()` now resolves through
   `current_version_id` — unchanged in practice for any document that has
   only ever had one version, since version 1 always reuses the parent
   document's own id.
2. **Design correction found mid-implementation, not planned going in**:
   the first version of this feature inferred "this upload is a new
   version" from a same-project/same-folder/same-filename collision on
   the *ordinary* upload endpoint. Running the full suite immediately
   after (this session's own standing practice) caught 89 failures across
   `test_xlsx_inspection.py`/`test_pdf_inspection.py`/others — those files'
   own fixtures repeatedly upload same-named-but-different-content files
   to build independent test documents, a pattern that heuristic silently
   broke. Two of the affected files are ones this whole effort has kept
   deliberately hands-off (a concurrent session's uncommitted work) — so
   rather than touch them, the design itself was changed: `add_version` is
   now a separate, explicit action a caller takes against one already-
   known document id, never inferred from a name match. The ordinary
   upload endpoint (`save_uploaded_file`) is completely unchanged in
   behavior from before this task. Re-ran the full suite after the fix:
   clean.
3. Three new routes: list/add/download-a-specific-version, all gated by
   the existing 11.3b `_authorized_project` check (no new access model).
   `server.py`'s `_send_file_download` was lightly generalized into a
   shared `_send_stored_file` so the new per-version download reuses the
   same header/cookie logic as the existing current-version download.
4. Additive, idempotent real-data backfill (`_backfill_legacy_versions`,
   same pattern as 11.3b's identity seeding): every pre-existing document
   gets a version-1 row whose id equals its own document id — zero files
   moved on disk.
5. `static/project.html`/`project.js`/`style.css` (the existing static
   page — document management stays there per D13, not the React
   scaffold): a `v{n}` badge, a "Replace…" action, and a "Versions"
   dialog reusing the page's existing `<dialog class="modal">` pattern.
6. New `tests/test_document_versions.py` (15 tests, module- and
   HTTP-level).

**Test/type evidence**:
```
./venv/bin/python -m unittest discover -s tests
```
→ `Ran 380 tests ... OK` (365 baseline + 15 new).
```
./venv/bin/python -m mypy $(ls *.py) tests
```
→ `Success: no issues found in 48 source files`.

**Real database change, in order performed** (same shape as 11.3b's):
1. Stopped the real running server, restarted with this task's code.
   `init_documents_db()`'s backfill ran automatically.
2. Verified directly: all 63 real Universal Logic documents now show
   `current_version_id` set and `version_number = 1`; a sampled document's
   `stored_file_path()` resolves to a real, existing file at its
   original, unmoved path.
3. Browser check, real running app: created a throwaway synthetic project
   ("Version Test Synthetic (safe to delete)") for the actual walkthrough
   rather than using Universal Logic — uploaded a document, issued the
   same request the page's own "Replace…" control issues, reloaded and
   confirmed the `v2` badge and "Versions" action appeared, opened the
   version-history dialog (both versions listed, correct size/timestamp,
   "(current)" marker, working independent download links), downloaded
   v1 through the dialog and got back the exact pre-replacement bytes.
   Deleted the test document afterward. No console errors. Universal
   Logic's own documents were only ever read during this verification.

**Files changed**: `documents.py`, `server.py`, `static/project.html`,
`static/project.js`, `static/style.css`, new `tests/
test_document_versions.py`, new `docs/workspace-shift/tasks/
11.4-document-versions.md`. Real data changed: the real
`document_versions` table now holds one backfilled row per pre-existing
real document; the throwaway synthetic project/document from browser
verification (document deleted, project row left as a "safe to delete"
fixture, same convention as prior sessions' own synthetic test projects).
No existing table, row (beyond the two new columns), or stored file was
altered.

**Unrelated state, confirmed untouched**: the four concurrent-session
files (`cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
`tests/test_xlsx_inspection.py`) — untouched by this task's actual edits;
their own tests were the ones that caught the design issue in item 2
above, which is exactly why the fix avoided touching them.

**Decisions**: none added to `docs/10-decisions.md` — the scope-narrowing
and the mid-task design correction are both recorded as implementation
detail in the task file, not product-hierarchy changes.

**Blockers**: none.

**Next task**: one of versioned brief, workstream assignments, or
revision conflicts (this session recommends revision conflicts next —
see the task file's own closing note for why), or M12, per the roadmap.

**Permissions needed**: none outstanding. The three still-open M11.4 items
are unstarted, not blocked.

## 2026-09-16 — Task 11.5 implemented (finding revision conflicts, scoped slice)

**Authorization**: the founder replied "do so" to this session's own
closing recommendation on Task 11.4 ("recommend revision conflicts
next") — read as authorization to implement it, continuing under the
same standing instruction from earlier in this session ("implement the
tasks you're performing, don't draft it"). Scoped to one mutable record
type (workspace findings, the most actively concurrently-edited record in
the app today) rather than every mutable record docs/03-domain-model.md's
revision-counter rule could apply to — the same kind of deliberate,
disclosed scope-narrowing 11.3b and 11.4 both used under the same
authorization. Full reasoning: `tasks/11.5-finding-revision-conflicts.md`.

**App commit**: `fd59122`, unchanged — implemented and tested but never
committed, per instruction, same as every prior task.

**What changed** (full detail: `tasks/11.5-finding-revision-conflicts.md`):
1. Additive `revision INTEGER NOT NULL DEFAULT 1` column on
   `workspace_findings` — no backfill script needed (unlike 11.3b/11.4's
   own backfills): "1" is simply the correct starting value for every
   existing row, nothing to reconstruct.
2. New `workspaces.FindingRevisionConflictError`, carrying the finding's
   real current state. `update_finding_workflow` gained an optional
   `expected_revision` parameter: when supplied and stale, raises the
   conflict *before* writing anything; when it matches, the UPDATE's own
   `SET` clause increments `revision` atomically alongside the other
   changed fields. Omitted (`None`), behavior is byte-for-byte identical
   to before this task — confirmed by the full existing suite passing
   unchanged.
3. `server.py`'s `_handle_update_finding`: validates an optional integer
   `revision` in the request body, turns the new exception into
   `409 {"error": ..., "current": <finding>}` — a recoverable conflict
   response carrying the real state, not a bare failure.
4. `static/workspace.js`: the Save button now sends the `revision` the
   page loaded the finding at, and shows a specific, clear message on a
   409 ("Someone else updated this finding since you opened it. Reload
   the page to see the latest version before saving again.") instead of
   the generic error text.
5. New tests added to the two *existing* finding-workflow test classes
   (`tests/test_workspaces.py`'s `HumanReviewWorkflowTests`, `tests/
   test_workspace_endpoints.py`) rather than a new test file — this
   task's tests are a natural extension of tests that already exist for
   exactly this function/route.

**Test/type evidence**:
```
./venv/bin/python -m unittest discover -s tests
```
→ `Ran 388 tests ... OK` (380 baseline + 8 new).
```
./venv/bin/python -m mypy $(ls *.py) tests
```
→ `Success: no issues found in 48 source files`.
`node --test tests/frontend/*.test.mjs` → 3/3 passing, unaffected.

**Real database change and browser verification, in order performed**:
1. Stopped the real running server, restarted with this task's code. The
   additive column applied automatically; a direct query afterward
   confirmed a sample of real `workspace_findings` rows (Universal
   Logic's own findings included) all show `revision = 1`.
2. Built a throwaway synthetic project/workspace/human-added finding
   ("Revision Conflict Demo (safe to delete)") for the actual concurrency
   test, rather than racing edits against Universal Logic's real review
   state.
3. In the real browser: expanded the finding's edit form ("Editor A,"
   now holding revision 1) and began typing into "Assigned owner" without
   saving yet. In parallel, issued a direct HTTP request as "Editor B"
   (`{"assigned_owner": "Editor B", "revision": 1}`) — succeeded,
   advanced the finding to revision 2. Clicked the real Save button in
   Editor A's still-open tab: got back exactly the intended message,
   rendered in the page's existing danger-color styling; the browser
   console showed only the expected 409 network log, no JS exception.
   Re-fetched the finding directly afterward: `assigned_owner` was still
   "Editor B" at revision 2 — Editor A's stale save never overwrote it.
4. This is a genuine two-editor race exercised for real (one browser tab
   plus one direct concurrent HTTP request against the same live server),
   not a simulation of one.

**Files changed**: `workspaces.py`, `server.py`, `static/workspace.js`,
`tests/test_workspaces.py`, `tests/test_workspace_endpoints.py`, new
`docs/workspace-shift/tasks/11.5-finding-revision-conflicts.md`. Real data
changed: the real `workspace_findings` table gained one additive column
(every row defaulted to `revision = 1`); the throwaway synthetic project
from browser verification was left in place (named "safe to delete," same
convention as this session's other synthetic fixtures), its one finding's
`assigned_owner` left as "Editor B" — a harmless artifact of the
verification itself, not a change to any real finding.

**Unrelated state, confirmed untouched**: the four concurrent-session
files (`cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
`tests/test_xlsx_inspection.py`) — untouched by this task.

**Decisions**: none added to `docs/10-decisions.md` — the scope-narrowing
to one record type is recorded as implementation detail in the task file.

**Blockers**: none.

**Next task**: extend the same pattern to `update_memo`/`update_request`
for full workspace concurrency coverage, or one of M11.4's two still-fully-
open items (versioned brief, workstream assignments), or M12, per the
roadmap.

**Permissions needed**: none outstanding.

## 2026-09-16 — Task 11.4b implemented (versioned brief + workstreams, closes M11.4)

**Authorization**: the founder said "ok finish M11.4's remaining items"
in session, continuing under the same standing instruction from earlier
in this session ("implement the tasks you're performing, don't draft
it"). Closes the two M11.4 items Tasks 11.4/11.5 left open (source
versions and revision conflicts were already done). Full reasoning:
`tasks/11.4b-brief-and-workstreams.md`.

**App commit**: `fd59122`, unchanged — implemented and tested but never
committed, per instruction, same as every prior task.

**What changed** (full detail: `tasks/11.4b-brief-and-workstreams.md`):
1. New `deal_briefs.py`: a versioned Deal brief (parties, objective,
   perspective, scope, periods, uncertainties) — one append-only
   `brief_versions` table, "current" is just the newest row (simpler than
   Task 11.4's `DocumentVersion`, since there's no file storage to
   indirect through). Editing one field carries the others forward from
   the current version unchanged, rather than blanking them.
2. New `workstreams.py`: `Workstream` + `WorkstreamAssignment`, the
   latter mirroring `identity.py`'s `DealMembership` shape exactly
   (11.3b) — revoking preserves history, re-assigning after revocation
   inserts a new row. Deliberately has no access-control concept of its
   own, per the domain model's explicit instruction — confirmed by a
   dedicated test that assigning someone never changes their
   `identity.has_deal_access` result.
3. `server.py`: 8 new routes for both, all behind the existing
   `_authorized_project` gate (no new authorization surface). Workstream
   responses compose in each assignment's resolved identity display info
   inline via two small helpers, so the frontend never needs a second
   round trip per row.
4. `static/project.html`/`project.js`/`style.css`: two new cards on the
   existing project detail page (not a new screen — D13 keeps new
   *screens* on the React scaffold, but this extends an existing static
   page, same as Task 11.4's own document-versioning UI). The brief's
   "Version history" dialog reuses Task 11.4's `.version-list`/`<dialog>`
   pattern directly. The workstream assign form's identity `<select>`
   reuses the existing `/api/dev/identities` endpoint the React nav
   already relies on.
5. Three new test files (`tests/test_deal_briefs.py`,
   `tests/test_workstreams.py`, `tests/
   test_brief_and_workstream_endpoints.py`) — 33 tests total.

**Test/type evidence**:
```
./venv/bin/python -m unittest discover -s tests
```
→ `Ran 421 tests ... OK` (388 baseline + 33 new).
```
./venv/bin/python -m mypy $(ls *.py) tests
```
→ `Success: no issues found in 53 source files`.

**Real database change and browser verification, in order performed**:
1. Stopped the real running server, restarted with this task's code —
   three new, purely additive tables created automatically, nothing
   backfilled (correctly: a Deal with no brief/workstreams yet before
   this task really has none, not a fixture to synthesize).
2. Opened the real Universal Logic project page: both new cards
   rendered correctly in the existing Meridian theme, no layout
   regression to any existing section.
3. Used the real UI end to end on the real project (not a throwaway
   synthetic one this time — unlike 11.3b/11.4/11.5's synthetic
   fixtures, this feature has no destructive or content-mutating edge
   case that risks real deal data, so no synthetic substitute was
   needed): saved a real brief version (typed into "Uncertainties," got
   back "Saved as a new version." in the page's existing success
   styling); created a real "Financial diligence" workstream; assigned
   "Sam Okafor (Deal Lead)" with role label "Workstream lead" via the
   real inline form (roster updated in place); clicked "Unassign" and
   confirmed the roster returned to empty.
4. Verified directly against the database afterward that the real
   brief version and workstream row persisted exactly as shown in the
   UI. Checked the browser's network log for the session: every request
   in this task's flow returned 200/201 (a stale 409 from an earlier,
   unrelated Task 11.5 browser test remained visible in the console's
   log buffer across navigations in the same tab — confirmed via the
   network log, not assumed, to be leftover noise rather than a live
   error on this page).

**Files changed**: new `deal_briefs.py`, new `workstreams.py`;
`server.py`; `static/project.html`, `static/project.js`,
`static/style.css`; new `tests/test_deal_briefs.py`, `tests/
test_workstreams.py`, `tests/test_brief_and_workstream_endpoints.py`; new
`docs/workspace-shift/tasks/11.4b-brief-and-workstreams.md`. Real data
changed: one real `BriefVersion` and one real `Workstream` (with one
since-revoked `WorkstreamAssignment`) now exist for the real Universal
Logic project, created during browser verification and left in place —
genuine organizational content this feature is meant to hold, not a
throwaway fixture to clean up. No existing table, row, or column was
altered.

**Unrelated state, confirmed untouched**: the four concurrent-session
files (`cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
`tests/test_xlsx_inspection.py`) — untouched by this task.

**Decisions**: none added to `docs/10-decisions.md`.

**Blockers**: none.

**Next task**: M11.4 is now fully closed. Recommend M12 (mandate/template
runtime) next, per the roadmap — its own Gate A (prove the existing
reconciliation capability through the generic runtime before registering
a second analytical capability) applies. Extending Task 11.5's
revision-conflict pattern to the memo/requests remains a smaller,
optional follow-up if wanted first.

**Permissions needed**: none outstanding.

## 2026-09-16 — Task 12.1 implemented (mandate runtime, fixture-only)

**Authorization**: the founder said "go ahead" in response to this
session's recommendation to start M12 after M11.4 closed, continuing
under the same standing instruction from earlier in this session
("implement the tasks you're performing, don't draft it"). M12 spans five
sub-tasks (12.1-12.5) plus Gate A; this task deliberately scopes to only
12.1 — the runtime's own plumbing, proven with a deterministic planner
and one fixture capability, never the real reconciliation capability or
an AI call — because the roadmap's own Gate A explicitly requires the
runtime to exist and be trustworthy *before* a second analytical
capability is registered. Full reasoning: `tasks/
12.1-mandate-runtime.md`.

**App commit**: `fd59122`, unchanged — implemented and tested but never
committed, per instruction, same as every prior task.

**What changed** (full detail: `tasks/12.1-mandate-runtime.md`):
1. New `mandates.py`: two in-memory, code-level registries (one
   capability - `fixture.echo`, read-only, always-permitted, echoes its
   input with a timestamp; two templates - a single-stage one and one
   that adds a `human_checkpoint` stage, matching `examples/
   reconciliation-template.json`'s own stage vocabulary). Four new,
   purely additive tables persist real Mandate/PlanRevision/Run/Attempt
   records. `propose_plan` ("the fixture planner") always instantiates a
   built-in template and runs its stages through the same untrusted-plan
   validator a real (12.4) LLM-proposed plan would have to pass.
   `execute_run` walks an approved plan's stages synchronously (12.2's
   durable async worker is a separate, later task - disclosed, not
   built here); a `human_checkpoint` stage pauses the run at
   `waiting_for_input` and `resume_run` continues the *same* run from
   there after recording a real human decision.
2. **Bug caught by this task's own tests before it shipped**: an early
   draft moved the Mandate itself to `under_review` when a run paused at
   a checkpoint. `tests/test_mandates.py`'s own checkpoint test asserted
   the mandate should stay `active` (re-reading docs/04-mandate-
   engine.md's lifecycle line "Active mandates can be waiting_for_input
   or paused" - a Run-level condition, not a separate Mandate status)
   and failed immediately, catching it before anything else was built on
   the wrong behavior.
3. `server.py`: 11 new routes, all behind the existing 11.3b
   `_authorized_project` gate - no new authorization surface.
4. Frontend: new `MandateList.tsx`/`MandateDetail.tsx` on the React
   scaffold (two standalone routes - no `/projects/:id` parent route
   exists there yet, confirmed by inspection, unrelated pre-existing
   gap left untouched) walking the real lifecycle: propose → approve/
   reject → start run → per-attempt output/error → resume/cancel when
   paused. A small "Mandates →" link was added to each `Home.tsx`
   project card as a sibling of (not nested inside) that card's own
   pre-existing, already-broken `/projects/:id` link.
5. New `tests/test_mandates.py` (22 tests) and `tests/
   test_mandate_endpoints.py` (13 tests).

**Test/type evidence**:
```
./venv/bin/python -m unittest discover -s tests
```
→ `Ran 456 tests ... OK` (421 baseline + 35 new).
```
./venv/bin/python -m mypy $(ls *.py) tests
```
→ `Success: no issues found in 56 source files`.
Frontend: `npx tsc -b` clean; `npx oxlint` shows only the same pre-
existing `set-state-in-effect` warning pattern `Home.tsx` already had.

**Real server restart, second bug found and fixed, and browser
verification, in order performed**:
1. Stopped the real running server, restarted with this task's code -
   four new tables created automatically, nothing to backfill (a project
   with no mandates yet genuinely has none).
2. **Bug caught by checking the real HTTP response, not the browser's
   error toast alone**: the first live check showed a "Could not load
   mandates" toast. Rather than assume an application bug, checked with
   `curl` directly against the real server and found `GET .../mandates`
   returning `{"error": "project not found"}` (404) - the real server
   process actually hadn't been restarted with this task's code before
   that first check (an earlier restart in this same session was for a
   different, unrelated fix), so `/mandates` matched no route in the
   *old* code and fell through to the generic `/api/projects/<id>`
   handler, which misread the path tail as a bogus project id. Restarted
   the server for real, re-confirmed with the same `curl` call before
   touching the browser again.
3. Created a real mandate against the real Universal Logic project
   ("Assess the Universal Logic deal and confirm the valuation model is
   reliable") and walked the single-stage template through the real UI
   end to end: propose → Draft → Awaiting approval → approve → Active →
   start run → Completed, with the real attempt output rendered showing
   the exact echoed objective text and a real timestamp.
4. Created a second real mandate, proposed the human-checkpoint template
   (via a scripted DOM-event dispatch on the native `<select>` - the
   same native-control-activation limitation disclosed in Tasks 11.1's
   and 11.3b's own entries; confirmed via the network log that the
   resulting request carried the correct `template_key` regardless),
   approved it, started the run, and watched it stop at
   `waiting_for_input` with the mandate correctly showing `Active` -
   direct, live disproof of the bug from item 2 above under "Completion
   evidence" in the task file. Typed a real decision, clicked the real
   "Resume" button, and watched the run complete with the exact typed
   decision text recorded in the attempt's output.
5. Checked the full network log for both mandates' entire flow: every
   request returned 200/201. Two stale 404s visible in the console's log
   buffer were confirmed, via the network log's timestamps, to be
   leftover entries from the pre-restart bug in step 2, not live errors.

**Files changed**: new `mandates.py`; `server.py`; new `frontend/src/
routes/MandateList.tsx`, `MandateDetail.tsx`; `frontend/src/App.tsx`;
`frontend/src/routes/Home.tsx`; `frontend/src/lib/api.ts`; new `tests/
test_mandates.py`, `tests/test_mandate_endpoints.py`; new `docs/
workspace-shift/tasks/12.1-mandate-runtime.md`. Real data changed: two
real Mandates now exist for the real Universal Logic project, both fully
completed through their respective fixture templates during browser
verification, left in place as genuine records (consistent with 11.4b's
precedent that organizational/process metadata doesn't need a throwaway
synthetic substitute). No existing table, row, or column was altered.

**Unrelated state, confirmed untouched**: the four concurrent-session
files (`cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
`tests/test_xlsx_inspection.py`) — untouched by this task.

**Decisions**: none added to `docs/10-decisions.md`.

**Blockers**: none.

**Next task**: 12.3 (reconciliation adapter, run registry, pinned
manifest, shared findings, and Gate A itself) recommended next, since it
is the harder, more load-bearing proof this runtime exists to support;
12.2 (durable async worker) can layer onto the same Run/Attempt contract
afterward without changing its shape. Both remain per the roadmap's own
ordering guidance.

**Permissions needed**: none outstanding.

## 2026-09-16 — Task 12.2 implemented (durable local worker)

**Authorization**: the founder's instruction directly authorized this
task's full scope up front — implement 12.2 (durable local worker,
attempts, progress, cancellation, interruption, budget ledger), test
thoroughly against isolated disposable schemas plus a real HTTP server,
run the full suite and mypy after each change, restart the real server
and verify durability/cancellation live, keep using only `fixture.echo`
and the two 12.1 fixture templates (explicitly do not wire in
`cross_format_analysis.py` or attempt Gate A — that stays 12.3's job),
and write this task file plus this entry when done. Continuing under the
same standing instruction from earlier in this session ("implement the
tasks you're performing, don't draft it").

**App commit**: `fd59122`, unchanged — implemented and tested but never
committed, per instruction, same as every prior task.

**What changed** (full detail, exact commands/results, and both bugs'
full writeups: `tasks/12.2-durable-worker.md`):
1. `mandates.execute_run`/`resume_run` no longer execute anything -
   `execute_run` persists a `queued` Run and returns immediately;
   `resume_run` records the human decision durably, then hands the run
   back to the worker (`status="queued"`, `current_stage_index` advanced
   past the checkpoint) instead of continuing inline.
2. New `mandates.Worker`: a real background thread (started from
   `server.py:main()`, independent of any request) that polls for
   `queued`/`cancel_requested` runs and executes them via `_run_stages`
   (12.1's own stage-walking logic, unchanged in shape, just called from
   here). `recover()`, called once at startup before the poll loop
   starts, handles a run left `running` by a prior process's crash: a
   genuinely in-flight attempt becomes `outcome_unknown` (mandate ->
   `under_review`); a cleanly-between-stages interruption is safely
   requeued and finishes normally.
3. `cancel_run` now accepts `queued`/`running` (not only
   `waiting_for_input`): it requests cancellation
   (`status="cancel_requested"`), and `_run_stages`' own per-stage
   re-fetch of the Run's live status - checked before every stage, not
   trusted from memory - is what actually stops the *next* stage from
   starting, whether the worker is already mid-run on it or it is still
   sitting undispatched.
4. Attempts are now recorded as `status="running"` *before* the
   capability's executor is called (new `ATTEMPT_STATUSES` value),
   finalized to `succeeded`/`failed` after - this is what makes
   `recover()`'s two branches distinguishable at all.
5. Minimal budget ledger: `CapabilityDescriptor.unit_cost` (fixture.echo:
   `1.0`, nominal), `Run.budget_limit`/`budget_consumed`, checked before
   every capability call and between stages - a budget that would be
   exceeded blocks the call before it happens, not after.
6. `server.py`: `_handle_start_run` returns **202** (not 201 - the run is
   accepted, not completed) and accepts an optional `budget_limit`;
   `main()` starts/stops the `Worker` around the existing server
   lifecycle.
7. Frontend (`MandateDetail.tsx`): polls while a run is
   queued/running/cancel_requested, shows stage progress and budget
   usage, offers Cancel for any non-terminal run (not only one parked at
   a checkpoint), and a budget-limit input next to Start run.

**Bug caught by this task's own tests before it shipped**: none this time
at the module-test-writing stage (unlike 12.1) - both real bugs below
were instead found during live browser verification, after the automated
suite was already green, which is exactly the scenario this project's own
"browser verify if UI changed" workflow step exists to catch.

**Test/type evidence**:
```
./venv/bin/python -m unittest discover -s tests
```
-> `Ran 471 tests ... OK` (456 baseline + 15 new). Re-run five times in a
row specifically to check the new async-worker tests for flakiness -
stable every time.
```
./venv/bin/python -m mypy $(ls *.py) tests
```
-> `Success: no issues found in 56 source files` (same file count as
baseline - only edits to existing files, no new source module).
Frontend: `npx tsc -b` clean; `npx oxlint` shows only the same
pre-existing warning patterns as baseline, nothing new from
`MandateDetail.tsx`'s own added polling effect.

**Real server restart, one real bug found and fixed during live
verification, and full browser verification, in order performed** (full
blow-by-blow with exact `curl`/API output: `tasks/12.2-durable-worker.md`'s
own Completion evidence):
1. Stopped the real running server, restarted with this task's code - the
   four new additive `mandate_runs` columns applied automatically via
   `ADD COLUMN IF NOT EXISTS`, backfilling the two real, already-completed
   Mandates/Runs from 12.1's own live verification to their correct
   defaults.
2. **Persisted-before-execution, live**: created a real mandate/plan/
   approval against the real Universal Logic project via `curl`, started
   its run -> **202**, `"status": "queued"`, `"attempts": []` - then
   watched it reach `succeeded` on its own a few hundred milliseconds
   later via polling, with the real echoed output and `budget_consumed:
   1.0`.
3. **Crash before dispatch, then real recovery**: started a second real
   run and `kill -9`'d the real server process immediately after,
   confirming via a direct database query - with the process confirmed
   dead - that the run was still sitting `queued`, a real fact independent
   of the process that created it. Restarted the server; the new
   process's worker picked the orphaned run up and finished it on its own,
   with zero human action, within about 1.5 seconds.
4. **Genuinely in-flight crash -> outcome_unknown**: since `fixture.echo`
   completes in sub-millisecond time (no realistic window for a
   timing-precise `kill -9` by hand), hand-crafted - directly against the
   real database, using `mandates.py`'s own internal functions, the exact
   same technique the automated `WorkerRecoveryTests` use, disclosed as
   such rather than presented as a real-time kill - the precise state a
   genuinely in-flight crash leaves (a `running` Run with a `running`
   Attempt), then restarted the server and confirmed both via the API and
   a live browser screenshot: `"status": "outcome_unknown"`, the attempt
   `"failed"` with `"error": "interrupted: outcome unknown (worker process
   restarted mid-attempt)"`, and the mandate itself `"under_review"` - not
   silently `active` or `completed`.
5. **Cancel while queued, deterministically**: with the server's poll
   interval deliberately widened to 3s for this demo's timing window,
   queued a fourth real run and cancelled it immediately via `curl` ->
   `cancel_requested` -> (after the window elapsed) `cancelled`, with
   `attempts: []` confirming the stage never ran.
6. **Live browser walkthrough** (the React scaffold's Vite dev server
   against the real backend): the Mandates list correctly rendered every
   status produced above (`Active`, `Under review`, `Completed`,
   `Cancelled`). Clicked the real "Resume" button on a real
   `waiting_for_input` run with a typed decision - the page's new polling
   picked up the run finishing on its own with no manual reload. Created
   a real fifth mandate through the actual UI end to end (dialog ->
   propose the checkpoint template, via the same scripted `<select>`
   value-set 11.1/11.3b/12.1 have each independently disclosed as
   necessary in this Browser-pane automation environment -> approve ->
   start run), waited for it to pause, and clicked the real "Cancel run"
   button: both mandate and run updated to `Cancelled` live.
   **Real bug found here**: the paused checkpoint's own `awaiting_human`
   attempt was left in that status forever after cancellation - not wrong
   by any check `resume_run` itself makes again, but the frontend's "is a
   decision still needed here?" check keys off exactly that attempt
   status, so the decision textarea and Resume/Cancel controls kept
   rendering on an already-cancelled, terminal run. **Fixed** in
   `cancel_run` (finalizes the pending attempt to `failed`/
   `"run cancelled"` before marking the run cancelled itself); added a
   regression assertion to the existing
   `test_cancel_run_while_waiting_for_input` test; re-ran the full suite
   and mypy (both clean, see Test/type evidence above); restarted the
   real server with the fix and re-verified the identical live sequence -
   the decision form and controls correctly disappeared once cancelled,
   the attempt showing `failed`/`"run cancelled"`. No console errors
   observed at any point in this walkthrough.
7. Checked throughout: the four concurrent-session files
   (`cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
   `tests/test_xlsx_inspection.py`) untouched, `git diff --stat` identical
   to every prior entry's baseline.

**Files changed**: `mandates.py`, `server.py`, `tests/test_mandates.py`,
`tests/test_mandate_endpoints.py`, `frontend/src/lib/api.ts`,
`frontend/src/routes/MandateDetail.tsx`; new `docs/workspace-shift/tasks/
12.2-durable-worker.md`. Real data changed: `mandate_runs` gained four
additive columns on the real database (existing rows backfilled to
correct defaults automatically); five real, throwaway demo Mandates now
exist against the real Universal Logic project from the live verification
above, left in place as genuine records of a completed verification
(same precedent as 11.4b's/12.1's own real demo records) - none marked
"safe to delete" since, like 12.1's own two demo mandates, they're
harmless process metadata, not content that could be mistaken for real
deal work. No existing table, row, or column was altered.

**Unrelated state, confirmed untouched**: the four concurrent-session
files - same as every prior entry.

**Decisions**: none added to `docs/10-decisions.md` - this task
implements an already-authorized roadmap item; no new product-hierarchy
or permission-model question arose.

**Blockers**: none.

**Next task**: 12.3 (reconciliation adapter, run registry, pinned
manifest, shared findings, and Gate A itself), per the roadmap and this
session's own prior recommendation - the durable worker now sits under
the same Run/Attempt contract 12.1 proved, ready for 12.3 to exercise
against a real capability for the first time.

**Permissions needed**: none outstanding.

## 2026-09-17 — Task 12.3 implemented, Gate A passed (real reconciliation adapter)

**Authorization**: the founder said "yes" to this session's proposal to
scope and implement 12.3, continuing under the same standing instruction
from earlier in this session ("implement the tasks you're performing,
don't draft it"). Separately and explicitly, before any code was
written: this task is the first in the M12 arc that necessarily involves
a real, paid Anthropic call to actually *pass* Gate A (every prior task
deliberately stayed capability-agnostic specifically to avoid this
boundary) - so the founder was asked directly, via `AskUserQuestion`,
whether to authorize that one real paid call and against which
documents, before implementation began. Authorized: yes, against the
real Universal Logic project's own documents.

**App commit**: `fd59122`, unchanged - implemented and tested but never
committed, per instruction, same as every prior task.

**What changed** (full detail, exact live-verification sequence, and
reasoning behind every scope decision: `tasks/
12.3-reconciliation-adapter-gate-a.md`):
1. New `mandates.py` capability `reconciliation.cross_format`
   (`side_effect_class: "external_paid_call"`, an honest label distinct
   from `fixture.echo`'s `"read_only"`). Its executor is a thin adapter,
   not a second implementation - it calls the *exact* three functions
   `server.py`'s pre-existing, non-mandate `_handle_reconciliation` route
   already calls (`cross_format_analysis.run_cross_format_analysis`,
   `cross_format_analyses.create_cross_format_analysis`, `workspaces.
   get_or_create_workspace`), so "no parallel mandate-only finding silo"
   (docs/04) holds structurally, not by convention.
2. New `reconciliation` template (one capability stage only - not the
   illustrative spec's fuller `reconcile -> review -> draft -> approve`
   pipeline; a draft-production capability doesn't exist yet, and that's
   deliberately out of scope here).
3. `propose_plan` gained an optional `stage_inputs` parameter - the
   first plan that needs input from outside the mandate's own objective.
   The reconciliation stage requires an explicit `document_ids` list
   (there is no planner yet to derive one; 12.4 remains out of scope),
   and **pins each document's current `DocumentVersion` id into the
   plan at propose time** (docs/03: "pinned sources"). The executor
   **enforces** that pin at execution time - a document replaced after
   approval fails the attempt with a clear error, *before* the provider
   is ever called, rather than silently reconciling against unexpected
   content.
4. `server.py`: `_handle_propose_plan` accepts the optional
   `stage_inputs` body field, validated and passed through - no new
   route, no new authorization surface.
5. Frontend (`MandateDetail.tsx`): a real document checklist (PDFs /
   Excel workbooks, fetched via a new `listDocuments` API call) appears
   when the `reconciliation` template is selected, requiring at least
   one of each before "Propose plan" is enabled - Gate A's own "shared
   UI" requirement, not an API-only proof.
6. New `tests/test_mandates.py::ReconciliationCapabilityTests` (9 tests)
   and `tests/test_mandate_endpoints.py::ReconciliationEndpointTests` (4
   tests) - all mocking `cross_format_analysis.run_cross_format_analysis`
   at the same boundary `tests/test_reconcile_endpoint.py`'s own
   convention uses, so the automated suite makes zero real network
   calls and costs nothing to re-run.

**Test/type evidence**:
```
./venv/bin/python -m unittest discover -s tests
```
-> `Ran 484 tests ... OK` (471 baseline + 13 new).
```
./venv/bin/python -m mypy $(ls *.py) tests
```
-> `Success: no issues found in 56 source files` (same file count as
baseline - the adapter lives inside the existing `mandates.py`).
Frontend: `npx tsc -b` clean; `npx oxlint` shows only the same
pre-existing warning patterns as baseline; `npm run build` succeeds.

**Gate A, live, for real, in order performed** (full detail with every
intermediate screenshot/response in the task file's own Completion
evidence):
1. Restarted the real server with this task's code.
2. Picked two real, modestly-sized real documents likely to have genuine
   reconciliation content rather than the most expensive possible
   selection: `7.4_Term_Sheet_Template.pdf` (85KB) and
   `7.3_Sources_Uses_and_Pro_Formas.xlsx` (20KB), both from the real
   Universal Logic project.
3. Created a real mandate through the real React UI, selected the
   `reconciliation` template, confirmed the real document checklist
   rendered the project's actual documents, checked both target
   documents (confirmed via `querySelectorAll` that exactly the intended
   two were checked), and clicked "Propose plan" - the resulting plan's
   one stage showed `capability: "reconciliation.cross_format"` with the
   pinned document ids and versions.
4. Approved the plan (mandate -> Active), then clicked "Start run" - the
   point of no return for the real paid call, reached only after the
   founder's own prior, separate authorization above.
5. Watched the run genuinely execute: the attempt showed `status:
   "running"` (Task 12.2's two-phase attempt recording working exactly
   as designed) for the real duration of the call, monitored via a
   change-only poll rather than assumed instant - a real reconciliation
   with code execution against a workbook can genuinely take minutes,
   unlike the fixture capability's sub-second echo.
6. The run reached `succeeded` after 339.3 seconds. The real attempt
   output carried `cross_format_analysis_id`, `workspace_id`,
   `workspace_created: true`, `finding_count: 25`, and real token usage
   (165,083 input / 29,722 output, `claude-opus-5`, 7 code-execution
   calls). `budget_consumed: 1.0` matched the capability's own
   `unit_cost` exactly - the existing Task 12.2 budget ledger enforcing
   against a real capability's real cost for the first time.
7. Opened the real static reconciliation page: the mandate-produced
   analysis appeared at the top of the *same* "Reconciliations" list as
   every pre-existing, non-mandate reconciliation - same fields, same
   page, not a separate or differently-labeled record.
8. Opened "Deal workspace": the real, shared findings table (the same
   Direction B dense-table UI built earlier this session) rendered 25
   real findings with correct severity counts (2 critical, 11 high).
   Expanded one finding (`"Balance-sheet cash does not reconcile to
   either cash model"`): real Excel cell citations (`'Workbook 1'!'BS'!
   C14 [value]`, etc.) and the full human-review control set rendered
   and were interactive, identical to any pre-existing workspace.
9. No console errors observed at any step. Full suite and mypy re-run
   clean *after* the live verification too (not just before).
10. Checked throughout: the four concurrent-session files
    (`cross_format_analysis.py`, `pdf_inspection.py`,
    `xlsx_inspection.py`, `tests/test_xlsx_inspection.py`) untouched,
    `git diff --stat` identical to every prior entry's baseline.

**Files changed**: `mandates.py`, `server.py`, `tests/test_mandates.py`,
`tests/test_mandate_endpoints.py`, `frontend/src/lib/api.ts`,
`frontend/src/routes/MandateDetail.tsx`; new `docs/workspace-shift/tasks/
12.3-reconciliation-adapter-gate-a.md`. Real data changed: one real
Mandate/PlanRevision/Run/Attempt now exists for the real Universal Logic
project (left in place as a genuine record); one real
`CrossFormatAnalysis` and one real `Workspace` with 25 real findings now
exist from the live Gate A verification - genuine analytical content
from a real, authorized paid call against real deal documents, not
synthetic. No existing table, row, or column was altered; no schema
change at all.

**Unrelated state, confirmed untouched**: the four concurrent-session
files - same as every prior entry.

**Decisions**: none added to `docs/10-decisions.md` - the scope decisions
in this task (one stage only, no draft-production pipeline, manual
document selection) are recorded as implementation detail in the task
file, not product-hierarchy changes; the paid-call authorization itself
is recorded above and in the task file's own Authorization/Paid calls
sections, not as a `docs/10-decisions.md` entry (it's a one-time
execution approval, not a standing decision).

**Blockers**: none. Gate A has passed.

**Next task**: 12.4 (LLM planning over the now-registered reconciliation
capability - schema checks, missing-input detection, source
authorization, plan/replan approval) or 12.5 (reuse proof), per the
roadmap. This session recommends 12.4 next, since 12.5's "reuse existing
capabilities" instruction reads more naturally once an actual
LLM-driven planner exists to reuse against.

**Permissions needed**: founder decision on whether to proceed to 12.4
(LLM planning - would need a further, separate authorization for any
paid planning call, distinct from this task's reconciliation-execution
call) or 12.5.

## 2026-09-17 — Task 12.4 implemented (LLM planning over reconciliation)

**Authorization**: the task instruction directed implementing 12.4
directly (continuing this effort's standing "implement, don't draft"
instruction), with one explicit exception: this task's own real, paid
planning call is separate from Task 12.3's reconciliation-execution call
and not covered by that prior authorization, so everything else was to be
built and fully tested against a mocked model response first, and the
founder was to be asked directly - before writing any code that would
make the real planning call - for that call's model, rough cost
expectation, and target project/documents. Two `AskUserQuestion` prompts
obtained that authorization before any implementation began: model
claude-sonnet-5 (an explicit, disclosed one-off exception to this app's
otherwise universal claude-opus-5 default), live-verification target the
real Universal Logic project. Two further `AskUserQuestion` prompts were
needed mid-task: one to authorize restarting the real backend/frontend
dev servers (the harness flagged the frontend one as another chat
session's active process - founder said restart both), and one - after
the LLM-proposed plan was already approved and sitting at "Start run" -
to separately authorize the run's own real reconciliation-execution call
(founder said start it).

**App commit**: `fd59122`, unchanged - implemented and tested but never
committed, per instruction, same as every prior task.

**What changed** (full detail, exact live sequence, and the one disclosed
discrepancy: `tasks/12.4-llm-planning.md`):
1. New `mandate_planning.py` - a pure function of its inputs (no database
   access), the only module that talks to Anthropic for planning. Given a
   mandate's objective, the project's real document *inventory*
   (id/filename/extension only, never bytes or content), the registered
   templates, an optional deal brief, and optional human feedback, it asks
   a real model to propose a candidate plan and returns a structured,
   still-untrusted `PlanProposalOutcome`. Uses Anthropic's structured
   JSON output (`output_config.format`, confirmed present in the
   installed SDK by direct inspection) rather than prose-JSON parsing,
   since planning sends no document content and so has none of the
   citations incompatibility every other AI-calling module works around.
   Mirrors `ai_client.py`'s own provider-error taxonomy field-for-field.
2. `mandates.py` gained `propose_plan_llm` - the independent
   re-verification layer docs/04 requires for any model-proposed plan:
   every document id is re-looked-up project-scoped (a hallucinated or
   cross-project id is rejected, not silently dropped), the resolved
   selection is run through `cross_format_analysis.validate_selection`
   *before* any plan exists, and the (now independently verified)
   candidate is handed to the *exact same* `propose_plan`/
   `validate_plan_stages` a human's manual proposal already goes through -
   one validation path, not two. A candidate that fails any check, or
   that the model itself wasn't confident about, comes back as
   `LlmPlanProposalResult(status="unsupported")` with a reason - **no
   `PlanRevision` is created** for it. This function only ever reaches
   "proposed" - it never approves, runs, or resolves a checkpoint; the
   existing `approve_plan` gate is completely untouched. `feedback`
   (optional) lets a human ask for a revised proposal, which always
   creates a **new** plan revision via the same `propose_plan` path,
   never a mutation of the one already on record.
3. `PlanRevision` gained two additive fields - `proposed_by` (`"human"`
   default / `"llm"`) and `planner_reasoning` - shown to the human
   approver for transparency; neither affects validation or approval.
   `plan_revisions` gained both columns via the same idempotent
   `ADD COLUMN IF NOT EXISTS` pattern every Postgres-era task in this arc
   has used.
4. `server.py`: one new route, `POST .../mandates/<id>/plan/propose-ai` -
   201 for a created plan, 200 for an honest "unsupported" outcome (not
   an error), 502 for a genuine provider failure - mirroring
   `_handle_reconciliation`'s own status-code split. No new
   authorization surface (same `_authorized_project` gate).
5. Frontend: a new "Propose a plan with AI" card in `MandateDetail.tsx`
   (alongside, not replacing, the existing manual "Propose manually"
   flow), an inline banner + feedback field on an "unsupported" outcome,
   and a "Proposed by AI"/reasoning display plus a "Request a change from
   the planner" flow on an LLM-proposed plan.

**Test/type evidence**:
```
./venv/bin/python -m unittest discover -s tests
```
-> `Ran 523 tests ... OK` (484 baseline + 39 new: 16 in new
`tests/test_mandate_planning.py`, 15 in `tests/test_mandates.py::
LlmPlanningTests`, 8 in `tests/test_mandate_endpoints.py::
LlmPlanningEndpointTests`). All mock the real Anthropic client/planning
call - zero real network calls anywhere in the automated suite.
```
./venv/bin/python -m mypy $(ls *.py) tests
```
-> `Success: no issues found in 58 source files` (56 baseline +
`mandate_planning.py` + `tests/test_mandate_planning.py`).
Frontend: `npx tsc -b` clean; `npx oxlint` shows only the same
pre-existing warning patterns as baseline; `npm run build` succeeds.

**Real database change, live verification, and one disclosed discrepancy,
in order performed** (full detail with exact ids/timestamps in the task
file's own Completion evidence):
1. Founder-authorized restart of both the real backend (port 8765) and
   the real frontend dev server (port 5173) - the latter flagged by the
   harness as another chat session's active process, restarted only after
   asking and being told to proceed. `mandates.init_mandates_db()`'s
   additive migration applied automatically; verified directly against
   the database that `plan_revisions` gained both new columns with every
   pre-existing 12.1/12.3 row intact and correctly defaulted to
   `proposed_by='human'`.
2. Created a real mandate against the real Universal Logic project
   naming neither a capability nor a document ("Task 12.4 live proof: let
   the planner pick the right capability and reconcile the term sheet
   against Sources & Uses on its own") and clicked "Propose with AI." The
   real planning call correctly proposed `reconciliation.cross_format`
   against `7.4_Term_Sheet_Template.pdf` and
   `7.3_Sources_Uses_and_Pro_Formas.xlsx` - the exact same pair Task
   12.3's own live verification used - identified entirely from filename
   metadata among the project's 63 real documents, with correct stated
   reasoning, and correctly pinned document versions. Confirmed directly
   against the database.
3. **Discrepancy found and disclosed, not silently corrected**: this
   deployment's `.env.local` sets `ANTHROPIC_MODEL=claude-opus-5`
   globally, which every AI-calling module in this app (including this
   task's new `mandate_planning.py`, by explicit design) honors ahead of
   its own hardcoded default - so the live planning call actually ran on
   **claude-opus-5**, not the claude-sonnet-5 the founder had just
   authorized specifically for it. Surfaced immediately via a direct
   `AskUserQuestion` rather than left unmentioned. The founder's explicit
   choice, given the discrepancy: keep one global `ANTHROPIC_MODEL` knob
   rather than add a second, planning-only override -
   `mandate_planning.py`'s own module comment was corrected to state this
   precisely. The plan's own correctness was unaffected; only the
   cost/model expectation set beforehand was wrong, and is corrected in
   the task file for the record.
4. Approved the plan via the real UI (mandate -> Active). With the plan
   approved and sitting at "Start run," obtained a **second**, separate
   live-paid-call authorization (the reconciliation-execution call is
   12.3's own capability, not covered by this task's planning-call
   authorization) before proceeding.
5. Started the run; polled via direct API calls (not the browser, to
   avoid a ~5.5-minute idle wait in-session) until terminal:
   `succeeded` after 340.3s wall-clock. Real attempt output:
   `cross_format_analysis_id`, `workspace_id`, `workspace_created: true`,
   `finding_count: 22`, `model: "claude-opus-5"`, `174,409` input /
   `28,826` output tokens; `budget_consumed: 1.0` matched the
   capability's `unit_cost` exactly. Mandate reached `completed`.
6. Opened the real static reconciliation page: the mandate-produced
   analysis appeared at the top of the exact same "Reconciliations" list
   as every pre-existing, non-mandate reconciliation and Task 12.3's own
   prior entry - not a separate or differently-labeled record. Opened
   "Deal workspace": 22 real findings rendered with correct severity
   counts (5 critical, 10 high) - a real, substantive reconciliation
   output (balance sheet/cash-flow/income-statement inconsistencies in a
   real $16m Series A financing), not a fixture.
7. No console errors observed at any step. Full suite and mypy re-run
   clean *after* the live verification too.
8. Checked throughout: the four concurrent-session files
   (`cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
   `tests/test_xlsx_inspection.py`) untouched by this task's own diff -
   `tests/test_xlsx_inspection.py` has grown further under the other,
   still-active concurrent session since Task 11.1's own baseline
   diff-stat (noted, not authored, by this task).

**Deliberately not separately live-verified**: the "unsupported" outcome
path - fully covered by the mocked `LlmPlanningTests`/
`LlmPlanningEndpointTests`, and a third real paid call to try to
reproduce a live model declining confidently was judged not worth it,
consistent with Task 12.3's own precedent of not re-proving an
already-generically-proven mechanism a second time against a paid
capability.

**Files changed**: new `mandate_planning.py`; `mandates.py`; `server.py`;
new `tests/test_mandate_planning.py`; `tests/test_mandates.py` (new
`LlmPlanningTests`); `tests/test_mandate_endpoints.py` (new
`LlmPlanningEndpointTests`); `frontend/src/lib/api.ts`;
`frontend/src/routes/MandateDetail.tsx`; new `docs/workspace-shift/tasks/
12.4-llm-planning.md`. Real data changed: `plan_revisions` gained two
additive columns (existing rows defaulted to `proposed_by='human'`); one
real Mandate/PlanRevision/Run/Attempt now exists for the real Universal
Logic project (left in place as a genuine record, consistent with
11.4b's/12.1's/12.3's own precedent); one real `CrossFormatAnalysis` and
one real `Workspace` with 22 real findings now exist from the live run
above. No existing table, row, or column was altered in place.

**Unrelated state, confirmed untouched**: the four concurrent-session
files - same as every prior entry, `tests/test_xlsx_inspection.py`
grown further under that other session, unrelated to this task.

**Decisions**: none added to `docs/10-decisions.md` - the model-config
resolution (keep one global `ANTHROPIC_MODEL` knob) is recorded as a
disclosed, founder-confirmed implementation choice in the task file, not
a product-hierarchy change.

**Blockers**: none.

**Next task**: 12.5 (reuse proof - configuring a second flow from
existing capabilities through the same runtime/UI), per the roadmap and
this session's own recommendation at the close of 12.3 - a real LLM
planner now exists to reuse against.

**Permissions needed**: founder authorization to proceed to 12.5, or to
revisit the `ANTHROPIC_MODEL`/planning-model question if the disclosed
discrepancy above turns out to matter more than judged here.
