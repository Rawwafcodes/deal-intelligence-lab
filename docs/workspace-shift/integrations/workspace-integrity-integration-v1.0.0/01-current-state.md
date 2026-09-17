# Current-state baseline

This is a compact summary of the latest supplied `STATUS.md`. It must be re-verified against the live repository before adoption.

## Completed foundation

### Milestones 1–9

The application already has projects, document upload and persistence, Anthropic connectivity, native PDF inspection, multi-PDF analysis, spreadsheet analysis, cross-format reconciliation, a human-scored Validation Lab and a decision-ready findings workspace.

### M11 — collaborative foundation

Reported complete:

- Local PostgreSQL cutover.
- Organizations, users, organization memberships, deal memberships and server-side authorization.
- Development identities for local multi-user proof.
- Immutable document versions.
- Stable UUIDs and immutable snapshots for AI findings.
- Optimistic revision conflict handling for findings.
- Versioned deal briefs.
- Workstreams and assignments.

### M12 — reusable mandate runtime

Reported complete:

- Mandate, plan revision, run and attempt contracts.
- Durable background execution, recovery, cancellation and budget ledger.
- Existing cross-format reconciliation registered through a thin adapter.
- Gate A passed through real execution.
- LLM planning over registered capabilities with server-side validation and human approval.
- A second configured flow combining reconciliation with a human review checkpoint, without a new capability or schema.

### M13.1 — team execution

Reported complete:

- Assignable tasks.
- Comments.
- Work products.
- Immutable submission versions.
- Submission automatically advances the task to `submitted`.

## Immediate next task

M13.2: version-specific review, return for revision, resubmission and approval.

## Important existing boundaries

- Findings are already stable, immutable observation snapshots with separate human workflow state.
- Work products and source documents are different domain objects and should remain different.
- A submission version is the correct immutable unit for Integrity Review.
- The mandate runtime is the correct execution mechanism for Integrity Review.
- The existing shared findings register is the correct destination for accepted Integrity Review output.
- The Validation Lab is the correct evaluation mechanism; a second grader must not be built.

## Historical-status warning

The supplied status file is append-only and contains older “not completed” statements that have since been superseded by later dated completion entries. Adoption must follow the latest header and latest dated evidence, not isolated historical paragraphs.

