# Post-M17 roadmap: validation, secure hosting and commercial pilot (M18-M25)

Adopted 2026-09-27, as a founder-directed documentation and planning task
performed immediately after the M17 product-integration program (Phases
A-F plus the Task 17.14 authorization closeout) was confirmed complete and
pushed to `origin/main` through commit `70f03ca`. This document is
planning only. No M18 implementation, infrastructure provisioning,
Anthropic API call, deployment, data migration or new dependency was
introduced to produce it. See `STATUS.md`'s matching dated entry and
`docs/10-decisions.md`'s D17 for the decision record.

Extended the same day (still documentation/planning only) with a
25-surface information-architecture reconciliation against
`docs/product/02-experience-and-information-architecture.md`'s canonical
target route/page inventory, and with three further milestones (M23-M25)
covering the repeatable commercial/customer-administration experience,
enterprise identity/audit/compliance, and volume-justified scale. See
`docs/10-decisions.md`'s D18 and the "25-surface reconciliation" section
immediately below.

**Superseded the same day (D19)**: the founder gave the exact names and
content for M21-M25 directly, after M17 was confirmed pushed to
`origin/main`. Per root `AGENTS.md`'s own authority rule ("latest
explicit founder instruction outranks accepted decisions"), D19 revises
M21's title, substantially redefines M22 (now a distinct product-
learning/unit-economics milestone, narrower than D18's merged
"repeatability and early scale"), renames M23, and broadens M25 into
growth/expansion/fundraising rather than only operational scale. D17 and
D18 remain in `10-decisions.md` unchanged, as the historical record of
what was adopted first; this document's own M21-M25 sections below now
state the D19 content, not the superseded D18 content. M18-M20 and the
25-surface reconciliation are unchanged by D19.

## 25-surface information-architecture reconciliation

`docs/product/07-surface-reconciliation.md` is the code-verified status
of every one of the 25 canonical surfaces in `docs/product/
02-experience-and-information-architecture.md`'s target route/page
inventory - current route (if any), backend capability, frontend
capability, page/panel/drawer/component form, and classification
(complete/partial/missing/static-only). It does not rename, replace or
expand that canonical table itself. Two things it found are load-bearing
for this roadmap and are not restated in full here:

- **A real conflict**: four shipped, backend-complete deal-level
  destinations (Readiness, Targeted Reassessment, Monitoring/Triggers,
  Assertions) exist with no corresponding row in the canonical 25.
  Presented as an open founder decision (amend the table, or declare
  them a disclosed exception), not resolved by either document.
- **Three confirmed-absent administrative surfaces**: Team and Access,
  Organization Settings, and Usage and Billing have no frontend at all,
  and in two of the three cases (Organization Settings; org-level Team
  membership) no HTTP route either - not merely unlinked, genuinely not
  built. These are exactly the surfaces M19 and M23 below now name
  explicitly, rather than leaving "production authentication" and
  "organization and tenant isolation" as the only description of what
  is missing.
- **One partial, product-facing gap inside the local product itself**:
  Document Detail is a raw inline file link, not an in-app version-
  history/citation-backlink view - flagged for an M18 founder decision
  on whether it is essential before local-product acceptance.

