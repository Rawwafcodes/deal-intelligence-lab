# Task 000 — Adopt the direction and reconcile actual code
Status: ready for execution inside the actual app repository.
Type: read-only application audit + documentation adoption.
No feature implementation, external writes, paid calls, deployments or data changes.

## Read
Host instructions; package README/AGENTS/STATUS; all docs/ files.
Inspect current Git HEAD/status, code layout, dependencies, frontend assets, actual
analysis/request flow, storage, tests, migrations and security boundaries.
Do not print secrets or examine real document contents unnecessarily.

## Work
1. Adopt package under docs/workspace-shift without overwriting root instructions.
2. Establish app revision and preserve all dirty work.
3. Run safe tests against temporary data if isolated; inspect tests first for live calls.
4. Compare reported M1–9 assets and gaps against actual code.
5. Recommend frontend, local API/session, database and worker choices with reasons.
   No current platform claims without checking primary documentation when relevant.
   Run or specify the smallest safe contention spike needed to decide SQLite/WAL versus
   local Postgres; do not mutate the real database and do not conceal uncertainty if the
   repository cannot support the spike within this read-only task.
6. Map existing modules to initial mandate capabilities and identify unavoidable changes.
   Confirm exactly how the existing `Workspace` model/table is named and used; reserve
   `Organization` for the new tenant boundary and preserve legacy routes/records.
7. Resolve or ask about substantive conflicts with existing instructions.
8. Draft task 11.1 from tasks/TEMPLATE.md with exact target files/tests based on inspection.

## Deliver
- adoption-report.md: code-backed baseline, discrepancies, decisions, risks and reuse map.
- tasks/11.1-closeout.md: bounded executable task.
- A proposed M11.3a database contention/recovery spike if it cannot safely run read-only.
- Updated STATUS.md and decision entries; no fake completion of implementation.
- Tell founder exactly what needs approval.

## Acceptance
No real DB/file mutations; no provider requests; existing work preserved.
Baseline evidence separates committed HEAD from dirty working tree.
First task has finite acceptance checks and rollback.
Stop for founder review.
