# Integration architecture

## Reuse map

| Need | Existing foundation | Integration rule |
|---|---|---|
| Source evidence | Document and DocumentVersion | Select immutable versions by project-scoped ID |
| Analyst work | Task, WorkProduct, SubmissionVersion | Review one immutable submission version at a time |
| Deal context | BriefVersion and Workstream | Pin the versions/context used by a run |
| Execution | Mandate, PlanRevision, Run, Attempt | Register a bounded capability; do not create a parallel worker |
| Human control | Plan approval and human checkpoint | Preserve approval gates and record review decisions |
| Outputs | Shared workspace findings | Publish through the existing register with origin and lineage |
| Evaluation | Validation Lab | Extend its scoring vocabulary only where necessary |
| Oversight | Planned Workspace/Deal Overview | Show decision exposure, not employee scores |
| Change | Document/submission versions | Add dependencies and stale markers in M15 |

## First capability

Proposed capability key:

```text
integrity.review_work_product
```

The capability receives identifiers, not client paths or arbitrary provider handles:

- `project_id`
- `submission_version_id`
- selected `document_version_ids`
- selected peer `submission_version_ids`
- pinned `brief_version_id`
- optional `workstream_id`
- review scope
- budget limits

The server independently verifies project membership, authorization, version existence, source type, uniqueness and scope before execution.

## First pipeline

1. **Scope check** — verify exact versions and the requested comparison set.
2. **Assertion mapping** — identify material factual, quantitative and decision-driving statements in the submission.
3. **Evidence resolution** — associate assertions with source evidence, explicit assumptions or named human judgment.
4. **Deterministic checks** — perform only checks that current inputs make mechanically reliable.
5. **Semantic review** — reason about remaining cross-source and cross-submission conflicts.
6. **Human checkpoint** — reviewer accepts, rejects, edits or links proposed challenges.
7. **Publish** — accepted outputs enter the existing findings register with full run/version lineage.

The planner may propose this pipeline, but it may not authorize new sources, expand access or skip the human publication checkpoint.

## Assertion snapshots before a universal claim store

M14.2 may persist material assertion snapshots used by a review. This is not yet a universal canonical claim store.

Suggested conceptual fields:

- Stable UUID.
- Exact original assertion text.
- Submission version and author.
- Evidence source version and locator.
- Verbatim source text or verified cell evidence.
- Optional resolved entity.
- Optional period, unit, currency and typed value.
- Modality: fact, estimate, forecast, assumption, management assertion, vendor assertion or human judgment.
- Extraction/provider/prompt version.
- Verification status.
- Relationships to findings and review decisions.

Fields should remain optional where the source does not support confident normalization. Preserve the original language. Never manufacture structure merely to satisfy the schema.

## Claims and findings are different

A claim/assertion is evidential state. A finding is a review conclusion about one or more claims.

Example assertions:

- Project cost is SAR 102.358 million.
- Initial DCF outflow is SAR 91.750 million.
- Working capital is SAR 10.608 million.

Example finding:

- Working capital is excluded from the initial investment outflow.

Do not migrate current findings into claims or treat one as a substitute for the other.

## Deterministic versus semantic

Deterministic checks are preferred when their prerequisites are verified. Examples include recomputable arithmetic, exact version references and normalized currency/unit mismatches.

However, entity resolution, time-period equivalence, accounting definitions and comparator suitability can remain uncertain. A rule is not “zero false positive” merely because its final operation is deterministic.

Semantic conflicts remain model-assisted challenges with uncertainty and human review.

## Deferred infrastructure

Do not add the following until benchmark evidence requires them:

- pgvector or a dedicated graph store.
- A separate NLI model.
- A commercial parsing service replacing provider-native document handling.
- CRDT/Yjs collaborative editing.
- Per-keystroke model evaluation.

PostgreSQL is already available and can host later evidence tables. That does not itself justify building them early.

