# Baseline Inventory — Actual State of Milestones 1–9

Method: re-ran the test suite and mypy from a detached, isolated git worktree at the
committed `HEAD` (`fd59122`), so none of this used the real `data/deal_lab.db` or
`~/DealLabData`, and none of it depended on another session's uncommitted edits. Every
number below is from that run or from a read-only query against the real database (no
writes). Where the prior Milestone 9 completion report is contradicted by this
re-verification, that is called out explicitly — the report was a starting point, not
proof, and it was wrong in two places.

## Corrections to the prior report

| Prior claim | Actual, re-verified | Why it differs |
| --- | --- | --- |
| "334 passing tests" | **333** tests pass at the committed baseline | One test (`test_workbook_missing_dimension_declaration_does_not_false_reject_citations` in `tests/test_xlsx_inspection.py`) exists only in another session's **uncommitted** working-tree edit, not in any commit. The prior report ran against the working tree, not the committed baseline, and didn't distinguish the two. |
| "Five unrelated uncommitted files" | **Four**, as of now | One of the original five (`static/project.js`, mixed with an unrelated byte-limit change) was partly committed in this session's own follow-up work (`fd59122`, the project-page reconciliations list). The other four — `cross_format_analysis.py`, `pdf_inspection.py`, `xlsx_inspection.py`, `tests/test_xlsx_inspection.py` — remain uncommitted and untouched, still belonging to a concurrent session. |
| "Clean mypy" | Confirmed clean, **43 source files**, at the committed baseline in the isolated worktree | Re-run independently; no regression. |

Everything else in the prior report checked out on re-verification (see below).

## Implemented and verified (re-confirmed this session)

- **333 tests pass, mypy clean** — committed baseline, isolated worktree, isolated
  temp SQLite DB per test class (`tempfile.TemporaryDirectory()`), never the real
  database.
- **Milestone 9's Deal Workspace works end-to-end against the real Universal Logic
  analysis** (project `e32167f6062f45d999259a360c1f04f9`, analysis
  `0eb3026719504139917038fb88f8a5fb`, workspace `859eaa8fd21d47208256660c803b93d4`):
  33 AI findings extracted without loss, filtering/sorting, evidence expansion with
  working PDF/workbook citation links, human review (accept/reject with notes,
  severity override), one human-added finding, one duplicate marking with lineage,
  one information request with a management response, memo generate → edit →
  approve → edit-reverts-to-draft, all four exports (native `.xlsx` findings/requests
  registers, printer-friendly memo and combined-package HTML), and persistence across
  a real server restart.
- **The verification-only edits are still sitting in the real Universal Logic
  workspace** (read-only re-query, this session): 34 finding rows (33 AI + 1 human:
  `human-eee3c29344b1454cb3a3f4fe18c9043f`, "Founder-friend note payable not
  reflected in the cap table"), one duplicate marking (`ai-2` → canonical `ai-0`, by
  "M. Diaz"), two findings with non-default review status (`ai-0` accepted, owner
  "J. Chen"; `ai-1` rejected), one information request, one memo (status `draft`,
  `overall_recommendation = pause_pending_information`, previously approved then
  reverted to draft by a later edit), and 22 audit-log rows. This milestone does not
  clean any of it up — see **Closeout tasks**, below, which are recorded but not
  executed here.
- **The two frontend bugs found and fixed during Milestone 9 verification are real
  and are fixed in the committed code**, but neither has a dedicated regression
  test:
  - `adjusted_severity: ""` vs `null` on save (was rejected by the server as an
    invalid enum value) — the server-side rejection *is* tested
    (`test_rejects_invalid_adjusted_severity`), but no test pins the client-side fix
    (sending `null` instead of `""`), because there is no JS test harness at all (see
    below).
  - The workspace summary strip (request count, awaiting-response count) not
    refreshing after creating/updating a request — purely a client-state bug, not
    something a Python test could have caught.
- **The accessibility limitation on findings-table rows is real and unfixed**:
  `static/workspace.js` sets `row.setAttribute("role", "button")` on a `<tr>`. Table
  row elements have an implicit ARIA `row` role; overriding it to `button` on a
  child of `table`/`tbody` violates ARIA's required-context-role rules, and browsers
  are expected to ignore the override for accessibility-tree purposes — so the row
  is very likely not announced as an interactive control by a screen reader, even
  though it *is* keyboard-focusable (`tabIndex = 0`) and *does* activate on
  Enter/Space (confirmed by dispatching a real `KeyboardEvent` at the focused
  element and observing the detail row render). Reachable and operable; not
  correctly announced.

