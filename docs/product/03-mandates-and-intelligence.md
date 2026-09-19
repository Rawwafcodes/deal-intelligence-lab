# Mandates and intelligence

## Mandates are the umbrella

A mandate is a flexible commission to AI within a governed workspace. It has an
objective, context, selected evidence, proposed plan, capabilities, limits,
human checkpoints, attempts, outputs and an audit trail.

Do not reduce mandates to investigation. Investigation, drafting, review,
reconciliation, valuation support, readiness assessment, decision-package
production and reassessment can all be mandate outcomes when the required
capabilities exist.

## Starting structures

### Flexible

The user states the objective and selects context/evidence. AI proposes the
method using registered capabilities. The proposal remains unapproved until a
human accepts it. Flexible does not allow the planner to invent tools, access,
providers, spending authority or arbitrary host code.

### Review

Review checks an exact human or AI work-product version against selected
evidence, peer submissions, the brief and applicable rules. It identifies
unsupported assertions, contradictions, missing evidence, calculation issues
and uncertainty. Proposed matters require a human disposition before becoming
shared findings.

**Review is not the Validation Lab.** Review is a customer workflow applied to
real work. The Validation Lab is an internal evaluation harness using locked
answer keys and human scoring to measure whether intelligence is reliable.

### Pipeline

A pipeline instantiates an approved professional method from reusable stages
and capabilities. It can represent reconciliation, Integrity Review, a
decision package, readiness review, targeted reassessment, valuation support,
pre-market assessment or another proven method.

Pipeline does not mean a general visual DAG builder. Add one proven method at a
time. A new combination of existing capabilities should usually be
configuration; a genuinely new analytical ability requires bounded code,
security review and tests.

### Monitoring

Monitoring reacts to explicit future events such as a material document
version, resubmission or requested reassessment. Every monitor has visible
scope, trigger, owner, approval policy and budget. It creates an ordinary,
auditable mandate rather than running hidden continuous inference.

## Three responsibility layers

### Deterministic software governs

- identity, authorization and tenant/deal isolation;
- storage, immutable versions and checksums;
- state machines, assignments, revisions and conflicts;
- capability schemas and allowed formats;
- exact source/version manifests;
- budgets, cancellation, retries and audit events;
- citation locator validation and deterministic calculations where justified;
- staleness/dependency propagation.

### AI comprehends and reasons

- document and model interpretation;
- plan proposals;
- ambiguity, materiality and cross-source relationships;
- analytical synthesis and drafting;
- potential contradiction or missing-evidence identification;
- targeted reassessment of changed evidence.

The design should avoid brittle hardcoded extraction that removes the evidence
the model needs. Equally, the model must not control access, persistence,
permissions or final approval.

### Humans exercise authority

- approve or reject plans;
- confirm context and entity relationships;
- accept, reject, edit or deduplicate candidate findings;
- review evidence and submission versions;
- approve deliverables and closure;
- accept residual risk;
- authorize exceptional spend or transmission.

## Evidence integrity

- Inputs are exact, authorized versions—not "whatever is current" at read time.
- Historical outputs and decisions are immutable; later evidence may mark them
  potentially stale but never rewrites history.
- Locator-valid, quoted-value-checked, calculation-reproduced and
  human-confirmed interpretation are distinct verification states.
- A citation proves where supporting material was located, not that the
  conclusion is correct.
- Prompt-injection defenses are independent of citation validation.
- Every provider transmission discloses the selected sources and applicable
  retention limitations.

## Usage and cost

Do not pretend that nominal internal budget units are currency. Until provider
cost accounting is implemented, the UI may show tokens, calls and configured
limits but must label unknown monetary estimates as unknown.

Future cost controls should support estimation, warning thresholds, approval to
exceed, organization/deal limits, model routing and targeted reassessment. Never
silently downgrade analytical quality on a consequential task merely to save
cost.
