# Deal Intelligence Lab

A local app for keeping track of your M&A deal projects. Create a project,
upload the original deal documents, and come back to them any time —
everything is saved on your own computer.

This is an early milestone: it handles projects, original-document
storage, and a basic AI connection check. Document analysis by AI comes
in a later step.

## Requirements

- Python 3 (already installed on this Mac — nothing else to install)

## One-time setup

This app now uses two small add-on packages (to talk to the Claude API),
so it runs inside a Python "virtual environment" — an isolated folder of
packages that doesn't affect anything else on your computer. Set it up
once:

1. Open the Terminal app.
2. Go to this folder:
   ```
   cd ~/Projects/deal-intelligence-lab
   ```
3. Create the virtual environment:
   ```
   python3 -m venv venv
   ```
4. Activate it and install the packages:
   ```
   source venv/bin/activate
   pip install -r requirements.txt
   ```

## How to run it

Every time you want to run the app:

1. Open the Terminal app.
2. Go to this folder and activate the virtual environment:
   ```
   cd ~/Projects/deal-intelligence-lab
   source venv/bin/activate
   ```
3. Start the app:
   ```
   python3 server.py
   ```
4. Open your browser to:
   ```
   http://localhost:8765
   ```

Leave the Terminal window open while you use the app. To stop the app,
click back in that Terminal window and press `Ctrl+C`.

## Your data

Your projects (name, description) are saved in `data/deal_lab.db` inside
this folder. It stays there between restarts.

**Uploaded documents are stored separately**, outside this app folder, at:

```
~/DealLabData/projects/<project-id>/originals
```

This keeps confidential deal documents out of the application's code
folder entirely (and out of git, if you ever put this folder under
version control). Don't delete `~/DealLabData` unless you want to erase
every document you've uploaded.

### Uploading documents

On a project's page, use **Choose files** to upload one or more files at
once, or **Choose a folder** (where your browser supports it) to upload
an entire folder, preserving its internal structure. Each uploaded file
is stored exactly as-is (byte-for-byte) and listed in an inventory with
its file type, size, checksum, and upload time. You can download the
original file back at any time, or remove it (after confirming).

Supported file types: PDF, DOCX, XLSX, XLS, PPTX, TXT, and common image
formats (PNG, JPG, GIF, BMP, TIFF, WEBP). Uploading the exact same file
twice to a project is detected and skipped rather than stored again.

By default, a single upload request is limited to 500 MB total and 200
files. To change these, set environment variables before starting the
app, for example:

```
DEAL_LAB_MAX_UPLOAD_BYTES=1000000000 DEAL_LAB_MAX_FILES_PER_UPLOAD=500 python3 server.py
```

You can also change where documents are stored with `DEAL_LAB_DATA_DIR`,
for example:

```
DEAL_LAB_DATA_DIR=/path/to/somewhere/else python3 server.py
```

## Inspecting a PDF with Claude

On a project's page, PDF documents get an **Inspect with Claude** action.
Clicking it asks you to confirm before sending anything, since this is the
one action in the app that transmits a document outside your computer.
After you confirm:

- The **original PDF file, and only that file** (no other project
  documents), is sent directly to Claude using Anthropic's native PDF
  support — the app never extracts, OCRs, converts, or otherwise
  preprocesses the file itself.
- Claude reads the PDF and identifies what the document is, its principal
  subjects, and its material factual statements, citing the source page
  for every factual statement using Anthropic's native citation feature.
  Citations link straight back to the original PDF, opened at that page.
- You land on a results page showing the analysis, with a clearly marked
  "(uncited)" tag on any material statement Claude could not tie to a
  page — never a fabricated page reference.
- Every inspection (its outcome, the model used, token usage, stop
  reason, and how long it took) is recorded in `data/deal_lab.db` so
  there's an audit trail of what was sent and when.

Only PDF files are supported in this milestone. Files above ~23 MB, PDFs
that are password-protected or encrypted, and malformed files are
rejected with a clear error before or after the request, instead of
being silently mishandled.

**Design note:** the PDF is sent inline (base64) in the request rather
than uploaded to Anthropic's Files API first, since each inspection is a
one-off analysis of a single document — this avoids creating a
*persistent* copy on Anthropic's side that the app would need to track
or delete. It is not a claim of zero data retention: like any API call,
the request itself remains subject to Anthropic's standard API data
retention and privacy terms.

## Comparing several PDFs with Claude

On a project's page, the **Run cross-document analysis** action lets you
select two or more uploaded PDFs — say, an NDA and a term sheet for the
same deal — and have Claude read them together as parts of one
transaction, rather than one at a time.

- A picker lists every PDF in the project with its size and a running
  total against the combined size limit, so you can see before
  confirming whether the selection fits in one request.
- A second, explicit step lists every filename that will be sent before
  anything is transmitted. No other project documents are included.
