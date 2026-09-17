# Existing baseline: evidence, not promises

## Provenance boundary
Application code is not present in this handoff. All implementation descriptions below
come from founder-supplied completion reports and M10 inventory. They were not
independently rerun by the author of this package. Task 000 must reconcile them.

| Milestone | Reported asset | Intended reuse |
| --- | --- | --- |
| 1 | Python local project app, SQLite persistence | Extend Project into deal context |
| 2 | Original uploads, checksums, scoped download/storage | Version and permission the sources |
| 3 | Anthropic connection/error handling | Provider adapter and connection checks |
| 4 | Native PDF inspection/citations | Evidence-reading capability |
| 5 | Multi-PDF review | Existing analysis adapter |
| 6 | Excel via Files API/code execution, citation checks, cleanup | Workbook capability |
| 7 | Cross-format PDF+Excel reconciliation | First executable mandate template |
| 8 | Locked answer keys, blind runs, human scoring | Isolated evaluation harness |
| 9 | Findings review, duplicates, requests, memo approvals, exports, audit | Shared human workflow |

## Reported application layout
Local location on founder's Mac: ~/Projects/deal-intelligence-lab.
Reported database: data/deal_lab.db. Originals outside code: ~/DealLabData/projects/.
Python server.py, static/ UI, venv; React/Vite frontend/ exists but was unintegrated.
Do not assume these paths or files still match. Never interpret these Mac paths as
paths in an agent's remote environment.

Modules reportedly include store.py, documents.py, ai_client.py, anthropic_errors.py,
pdf_inspection.py, xlsx_inspection.py, cross_document_analysis.py,
cross_format_analysis.py, evaluations.py, workspaces.py, workspace_exports.py,
answer_keys.py, validation_cases.py and validation_runs.py.

## Historical verification
M9 report: 334 tests. Later supplied inventory: 333 at committed fd59122, mypy clean
on 43 files; extra regression was in a dirty working tree. Both are historical.
The inventory listed uncommitted analysis files and unused frontend work.
Never overwrite or claim those edits were integrated.

A genuine financing-room run reportedly produced 33 findings; human scoring was not
demonstrated complete. This is promising evidence, not proof of general accuracy.
The earlier synthetic tests prove mechanics, not commercial diligence validity.

## Known gaps to recheck
- Position-based finding IDs and extraction on read.
- No actual identity/membership model; owner names are plain text.
- No proper document-version lineage.
- Inline long-running requests and weak duplicate/cost controls.
- Missing frontend regressions for severity-null and request-summary refresh.
- Findings expansion accessibility issue.
- Exported free text may be interpreted as spreadsheet formulas.
- Test/reviewer artifacts remain in a real workspace; do not delete without approval.

## Reuse policy
Wrap analytical modules before rewriting them. Introduce an additive run registry
pointing to legacy records. Preserve old URLs, citations, reviews and result content.
Inspect each proposed adapter against actual code. New prompt semantics still require
evaluation even if the transport is unchanged.
