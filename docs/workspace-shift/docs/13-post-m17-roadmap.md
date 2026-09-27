# Post-M17 roadmap: validation, secure hosting and commercial pilot (M18-M22)

Adopted 2026-09-27, as a founder-directed documentation and planning task
performed immediately after the M17 product-integration program (Phases
A-F plus the Task 17.14 authorization closeout) was confirmed complete and
pushed to `origin/main` through commit `70f03ca`. This document is
planning only. No M18 implementation, infrastructure provisioning,
Anthropic API call, deployment, data migration or new dependency was
introduced to produce it. See `STATUS.md`'s matching dated entry and
`docs/10-decisions.md`'s D17 for the decision record.

This extends `08-roadmap.md` (which retains the short M18-M22 pointer
entries in its own dependency-ordered style) with the entry/exit-criteria
detail those short entries cannot hold. It does not replace or
retroactively edit any M10-M17 entry, any decision D01-D16, or any
`STATUS.md` entry. Historical material is unchanged.

## Relationship to existing canonical documents

- `08-roadmap.md` — dependency-ordered task list; keep reading it for
  M10-M17. Its M18-M22 entries are short pointers into this file.
- `10-decisions.md` — D17 records the adoption of this roadmap; further
  M18-M22 decisions are appended there as D18+ when the founder actually
  decides them, using the existing decision procedure. This file's own
  "Open founder decisions" section below is the register of what is not
  yet decided — it is not itself a decision record.
- `09-acceptance.md` — the existing T01-T20 scenarios are safety/integrity
  properties (permission boundaries, revision conflicts, audit lineage,
  export literalness) proven at the code/API level. M18 Track A's S01-S20
  scenarios below are a different, additive set: end-to-end product/
  usability workflow acceptance, run against the integrated product as a
  whole. Track A does not replace or renumber T01-T20; both must pass.
- `docs/product/06-truth-register.md` — "Open production decisions" there
  is the same list M19's required architecture decision covers; this file
  does not duplicate it with different content, only points to it.