- Claude builds a connected understanding of the documents, then reports
  material facts, potential inconsistencies, unsupported cross-document
  claims, missing information, ambiguities, and recommended follow-up
  questions — deliberately avoiding the assumption that every difference
  between documents is a contradiction (a date, scope, or definitions
  mismatch might explain it).
- Each finding (an inconsistency or an unsupported claim) is broken out
  with a title, classification, severity, explanation, commercial
  relevance, an explicit uncertainty note, and a recommended action. A
  cross-document inconsistency is only presented as grounded once every
  side of it is cited — citations always link back to the exact original
  PDF and page they came from, using Anthropic's native citation
  metadata (never a reference the app invented).
- Every run is recorded as an immutable entry in `data/deal_lab.db`: the
  exact document IDs and checksums selected, the model, the review
  mandate version, token usage, stop reason, and timing — so there is a
  permanent record of exactly what was sent and what came back, even if
  a document is later changed or removed from the project.

Like single-document inspection, this sends each selected PDF inline
(base64) rather than through the Files API, and the same 32 MB /
~600-page combined request limits apply — now shared across every
document you select, not just one.

## Inspecting an Excel workbook with Claude

XLSX and XLS documents get their own **Inspect with Claude** action. This
works differently from PDF inspection, because Excel isn't something
Claude can read inline the way it reads a PDF:

- The original workbook is uploaded to Anthropic's **Files API**, then
  handed to Claude inside a **sandboxed code-execution container** (Python,
  with `openpyxl`/`xlrd`/`pandas` pre-installed). Claude opens and queries
  the file itself — this app never extracts, converts, or interprets the
  workbook's contents locally.
- After analysis, the app **deletes the uploaded file from Anthropic** and
  records whether that deletion succeeded. This is not a claim of instant,
  total erasure everywhere: per Anthropic's own documentation, a deleted
  file "may persist in active Messages API calls and associated tool uses"
  already in flight, and — separately from Files API deletion —
  **code-execution container data is retained for up to 30 days** as
  Anthropic's standard retention for that feature. Neither the Files API
  nor code execution is eligible for Zero Data Retention. The results page
  states this plainly rather than implying the file is gone the instant
  deletion is attempted.
- Excel has no native citation feature the way PDFs do, so this app
  defines its own convention and asks Claude to follow it: every
  workbook-specific claim is cited as `('Sheet Name'!B7 [value])` (or
  `[formula]` / `[label]`, and `B7:C10` for a range). After Claude
  responds, the app **independently opens the same original workbook**
  (reading only sheet names and grid bounds — never cell values) and
  checks that every cited sheet and cell/range actually exists, marking
  each citation verified or not. A citation in some other shape is simply
  never treated as one.
- A collapsible **code-execution trace** on the results page shows what
  Claude actually ran (commands and capped output snippets), so the
  process can be reviewed without the app storing full raw spreadsheet
  dumps.

