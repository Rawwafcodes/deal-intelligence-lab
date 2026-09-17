# Acceptance and evaluation

## Evaluation principle

An impressive-looking report is not proof. Integrity Review must be scored against known issues and reviewed for false positives.

Reuse the existing Validation Lab. Extend it only when current fixed vocabularies cannot represent Integrity Review outcomes.

## Required metrics

- Recall by defect taxonomy.
- Critical/high recall.
- Reviewed-finding precision.
- False positives by taxonomy.
- Evidence-locator validity.
- Quoted-value or cell-value verification.
- Calculation reproduction accuracy.
- Entity/period normalization accuracy.
- Human-confirmed interpretation rate.
- Recommended-action usefulness.
- Dismissal reason distribution.
- Cost, tokens and elapsed time per run.

Never flatten these into one “accuracy” or “deal health” score.

## Evidence-status language

Keep separate:

- Locator valid.
- Quoted/cell value checked.
- Calculation reproduced.
- Interpretation accepted by a human.

A green citation badge must not imply all four.

## Comparative experiment

Before adopting a specialized NLI/retrieval stack, run the same golden set through:

1. Existing strong-model long-context review.
2. Structured assertion extraction plus strong-model review.
3. Retrieval-gated review.
4. A specialized NLI hybrid only if still justified.

Compare quality, not architectural sophistication.

## Product success test

The first useful proof is:

> A reviewer submits known work, the system finds material issues the reviewer cares about, cites both sides correctly, avoids noisy false positives, and routes the result into a workflow that ends in a better approved deliverable.

## Failure criteria

Pause deeper engine investment if:

- A strong model already finds nearly all known issues and the proposed structured layer adds no meaningful reliability or cost improvement.
- False-positive fatigue makes reviewers bypass the feature.
- Evidence resolution is too unreliable to support challenges.
- Users value one-shot review but not shared/continuous state.
- The deeper engine requires a rigid schema that repeatedly fails on real deal material.

In those cases, retain Integrity Review as a mandate workflow rather than pretending there is a defensible custom contradiction engine.