M18's exit gate below is unchanged in spirit but now explicit: it cannot
close until every one of the 25 canonical surfaces has been classified
(done, in `07-surface-reconciliation.md`) and every essential
local-product surface has either passed founder acceptance or received
an explicitly approved later milestone (the assignments in this
document's M18-M25 sections, and the open decisions above).

This extends `08-roadmap.md` (which retains the short M18-M22 pointer
entries in its own dependency-ordered style) with the entry/exit-criteria
detail those short entries cannot hold. It does not replace or
retroactively edit any M10-M17 entry, any decision D01-D16, or any
`STATUS.md` entry. Historical material is unchanged.

## Relationship to existing canonical documents

- `08-roadmap.md` — dependency-ordered task list; keep reading it for
  M10-M17. Its M18-M22 entries are short pointers into this file.
- `10-decisions.md` — D17 records the original adoption of this roadmap;
  D18 the 25-surface reconciliation and its M23-M25 extension; D19 the
  founder's direct M21-M25 naming/content revision that supersedes D18's
  version of those five milestones (D17/D18 are not deleted or rewritten
  - D19 records the supersession explicitly, per root `AGENTS.md`'s
  "latest explicit founder instruction outranks accepted decisions").
  Further M18-M25 decisions are appended there as D20+ when the founder
  actually decides them. This file's own "Open founder decisions" section
  below is the register of what is not yet decided — it is not itself a
  decision record.
- `09-acceptance.md` — the existing T01-T20 scenarios are safety/integrity
  properties (permission boundaries, revision conflicts, audit lineage,
  export literalness) proven at the code/API level. M18 Track A's S01-S20
  scenarios below are a different, additive set: end-to-end product/
  usability workflow acceptance, run against the integrated product as a
  whole. Track A does not replace or renumber T01-T20; both must pass.
- `docs/product/06-truth-register.md` — "Open production decisions" there
  is the same list M19's required architecture decision covers; this file
  does not duplicate it with different content, only points to it.
- `docs/product/02-experience-and-information-architecture.md` — the
  canonical 25-surface target route/page inventory. `docs/product/
  07-surface-reconciliation.md` is this roadmap's own code-verified
  reconciliation of that table against the actual implementation; see
  this file's "25-surface information-architecture reconciliation"
  section below.
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

A concrete, UI-grounded execution script for all 20 scenarios - roles,
preconditions, exact steps, and the known gaps each scenario will
confirm rather than "discover" - is scoped in `docs/workspace-shift/
tasks/18.1-track-a-walkthrough-script.md`. That task produces the script
only; it does not execute the walkthrough, record actual results, or
constitute founder acceptance.

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
- **every one of the canonical 25 surfaces in `docs/product/
  02-experience-and-information-architecture.md` has been classified**
  (route, backend, frontend, form, status) per
  `docs/product/07-surface-reconciliation.md`, and every surface that
  reconciliation marks essential to the local product has either passed
  founder acceptance or received an explicit, founder-approved later
  milestone (not a silent gap) - satisfied for 22 of 25 by this
  reconciliation's own milestone assignment; the Document Detail gap and
  the four non-canonical surfaces remain open founder decisions per the
  section above, and must be closed (either direction) before this gate
  is satisfied;
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

Production authentication (canonical surface #5, Sign in - currently a
dev-only identity switcher, not a real sign-in page); organization and
tenant isolation, including the minimum Team and Access and Organization
Settings surfaces (#23-24 - currently no frontend and, for org-level
membership and organization creation/update, no HTTP route at all) needed
to actually run a private multi-user staging pilot, not their full
self-serve form (deferred to M23); server-side authorization (extending,
not replacing, the existing `authz.py` capability policy from Task
17.14/D16); rate and budget limits, which is this milestone's own share
of Usage and Billing (#25) - usage/cost *reporting* is M20's, real
billing is M23's; managed PostgreSQL and migrations;
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
prepare onboarding materials (canonical surface #6, Invitation/
onboarding - confirmed to have no invite/token flow at all, only direct
membership-creation functions with no route); prepare administrator
guidance; prepare support and incident procedures; prepare usage and cost
reporting (the customer-facing half of surface #25 - M19 already covers
rate/budget limits, M23 covers real billing); prepare data-retention/
deletion process; obtain suitable legal advice; prepare privacy, terms
and data-processing documents; prepare pilot agreement; prepare security
questionnaire responses; prepare sales demonstration and follow-up
process (may pull surfaces #1-4 forward from M23 if the founder judges a
minimal pilot landing/contact page necessary for outreach - not required
by default); define pilot-success metrics.

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

## M21 — Paid Design-Partner Pilots

**Purpose** (D19, supersedes D18's "Live Design-Partner Pilot" naming):
run controlled **paid** engagements - one or more design partners, not
necessarily exactly one - and measure whether the product creates real
customer value under paid terms, not a free trial's weaker signal.

**Entry criteria**: M20 exit gate satisfied (go decision).

**Surface policy**: use the existing surfaces (the 25 canonical plus the
four disclosed above, whichever the founder decision resolved) as they
stand at M20's close. Add a new surface during a pilot only in response
to a specific blocking incident the pilot itself surfaces, never merely
for completeness or to look more finished - the same discipline
`docs/product/06-truth-register.md` already applies to commercial
claims, applied here to product surfaces.

### Required evidence

Actual workflow usage; time saved; accepted/rejected findings; senior-
review value; support burden; AI/infrastructure cost; user feedback;
willingness to continue; willingness to pay; repeat-deal intent. (Also
carried from D18's original evidence list, unchanged: authorized
customer and users; signed pilot terms; approved data handling; recorded
onboarding effort; active users and roles; errors and incidents;
customer interviews.)

A login or free demonstration is not commercial traction.

### M21 exit gate

M21 closes with one explicit conclusion — proceed; remediate and repeat;
reposition; or stop — supported by customer and usage evidence, not
engineering completion alone.

## M22 — Product Learning and Unit Economics

**Purpose** (D19, supersedes D18's merged "Repeatability and Early
Scale"): use M21's real paid-pilot evidence to learn what the product
actually is, before building the repeatable commercial product around
it. This is deliberately narrower than D18's version - "acquire further
paying customers" and "standardize onboarding" now belong to M23 below,
not here. M22 is analysis and decision, not delivery.

**Entry criteria**: M21 concludes "proceed" (or "remediate and repeat"
after remediation).

**Surface policy**: refine, remove or add a surface only from measured
M21 pilot evidence (a real usability finding, a real support incident, a
real customer request) - not from this document's own unexercised
predictions about what a second customer might want.

### Required work

Determine, from M21's real evidence and nothing else: what customers
genuinely use; what requires founder assistance (and therefore isn't yet
repeatable); what should be fixed, removed or simplified; revenue per
engagement/customer; AI and infrastructure cost; support hours; gross
margin; pilot conversion; repeat usage; retention; pricing viability.

### M22 exit gate

M22 closes only when every item above has a real, evidenced answer (not
a guess) and the founders have decided, from that evidence, what M23's
repeatable product must actually contain - M22 produces the specification
M23 builds against, it does not itself build anything.

## M23 — Repeatable Commercial Product

**Purpose** (D19, renamed and refocused from D18's "Repeatable Commercial
and Customer-Administration Experience"): build the repeatable
commercial product M22's evidence specified - the point at which the
product can be sold and self-administered without founder hand-holding
on every deal. This is where `07-surface-reconciliation.md`'s
administrative surfaces (#23-25, deferred past M19/M20's staging/pilot
minimums) and generalized onboarding/marketing surfaces (#1, #6) belong,
consistent with this roadmap's own governing rule: **the architecture is
mapped now, developed gradually, and commercially complete by M23** -
this milestone is that completion point, not M25.

**Entry criteria**: M22 exit gate satisfied (a real, evidenced product
specification exists).

### Required work

Standardized onboarding; repeatable deal setup; reliable professional
templates; stable packaging and pricing; customer administration - full
self-serve Organization Settings and Team and Access (surfaces #23-24:
M19 built only the private-staging minimum, no self-serve invite flow,
no organization creation/rename UI) and a real Invitation/onboarding flow
with tokens/expiry (#6, generalized beyond M20's founder-assisted
membership creation); usage and cost reporting at the repeatable-product
level, plus real billing beyond M19's rate/budget limits and M20's
reporting (#25); repeatable support; repeatable sales demonstration
(public-facing marketing surfaces #1-4 - Public homepage, Product/how it
works, Security and trust, Request pilot/contact - if the founder judges
outbound/self-serve acquisition now justifies them, per M22's own
evidence, not built speculatively before it); multiple paying customers;
repeat engagements. Resolve the four non-canonical-surface and Document
Detail decisions from the reconciliation above if not already resolved
by M18.

### M23 exit gate

M23 closes only when a new customer can be onboarded, administer their
own organization/team, and be billed, without a founder performing a
manual database or API step on their behalf; and there is evidence of
multiple paying customers and at least one repeat engagement - demonstrated
with real customers, not only a synthetic one.

## M24 — Enterprise and Regulated-Market Readiness

**Purpose** (D19, renamed from D18's "Enterprise Identity, Audit,
Compliance and Isolated Deployment"; same anti-speculation gating,
content extended with explicit Saudi/GCC regulated-market scope): meet
the identity, audit, compliance, security, deployment-isolation and
regional-regulatory requirements a larger or regulated customer's
procurement process requires - completed here, after M23's commercial
completion, per this roadmap's own governing rule that enterprise
additions are an M24 addition on top of a finished basic product, not a
substitute for finishing it.

**Entry criteria**: M23 exit gate satisfied, and a real prospective
customer or signed deal whose procurement process names a specific
requirement below (do not build enterprise identity/compliance
speculatively against no named requirement).

### Required work

Enterprise identity and SSO (SAML/SCIM as a named customer's procurement
actually requires, not preemptively); advanced access control beyond
`authz.py`'s existing role-capability matrix, if a named requirement
needs finer grain; extended audit retention and export beyond M19's
baseline; data residency, including Saudi/GCC-specific regulated-customer
requirements if a named prospect requires them; penetration testing;
compliance mapping and documentation/attestations a named deal actually
requires (e.g. SOC 2, ISO 27001 - do not pursue a certification with no
customer requirement driving it); procurement documentation; SLA and
disaster-recovery commitments; isolated/private deployment administration
for a customer whose data-residency or isolation requirement M19's shared
staging architecture cannot satisfy; advanced administration beyond M23's
self-serve baseline.

### M24 exit gate

M24 closes only when the specific named requirement that triggered this
milestone is satisfied and verified against that requirement, not
against a generic enterprise checklist assembled without a real customer
driving it.

## M25 — Scalable Growth

**Purpose** (D19, broadened from D18's narrower "Scalable Operational
Capabilities"): grow the repeatable, commercially-complete product (M23)
and its enterprise readiness (M24, where applicable) at real volume -
acquisition, expansion and, if the evidence supports it, fundraising or
acquisition positioning. This roadmap's own governing rule applies
directly: **M25 is for scaling, not finishing the basic product** - any
item below that turns out to require finishing product surfaces M23
should have completed belongs there, not here.

**Entry criteria**: M23 (and M24, if triggered) exit gates satisfied, and
M22/M23 evidence shows customer/usage volume or growth opportunity that
justifies the specific item below (measured or evidenced, not assumed).

### Required work

Repeatable customer acquisition; scalable onboarding and customer
success; engineering ownership; operational automation; improved gross
margins; regional/international expansion (building on M24's regulated-
market work where relevant); partnerships; model/provider cost
optimization at volume; fundraising material supported only by verified
evidence (`docs/product/06-truth-register.md`'s existing rule against
unverified demand/traction/valuation claims, unchanged); acquisition
positioning, only if strategically relevant and only from real evidence.

### M25 exit gate

M25 closes only when the specific growth or scale problem that triggered
a given item is measurably addressed (a stated metric, before/after) -
not merely when generic growth or infrastructure activity has occurred.
Only scale-related surfaces justified by real volume are added here;
M25 does not retroactively finish M23's commercial product.

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
- Whether to amend `docs/product/02-experience-and-information-
  architecture.md`'s canonical 25-surface table to add the four
  non-canonical destinations `07-surface-reconciliation.md` found
  (Readiness, Reassessments, Triggers, Assertions), or declare them a
  disclosed exception instead.
- Whether Document Detail's current raw-file-link form (canonical
  surface #13) is sufficient for M18 founder acceptance, or must gain
  in-app version-history/citation-backlink context before M18 closes.
- M24's actual trigger: which named customer requirement, if any, first
  makes enterprise identity/compliance/isolated-deployment work
  necessary (not decided in advance of a real requirement).
- M22's own product-learning conclusions (what to fix/remove/simplify,
  pricing viability) - deliberately not pre-decided here; M22 exists
  precisely to produce this decision from M21's real evidence.
- M25's specific growth/expansion/fundraising priorities - deliberately
  unspecified until M23/M24 evidence exists to justify a particular one
  over another.

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

## Explicit non-goals through M25

Restated from the milestone-by-milestone exclusions above: this roadmap
does not authorize, at any point before its own relevant gate, cloud
deployment (before M19), production authentication or real customer data
(before M19's exit gate and M20's legal/security work), acquiring
customers beyond the paid design partners themselves or standardizing
onboarding (before M22's evidence exists to specify what "standardized"
should mean), public launch, self-serve billing or public marketing
surfaces (before M23, this roadmap's own commercial-completion point),
enterprise identity/compliance/isolated-deployment work against no named
customer requirement (before M24's own gated entry), or growth/scale
activity against no measured volume or evidenced opportunity (before
M25's own gated entry) - or any claim of commercial demand,
traction, retention or valuation without the specific evidence each
milestone's exit gate requires (`06-truth-register.md`'s existing rule,
carried forward unchanged).
