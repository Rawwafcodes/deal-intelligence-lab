# Reconciliation capability contract (Task 14.1)

Formalizes the `reconciliation.cross_format` mandate capability - real
and in production use since Task 12.3 - against docs/04-mandate-
engine.md's own capability-boundary requirement: "Register each
capability with: name/version; input schema; output schema; allowed
formats; side-effect class; permission check; executor; error/retry
behavior; source handling; usage accounting." Nothing in this document
changes the capability's real behavior; it pins down, in one place, a
contract that previously existed only informally, split across
`mandates.py`, `cross_format_analysis.py`, and `cross_format_analyses.py`.
Where this document and the code disagree, the code is authoritative -
this is a description of what already exists and is tested, not a new
promise.

Gates M14.2 (Work-product Integrity Review): docs/08-roadmap.md's own
line for that task reads "Do not implement before M13 is accepted and
this task's own 14.1 is done." This document, plus the schema fields it
describes now being real fields on `CapabilityDescriptor` (see below),
is what "14.1 done" means.

## Identity

- **Name**: `reconciliation.cross_format`
- **Version**: `"1"` (the `CapabilityDescriptor.version` field; bump
  whenever the input/output schema or evidence semantics change in a way
  that could invalidate a plan proposed against the prior version).
  Distinct from `cross_format_analysis.MANDATE_VERSION` (currently also
  `"1"`), which versions the exact prompt text (`MANDATE`/
  `STRUCTURE_INSTRUCTIONS`) sent to the model - the two version numbers
  move independently.
- **Side-effect class**: `external_paid_call` (a real, billed Anthropic
  API request per invocation).
