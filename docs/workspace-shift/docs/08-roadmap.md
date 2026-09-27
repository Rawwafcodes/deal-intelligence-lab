# Dependency-ordered roadmap — no calendar dates
This replaces the competing earlier M11–15 sequences.
Each numbered task is separately reviewable; do not execute a whole milestone blindly.

M14.2 and M15's Integrity Review content, and the new M16, were adopted
2026-09-17 from the externally-supplied `workspace-integrity-integration`
v1.0.0 package (preserved in full at
`docs/workspace-shift/integrations/workspace-integrity-integration-v1.0.0/`;
see its own `00-README.md`/`AGENTS.md`, and `docs/10-decisions.md`'s I01–I08).
That package integrates a "Multiplayer Diligence System" contribution as a
capability family called **Integrity Review** *inside* the existing
Workspace/Mandate hierarchy — it does not replace the workspace, the
mandate runtime, or the shared findings register, and it does not
authorize implementing M14–M16 immediately. M13.2 remains the next
implementation task; M14.2 is the first point at which any Integrity
Review code is written, gated on M13 and M14.1 completing first.

## M10-R — Adopt the shift (current)
Task 000: adopt specs, inspect actual repo, establish baseline and decisions.
Deliver adoption report, reuse map, frontend/DB/framework recommendation and first task.
No application changes or paid calls. Founder reviews the report.

## M11 — Trustworthy local collaborative foundation
11.1 Targeted closeout: verify/fix export safety, severity-null regression,
request refresh regression and accessible finding expansion. Choose minimal test tooling.
11.2 Stable observation snapshots/UUIDs and audited legacy migration, clone-tested.
11.3a SQLite contention/recovery spike with two sessions plus representative worker
writes; decide and record SQLite/WAL versus local Postgres before collaborative schema.
11.3b Organization, user, memberships, deal context and server-side authorization.
Development-only identity sessions; test revocation, mixed permissions and two browsers.
11.4 Source versions, versioned brief, workstream assignments, revision conflicts.
Preserve project/deal compatibility and narrow document access.
Outcome: two local identities can work in one deal safely with stable evidence/history.

## M12 — Reusable local mandate runtime
12.1 Mandate/template/plan/run contracts and fixture planner; shared composer/detail.
12.2 Durable local worker, attempts, progress, cancellation, interruption and budget ledger.
12.3 Adapter for existing reconciliation, run registry, pinned manifest and shared findings.
**Gate A:** prove one existing reconciliation completes through the generic runtime and
shared UI, including persistence, citations, findings and recovery. Do not register a
second analytical capability until this passes.
12.4 LLM planning over the already-registered capability: schema checks, missing inputs,
source authorization, plan approval and replan approval.
12.5 Reuse proof: configure a second flow from existing capabilities using the same
runtime/UI. If draft production needs a genuinely new capability, specify and validate
it as its own bounded task before registration.
Outcome: commissioner → approved plan → durable execution → reviewed outputs, locally.
Paid checks require explicit budget/source approval. Do not rewrite all modules first.

## M13 — Team execution and principal visibility
13.1 Assigned tasks/comments and immutable work-product submissions.
13.2 Review → return for revision → resubmit → approval; version-specific decisions.
13.3 Workspace Overview and Deal Overview built from available real state, plus live
refresh and MD drill-down. Add simple overview shells earlier if useful; never fake metrics.
13.4 Two-browser end-to-end journey with analyst, reviewer and lead; restricted executive view.
Outcome: actual collaborative work and oversight, not a single-user admin demo.

## M14 — Professional mandate templates and validation
14.1 Formalize existing diligence/reconciliation template.
14.2 Work-product Integrity Review: registers one new capability,
`integrity.review_work_product`, exposed through one mandate template.
Reviewer selects an exact immutable target SubmissionVersion, source
DocumentVersions, optional peer SubmissionVersions, a pinned BriefVersion
and optional Workstream; the server independently re-verifies every
identifier and permission. Reuses the existing mandate runtime, plan
approval/replan, budget ledger, cancellation/recovery, and the shared
findings register unchanged — no parallel worker, no parallel findings
silo. Proposed candidates (title, classification, severity, assertion,
conflicting/missing evidence, source locators, uncertainty, recommended
resolution, deterministic-vs-model-judgment flag, exact versions used)
pass through a mandatory human checkpoint (accept/reject/edit/link-as-
duplicate/leave unresolved) before anything publishes to the shared
findings register; a rejected candidate stays auditable in the run but
never becomes a finding. Full bounded spec, required tests, and the
completion gate: `docs/workspace-shift/integrations/
workspace-integrity-integration-v1.0.0/05-task-14.2-integrity-review.md`.
Do not implement before M13 is accepted and this task's own 14.1 is done.
14.3 Decision-package production from explicit reviewed/unresolved material.
14.4 Readiness template: checklist scope explicit; no claim of universal completeness.
One template at a time; unsupported format/capability becomes a separate bounded task.
Validate on independently reviewed real authorized material, not just fixture success.
Outcome: reusable engine demonstrated across materially different work.

## M15 — Change awareness and monitoring
15.1 Version dependency tracking and potentially-stale badges (no AI required).
Required relationships (adopted from the Integrity Review integration,
full detail in `integrations/workspace-integrity-integration-v1.0.0/
06-m15-change-awareness.md`): DocumentVersion/SubmissionVersion → their
assertion/evidence snapshots (M14.2); assertion/evidence snapshot →
finding/challenge; finding → review decision/request/memo conclusion;
SubmissionVersion → approval decision; MandateRun → every version it
consumed. A new source/submission version never mutates a historical
conclusion — it marks dependent current items `potentially_stale` with a
reason and the superseding version, with no AI call required.
15.2 Explicit targeted reassessment mandate and preserved historical conclusions:
compares old and new evidence, explains what changed, and proposes which
prior conclusions remain valid, change materially, or need human
reconsideration — as a new revision, never a rewrite of the old one.
15.3 Opt-in monitoring with scope, owner, budget, trigger, downtime visibility.
Triggers (submission enters `submitted`; returned work resubmitted; a
material source gets a new version; a reviewer requests cross-workstream
review; a decision package is prepared for approval) each create a
normal, visible mandate with owner/scope/budget/reason/approval policy -
never hidden background monitoring of every edit.
Outcome: workspace remains accurate about what is current as work evolves;
the workspace can explain what may have become stale and commission
bounded, auditable reassessment.

## M16 — Continuous workspace integrity (new, evidence-gated)
Adopted 2026-09-17 from the Integrity Review integration; full detail in
`integrations/workspace-integrity-integration-v1.0.0/
07-m16-continuous-integrity.md`. Deepens M14.2/M15 into a reusable layer -
it must not begin merely because the architecture is attractive. Entry
gates, all required: M13 collaboration proven with multiple identities;
M14.2 has at least one independently scored real authorized case; M15
dependency tracking and reassessment work; review outputs show recurring
reusable assertions; measured failure modes justify more structure than a
strong LLM plus native document access.
16.1 Taxonomy and golden set across defect types (numerical conflict,
temporal/period mismatch, unit/currency mismatch, derivation divergence,
entity conflation, modality escalation, unsupported assertion, staleness,
logical contradiction, comparator/specificity mismatch).
16.2 Reusable evidence assertion ledger: promotes proven assertion
snapshots (M14.2's own, not a new schema built ahead of evidence) into
versioned records with stable identity, provenance, modality, supersession
history and human confirmation/dispute state.
16.3 Deterministic reconciler: one rule at a time, each justified by the
golden set, with explicit preconditions/tolerances/tier/overrides/
regression fixtures - least-ambiguous checks first, no zero-false-positive
claims without measured evidence.
16.4 Semantic cross-workstream review, benchmarked against plain
long-context review and retrieval-gated review before any specialized
NLI/embedding infrastructure is added.
16.5 Incremental/event-triggered evaluation: only changed assertions and
their recorded dependencies are reevaluated; full reassessment stays an
explicit mandate.
16.6 Inline assistance decision: attach challenges to immutable submission
spans first; a native CRDT editor is considered only if evidence shows
submission-time review is too late, and only then weighed against the
cost of building a document editor.
Outcome: cross-source and cross-author integrity issues are detected and
managed as part of normal work, preserving uncertainty, human authority,
evidence lineage and historical versions - not a one-shot report.
Explicitly deferred pending measured evidence, at every sub-stage above:
pgvector or a dedicated graph store, a separate NLI model, a commercial
parsing service, CRDT/Yjs collaborative editing, per-keystroke model
evaluation, a universal controlled predicate vocabulary, and any employee
scoring or analyst leaderboard.

## M17 — Product-integration phase (founder-directed, 2026-09-27)
Adopted from the 2026-09-27 re-entry audit (see STATUS.md's own dated
entry and `docs/workspace-shift/tasks/17.0-product-integration-program.md`
for the full plan). The audit found the backend substantially complete
through M16, but several backend-complete workflows became unreachable
from the shipped React product when the legacy-page exit was removed
(M16's own closing entries): Information Requests, Decision Packages,
Readiness, targeted Reassessment, and Monitoring/Triggers have real,
tested routes and tables but no React surface, or their old static home
lost its navigation link. M17 is an integration and product-architecture
phase, not a new backend: it reuses existing routes/schemas/domain logic
throughout and does not rewrite the mandate runtime, the findings model,
or the Python server framework. Full phase order, acceptance criteria,
and status: `tasks/17.0-product-integration-program.md`.
17.1 Information Requests — React surface over existing `workspaces.py` request routes.
17.2 Decision Packages — React surface over existing `decision_package.py`/`deliverables.py` routes.
17.3 Readiness — React surface over existing `readiness.py`/`readiness_assessments.py` read routes.
17.4 Targeted Reassessment — React surface over existing `reassessments.py` routes.
17.5 Monitoring/Triggers — the first React surface for `triggers.py` (previously backend-only).
17.6 Six-destination product shell completion (Overview 5-component
composition, distinct Deals destination, organization-wide Mandates view).
17.7 Unified Mandates composer (Flexible/Review/Pipeline/Monitoring as
one composer over the existing template/capability registry).
17.8 Unified Findings register across origins, including the founder
decision on whether/how to wire `assertion_ledger.py`/`reconciler.py`
into any live path (currently zero callers — see 17.0's own section on
this).
17.9 Design-system consistency pass (Meridian) across the completed
destinations — after structure, not before.
17.10 Local collaborative proof — re-run the applicable T01-T20
acceptance scenarios against the integrated product with synthetic
identities/data.
Outcome: every backend-complete capability through M16 is reachable and
operable from the real six-destination React product, with no normal
workflow requiring a hand-typed legacy URL. This milestone does not
itself satisfy M16's own outstanding validation gates (independent
scoring, recurring assertions, measured failure modes) and must not be
read as doing so.

## M18 — Product and Intelligence Validation (founder-directed, adopted 2026-09-27)
Entry: M17 complete and on `origin/main` (satisfied, `70f03ca`). Full
entry/exit criteria, required scenarios and measurement list:
`docs/13-post-m17-roadmap.md`. Two tracks, both required.
Track A: end-to-end product acceptance (S01-S20) across the integrated
six-destination product with synthetic and authorized-historical data -
additive to, not a replacement of, `09-acceptance.md`'s existing T01-T20.
Track B: closes M16's outstanding validation gates (independent scoring,
recurring reusable assertions, measured failure modes) with genuinely
blind cases and locked answer keys - not the retrospective self-scoring
already disclosed as a limitation. Provisional pass thresholds require
founder approval before scoring starts; none are set in advance.
A 25-surface information-architecture reconciliation against
`docs/product/02-experience-and-information-architecture.md`'s canonical
target inventory - `docs/product/07-surface-reconciliation.md` - is
required before this milestone closes: it classifies every canonical
surface, discloses one real conflict (four shipped destinations outside
the canonical 25) and confirms three administrative surfaces (Team and
Access, Organization Settings, Usage and Billing) are genuinely absent,
not merely unlinked.
Outcome: an explicit founder proceed/remediate/stop decision on whether
the local product justifies secure online pilot investment. Local
completion does not certify production safety and is not itself
commercial validation.

## M19 — Secure Online Foundation
Entry: M18 exit gate satisfied. Must **begin** with a plain-English
architecture decision report (simplest safe staging architecture; likely
non-regulated-pilot architecture; likely Saudi-residency/regulated
changes; costs at founder-only/one-pilot/several-pilot scale; migration/
rollback plan) before any provisioning. A working hypothesis is recorded
(D20: Railway web+worker, Neon Postgres, Cloudflare R2, Clerk, GitHub
Actions, Sentry, Anthropic unchanged, Cloudflare DNS optional) - not a
pre-approved decision; compare it against Railway+Railway Postgres,
Render, Fly.io, a Vercel-frontend/separately-hosted-API split, an AWS
architecture, and any stronger option found in current research, across
compatibility, migration effort, worker support, document security,
managed Postgres, auth integration, data residency, operational
complexity, backup/recovery, observability, cost at three scales,
lock-in, and the Saudi/GCC regulated-customer path. **Do not provision
or deploy anything until the founder approves the report and its cost.**
Preserves the existing mandate runtime, findings register, assertion
ledger and `authz.py` policy through the migration; this is a
hosting/security migration, not a rewrite. Covers canonical surface #5
(Sign in - a real production sign-in replacing the dev-only identity
switcher) and the private-staging minimum of #23-24 (Team and Access,
Organization Settings - confirmed to have no frontend and, in places, no
API route at all); its own share of #25 (Usage and Billing) is rate/
budget limits only. Full required implementation areas and exit gate:
`docs/13-post-m17-roadmap.md`.
Outcome: a privately-accessible staging environment with tenant
isolation, authenticated multi-user access, durable background jobs,
backup/restore, logging/alerting and an independent security review -
real customer data remains prohibited until formally approved beyond
this gate.