## Implemented but not independently re-verified this session

These were verified during Milestone 8/9's own work and are almost certainly still
correct (nothing since has touched them), but this session did not re-exercise them
directly:

- PDF native-citation resolution and Excel citation mechanical verification for
  documents *other than* the Universal Logic set (the parsing/verification code is
  shared and unit-tested, so this is low risk).
- The Validation Lab's blindness guarantees (locked-answer-key isolation from the
  Anthropic request) beyond re-reading the code and its existing dedicated test
  (`test_full_blind_workflow_and_secret_marker_never_leaks`), which still passes.
- Provider-side Files API cleanup behavior under real (non-mocked) network
  conditions — always tested against a mocked Anthropic client, by design (no paid
  calls).

## Known gaps (confirmed by direct inspection this session)

1. **AI finding identity is a list position, not a stable ID.**
   `evaluations.extract_findings()` assigns `"index": len(findings)` — pure
   sequential position in the regex-parser's output — and
   `workspaces._insert_ai_finding_row()` stores that as the permanent key
   (`f"ai-{ai_index}"`) at workspace-creation time. AI content is (correctly) never
   stored — it is re-derived from the immutable `segments` on every read, by
   re-running the parser — but the *link* between a stored human-review row and
   "which finding it is about" is only the parser's current output order. If the
   parser is ever improved (a fixed edge case, a merged bullet split into two, a
   previously-mis-captured phantom entry removed), the *n*-th item in its output
   can silently become a different finding, and every already-reviewed workspace
   would reattach "Accepted, owner J. Chen" to the wrong finding on its very next
   read — with no error, no warning, and (today) no way to detect it happened. This
   is the single most important structural gap this inventory found. See
   `03-data-model.md` for the stable-identity design.
2. **No user, session, or authentication concept exists anywhere in the codebase.**
   Confirmed by search: no `password`/session-token handling that isn't about
   *encrypted PDFs*, no login, no user table. `workspace_findings.assigned_owner` is
   a free `TEXT` column with no relationship to any identity — exactly the "local
   owner-name fields are not authentication" risk this milestone was asked to plan
   around. Every "ownership" check anywhere in `server.py` today is a *project*-ID
   match, nothing more.
3. **Zero automated test coverage for any frontend JavaScript.** No test runner is
   installed anywhere in the repository — not for `static/*.js` (no harness exists
   for it at all) and not for `frontend/` (its `package.json` only has `oxlint` for
   linting, no `vitest`/`jest`/anything that runs a test). Roughly 3,000+ lines of
   hand-written DOM manipulation across the static pages have only ever been
   verified by manual browser-tool walkthroughs, repeated fresh each milestone.
4. **A real, currently-unmitigated spreadsheet formula-injection path.**
   `workspace_exports.py`'s `_write_table()` writes free-text fields — `title`,
   `assigned_owner`, `management_response`, `reviewer_notes`, a human-added
   finding's `evidence_notes`, a request's `question`/`assigned_recipient` — directly
   into `openpyxl` cells with no leading-character neutralization. A value starting
   with `=`, `+`, `-`, or `@` (e.g. someone typing `=HYPERLINK(...)` into "Reviewer
   notes") is written verbatim and will execute as a live formula when the exported
   `.xlsx` is opened in Excel or Sheets. This did not surface during Milestone 9's
   verification because no test data happened to start with one of those
   characters. Needs a systemic fix (sanitize every exported free-text cell, not a
   one-off patch) before any export path is used with real, uncontrolled user input.
   See `05-permissions-and-security.md`.
5. **The development server is explicitly documented as unfit for this.**
   `server.py` is built on Python's `http.server` / `BaseHTTPRequestHandler`. The
   official Python docs state plainly: *"`http.server` is not recommended for
   production. It only implements basic security checks."* — and separately warn
   about symlink-following outside the served directory and header-injection risk
   from unsanitized input to `send_header()`. This doesn't call the *analysis logic*
   into question (that lives in separate, well-tested modules) — it calls the
   *routing/serving layer itself* into question. See `06-architecture-and-infrastructure.md`.
6. **No spending limits, no per-run usage ceiling, no duplicate-submission
   protection.** Every analysis module records token usage after the fact
   (`input_tokens`/`output_tokens` columns already exist on every analysis table —
   good raw material to build on), but nothing today stops two overlapping requests
   for the same document set, and nothing enforces a budget before or during a call.
7. **No document versioning.** `documents.py`'s `Document` is a flat row; re-uploading
   a changed file either creates an unrelated new document (different id, no link to
   the old one) or is silently treated as a duplicate if the bytes match exactly
   (`find_duplicate` keys purely on SHA-256). There is no concept of "version 2 of
   this same source document," which the assignment's core workflow (step 10,
   "revisit affected conclusions when evidence changes") depends on.
