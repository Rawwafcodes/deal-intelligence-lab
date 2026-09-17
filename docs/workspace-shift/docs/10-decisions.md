# Decisions and open questions

## Established direction
D01 Team workspace above deals; deal-independent mandates supported.
D02 Mandates are the umbrella; modes/templates share one runtime and UI.
D03 Collaborative Analyst/Principal layers are core and built locally.
D04 Preserve existing intelligence and human workflow; avoid big-bang rewrite.
D05 AI interprets; software governs access/state; humans approve consequential outcomes.
D06 Historical evidence, observation identity and decisions must remain stable.
D07 Workspace and Deal Overviews are distinct, permission-filtered views.
D08 Hosting deferred; local durable jobs and concurrency are not deferred.
D09 No Office clone, activity-ranking product or pipeline-builder framework first.
D10 Organization is the persisted tenant term; Workspace remains the product/UX term;
Milestone 9's per-analysis Workspace remains a preserved legacy record.
D11 (added 2026-09-15, Task 11.3a) Local database is PostgreSQL, not SQLite -
implemented, not proposed. This is a founder preference decision, explicitly not an
evidence-driven one: offered the M11.3a spike's own recommendation (P06: stay on
SQLite + a retry wrapper) directly, the founder rejected it and chose Postgres. The
spike's findings are not contradicted or invalidated by this - SQLite was never shown
to be insufficient, Postgres was simply preferred. Implementation: Postgres installed
locally via conda (no Homebrew, no sudo, no system changes - see POSTGRES.md), one
Unix-socket server at a project-local `pgdata/`, no password. `store.py`'s
`get_connection()` is the sole call site that changed shape; every other module kept
its `conn.execute(...)` call sites unchanged beside the `?`->`%s` placeholder swap.
The real local database (all projects, including Universal Logic) was migrated for
real in this session via `migrate_sqlite_to_postgres.py`, verified row-count-exact
and content-byte-exact against the original SQLite file, which remains on disk
untouched (`data/deal_lab.db` and its Task 11.2 backup) as a permanent historical
reference. Full detail: `tasks/11.3a-postgres-migration.md`, `STATUS.md`.
D13 (added 2026-09-16) O01 resolved: adopt the untracked `frontend/` React +
Vite + TypeScript + Tailwind + shadcn/ui scaffold for new screens going forward,
starting with 11.3b (Organization switcher, membership management, the new
workspace-level nav). The existing 9 static HTML/CSS/JS pages are not ported and
keep working as-is - two stacks coexist deliberately, not a forced rewrite (per
D04, avoid big-bang rewrite). The scaffold's own `index.css` currently ports the
retired light "Trust & Authority" tokens (see D12) onto shadcn's variable names;
it needs the same dark-Meridian retheme applied before any real 11.3b screen is
built on it, so the two stacks read as one product, not two. `next-themes` is
already a scaffold dependency, unused so far.
D12 (added 2026-09-16) Visual identity is the dark "Meridian" design (near-black
ground, one blue reserved for selection/links, a stark white primary-action pill,
Inter/Inter Tight) - one committed look app-wide, not a light/dark toggle and not
split by surface. This retires the earlier light "Trust & Authority" navy/gold/
EB Garamond identity everywhere, including the findings/review surfaces it was
originally scoped to for print-worthy sobriety - the founder explicitly chose
consistency over that earlier split when asked directly. Grounded in a real
reference screenshot (a "Meridian Advisory" mandate-composer mockup, confirmed by
the founder as this app's own actual target design, not a borrowed style). Applied
by retheming the two shared stylesheets (`static/style.css`, `static/workspace.css`)
at the token/component level only - no HTML markup, no JS, no per-page styles
touched, since every one of the app's 9 pages already inherits from those two files
with no inline styles. Full evidence: `STATUS.md`'s 2026-09-16 entry.

## Proposed defaults for founder review during adoption
P01 Reviewer can approve assigned submissions; only deal lead approves final position.
P02 Start sequential stages with explicit waits; add branches when a real case requires.
P03 Basic polling before server events; revision conflicts from first collaborative writes.
P04 Start one Organization operationally, test cross-organization and cross-deal denial.
P05 Model/provider configurable; first execution uses existing Anthropic integration.
P06 (added 2026-09-15, Task 000; REJECTED 2026-09-15, Task 11.3a — see D11) SQLite
remains the local/pilot database through at least Milestone 13. Evidence: the
M11.3a contention/recovery spike (executed against an isolated temp DB using the
app's real schema/connection code, never the real database) found zero lock errors
at a realistic small-team write load using the app's own existing default connect
timeout, no data corruption or leaked uncommitted writes after a simulated crash,
and a working plain-file backup/restore. It also found WAL mode does not reduce
write-write contention under stress load (SQLite allows one writer regardless of
journal mode) — recommend an app-level bounded retry-with-backoff wrapper on the
write path instead of adopting WAL or Postgres on the strength of this spike. Full
results: docs/workspace-shift/adoption-report.md §3. Kept here, not deleted, per
this file's own rule: the founder was offered this exact recommendation directly and
rejected it in favor of Postgres (D11) — the evidence above was not wrong or
invalidated, it just wasn't the deciding factor.
P07 (added 2026-09-15, Task 000) Task 11.1 (targeted closeout: export safety, two
frontend regressions, accessibility fix) does not require the frontend decision (O01)
first, since it adds no new screen. O01 remains a hard prerequisite for 11.3b, which
does.

## Open, not blockers to documenting the direction
O01 RESOLVED 2026-09-16 — see D13: adopt the React/shadcn scaffold for new screens
(starting with 11.3b), existing static pages stay as-is. No longer open.
O02 Web framework/session library and exact local job implementation.
O03 RESOLVED 2026-09-15 (Task 11.3a) — see D11: local Postgres, founder preference,
not a continuation of the spike's own recommendation. No longer open.
O04 Workspace document visibility defaults and explicit executive sharing policy.
O05 Which workflow is the first customer-paid service; current wedge is financial deals.
O06 Exact spending caps, models and test authorization.
O07 Which real case has independent human-scored ground truth.
O08 Retention and external-research policy. No new external research tools enabled by default.
O09 Brand and pricing: not selected here.

## Decision procedure
Record id/date/status/options/reason/impact/approver. Agents may choose reversible
implementation details within a task. They may not silently change product hierarchy,
permissions, data destinations or scope. Revise this file when the founder decides.
