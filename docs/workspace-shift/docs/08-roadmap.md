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

## Later: online-readiness gate
Not a prerequisite for M11–16. Local completion does not certify production safety.
Separate authority for deployment, external access, real-data transfer and provider spend.

## Global acceptance/rollback
Each task: preserve baseline tests; add unit/integration/UI tests appropriate to changes;
use isolated synthetic data; prove persistence and permissions; report limitations.
Migrations: dry-run on authorized disposable copy, row/link reconciliation, backup and
restore verification. Never casually drop tables/columns as the production rollback.
See tasks/TEMPLATE.md and docs/09-acceptance.md.
