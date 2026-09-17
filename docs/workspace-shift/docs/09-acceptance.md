# Acceptance and evaluation

## Three evidence levels
1. Fixture tests prove mechanics and error paths.
2. Authorized live provider tests prove actual integration and citation behavior.
3. Independent real-case human scoring evaluates analytical usefulness and accuracy.
Do not substitute one for another. Existing high-quality reports do not establish
generalized accuracy or full data-room coverage.

## Required scenarios
- T01: original download equals upload hash; old versions remain citeable.
- T02: parser output reordering cannot move human decisions to another finding.
- T03: two browser sessions have distinct actors and correctly refreshed shared records.
- T04: analyst cannot approve final package; revoked user loses API/download/tool access.
- T05: external viewer cannot obtain internal notes via overview/search/export/citation.
- T06: simultaneous edits cause an explicit revision conflict.
- T07: fixture planner proposes unknown tool/source: server rejects before execution.
- T08: adding a second template using existing capabilities changes configuration,
  not routes/pages/runtime branches. New capability exceptions documented.
- T09: browser closes while job runs; reconnect returns persistent state.
- T10: worker fails after a request was sent: outcome unknown, no automatic paid replay.
- T11: cancel stops future steps; cleanup and in-flight uncertainty visible.
- T12: changed scope/budget requires new approval; injected source cannot approve itself.
- T13: requests, findings and draft artifacts retain source/run/actor lineage.
- T14: approved submission v1 survives v2 draft; v1 approval never transfers silently.
- T15: new evidence marks potentially affected conclusions without rewriting them.
- T16: validation secret marker absent from every AI path, request, upload and log.
- T17: exported free text remains literal; HTML/model output cannot execute.
- T18: keyboard navigation, Arabic/English references, narrow layout and error recovery.
- T19: plain factual locator check never shown as proof of commercial correctness.
- T20: unsupported/unreadable sources and partial completion are explicit.

## Live analytical quality
Before each paid test record authorization, selected files, purpose and spending bound.
Use locked private expected issues/must-not-claims prepared independently.
Review findings for correctness, evidence support, calculation reproducibility, severity,
useful next action and missed issues. Report N/M with unreviewed items explicit.
Distinguish retrospective comparison from genuinely blind scoring.
Synthetic issues are integration fixtures, not commercial validation.

## Completion report
Include exact app commit and dirty state, commands/results, browser checks, migration
evidence, authorized usage, raw-evidence location (private), limitations and next task.
Keep secrets and real deal documents out of this specification repository.