## Post-M19 strategic pause (D20)
A deliberate stop point, not a rolling handoff. Reaching M19's exit gate
does **not** automatically begin M20. Requires a formal review (product
coherence, intelligence quality, backend/frontend maintainability,
authorization/document security, infrastructure reliability, AI/
infrastructure cost, the initial customer, the sellable first service,
pricing, differentiation, legal/procurement obstacles, founder capacity
and budget) concluding in exactly one of: Proceed, Remediate, Narrow,
Reposition, Pause, Stop. Full framing: `docs/13-post-m17-roadmap.md`.
Outcome: **only an explicit Proceed decision authorizes M20** - every
other outcome ends this roadmap's forward motion here until a further,
separately recorded founder decision reopens it.

## M20 — Commercial Pilot Readiness
Entry: M19 exit gate satisfied **and** the post-M19 strategic pause
concluded with an explicit Proceed decision - not M19's exit gate alone.
Defines segment, buyer, one bounded paid
pilot offer, pricing hypothesis, legal/privacy/DPA/pilot-agreement
material and support/onboarding process. Covers canonical surface #6
(Invitation/onboarding - confirmed to have no invite/token flow at all)
and the customer-facing half of #25 (usage/cost reporting). Full
required work and exit gate: `docs/13-post-m17-roadmap.md`.
Outcome: a founder go/no-go decision for customer outreach.