8. **`frontend/` (React/Vite scaffold) has never been wired into `server.py` and has
   no git history at all** — confirmed via `git log --all -- frontend/` (no
   results). See the frontend-assets section below for what it actually contains.

## Reuse map

| Component | Disposition | Why |
| --- | --- | --- |
| `store.py` (project CRUD, `get_connection()` pattern) | **Reuse as-is** | Small, correct, no issues found. The per-module `init_*_db()` / dataclass / `to_dict()` convention it established is worth *keeping as the migration-writing convention* even after moving off SQLite (see architecture doc). |
| `documents.py` (upload, checksum, path safety) | **Adapt** | Path-safety and content-type handling are solid and should carry over conceptually; needs an added `document_versions` concept (or a new table alongside it) and, for cloud, needs its `DATA_DIR`-on-local-disk assumption replaced with object storage — see architecture doc. |
| `ai_client.py`, `anthropic_errors.py` | **Reuse as-is** | Connection-testing and typed-error-classification logic; provider-agnostic-enough and already well tested. |
| `pdf_inspection.py`, `xlsx_inspection.py`, `cross_document_analysis.py`, `cross_format_analysis.py` | **Reuse, extend surface only** | This *is* "the existing analytical engine" the assignment says to reuse for Investigation. Citation handling (native PDF citations, the Excel citation convention + mechanical verification) is the hardest-won, most-tested part of the whole codebase — don't touch the mechanism. What needs to change is what *calls* these modules: today each is invoked synchronously inline in an HTTP handler; Milestone 12+ needs them invoked from a background job with persisted progress (see architecture doc's background-job section). |
| `evaluations.py`'s `extract_findings()` | **Reuse the parser, fix what wraps it** | Milestone 9 was explicit that this must not be reimplemented, and this inventory agrees — the parser itself is fine and well tested. The problem is purely the *identity* scheme built on top of it (gap #1 above), not the parsing logic. |
| `workspaces.py`, `workspace_exports.py` | **Adapt** | The workflow-state model (review status / adjusted severity / resolution status / duplicate lineage / audit log) is the right shape and should become the *finding-review* half of the deal-level `tracked_issue`/`review_decision` model — it just needs to move from "one workspace per analysis" to "one workspace per deal, with findings attributable to whichever run produced them." See `04-workspace-experience.md` and `03-data-model.md` for the compatibility approach. |
| `server.py`'s routing (`http.server` + regex `re.compile` dispatch) | **Replace the framework, keep the route shapes** | Every individual handler method is small, single-purpose, and already does the right ownership checks for what "ownership" means today (project-scoped). That pattern translates directly onto FastAPI/Flask route handlers with real dependency-injected auth — see architecture doc. What must not survive is `http.server` itself, per the official warning above. |
| `answer_keys.py`, `validation_cases.py`, `validation_runs.py`, `evaluations.py`'s scoring half | **Reuse as-is, isolate harder** | The Validation Lab's blindness discipline (answer-key content never touches a request-building code path) is real and tested. It needs one addition, not a rewrite: an explicit, enforced boundary so that once organizations/deals exist, a validation case can never be attached to a shared, multi-user deal workspace, and a validation answer key is never reachable by any AI tool-use code path regardless of which user or deal is active. See `05-permissions-and-security.md`. |
| `static/*.html` / `static/*.js` (10 pages, ~3,000+ lines) | **Reuse for now; framework decision deferred to Milestone 12** | See the frontend-assets discussion below. |
| `server.py`'s multipart parser (`multipart.py`) | **Reuse as-is** | Self-contained, well tested, framework-agnostic. |

No component was found to need outright replacement for a reason *other than* the
ones above (i.e., nothing is simply wrong or obsolete) — every "replace" call in this
inventory is about the *hosting/framework shell*, not the domain logic inside it.

## Frontend assets: what actually exists, inspected before proposing a direction

Two untracked, uncommitted things exist beyond the static pages, and per this
milestone's instructions they were inspected (not touched) before any frontend
direction was proposed:

