# Dependency-ordered roadmap — no calendar dates
This replaces the competing earlier M11–15 sequences.
Each numbered task is separately reviewable; do not execute a whole milestone blindly.

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
14.2 Work-product review template with evidence-status distinctions.
14.3 Decision-package production from explicit reviewed/unresolved material.
14.4 Readiness template: checklist scope explicit; no claim of universal completeness.
One template at a time; unsupported format/capability becomes a separate bounded task.
Validate on independently reviewed real authorized material, not just fixture success.
Outcome: reusable engine demonstrated across materially different work.

## M15 — Change awareness and monitoring
15.1 Version dependency tracking and potentially-stale badges (no AI required).
15.2 Explicit targeted reassessment mandate and preserved historical conclusions.
15.3 Opt-in monitoring with scope, owner, budget, trigger, downtime visibility.
Outcome: workspace remains accurate about what is current as work evolves.

## Later: online-readiness gate
Not a prerequisite for M11–15. Local completion does not certify production safety.
Separate authority for deployment, external access, real-data transfer and provider spend.

## Global acceptance/rollback
Each task: preserve baseline tests; add unit/integration/UI tests appropriate to changes;
use isolated synthetic data; prove persistence and permissions; report limitations.
Migrations: dry-run on authorized disposable copy, row/link reconciliation, backup and
restore verification. Never casually drop tables/columns as the production rollback.
See tasks/TEMPLATE.md and docs/09-acceptance.md.
