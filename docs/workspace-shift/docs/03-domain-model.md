# Domain model and invariants
Logical contracts, not a demand to create every table before the first feature.

## Terminology and ownership
Use **Organization** as the new persisted team/tenant boundary and
`OrganizationMembership` for administrative membership. Keep **workspace** as the
product and UX term: the collaborative environment presented to users. Do not create
a new database entity or table named `Workspace` for the tenant concept.

Milestone 9 already ships a different per-analysis `workspaces` table and
`Workspace` code concept. Preserve that table and refer to it in new adapter code and
documentation as `LegacyAnalysisWorkspace` where an alias or wrapper helps clarity;
do not rename or destructively migrate it during adoption.

Deal extends existing Project and belongs to one Organization. DealMembership grants
engagement access and role. WorkstreamAssignment assigns responsibility; it does not
silently grant or restrict document access.

Mandate belongs to one Organization and optionally one Deal. Cross-deal mandates are
deferred until an explicit multi-deal permission model exists. Organization-level
mandates may use explicitly authorized library documents.

## Core records
| Record | Essential contract |
| --- | --- |
| Organization / OrganizationMembership | Stable tenant identity and administrative membership; product label may remain Workspace |
| User / DealMembership | Stable identity; scoped deal roles; revocation preserves history |
| Deal / BriefVersion | Parties, objective, perspective, scope, periods, uncertainties; brief is context, not evidence |
| Workstream / Assignment | Configurable grouping and named responsibilities |
| Document / DocumentVersion | Stable parent; immutable bytes/hash/version; explicit access grants |
| DealDocumentLink | Association is not automatic workspace-wide disclosure |
| Mandate / MandateRevision | Objective, owner, context, constraints, expected outputs |
| Template / TemplateVersion | Reusable method; distinct from an actual commissioned mandate |
| PlanRevision / Stage | Immutable approved plan; dependencies, capabilities, input scope, output contract |
| Run / Attempt / InputManifest | Actual execution; pinned sources/brief/plan/template/model; tool calls and usage |
| FindingObservation | UUID, immutable content/evidence snapshot, originating run and extraction version |
| TrackedIssue / ObservationLink | Human-managed issue joining observations without erasing lineage |
| WorkProduct / SubmissionVersion | Analyst-produced output and immutable submitted versions |
| Task / Comment / Request / Response | Actor, target, owner, status, visibility, evidence |
| ReviewDecision / Approval | Append-only actor, target version, rationale, time and evidence |
| DeliverableVersion | Draft/approved history and source dependencies |
| AuditEvent | Actor/system origin, target, change and scope |
| Notification | Permission-scoped attention item; not authority itself |

## Finding migration
Store immutable structured snapshots alongside original provider output.
Hashes detect changes; UUIDs identify records. Retain parser version and exact source.
Legacy ai-N mapping requires a reproducible extraction version and explicit migration
report. If mapping is ambiguous, stop and retain an unresolved mapping; do not guess.
Read operations never re-extract or mutate historical findings.
New extraction creates a new revision; human relinking is explicit and audited.

## Source and output truth
Separate document facts, management statements, user brief, AI inference, external
context and human decisions. A generated memo is not independent supporting evidence
for the finding that generated it. Reusing an output carries its uncertainty and lineage.

Citations pin version + locator + native provider metadata where available.
Distinguish locator-valid, quoted-value-checked, calculation-reproduced and
human-confirmed-interpretation. Do not flatten these into one green 'verified' badge.

## Concurrency and approvals
Mutable records carry a revision counter. Updates supply expected revision;
conflicts return a recoverable conflict response, never silent last-write-wins.
An approval targets a precise submission/deliverable/plan version.
Editing creates a draft successor; the old approved version remains visible.
Evidence changes flag applicability; they do not automatically revoke historical decisions.
