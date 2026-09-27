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
D14 (added 2026-09-17, Task 14.1) Every registered mandate capability
declares a real, enforced `input_schema`/`output_schema`/
`allowed_source_formats` on its own `CapabilityDescriptor` - checked by a
minimal, hand-rolled schema validator (`mandates._validate_against_schema`;
object/required/properties/type/items/minItems only, not a general JSON
Schema engine or an added dependency) at plan-propose time (input) and
immediately after every execution (output). This replaces the prior
pattern of ad hoc, capability-name-keyed `if capability == "...":` checks
scattered across `_default_input_for_stage` and each executor with one
declared, introspectable contract per capability - the literal
mechanism docs/04-mandate-engine.md's capability-boundary paragraph
("Register each capability with: ... input schema; output schema;
allowed formats...") already called for. Binding on every future
capability, starting with M14.2's own `integrity.review_work_product`:
a new capability that does not declare both schemas is incomplete, not
merely under-documented. Full contract for the one capability this
formalizes today: `docs/12-reconciliation-capability-contract.md`.

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

## Integrity Review product/roadmap integration (proposed 2026-09-17)
Adopted into documentation only, from an externally-supplied package
(`workspace-integrity-integration` v1.0.0, prepared from the current
workspace-shift status/roadmap plus a third-party contribution titled
*A Multiplayer Diligence System for Deal Teams*; preserved in full at
`docs/workspace-shift/integrations/workspace-integrity-integration-v1.0.0/`).
This is a roadmap/product-hierarchy proposal the founder directed this
session to adopt as documentation - not an implementation authorization.
No code was written or changed for any of I01-I08 below; M13.2 remains
the next implementation task unchanged. Numbered "I" (integration) here
to match the source package's own numbering, distinct from this file's
own D/P/O series.

I01 Workspace remains the product centre; Integrity Review is a capability
family inside Mandates, not a replacement product hierarchy.
I02 First implementation occurs at M14.2 (Work-product Integrity Review),
gated on M13 acceptance and M14.1 completion - not before.
I03 One shared findings workflow: Integrity findings, human findings and
existing reconciliation findings share one review/resolution system with
origin labels and lineage - no parallel "integrity" findings silo.
I04 Review immutable work-product SubmissionVersions (13.1) first; a
native collaborative editor is deferred until evidence proves it necessary.
I05 Persist only material assertion snapshots actually used in real
M14.2 reviews; promote them into a reusable ledger (M16.2) only after
validation - no universal claim-store schema built ahead of evidence.
I06 NLI, pgvector, graph storage, commercial parsing and CRDTs remain
candidates for M16, not predetermined requirements - benchmark before adding.
I07 Authorized leaders may inspect work, versions, review state and
decisions; no AI performance scoring or analyst leaderboard, ever.
I08 Event-triggered Integrity Review (M15.3) stays a normal, visible,
authorized, budgeted, auditable mandate - never hidden background
monitoring of every edit.

Non-goals carried over from the source package: rebuilding Milestones
1-13; building another data room; replacing Slack/Teams/Word/Excel/
PowerPoint; autonomous delivery approval; a universal ontology; hidden
surveillance; unbounded continuous inference; premature cloud/production
deployment. Open questions needing evidence before M16 (not blockers to
M13.2/M14): which assertions recur enough to justify a persistent ledger;
what proportion of valuable defects is truly deterministic; whether
retrieval improves over native long-context reasoning on real deal
material; whether a specialized NLI model helps after strong-model
filtering; how bilingual aliases/translations get human-confirmed; at
what workflow point (submission/review/live drafting) users actually want
challenges surfaced; which Integrity Review trigger events should require
approval before execution.

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

D15 (added 2026-09-27, Task 17.10) Wire `assertion_ledger.py` into the
real Integrity Review accept-decision path and give it a real, visible
surface in the unified Findings register - not silent backend-only
bookkeeping. Context: the 2026-09-27 re-entry audit found
`assertion_ledger.py`/`reconciler.py` fully built and tested but with
zero live callers anywhere. The M17 product-integration program's own
Phase D procedure required a founder decision before wiring either
in, since doing so changes professional semantics (a new "assertion"
concept becomes visible to users) rather than only exposing existing
substrate. Options presented: (a) wire `promote_candidate` silently,
no new UI; (b) wire it and add a visible assertion view in Findings;
(c) leave both unwired, pending M16 gate 4's own still-unmet "recurring
reusable assertions" evidence bar. Founder chose (b) directly. Scope,
for both this repository and any successor session picking up Task
17.10/17.11: `assertion_ledger.promote_candidate` is called from
`server.py`'s `_handle_integrity_candidate_decision` on every real
`accepted` decision (the same data already assembled there for
`publish_integrity_candidate_as_finding`'s own lineage); the unified
Findings register gets a real, permission-scoped view of promoted
entries (verification status, provenance, supersession/dispute state) -
not a synthesized or invented display. **`reconciler.py` remains
unwired** - the founder's chosen options did not extend to it, and no
real fact-extraction pipeline exists to feed it; wiring it would still
require building new capability, not integration, and stays out of
this program's scope until a separate, explicit decision authorizes
that new work.

D16 (added 2026-09-27, Task 17.14) Close M17 with a centralized,
backend-enforced, capability-based authorization policy replacing plain
deal-membership gating - not a new product milestone, the M17 program's
own final closeout. Context: Task 17.13 (Phase F, local collaborative
proof) disclosed two real gaps rather than fixing them, since fixing
either was a permission-model decision outside a verification task's
authority: (1) seven destinations Phase A-D built (Findings, Documents,
Decision Package, Readiness, Reassessments, Assertions, Triggers) were
reachable by any deal member regardless of role - only Overview/Activity
self-restricted; (2) `Work.tsx`'s Approve/Return buttons rendered for
every role, relying entirely on the backend's real 403. The founder
directly authorized closing both, with a full role interpretation for
all four `identity.DEAL_ROLES` (analyst/reviewer/deal_lead/
external_executive) and explicit requirements: backend-authoritative
enforcement, frontend guards as a usability aid only, no broad sharing
subsystem, deny-by-default where the data model can't express "explicitly
shared". Implemented as a new `authz.py` module (one `(role,
capability) -> bool` matrix plus two object-level filters for request/
deliverable visibility, entirely pure and unit-tested independent of
any server) and `server.py`'s new `_require_capability`/
`_require_capability_only` helpers, replacing `_authorized_project` at
every one of its ~75 call sites with the correctly-scoped capability
check. `identity.py`'s own role model (`DEAL_ROLES`, `get_deal_role`,
`has_deal_access`) was deliberately left unchanged - this closeout adds
a policy layer on top of it, not a new identity architecture. Full
detail: `docs/workspace-shift/tasks/17.14-authorization-closeout.md`,
`docs/06-security-and-collaboration.md`'s new "Final authorization
matrix" section (the row-by-row table this decision authorized),
`STATUS.md`'s own dated entry. A React `DealAccessProvider`/
`RequireCapability` guard (fed by the same `GET .../overview` response,
extended with `role`/`capabilities` fields) now hides inaccessible
destinations and blocks direct navigation with a clear denied state
before the guarded page's own data fetch ever fires; `Work.tsx`'s
Approve/Return controls render only when the caller's own capability
set includes `review_work`. A small, explicitly-scoped frontend
addition beyond the two disclosed gaps: the restricted Deal Overview
(the one screen `external_executive` actually lands on) now also shows
requests already sent to them with real `management_response` controls
- the approved role interpretation's own "management-response controls
needed to answer those requests," which had no frontend surface at all
before this task despite the backend already supporting it.

D17 (added 2026-09-27) Adopt the post-M17 roadmap (M18 Product and
Intelligence Validation, M19 Secure Online Foundation, M20 Commercial
Pilot Readiness, M21 Live Design-Partner Pilot, M22 Repeatability and
Early Scale) as the approved path from the M17 local-integrated-product
baseline to a validated, securely hosted and commercially pilotable
product. Full detail, entry/exit criteria and measurement requirements:
`docs/13-post-m17-roadmap.md`; short dependency-ordered pointers:
`08-roadmap.md`'s own M18-M22 entries. Documentation and planning only -
no M18 implementation, infrastructure provisioning, Anthropic API call,
deployment, data migration or new dependency was introduced by this
decision. Context and explicit carry-forwards, recorded here rather than
left implicit:
- Milestones are evidence gates, not calendar periods; engineering
  completion is not commercial validation; local test success is not
  production security; a deployed application is not automatically
  pilot-ready; a pilot is not proof of repeatability - carried forward
  from the founder's own stated planning principles, binding on every
  M18-M22 task.
- M16's outstanding validation gates (independent scoring, recurring
  reusable assertions, measured failure modes - see this file's own O07
  and `08-roadmap.md`'s M16 entry) are **incorporated into M18 Track B,
  not marked complete** by this decision or by M17's own completion.
  Proceeding past M16 in the milestone sequence did not and does not
  close those gates.
- Deployment/provider selection (hosting, database, storage, auth,
  secrets, CI/CD) remains explicitly open until M19's own
  architecture-decision task, per the same discipline O01/O03 already
  applied to the frontend/database choices in M11-M13 - no earlier
  document's mention of any provider is a decision, and this decision
  does not select one.
- Real customer data remains prohibited until M19's exit gate and M20's
  legal/security work are satisfied; this decision does not authorize
  any customer-data use.
- `docs/13-post-m17-roadmap.md`'s own "Open founder decisions" and
  "External dependencies" sections are a register, not a decision record
  - each becomes its own dated D18+ entry here only when the founder
  actually decides it.
- All previous roadmap history (M10-M17), decisions (D01-D16) and status
  entries are preserved unchanged; this is an additive extension, not a
  competing planning system.

D18 (added 2026-09-27) Extend the post-M17 roadmap (D17) through M23
(Repeatable Commercial and Customer-Administration Experience), M24
(Enterprise Identity, Audit, Compliance and Isolated Deployment) and M25
(Scalable Operational Capabilities), and adopt a code-verified
reconciliation of every canonical surface in `docs/product/
02-experience-and-information-architecture.md`'s 25-surface target
route/page inventory against the actual implementation - full detail:
`docs/product/07-surface-reconciliation.md`; roadmap integration:
`docs/workspace-shift/docs/13-post-m17-roadmap.md`'s "25-surface
information-architecture reconciliation" section and `08-roadmap.md`'s
M18-M25 entries. Documentation and planning only - no implementation,
route, schema or dependency change. Findings and their disposition,
recorded here rather than left implicit:

- 13 of 25 canonical surfaces are complete and reachable through the
  real product (verified route-by-route against `frontend/src/App.tsx`
  and the corresponding route component, not inferred from a milestone
  title); 2 more (#21-22, Validation Cases/Case-Report) are correctly
  static-only, a deliberate preserved exception, not a gap. The other 9
  (#1-4 public marketing pages, #5 Sign in, #6 Invitation/onboarding,
  #23 Team and Access, #24 Organization Settings, #25 Usage and Billing)
  are genuinely absent or dev-stub-only, confirmed at the code level
  including, for #24 and org-level #23, that no HTTP route exists at
  all, not merely no frontend. Each is assigned to a specific later
  milestone (M19, M20 or M23) in `13-post-m17-roadmap.md` rather than
  left as an unattributed gap.
- One partial gap inside the local product itself: canonical surface #13
  (Document Detail) resolves to a raw inline file link, not an in-app
  version-history/citation-backlink view. Left as an open founder
  decision for M18 (build it before founder acceptance, or explicitly
  defer it) - not decided here.
- **A real conflict, not resolved by this decision**: four shipped,
  backend-complete deal-level destinations - Readiness (`readiness.py`),
  Targeted Reassessment (`reassessments.py`), Monitoring/Triggers
  (`triggers.py`), and Assertions (`assertion_ledger.py`, wired per D15)
  - exist in the real product with no corresponding row in the canonical
  25-surface table. This decision does not amend that table. Two options
  are presented in `07-surface-reconciliation.md` (amend the table to add
  them; or declare them a disclosed exception) and left open for the
  founder.
- No canonical surface was found to be no longer justified, so none was
  removed; this decision's own disposition rule (record removal as an
  explicit founder decision, never delete silently) was not triggered
  but is recorded here for when a future reconciliation does trigger it.
- Static pages `static/index-legacy.html`, `project.html`,
  `workspace.html`, `cross-analysis.html`, `inspect.html`,
  `reconcile.html` and `workbook-inspect.html` are confirmed orphaned (no
  live link from `frontend/src` anywhere) and are not counted as
  completed implementations of any canonical surface.
  `static/validation.html` and its two case/report pages remain the sole
  disclosed, deliberate exception (canonical surfaces #21-22, Validation
  Cases/Case-Report) - internal quality surfaces, not the customer-facing
  Review workflow, per the existing D13 and `06-truth-register.md`
  Review-vs-Validation-Lab boundary; this decision leaves that boundary
  unchanged.
- M18's exit gate (`13-post-m17-roadmap.md`) now explicitly requires
  every canonical surface to be classified and every essential
  local-product surface to have either passed founder acceptance or
  received an explicit approved later milestone, before M18 can close -
  this reconciliation is what makes that condition checkable, not itself
  the founder acceptance decision.

D19 (added 2026-09-27, after M17 confirmed pushed to `origin/main` at
`70f03ca`) The founder gave the exact names and content for M21-M25
directly. Per this file's own authority rule (latest explicit founder
instruction outranks accepted decisions) and root `AGENTS.md`'s matching
rule, this supersedes D18's version of those five milestones. D17 and
D18 are **not deleted or rewritten** - they remain above as the
historical record of what was adopted first; this decision records the
supersession explicitly rather than silently overwriting them. M18-M20
and the 25-surface reconciliation (D18) are unchanged by this decision.

Full revised content: `docs/workspace-shift/docs/13-post-m17-
roadmap.md`'s M21-M25 sections and `08-roadmap.md`'s matching short
entries, both updated in place. Summary of what changed:

- **M21** renamed "Live Design-Partner Pilot" → **Paid Design-Partner
  Pilots** - emphasizes paid engagements (possibly more than one design
  partner), not a single unpaid/free pilot. Evidence list otherwise
  carried forward from D18 largely unchanged.
- **M22** substantially redefined. D18's "Repeatability and Early Scale"
  merged product-learning and repeatable-delivery into one milestone;
  D19's **Product Learning and Unit Economics** is narrower and comes
  first - it uses M21's real evidence to determine what customers
  genuinely use, what needs founder assistance, what to fix/remove/
  simplify, and unit economics, producing the specification M23 then
  builds against. "Standardize onboarding" and "acquire further paying
  customers" - present in D18's M22 - move to M23 under D19.
- **M23** renamed "Repeatable Commercial and Customer-Administration
  Experience" → **Repeatable Commercial Product**, and now explicitly
  absorbs the delivery work D18 had split into M22 (standardized
  onboarding, further paying customers, repeat engagements) alongside
  D18's original M23 content (self-serve #23-25, generalized #6,
  conditional #1-4). The founder's own framing governs directly: **the
  architecture is mapped now, developed gradually, and commercially
  complete by M23**.
- **M24** renamed "Enterprise Identity, Audit, Compliance and Isolated
  Deployment" → **Enterprise and Regulated-Market Readiness**; content
  extended with explicit penetration testing, procurement documentation,
  SLA/disaster-recovery, and Saudi/GCC regulated-customer requirements.
  Anti-speculation gating (a real named customer requirement triggers
  it) unchanged from D18. The founder's own framing: enterprise
  additions are completed here, on top of M23's finished basic product,
  not a substitute for finishing it.
- **M25** renamed "Scalable Operational Capabilities" → **Scalable
  Growth**, broadened well beyond infrastructure scale to repeatable
  customer acquisition, regional/international expansion, partnerships,
  evidence-backed fundraising material, and acquisition positioning if
  strategically relevant. The founder's own framing governs directly:
  **M25 is for scaling, not finishing the basic product** - unfinished
  M23 work found here belongs in M23, not M25.

No canonical surface assignment from D18's 25-surface reconciliation
changed - surfaces #23-25/#1/#6 still land at M23 (not M22, which no
longer does delivery work) and #24's enterprise/isolated-deployment
extension still lands at M24, consistent with the founder's own
"commercially complete by M23, enterprise additions at M24, M25 for
scaling only" framing.

## Decision procedure
Record id/date/status/options/reason/impact/approver. Agents may choose reversible
implementation details within a task. They may not silently change product hierarchy,
permissions, data destinations or scope. Revise this file when the founder decides.