Only `.xlsx` and `.xls` are supported in this milestone (500 MB upload
limit, matching Anthropic's own Files API limit). Encrypted or unreadable
workbooks are reported clearly, and are distinguished from a workbook that
analyzed successfully but whose citations simply couldn't be checked
locally this run (verification and analysis success are tracked and shown
separately, never conflated).

## Reconciling a deal across PDFs and Excel workbooks

On a project's page, the **Reconcile documents** action (under "Cross-format
deal reconciliation") lets you select one or more PDFs together with one or
more Excel workbooks - say, an information memorandum and its financial
model - and have Claude read all of them together as evidence for one
transaction, rather than inspecting each file on its own.

- A picker lists every PDF and Excel document in the project; you must
  select at least one of each before continuing.
- A second, explicit step lists every filename that will be sent before
  anything is transmitted, and explains that PDFs go directly to Claude
  while Excel workbooks are uploaded to Anthropic's Files API for
  sandboxed code execution. No other project documents are included.
- The frontend only ever sends document IDs, never filesystem paths. The
  server independently re-validates the selection: every document must
  belong to the project and actually exist, duplicates are rejected, the
  selection must contain both a PDF and an Excel file, and no unsupported
  file type is allowed through.
- **Both mechanisms run in one analytical context, in a single request**:
  every selected PDF is sent inline using Anthropic's native PDF document
  input with citations enabled (exactly as in single- and cross-document
  PDF inspection), and every selected Excel workbook is uploaded to the
  Files API and handed to Claude as a `container_upload` block alongside
  the sandboxed code-execution tool (exactly as in workbook inspection).
  Claude sees all of it together and is instructed to treat every source as
  evidence for one deal - not to summarize each file separately and merge
  the summaries with hardcoded rules.
- Claude reports an executive conclusion, a review of each source
  (including whether it could be interpreted and any limitations), a set of
  reconciliation findings (title, classification, severity, explanation,
  separate PDF and workbook evidence, commercial/financial relevance,
  uncertainty, and a recommended action), unresolved questions to raise
  with the deal team, and anything it could not read, calculate, verify, or
  reconcile.
- **PDF evidence** uses Anthropic's native citations, exactly as elsewhere
  in this app - they link straight back to the original PDF at the cited
  page. **Excel evidence** uses this app's own citation convention (as in
  workbook inspection), extended so a citation names the exact workbook it
  came from (`'Workbook 1'!'Sheet Name'!B7 [value]`) rather than only a
  sheet and cell - this matters once more than one workbook is selected,
  since two models can easily share a sheet name like "Assumptions". Every
  Excel citation is independently checked against the real workbook's
  structure after the fact and marked verified, not found, or unresolved;
  an Excel citation naming an unrecognized workbook is never guessed at, it
  is simply marked as not resolved. If a finding only has evidence from one
  format, Claude is instructed to say so explicitly (e.g. "No workbook
  evidence located") rather than inventing the other side.
- You land on a dedicated results page. The record is saved to
  `data/deal_lab.db`, so refreshing the page or restarting the app never
  loses a completed reconciliation.

**Provider file cleanup:** every Excel workbook uploaded for a
reconciliation run gets its own delete attempt afterward - on success, and
on every failure path (a provider error, a parsing failure, or an
unexpected exception) - and each workbook's cleanup outcome is recorded and
shown independently, the same way as single-workbook inspection. See
"Inspecting an Excel workbook with Claude" above for what a successful
delete does and does not imply about Anthropic's broader data retention for
the Files API and code execution; the same caveats apply here.

This action does not locally extract PDF text, convert spreadsheets to
CSV/JSON, perform OCR, or use retrieval/embeddings - the app's role is
transport, validation, persistence, and mechanical citation checking; all
semantic understanding and reconciliation is Claude's.

## Validation Lab: blind-testing Claude against a completed deal

Milestone 7 proved this app can produce strong PDF–Excel deal analysis.
The **Validation Lab** (reachable from a project page) exists to answer a
harder question: can Claude reliably find the material issues in a
*completed* deal *without being told what those issues are first*? This
is a evaluation harness, not another analysis feature — it doesn't change
how Claude analyzes anything.

### How blindness is protected

The core rule: a private **answer key** — the issues a human evaluator
already knows are in a deal, prepared independently before the run — must
never influence the analysis under test.

- Answer-key content lives in its own database table, never in the
  documents table, never inside a project's `originals` folder on disk,
  and is never read by any code path that builds a request to Anthropic.
  `validation_runs.py` (the only module that starts a run) only ever
  touches an answer key's *metadata* — its lock timestamp, version number,
  and checksum — never its content.
- **A run cannot start until its answer key is locked.** Locking stamps a
  timestamp and a SHA-256 checksum of the key's exact content and freezes
  it permanently: after that, only a brand-new version (with its own
  checksum) can hold different content — the original locked version and
  its checksum are never overwritten.
- Every validation run records whether it was genuinely blind: locked
  *before* the analysis started (or, for an already-completed analysis you
  attach retrospectively, locked before that analysis was originally run).
  A run attached to an analysis that predates the lock is labeled
  **retrospective** and can never be marked "passed" or "failed" — only
  "incomplete review" or "not a genuinely blind test".
- The app also won't re-display a locked answer key's content to you until
  a run against that exact version has completed — the same discipline a
  human blind reviewer would apply to themselves.
- An automated test (`tests/test_validation_endpoints.py`,
  `test_full_blind_workflow_and_secret_marker_never_leaks`) plants a
  unique secret marker inside a locked answer key and proves it in the
  mocked Anthropic request, the uploaded workbook bytes, application
  stdout/stderr, and the analysis result.

### The workflow

On a project page, **Validation Lab** lets you:

1. Create a validation case: a name, an optional description, and a
   selection of that project's PDFs and Excel workbooks (at least one of
   each).
2. Write a private answer key: expected issues (title, description,
   expected classification and severity, why it's material, known
   source/page/sheet/cell, expected corrected value, evaluator notes), and
   a separate **must-not-claim** list for conclusions that would be false
   or unsupported if Claude stated them (e.g. asserting a relationship the
   documents never establish, or presenting a calculated value as if it
   were a source value).
3. Lock the answer key. You'll see its checksum immediately as
   confirmation; it stays on this computer.
4. Run the normal Milestone 7 cross-format reconciliation — exactly the
   same mandate, model, citation validation, provider-file cleanup, and
   error handling as the plain reconciliation flow, unmodified. You can
   also attach an already-completed analysis from the project instead of
   transmitting a new one (useful for retrospective scoring, and always
   labeled accordingly).