- **Permission check**: `lambda project_id: True` today - every project
  member may run this capability; a future per-role or per-budget-policy
  restriction (docs/06's "Create mandate: Within granted capability/
  budget") would tighten this function, not the contract shape.
- **Executor**: `mandates._reconciliation_executor` - a thin adapter, not
  a second implementation. It calls the same two functions the
  pre-existing, non-mandate `/api/projects/<id>/reconciliation` route
  already calls: `cross_format_analysis.run_cross_format_analysis` (the
  real, paid model call) then `cross_format_analyses.
  create_cross_format_analysis` (the persisted audit record), and the
  same `workspaces.get_or_create_workspace` the static page's own "Open
  deal workspace" link uses - so a mandate-driven reconciliation and a
  manually-triggered one produce identical, indistinguishable records
  and land in the identical shared findings register. There is no
  mandate-only finding silo.

## Input schema

Enforced (not merely documented) as `CapabilityDescriptor.input_schema`,
checked by `mandates._validate_against_schema` both at propose time
(inside `_default_input_for_stage`, before a plan can even be approved)
and is available for inspection by any future caller (e.g. a planner)
via `mandates.get_capability("reconciliation.cross_format").input_schema`:

```json
{
  "type": "object",
  "required": ["document_ids"],
  "properties": {
    "document_ids": {"type": "array", "items": {"type": "string"}, "minItems": 1},
    "pinned_versions": {"type": "object"}
  }
}
```

- `document_ids`: at least one document id, supplied explicitly - either
  by a human at propose time (`stage_inputs`) or by Task 12.4's
  `propose_plan_llm`, which derives a selection from a real model call
  and passes it through the exact same parameter. There is no separate,
  laxer path for a model-proposed selection.
- `pinned_versions`: populated automatically by `_default_input_for_stage`
  (never supplied by the caller) - each `document_id` is pinned to its
  *current* `DocumentVersion` at the moment the plan is proposed
  (docs/03's "Run / Attempt / InputManifest... pinned sources"). The
  object's value shape (`document_id -> version_id`) is intentionally
  outside this schema's own type-checking (see `_validate_against_schema`'s
  own docstring) - it is enforced instead by real document lookups, both
  at propose time and, independently, by the executor immediately before
  the paid call (see "Version pinning" under Limitations).
- A stage input that is missing `document_ids`, supplies an empty list,
  or supplies a non-string id is rejected with `PlanValidationError`
  before a run is ever created - proven by `tests/test_mandates.py`'s
  `CapabilityContractTests` and `ReconciliationCapabilityTests` classes.

Beyond the schema itself, `document_ids` are further constrained by
`cross_format_analysis.validate_selection` (called by the executor
immediately before the paid call - see "Supported formats" and
"Limitations" below): a valid selection needs at least one PDF and at
least one Excel workbook, not merely "at least one document of any kind."

## Output schema

```json
{
  "type": "object",
  "required": [
    "cross_format_analysis_id", "workspace_id", "workspace_created",
    "finding_count", "model"
  ],
  "properties": {
    "cross_format_analysis_id": {"type": "string"},
    "workspace_id": {"type": "string"},
    "workspace_created": {"type": "boolean"},
    "finding_count": {"type": "number"},
    "model": {"type": "string"}
  }
}
```

The executor's real return value also includes `input_tokens`/
`output_tokens` (each `int | None` - `None` only if the provider
response carried no usage block, which does not happen on a successful
call) as unenforced bonus fields, not part of the pinned contract.
Enforced by `mandates._run_stages` immediately after every invocation of
this executor - a return value that does not match this schema fails the
attempt and the run exactly like any other executor exception (see
`tests/test_mandates.py`'s `test_output_that_violates_its_own_declared_
schema_fails_the_run`, proven against a deliberately non-conforming test
capability). This is a genuine safety property: a future edit to
`_reconciliation_executor` that accidentally drops a field the rest of
the app depends on (e.g. `workspace_id`, which `_run_stages`'s own
attempt record and any future capability that reads a prior stage's
output would need) fails loudly at the exact point of drift, not
silently downstream.

## Evidence semantics

- **PDFs**: sent as inline base64 `document` content blocks with
  Anthropic's native `citations: {"enabled": true}` feature turned on -
  the same mechanism `pdf_inspection.py`/`cross_document_analysis.py`
  already use. A PDF-sourced finding field carries a real, provider-
  verified citation span, not a page number Claude typed from memory.
- **Excel workbooks**: no native citation feature exists for spreadsheets,
  so this capability reuses `xlsx_inspection.py`'s citation *convention*:
  Claude is instructed to write `('Workbook N'!'Sheet Name'!CellRef
  [value|formula|label])` inline in its own reply, using an app-assigned,
  stable "Workbook N" label (not the filename or sheet name) so two
  workbooks that happen to share a sheet name or a similar filename can
  never be confused. Every such citation is mechanically checked against
  the real workbook's own structure after the fact - a citation that does
  not resolve to a real cell is marked as not resolving, never silently
  accepted as true.
- **Cross-source claims**: the model prompt (`cross_format_analysis.
  MANDATE`) explicitly requires that "a finding alleging a cross-source
  conflict must cite evidence from every side it compares" and forbids
  claiming two values conflict "without having examined both sources
  yourself" - evidence completeness is a prompt-level requirement, not
  merely descriptive.
- **Uncertainty is a required, explicit field per finding** (`**Uncertainty:**
  fully supported by citations | partially supported | uncited`), not an
  inferred property - a finding missing a citation on either side must
  say so in this field rather than presenting as fully grounded.

## Supported formats

Enforced by `cross_format_analysis.validate_selection`, called by the
executor immediately before the paid call, and declared on the
capability descriptor itself as `allowed_source_formats = (".pdf",
".xlsx", ".xls")`:

- PDF (`.pdf`)
- Excel workbooks (`.xlsx`, `.xls`)

No other document type (`.docx`, `.pptx`, `.txt`, image formats) is
accepted by this capability, even though those types are otherwise
valid, storable document types elsewhere in the app
(`documents.ALLOWED_EXTENSIONS`). A selection containing any other type
is rejected outright (`unsupported_type`), not silently dropped from the
run.

A valid run additionally requires **at least one PDF and at least one
Excel workbook** - a selection of only PDFs or only workbooks is
rejected (`missing_pdf`/`missing_excel`); this is a cross-format
reconciliation capability specifically, not a general document analyzer.

## Outputs

- **`CrossFormatAnalysis` record** (`cross_format_analyses.py`): the full
  audit trail of one invocation - selected document ids/filenames/
  checksums for both PDFs and workbooks, success/error status, whether
  the request was actually transmitted, wall-clock analysis time, the
  real model used, `MANDATE_VERSION`, stop reason, real token usage, the
  raw response segments (including native citation spans), tool-call
  trace, and per-workbook Files API cleanup/verification outcomes.
  Persisted regardless of success or failure - a failed run's own record
  of what was attempted and why it failed is never discarded.
- **Workspace and findings**: `workspaces.get_or_create_workspace`
  materializes (or reuses) one workspace per `CrossFormatAnalysis`;
  `evaluations.extract_findings` parses the model's own structured-
  markdown reply into individual findings, each carrying a
  **classification** (`cross-source conflict | unsupported model
  assumption | missing evidence | calculation or formula concern |
  definition/methodology mismatch | timing or period mismatch |
  confirmed consistency | unable to reconcile`), a **severity**
  (`critical | high | medium | low | informational` -
  `workspaces._SEVERITY_RANK`'s own ordering), and a resolution status
  (`open` by default, tracked and changed only by real human decisions -
  `workspaces.py`'s `resolution_status` column). Findings land in the
  one shared findings register every other reconciliation path (the
  pre-existing non-mandate route) already writes to - there is no
  mandate-only copy.
- **Capability's own return value**: see "Output schema" above - the ids
  needed to look up the full record and workspace, plus a finding count
  and the real model used, for the Attempt record and any composition
  that reads a stage's own output.

## Error and retry behavior

No automatic retry of any kind. A failed provider call (any of the
taxonomy in `cross_format_analysis._ERROR_MESSAGES` - missing/invalid
API key, insufficient credit, rate limit, network error, model
unavailable, encrypted/malformed/invalid PDF, upload failure, repeated
pause without finishing, refusal, truncated response, empty response, or
an unexpected error) fails the Attempt and the Run outright
(`RuntimeError` raised from the executor, caught by `_run_stages`
exactly like any other executor exception) - the human must re-propose
or re-run explicitly; nothing in this capability silently retries a
paid call. The one exception is Anthropic's own `pause_turn` mechanism
during a single logical analysis (code execution can span more than one
turn) - `_run_cross_format_analysis` continues that *same* in-flight
turn up to `MAX_PAUSE_CONTINUATIONS` (5) times before giving up as
`still_paused`; this is continuing one request, not retrying a failed
one.

## Source handling

Every `document_id` is independently re-verified against the real,
current project state at two separate points, never trusted from an
earlier step:
1. **At propose time** (`_default_input_for_stage`): each id must resolve
   to a real `Document` in this project (`PlanValidationError` if not),
   and its *current* `DocumentVersion` is pinned into the plan.
2. **At execution time** (`_reconciliation_executor`, immediately before
   the paid call): each id is re-fetched; a document deleted since
   approval raises `ReconciliationInputError`, and a document whose
   *current* version no longer matches the plan's pinned version also
   raises `ReconciliationInputError` (an approved plan is never silently
   executed against a source that has changed since approval).
Original PDF/workbook bytes are sent to the provider unmodified - no
mandatory extraction funnel - matching docs/04's "Preserve original PDF/
workbook paths to the provider where supported."

## Usage accounting

`unit_cost=1.0` on the `CapabilityDescriptor` - a nominal, non-dollar
number the real, enforced Task 12.2 budget ledger checks a Run's
`budget_limit` against before this capability is ever invoked (see
`tests/test_mandates.py`'s `test_budget_exceeded_blocks_the_paid_call`).
Real dollar-cost accounting from actual token usage is explicitly out of
this contract's scope (12.4/AI-integration territory) - the mechanism
that would enforce a real-dollar ceiling is already real; the number fed
into it today is not yet cost-calibrated. Real token usage
(`input_tokens`/`output_tokens`) is recorded on every `CrossFormatAnalysis`
record regardless.

## Limitations

- **App-side sanity ceilings, not provider limits**: at most 40 PDF
  documents and 20 Excel workbooks per run (`MAX_PDF_DOCUMENTS`/
  `MAX_EXCEL_DOCUMENTS`, both raisable via environment variables) - these
  exist to catch a pathological selection, not because Anthropic itself
  imposes a document-count limit.
- **Byte ceilings**: combined PDF bytes are capped by Anthropic's own
  32 MB whole-request limit (checked locally before ever contacting the
  API); each Excel workbook is capped individually by the Files API's
  own size limit.
- **No OCR/scanned-PDF distinction**: an encrypted or malformed PDF is
  rejected outright (`encrypted_pdf`/`malformed_pdf`); a scanned,
  image-only PDF that parses as valid is not specially detected or
  flagged - if Claude cannot extract meaningful text from it, that
  shows up only as a gap in the model's own "Analysis Limitations"
  section of its reply, not as a distinct app-level error.
- **Model judgment, not deterministic reconciliation**: every finding is
  the model's own interpretation of the sources it was given, explicitly
  distinguishing "a fact stated in a source" from "inference," but this
  is not a deterministic, formula-verified reconciliation engine -
  a human review step is what turns a candidate finding into an accepted
  one (the exact hook Task 13.2's review lifecycle and reconciliation-
  with-review template already provide).
- **No version-change/staleness awareness yet**: the version-pinning
  described above prevents an *approved plan* from silently running
  against changed sources, but there is no mechanism yet for detecting
  that a *finding already accepted* has become stale because one of its
  source documents gained a new version afterward - that is M15's own
  scope (15.1 version dependency tracking / "potentially stale" badges),
  not this capability's.
- **Files API cleanup is best-effort per workbook**, not a guarantee -
  each upload gets an independent deletion attempt and its outcome is
  recorded, but a deletion failure does not fail the run; see
  `xlsx_inspection.py`'s own module docstring for exactly what "cleanup
  succeeded" does and does not imply about Anthropic's broader data
  retention.
- **No partial-selection guidance**: if some but not all selected
  documents are unreadable (e.g. one workbook exceeds the size cap), the
  entire selection is rejected up front (`validate_selection`) rather
  than proceeding with a reduced set - the caller must fix the selection
  and re-propose, not expect the capability to silently drop the
  offending file.
- **English-language, transaction-shaped prompt**: the mandate prompt
  (`cross_format_analysis.MANDATE`) is written for M&A-style diligence
  reconciliation specifically ("valuation, consideration, financing,
  profitability, risk, negotiations or diligence") - it is not a general-
  purpose document-comparison capability, and using it outside that
  framing is unsupported.

## What this task did not change

No code behavior changed as a result of writing this document. The
`CapabilityDescriptor.input_schema`/`output_schema`/`allowed_source_formats`
fields (Task 14.1) are a real, enforced restatement of checks that
already existed, scattered, before this task - see the task's own
completion evidence (`tasks/14.1-formalize-reconciliation-contract.md`)
for exactly what was refactored versus newly added. `MANDATE_VERSION`
and the capability's own `version` field remain `"1"` - nothing about the
prompt, the finding taxonomy, or the supported formats changed.