- **`frontend/`** — a real, working React 19 + Vite + Tailwind 4 + shadcn/ui (Base UI
  primitives) + React Router 7 scaffold, with `node_modules/` installed and a
  successful prior `npm run build` output already sitting in `frontend/dist/`. It is
  not boilerplate in the throwaway sense — `frontend/src/routes/Home.tsx` is a
  faithful, working re-implementation of the *existing* project-list-and-create page
  against the *same* `/api/projects` backend, matching the existing design tokens by
  name (`--gold`, `--shadow-elevation-1/2` mirror `style.css`'s `--accent-gold`,
  `--elevation-1/2`) and even the same copy ("Your M&A transaction projects, stored
  locally on this computer."). `frontend/src/lib/api.ts` is a small, correctly typed
  API client (`listProjects`, `createProject`). GSAP entrance animation is already
  gated behind `prefers-reduced-motion`. All file timestamps cluster within five
  minutes (08:39–08:44 on the day this was built) and nothing has touched it since —
  this reads as one focused scaffolding session establishing a foundation, not
  ongoing parallel development, and it has **zero git history** (`git log --all --
  frontend/` returns nothing) and is **not wired into `server.py`** (which only ever
  serves `static/*.html`). No route exists yet beyond `/`.
- **`scripts/run-frontend.sh`** — a two-line launcher (`cd frontend && npm run dev`)
  with a hardcoded `nvm` path. Trivial; not evidence of anything beyond "someone ran
  the dev server once."
- **No "original pitch" document exists inside the repository.** Searched
  exhaustively (`grep -rli` for "gaffer"/"pitch" across every `.md`/`.txt`/`.py`/
  `.tsx`/`.ts` file, full repo-wide `find -iname "*.md"`) — nothing. The pitch deck
  referenced in this milestone's instructions
  (`Deal-Room-AI-Native-Banker-Workspace-Revised.pdf`) was supplied directly by the
  founder mid-session from outside the repository; its content is reconciled with
  the built lab in `02-product-direction.md`.

**Recommendation on the frontend framework question** (a decision the founder
should make explicitly, not one this inventory decides unilaterally): keep building
on the existing static-page pattern through Milestone 11 specifically, because
Milestone 11's own scope (a narrow backend-and-persistence vertical slice) doesn't
need it and CLAUDE.md's standing instruction is to avoid a rewrite without a
demonstrated need. Revisit at the Milestone 12 boundary, where the *demonstrated
need* starts to exist for the first time: authentication-aware rendering, real-time-
ish multi-user state (someone else's review just landed while you're looking at the
same finding), and roughly twice as many navigation sections as exist today
(Overview/Documents/Workstreams/Findings/Requests/Submissions/Reports/Activity) are
all things a component framework with client-side routing handles structurally
better than hand-assembled DOM per page — and a working, design-matched foundation
for exactly that already exists, unused, at zero sunk cost to adopt. This is listed
as a founder-approval decision in `00-executive-summary.md`, not assumed here.

## Closeout tasks (recorded, not performed this milestone)

Per instructions, these are identified and recorded, not executed:

1. Decide and document how to distinguish "real reviewer state" from
   "verification-only state" in the Universal Logic workspace — the specific rows
   are listed in full above so nothing has to be re-derived later. Candidates: a
   `source: "verification" | "review"` tag added per audit event / workflow edit
   going forward (doesn't retroactively tag the existing rows), or a one-time,
   explicitly-approved manual reset of just the listed rows. **Do not reset
   anything until the founder picks one of these and approves it.**
2. Add a regression test for the `adjusted_severity` null-vs-empty-string save path
   once frontend testing exists (gap #3) — today there is nowhere to put such a
   test that would actually exercise the bug (the server-side behavior is already
   correctly tested; the bug was purely client-side).
3. Add a regression test for the workspace-summary-refresh-after-request-mutation
   behavior, same caveat as above.
4. Fix the `role="button"` accessibility gap on findings-table rows — likely
   solution is a real `<button>` (or a `<div role="row">` wrapping a focusable
   `<button role="button">` cell) rather than overriding a `<tr>`'s role; needs a
   small, isolated coding mandate with its own before/after accessibility-tree
   check, not bundled into a larger change.
5. Neutralize formula-injection-capable characters (`=`, `+`, `-`, `@`, leading
   tab/CR) in every free-text field written into an exported `.xlsx` cell — this is
   a systemic fix across `workspace_exports.py`'s `_write_table()`/row-building
   functions, not a one-off patch, and should ship before any export path handles
   real, uncontrolled user input at multi-user scale.