5. Once the run completes, the answer key is revealed and you score it
   yourself: mark each expected issue found completely / partially /
   missed / not applicable and link it to the Claude findings that found
   it; rate each Claude finding correct-and-material / correct-but-
   immaterial / partially correct / unsupported / false / needs a
   specialist; separately check citation accuracy, calculation
   reproducibility, severity appropriateness, and recommended-action
   usefulness; and classify any finding *not* linked to an expected issue
   as a newly verified issue, a valid-but-immaterial observation,
   unsupported, false, or needing further investigation. None of this
   scoring is automatic — no keyword matching, no second LLM grading it.
6. Read the computed metrics (critical/high/overall recall, reviewed-
   finding precision, false positives, citation and calculation accuracy,
   severity agreement, verified unexpected findings) — always shown as
   "N of M", and explicitly marked **provisional** while any finding
   remains unreviewed.
7. Record your own conclusion, material limitations, recommended
   improvements, and a final status: passed / passed with material
   limitations / failed / incomplete human review / not a genuinely blind
   test. A human always sets this — the software never declares a result.

Everything persists in `data/deal_lab.db` (outside git, like every other
audit record in this app) — refreshing or restarting the app never loses
a case, an answer key, a run, or an evaluation.

## Deal Workspace: from a reconciliation into a decision-ready package

Milestone 7 produces a long AI reconciliation report; Milestone 8 proved
Claude's findings are trustworthy in a blind test. Neither is a diligence
*workflow* a human reviewer can actually run a deal through. The **Deal
Workspace** (reachable from a completed reconciliation via "Open deal
workspace") turns one reconciliation into a structured, human-controlled
review: an individual, filterable/sortable record per finding; an
information-request list; and an executive deal memo — all persisted
locally and never requiring another Anthropic call to open or use.

### AI content stays immutable by construction, not convention

`workspaces.py` never copies Claude's finding text into its own tables.
Every AI-origin finding's content (title, classification, severity,
explanation, evidence, citations) is re-derived on every read from the
write-once `cross_format_analyses` record via `evaluations.extract_findings`
— the same parser Milestone 8 already built, reused as-is rather than
re-implemented. What this milestone stores is only the human side:
workflow state per finding (human review status, human-adjusted severity,
resolution status, assigned owner, management response, reviewer notes,
due date), duplicate relationships (with full lineage — canonical finding,
duplicate IDs, who marked it, when — never a destructive merge), human-
added findings (always labeled as such, never presented as AI output),
information requests, and the executive memo.

One workspace exists per analysis (`UNIQUE` constraint on the analysis
id) and is created idempotently — opening an already-open workspace never
re-creates or duplicates its findings, and never contacts Anthropic.

### The executive memo

The initial memo is generated **deterministically** from the current,
human-reviewed workspace state (accepted/partially-accepted findings by
severity, missing-evidence and uncited findings, confirmed consistencies,
recommended actions) — no Anthropic call, no free-text generation, and it
is never silently regenerated over a human's edits afterward. The overall
recommendation defaults to "no conclusion" and is only ever set by a
human; the app never presents an automated investment decision. Approving
the memo records an approver name and timestamp; editing an approved memo
returns it to draft status automatically.

### Exports

- **Findings register** and **information-request list**: native `.xlsx`
  (via `openpyxl`, already a dependency — nothing new added for this).
- **Executive memo** and a **combined decision package** (memo + findings
  register + requests): printer-friendly HTML you save as a PDF through
  the browser's own print dialog.

Every export carries project/analysis/workspace identifiers, an export
timestamp, both the original AI severity and any human-adjusted severity,
review/resolution state, evidence and citation text, whether each finding
is AI-generated or human-added, duplicate relationships, and a disclaimer
that findings require independent professional judgment — and never an
API key, a filesystem path, or raw document bytes.

## AI connection

On the home page, the **AI connection** card has a **Test AI connection**
button. It sends one tiny request to Claude asking it to reply with a
fixed confirmation phrase, and reports whether it worked, which model
responded, and how many tokens were used. It never sends any of your
uploaded documents — it's just a connectivity check.

To use it, you need an Anthropic API key (get one at
[console.anthropic.com](https://console.anthropic.com/)). Set it up
once:

```
cp .env.example .env.local
```

Then open `.env.local` in any text editor and paste your key after
`ANTHROPIC_API_KEY=`. This file is ignored by git and never shared —
only your own computer reads it. Restart the app (`Ctrl+C`, then
`python3 server.py` again) after editing it.

`ANTHROPIC_MODEL` in the same file controls which Claude model is used
for the test; leave it as-is unless you have a reason to change it.

## Running the tests (optional)

If you want to double-check everything still works after any changes
(this uses a stand-in for the AI connection, so it never contacts the
real API or uses any credit):

```
source venv/bin/activate
python3 -m unittest discover -s tests
```
