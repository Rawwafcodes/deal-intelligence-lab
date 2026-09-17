# Mandate engine

## Design
Stable rules in software; methods in configuration; contextual reasoning in the model;
consequential judgment with humans. Keep this an incrementally built application,
not a universal workflow platform.

One mandate API, composer, runtime and output family. Modes are starting structures,
not mutually exclusive engines: flexible, review, production, pipeline, monitoring.
A review can contain production; a pipeline can include human review.

## Capability boundary
Start with existing cross-format reconciliation and a draft-production capability.
Register each capability with:
name/version; input schema; output schema; allowed formats; side-effect class;
permission check; executor; error/retry behavior; source handling; usage accounting.

A template can combine registered capabilities. It cannot invent an executable tool.
New professional standards, output formats or capabilities need implementation/tests.
Separate adapter modules are fine; duplicated orchestration per template is not.

## Plan contract
Plan has id, revision, mandate revision, selected source versions, scope,
expected deliverables, constraints and ordered stages.
Stage has stable id, purpose, capability, input references, dependencies,
output kind and human gate when needed.
Initial runtime supports sequential steps and human waits. Branching/parallel execution
is added only for a tested workflow. Do not build a DAG editor as the first task.

Model-proposed plans are untrusted. Validate schemas, capability names, source access,
dependencies, limits and approval rules. Display unavailable work as unsupported.
Planner proposes; server authorizes; executor invokes registered capability.

AI can request adaptation. Record a new plan revision. Scope expansion, new data
destinations, larger spend or changed approval requirements require explicit approval.
It cannot rewrite its own policy or mark human gates approved.

## Lifecycle
Mandate: draft → planning → awaiting_approval → active → under_review → completed.
Active mandates can be waiting_for_input or paused. Cancelled/failed are explicit.
Reopen creates a new revision/run; does not change the historical completed run.
Run separately tracks queued/running/succeeded/failed/interrupted/outcome_unknown/
cancel_requested/cancelled. A completed provider call is not human approval.

## Context and originals
Start with authorized brief and document manifest. Model may request further sources
within the approved scope. Server checks every fetch and records actual access.
Metadata-only selection can miss evidence: show coverage, unresolved sources and
selection uncertainty. Allow user-required sources and broader review.
Preserve original PDF/workbook paths to the provider where supported. No mandatory
brittle extraction funnel. Tools/conversions are allowed when necessary, with provenance.
Do not promise unrestricted files or total comprehension; show unreadable/omitted inputs.

## Output contract
Typed envelopes for finding, question, task proposal, calculation, draft deliverable,
progress and limitation. Preserve original model output and native citation spans.
Use schema validation where provider features allow it. Test structured output plus
citations compatibility; if unsupported, use a versioned extraction adapter and validate,
never fabricate evidence to satisfy the schema.
Published findings enter the shared register; no parallel mandate-only finding silo.
Task/request creation remains a visible, authorized action. External sending is separate.

## Durable execution is local work
Persist job before acknowledging start. Worker continues independently of browser.
Record attempts before provider calls, heartbeat, bounded continuation, cleanup state,
actual model, tokens/cache categories/tool use, and estimated versus known charges.
At interruption, unknown provider outcome is not automatically retried.
Internal idempotency does not imply provider-side deduplication.
Cancellation stops future steps; disclose uncertain in-flight work and cost.
Budgets check before calls and between stages; cannot guarantee a perfect hard-dollar
ceiling during an already-running provider operation.

## Chat
Optional steering within the mandate. Approved plan revisions and decisions are records,
not facts hidden in chat history. Free-text changes are proposed, not silently executed.

## Monitoring
Later capability with an explicit watched scope, trigger, duration, budget and owner.
Local monitoring runs only while the relevant local processes run; report downtime.
Deterministic version changes can mark potential impact without a paid model call.
Materiality assessment/reanalysis is a separately authorized operation.