- M16 (`08-roadmap.md`'s own M16 entry) — its outstanding validation gates
  (independent scoring, recurring reusable assertions, measured failure
  modes; see `STATUS.md`'s M16 gate-check entry and `06-truth-register.md`'s
  O07) are **incorporated into M18 Track B below, not marked complete**.
  M18 does not silently close them by proceeding past M16 in the milestone
  sequence.

## Planning principles (binding on every milestone below)

- Milestones are evidence gates, not calendar periods.
- Engineering completion is not commercial validation.
- Local test success is not production security.
- A deployed application is not automatically pilot-ready.
- A pilot is not proof of repeatability.
- Do not add features merely to make a milestone look substantial.
- Every milestone states what it proves, and has explicit entry and exit
  criteria (below).
- Every milestone discloses its dependencies on founders, domain
  reviewers, customers or professional advisers.
- Real customer data is not used until the required security and
  contractual gates are satisfied (M19 exit gate, M20 legal/security work).
- Paid API calls require explicit, task-specific authorization — unchanged
  from the standing rule in root `AGENTS.md`.
- Deployment/provider selection (hosting, database, storage, auth, CI/CD)
  remains **open until M19's own architecture-decision task**. This
  document does not select or imply Vercel, Neon, Supabase, AWS or any
  other provider, and no earlier document's mention of any provider name
  is a decision.
- Existing working intelligence and domain logic (the mandate runtime,
  findings register, assertion ledger, authz policy, and every backend
  module M11-M17 built) is preserved through M19's infrastructure
  changes — M19 is a hosting/security migration of the existing system,
  not a rewrite.

## M18 — Product and Intelligence Validation

**Purpose**: prove the integrated M17 product is usable as one
professional workspace and that its intelligence performs reliably enough
to justify secure online pilot investment. Two tracks; both must pass.

**Entry criteria**: M17 complete and on `origin/main` (satisfied,
`70f03ca`).

### Track A — Product acceptance

Validate the full integrated workflow locally with synthetic and
authorized-historical data, across the six-destination React product.

Required scenarios (numbered S01-S20 here to stay distinct from
`09-acceptance.md`'s T01-T20; additive, not a replacement):

| # | Scenario |
|---|---|
| S01 | Create or enter an organization |
| S02 | Create/open a deal |
| S03 | Establish users and roles |
| S04 | Create/edit the deal brief |
| S05 | Add workstreams and assignments |
| S06 | Upload documents and document versions |
| S07 | Create tasks and comments |
| S08 | Submit work products |
| S09 | Review, return and approve work |
| S10 | Create and execute mandates |
| S11 | Use Flexible, Review, Pipeline and Monitoring structures |
| S12 | Review findings and evidence |
| S13 | Create and respond to information requests |
| S14 | Use readiness and reassessment |
| S15 | Use assertions and evidence status |
| S16 | Produce/review a decision package |
| S17 | Review material changes and activity |
| S18 | Verify restricted external-executive experience |
| S19 | Verify restart persistence |
| S20 | Verify concurrent identities and revision conflicts |

For each scenario, record: role; starting state; actions; expected
result; actual result; usability issue; technical defect; severity;
evidence/screenshot; resolution status. Use the same discipline
`09-acceptance.md`'s "Completion report" section already requires
(exact commit/dirty state, real browser evidence, no claiming a check
that was not actually run).

Required product outputs: accepted terminology; accepted navigation;
accepted end-to-end workflow; usability issue register; accessibility
check; performance observations; founder acceptance decision.

### Track B — Intelligence validation

Closes the outstanding M16 validation gates (gate 2: independent scoring;
gate 4: recurring reusable assertions; gate 5: measured failure modes —
see `08-roadmap.md`'s M16 entry and `STATUS.md`'s gate-check entry) using
genuinely blind cases, not the retrospective self-scoring already
disclosed as a limitation of the one existing M14.2 scored case.

Required methodology:

- Use authorized historical deals with sufficiently complete source
  material.
- Create and lock answer keys before running the product.
- Keep answer-key content out of model requests.
- Use an independent knowledgeable human evaluator wherever possible.
- Distinguish retrospective cases from genuinely blind cases.
- Do not auto-grade qualitative correctness with another LLM.
- Preserve raw outputs, document versions, model, prompts, token usage,
  runtime and scoring decisions.
- Separate model failure from source-data insufficiency and application
  failure.

Measure at minimum: critical-issue recall; high-severity recall; overall
expected-issue recall; reviewed-finding precision; false-positive count
and rate; citation locator validity; quoted-value accuracy; calculation
reproduction accuracy; severity accuracy; recommended-action usefulness;
unsupported-claim rate; missed-material-issue register; repeatability
across repeated runs; runtime per engagement; AI cost per engagement;
human review time; recurring-assertion reuse; detected failure modes.

Do not invent universal pass thresholds without evidence. Provisional
thresholds must be proposed and recorded (as a new decision in
`10-decisions.md`) **before scoring starts**, and require founder
approval — this document deliberately does not set them.

### M18 exit gate

M18 closes only when:

- the integrated workflow has been completed end-to-end (Track A);
- no unresolved critical product defect remains;
- independent scoring exists (Track B);
- the outstanding M16 gates are either satisfied or explicitly failed —
  not silently left unaddressed;
- performance and cost are measured;
- material failure modes are documented;
- the founders make an explicit proceed/remediate/stop decision.

### M18 exclusions

Cloud deployment; production authentication; live customer onboarding;
feature expansion unrelated to observed validation defects; claims of
commercial demand.

## M19 — Secure Online Foundation

**Purpose**: create a private production-like environment that can safely
support an authorized pilot.

**Entry criteria**: M18 exit gate satisfied (proceed decision).

### Required architecture decision (before implementation)

Inspect the actual system and compare suitable options for: React
hosting; Python API hosting; long-running background workers; managed
PostgreSQL; private object storage; authentication; secrets management;
logs and error tracking; CI/CD; backups; regional/data-residency needs;
expected AI runtime and concurrency; cost at zero, one and several pilot
customers.

Do not assume Vercel, Neon, Supabase, AWS or any other provider in
advance (per this file's own planning principles above). The chosen
architecture must support long-running analysis without depending on one
browser request remaining open — the existing durable local worker
(M12.2) is the functional precedent to preserve, not discard, when
choosing the hosted equivalent.

### Required implementation areas

Production authentication; organization and tenant isolation; server-side
authorization (extending, not replacing, the existing `authz.py`
capability policy from Task 17.14/D16); managed PostgreSQL and migrations;
private document storage; document encryption in transit and at rest;
signed/scoped document access; background-job queue and worker; retries,
idempotency and cancellation; secret management; environment separation;
staging deployment; CI/CD; rate and budget limits; structured logging;
error tracking; health checks; backup and restore; data export and
deletion; dependency and security scanning; audit retention; operational
runbooks.

### M19 exit gate

M19 closes only when:

- staging is privately accessible;
- two authorized users can complete the core workflow;
- tenant-isolation tests pass;
- document-access tests pass;
- a long-running job survives browser closure and worker interruption;
- backup restoration is demonstrated;
- logs and alerts work;
- no production secret exists in source control;
- an independent security review or equivalent documented review is
  completed;
- costs are measured;
- real customer data remains prohibited until formal approval (separate
  from this gate).

### M19 exclusions

Public launch; broad customer onboarding; billing automation unless
essential for pilot controls; large-scale architecture without
demonstrated need.

## M20 — Commercial Pilot Readiness

**Purpose**: prepare the product, operating process and commercial offer
for a first design partner.

**Entry criteria**: M19 exit gate satisfied.

### Required work

Confirm the initial customer segment; define buyer, user and approver;
conduct customer discovery interviews; define one bounded paid pilot
offer; define scope, exclusions and deliverables; establish pricing
hypothesis; establish included AI usage and overage policy; prepare a
safe demonstration environment; create a synthetic demonstration deal;
prepare onboarding materials; prepare administrator guidance; prepare
support and incident procedures; prepare usage and cost reporting;
prepare data-retention/deletion process; obtain suitable legal advice;
prepare privacy, terms and data-processing documents; prepare pilot
agreement; prepare security questionnaire responses; prepare sales
demonstration and follow-up process; define pilot-success metrics.

This resolves several of `docs/product/06-truth-register.md`'s "Open
product decisions" (segment, buyer title, first paid offer, pricing) with
real evidence rather than restating them as hypotheses; that file should
be updated with the founder's actual answers when M20 produces them, not
before.

### Recommended commercial principle

Sell a bounded professional review/pilot first; use the broader workspace
as the delivery and collaboration environment; do not require the
customer to replace its entire workflow immediately; do not position
unvalidated AI output as autonomous professional advice.

### M20 exit gate

M20 closes only when:

- a specific customer segment is chosen;
- genuine customer interviews have occurred;
- the pilot offer is understandable and priced;
- the demo can be delivered reliably;
- onboarding and support are documented;
- legal/security requirements are sufficiently addressed;
- staging is approved for the intended data class;
- founders sign a go/no-go decision for customer outreach.

## M21 — Live Design-Partner Pilot

**Purpose**: run a controlled real engagement and measure whether the
product creates customer value.

**Entry criteria**: M20 exit gate satisfied (go decision).

### Required evidence

Authorized customer and users; signed pilot terms; approved data
handling; recorded onboarding effort; workflow completion; active users
and roles; analyses and mandates performed; senior-review usage;
accepted/rejected findings; information requests; time saved; errors and
incidents; human support required; infrastructure and AI costs; customer
interviews; willingness to continue; willingness to pay; repeat-deal
intent.

No result is represented as traction merely because a user logged in.

### M21 exit gate

M21 closes with one explicit conclusion — proceed; remediate and repeat;
reposition; or stop — supported by customer and usage evidence, not
engineering completion alone.

## M22 — Repeatability and Early Scale

**Purpose**: turn successful pilot evidence into a repeatable early
business.

**Entry criteria**: M21 concludes "proceed" (or "remediate and repeat"
after remediation).

### Required work

Fix recurring pilot issues; standardize onboarding; reduce
founder-assisted steps; improve reliability and observability; validate
pricing; acquire further paying customers; measure retention and repeat
usage; track gross margin and AI cost; establish support expectations;
establish engineering ownership; prioritize capabilities using observed
demand; prepare fundraising material only from verified evidence.

### M22 exit gate

M22 closes only when the company has evidence that the product can be
sold and delivered repeatedly — not merely one successful engagement.
Track: paying customers; repeat engagements; annualized or contracted
revenue; retention; average revenue per customer/deal; AI and
infrastructure cost; support hours; gross margin; sales-cycle length;
implementation effort; customer references; security/procurement
blockers.

## Open founder decisions (register, not a decision record)

These are not yet decided. Each becomes a new `10-decisions.md` entry
(D18+) only when the founder actually decides it — recording it here does
not close it.

- M18 Track B's provisional pass thresholds (recall/precision/false-positive
  rate, etc.) — must be proposed and approved before scoring starts.
- Which historical deals are "authorized" and sufficiently complete for
  M18 Track B's blind cases (relates to `06-truth-register.md`'s O07).
- M19's full architecture selection (hosting, database, storage, auth,
  CI/CD, secrets, log/error tooling) — explicitly deferred to M19 itself,
  not decided here.
