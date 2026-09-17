# M15 — Change-aware integrity mandates

M15 turns one-shot Integrity Review into an accurate continuing workflow without uncontrolled continuous inference.

## 15.1 Dependency tracking

### Goal

Answer: “Which reviewed work, findings and conclusions may be affected by this new version?”

### Required relationships

- DocumentVersion → assertion/evidence snapshot.
- SubmissionVersion → assertion/evidence snapshot.
- Assertion/evidence snapshot → finding/challenge.
- Finding → review decision/request/memo conclusion.
- SubmissionVersion → approval decision.
- MandateRun → every version it consumed.

### Behavior

When a source or submission receives a new version, do not mutate historical conclusions. Mark dependent current items `potentially_stale` with a reason and the superseding version.

No AI call is required for staleness propagation.

## 15.2 Targeted reassessment

Register or configure a reassessment mandate that receives:

- Superseding version.
- Affected dependencies.
- Prior finding/conclusion snapshots.
- Explicit reviewer scope.

The mandate compares old and new evidence, explains what changed and proposes which items remain valid, change materially or require human reconsideration.

It must preserve the old conclusion and produce a new revision rather than rewriting history.

## 15.3 Trigger policy

Authorized users may configure opt-in triggers such as:

- Submission enters `submitted`.
- Returned work is resubmitted.
- A material source receives a new version.
- A reviewer requests cross-workstream review.
- A decision package is prepared for approval.

A trigger creates a normal visible mandate and plan/run lineage. It has:

- Owner.
- Scope.
- Budget.
- Selected sources.
- Reason for trigger.
- Human approval policy.
- Downtime/failure visibility.

No hidden background “AI monitoring” may inspect every edit indefinitely.

## M15 completion gate

Prove with a real local flow:

1. An approved submission depends on source version 1.
2. Source version 2 is uploaded.
3. The submission and dependent conclusion become potentially stale without an AI call.
4. A targeted mandate is approved and runs.
5. The result either preserves or revises the conclusion with both histories intact.
6. A lead sees the change and its unresolved decision exposure in Deal Overview.