## M21 — Paid Design-Partner Pilots (D19; supersedes D18's "Live Design-Partner Pilot" naming)
Entry: M20 exit gate satisfied (go decision). Runs controlled **paid**
engagements (one or more design partners) and measures customer value
under paid terms, not a free trial. Uses existing surfaces as they stand
at M20's close; adds a new one only in response to a specific blocking
incident the pilot itself surfaces, never for completeness. A login or
free demonstration is not commercial traction. Full required evidence
and exit gate: `docs/13-post-m17-roadmap.md`.
Outcome: one explicit conclusion - proceed, remediate and repeat,
reposition, or stop - supported by customer and usage evidence.

## M22 — Product Learning and Unit Economics (D19; supersedes D18's merged "Repeatability and Early Scale")
Entry: M21 concludes proceed (or remediate-and-repeat after
remediation). Uses M21's real evidence to determine what customers
genuinely use, what needs founder assistance, what to fix/remove/
simplify, and unit economics (revenue, AI/infrastructure cost, support
hours, gross margin, conversion, retention, pricing viability).
Deliberately narrower than D18's version - standardizing onboarding and
acquiring further customers now belong to M23, not here. Analysis and
decision, not delivery. Full required work and exit gate: `docs/13-
post-m17-roadmap.md`.
Outcome: a real, evidenced specification of what M23's repeatable
product must contain - not itself a repeatable product.