- M19's independent security review provider/method.
- M20's initial customer segment, buyer title, pilot offer scope, pricing
  hypothesis and overage policy (`06-truth-register.md`'s existing open
  product decisions).
- M20's legal advisor and the resulting privacy/terms/DPA/pilot-agreement
  content.
- Whether/when a pilot customer's real data clears the M19/M20 gates for
  use (must never be assumed from engineering readiness alone).

## External dependencies (register)

- Domain reviewers/independent human evaluators for M18 Track B blind
  scoring (must not be the same person who built the capability being
  scored, extending the limitation already disclosed for M14.2's one
  existing scored case).
- A security reviewer (internal-independent or external) for M19's exit
  gate.
- Legal/professional advisers for M20's privacy, terms, DPA and pilot
  agreement.
- A design-partner customer, its users and approver for M20 discovery and
  the M21 pilot itself.
- A hosting/database/storage/auth provider, selected only at M19 per the
  deferral above.

## Explicit non-goals through M22

Restated from the milestone-by-milestone exclusions above: this roadmap
does not authorize, at any point before its own relevant gate, cloud
deployment (before M19), production authentication or real customer data
(before M19's exit gate and M20's legal/security work), public launch or
broad onboarding (before M22), or any claim of commercial demand,
traction, retention or valuation without the specific evidence each
milestone's exit gate requires (`06-truth-register.md`'s existing rule,
carried forward unchanged).
