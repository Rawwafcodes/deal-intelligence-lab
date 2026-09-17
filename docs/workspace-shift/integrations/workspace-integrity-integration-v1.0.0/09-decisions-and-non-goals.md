# Decisions and non-goals

## Established by this integration proposal

### I01 — Workspace remains the product centre

Integrity Review is a capability family inside Mandates, not a replacement product hierarchy.

### I02 — First implementation occurs at M14.2

Adopt the design now. Finish M13 first. The first coded integration is Work-product Integrity Review.

### I03 — One shared findings workflow

Integrity findings, human findings and existing reconciliation findings share one review/resolution system with origin labels and lineage.

### I04 — Submitted versions before live editing

Review immutable work-product versions first. A native collaborative editor is deferred until evidence proves it necessary.

### I05 — Assertion snapshots before universal claim store

Persist only material assertions used in real reviews. Promote them into a reusable ledger after validation.

### I06 — Benchmark infrastructure choices

NLI, pgvector, graph storage, commercial parsing and CRDTs are candidates, not predetermined requirements.

### I07 — Senior visibility without employee scoring

Authorized leaders may inspect work, versions, review state and decisions. No AI performance scoring or analyst leaderboard.

### I08 — Triggered review stays a mandate

Event-triggered work remains visible, authorized, budgeted and auditable through the mandate runtime.

## Non-goals

- Rebuilding Milestones 1–13.
- Building another data room.
- Replacing Slack/Teams.
- Replacing Word, Excel or PowerPoint.
- Autonomous delivery approval.
- Universal ontology construction.
- Hidden surveillance.
- Unbounded continuous inference.
- Premature cloud or production deployment.

## Open questions to resolve with evidence

- Which assertions recur enough to justify a persistent ledger?
- What proportion of valuable defects is truly deterministic?
- Does retrieval improve over native long-context reasoning on the actual corpus?
- Is a specialized NLI model useful after strong-model filtering?
- How should bilingual aliases and translations be human-confirmed?
- At what point in the workflow do users want challenges: submission, review or live drafting?
- Which Integrity Review events should require approval before execution?