## M23 — Repeatable Commercial Product (D19; renamed/refocused from D18's "Repeatable Commercial and Customer-Administration Experience")
Entry: M22 exit gate satisfied (an evidenced product specification
exists). Builds what M22 specified: standardized onboarding, repeatable
deal setup, reliable professional templates, stable packaging/pricing,
customer administration (self-serve form of canonical surfaces #23-25 -
Team and Access, Organization Settings, Usage and Billing - beyond M19/
M20's staging/pilot minimums), a real Invitation/onboarding flow (#6,
generalized beyond M20's founder-assisted version), repeatable support
and sales demonstration, and canonical surfaces #1-4 (public marketing
pages) if the founder judges outbound/self-serve acquisition now
justifies them. This roadmap's own governing rule: **the architecture is
mapped now, developed gradually, and commercially complete by M23** -
this is that completion point. Also where the M18 25-surface
reconciliation's still-open founder decisions (the four non-canonical
destinations; Document Detail) must be closed if not already resolved
earlier. Full required work and exit gate: `docs/13-post-m17-
roadmap.md`.
Outcome: a new customer can be onboarded, self-administer their
organization, and be billed, without a founder performing a manual
step on their behalf; multiple paying customers and at least one repeat
engagement - demonstrated with real customers.

## M24 — Enterprise and Regulated-Market Readiness (D19; renamed from D18's "Enterprise Identity, Audit, Compliance and Isolated Deployment")
Entry: M23 exit gate satisfied, and a real named customer requirement
triggers it - never built speculatively against no named requirement.
Adds enterprise identity/SSO, advanced access control, extended audit,
data residency (including Saudi/GCC regulated-customer requirements
where named), penetration testing, compliance mapping, procurement
documentation, SLA/disaster-recovery and isolated deployment - an
addition on top of M23's finished basic product, per this roadmap's own
governing rule, not a substitute for finishing it. Full required work
and exit gate: `docs/13-post-m17-roadmap.md`.
Outcome: the specific named requirement that triggered this milestone is
satisfied and verified against that requirement, not a generic checklist.

