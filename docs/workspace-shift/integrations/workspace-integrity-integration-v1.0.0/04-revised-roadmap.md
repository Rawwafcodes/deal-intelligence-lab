# Revised dependency-ordered roadmap

This extends the existing roadmap. It does not invalidate completed tasks or authorize a full milestone at once.

## M13 — Team execution and principal visibility

### 13.1 Assigned tasks, comments and immutable work-product submissions

Reported complete.

### 13.2 Version-specific review lifecycle

Implement review → return for revision → resubmit → approval.

Preserve these future integration hooks without implementing Integrity Review:

- Every review decision identifies the exact SubmissionVersion.
- Returned work may link to existing findings or human review comments.
- Approval is version-specific and cannot silently transfer to a new version.
- Resubmission creates a new immutable version.
- Reviewer, timestamp, decision and rationale are auditable.

### 13.3 Workspace Overview and Deal Overview

Build from real available state. Include submitted/returned/approved work, open material findings, requests, blockers and recent changes. Reserve no fake contradiction metrics.

### 13.4 Two-browser proof

Prove analyst, reviewer, lead and restricted-executive journeys locally.

**M13 outcome:** actual collaborative work and oversight over immutable submissions.

## M14 — Professional intelligence mandates

### 14.1 Formalize existing diligence/reconciliation

Pin its contract, evidence semantics, supported formats, outputs and limitations.

### 14.2 Work-product Integrity Review

Implement the bounded mandate specified in `05-task-14.2-integrity-review.md`.

This is the first coded integration of the friend's contribution.

### 14.3 Decision-package production

Generate only from explicit reviewed, accepted and unresolved state. Preserve human approval.

### 14.4 Readiness assessment

Assess against an explicit checklist/scope. Never claim universal completeness.

**M14 outcome:** the mandate engine is proven across diligence, work-product review and production.

## M15 — Change awareness and triggered integrity

### 15.1 Version dependency tracking

Record which source/submission versions support assertions, findings, approvals and conclusions. Mark potentially stale state without an AI call.

### 15.2 Targeted reassessment mandate

Reassess only affected material with preserved historical conclusions.

### 15.3 Opt-in triggered Integrity Review

Allow approved policies to create visible, scoped mandate runs when a submission or material source version changes.

**M15 outcome:** the workspace can explain what may have become stale and commission bounded reassessment.

## M16 — Continuous workspace integrity

M16 is new and evidence-gated. It is specified in `07-m16-continuous-integrity.md`.

### 16.1 Taxonomy and golden set

### 16.2 Reusable evidence assertion ledger

### 16.3 Proven deterministic reconciler

### 16.4 Semantic cross-workstream review

### 16.5 Incremental/event-triggered evaluation

### 16.6 Inline assistance decision

**M16 outcome:** validated cross-source and cross-author integrity becomes a reusable workspace layer rather than a one-shot report.

## Later — online readiness

Deployment, external access, production identity, residency architecture, certification and provider selection remain separately authorized work. Local completion is not production certification.