## M25 — Scalable Growth (D19; broadened from D18's narrower "Scalable Operational Capabilities")
Entry: M23 (and M24, if triggered) exit gates satisfied, and M22/M23
evidence shows a growth or scale opportunity/problem - measured or
evidenced, not assumed. Growth-oriented, not only infrastructure:
repeatable customer acquisition, scalable onboarding/customer success,
engineering ownership, operational automation, margin improvement,
regional/international expansion, partnerships, model/provider
optimization at volume, evidence-backed fundraising material, and
acquisition positioning if strategically relevant. This roadmap's own
governing rule: **M25 is for scaling, not finishing the basic product**
- any item that turns out to be unfinished M23 product work belongs
there, not here. Full framing and exit gate: `docs/13-post-m17-
roadmap.md`.
Outcome: a specific, measured growth or scale problem is resolved with a
stated before/after metric - M25 does not retroactively finish M23's
commercial product.

## Global acceptance/rollback
Each task: preserve baseline tests; add unit/integration/UI tests appropriate to changes;
use isolated synthetic data; prove persistence and permissions; report limitations.
Migrations: dry-run on authorized disposable copy, row/link reconciliation, backup and
restore verification. Never casually drop tables/columns as the production rollback.
See tasks/TEMPLATE.md and docs/09-acceptance.md.
