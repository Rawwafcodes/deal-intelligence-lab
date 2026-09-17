# Workspace Experience: Navigation, Low-Fidelity Layouts, Click-Through Narratives

Design guidance applied: **`emil-design-eng`** (read in full) — restrained,
purposeful motion only, transitions on `transform`/`opacity` under ~250ms,
`prefers-reduced-motion` honored, no animation on keyboard-driven or
frequently-repeated actions, status conveyed by more than color. **`ui-ux-pro-max`**
— queried directly (not assumed) for navigation-with-many-sections, dense
sortable/filterable tables, and empty/loading/error patterns; results below are
cited inline as *(ui-ux-pro-max)*. One guidance area — RTL/bidirectional text — had
no matching entry in that skill's local database after two query attempts; the
RTL section below is explicitly labeled as general web-standards guidance, not a
skill-database match, per that skill's own instruction not to present a
non-match as if it were one. Neither skill was installed, removed, or modified.

## Navigation structure

Eight sections collapse to six for the first workflow — Submissions and Requests
are real record types (per the data model) but don't need their own top-level
sidebar destination yet; they're reachable from where they're actually used
(a finding's "convert to request" action, a workstream's submission list) until
there's enough volume in either to justify a dedicated list view. This follows
*(ui-ux-pro-max)*'s navigation guidance directly: breadcrumbs are for 3+ levels of
depth, not for flattening everything into the top nav, and an overloaded top-level
nav is exactly the anti-pattern to avoid.

```
Deal: Meridian Robotics — Series A          [Deal lead ▾]  [Your role: Analyst]
┌──────────────────────────────────────────────────────────────────────┐
│ Overview   Documents   Workstreams   Findings   Reports   Activity    │
└──────────────────────────────────────────────────────────────────────┘
```

- **Overview** — deal-lead-oriented by default, but every analyst sees it too
  (scoped to what's relevant to them — see the two click-throughs below).
  Reachable and role-adapted, not role-hidden: an analyst benefits from knowing
  what's blocked deal-wide, just not from a page built as an org chart.
- **Documents** — source documents, versions, upload. Same page serves
  "upload a new source" and "see what version a citation pointed at."
- **Workstreams** — the configurable list (Financial Diligence, Financing Review, …
  whatever the deal lead created); each workstream page holds its tasks, its
  submissions, and the findings/tracked issues scoped to it.
- **Findings** — the one connected register the assignment requires: every
  `FindingObservation` across every run (investigation and submission-review),
  filterable by workstream, source run, status — not a separate page per run.
  Requests and tasks born from a finding are visible inline on that finding, not
  off in a disconnected list.
- **Reports** — the memo (generate → edit → approve, carried over from Milestone 9
  almost unchanged) and exports.
- **Activity** — the audit log, human-readable. Doubles as the "what changed
  recently" surface that feeds the deal-lead overview's "recently changed
  evidence" item.

Active section indicated by underline + color per *(ui-ux-pro-max)*'s
active-state guidance (never color alone — text weight changes too, matching
`static/style.css`'s existing pattern of pairing a color change with a visual
weight change, e.g. its severity badges already do this).

## Low-fidelity layouts

### Deal Overview — deal lead's view

```
┌─ Meridian Robotics — Series A ──────────────────────────── status: Active ─┐
│                                                                              │
│  OPEN MATERIAL ISSUES (4)          UNSUPPORTED, DECISION-DRIVING (2)       │
│  ┌────────────────────────────┐    ┌────────────────────────────────┐     │
│  │ • Contract term conflict    │    │ • Growth-rate assumption has   │     │
│  │   Financial · critical      │    │   no cited source              │     │
│  │ • Rolling contract vs model │    │   Financial · used in memo     │     │
│  │   Financial · high      →   │    │   conclusion                →  │     │
│  └────────────────────────────┘    └────────────────────────────────┘     │
│                                                                              │
│  BLOCKED WORK (1)                   PENDING REVIEW (3)                     │
│  ┌────────────────────────────┐    ┌────────────────────────────────┐     │
│  │ • Financing model — waiting │    │ • Q3 bridge submission          │     │
│  │   on Cap Table v3           │    │ • Legal contract summary        │     │
│  └────────────────────────────┘    └────────────────────────────────┘     │
│                                                                              │
│  RECENTLY CHANGED EVIDENCE          CONCLUSIONS NEEDING REASSESSMENT (1)   │
│  ┌────────────────────────────┐    ┌────────────────────────────────┐     │
│  │ • Cap Table.xlsx → v3       │    │ • Memo v2 (approved 9/12):      │     │
│  │   2 hours ago, by A. Chen   │    │   cited Cap Table v2, now       │     │
│  │   affects 3 findings     →  │    │   superseded — reassess     →   │     │
│  └────────────────────────────┘    └────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────────────────┘
```

Deliberately six work-item lists, zero numbers-without-context, zero per-person
rollups. No "Analyst X: 62% evidencing rate" anywhere — that comparison is exactly
what the milestone instructions forbid ("avoid employee rankings and unvalidated
composite deal health scores"), even though the original pitch's Principal Layer
proposed it as a raw statistic. The same underlying signal (how well-evidenced is
this submission) still shows up, but only *in context, per item* ("this
submission has 2 unsupported claims"), never aggregated into a score that ranks
people against each other.

### Deal Overview — analyst's view

Same page, same six sections, silently scoped: "Open material issues" shows only
the analyst's assigned workstream(s); "Blocked work" shows only their own; a
sidebar note explains the scoping ("Showing your workstreams — [see all]" for
anyone who wants the deal lead's unscoped view and has permission to see it,
i.e. a deal lead viewing as themselves, or a read-only reviewer with deal-wide
visibility). One page, one layout, permission-scoped query — not two different
UIs to build and keep in sync.

### Findings register

```
┌─ Findings ──────────────────────────────────────────────── [+ Add finding] ─┐
│ Search [________]  Workstream[▾] Status[▾] Source-run[▾] Severity[▾]        │
├───────────────────────────────────────────────────────────────────────────┤
│ ▸ Critical  Contract term conflict           Financial   Open      AI      │
│ ▸ High      Rolling-contract revenue basis   Financial   Accepted  AI      │
│ ▸ High      Growth rate unsupported          Financial   Open      Human   │
│ ▸ Medium    Q3 bridge submission — 2 claims  Financing   Review    AI      │
│             unsupported by cited workbook       (submission review run)   │
└───────────────────────────────────────────────────────────────────────────┘
```

Carries over Milestone 9's proven table almost unchanged (sortable headers,
severity/status as text-labeled badges never color-only, expandable row for
evidence — with the `role="button"`-on-`<tr>` accessibility gap from the baseline
inventory fixed as part of the same work, not left in place). New: a
**Source-run** filter and a visible tag distinguishing which mandate produced a
row (investigation vs. submission review) — this is what keeps it "one connected
register" instead of two competing ones, per the assignment's explicit
requirement, while still letting anyone see only what a submission-review run
found if that's what they came for. Rows belonging to a `TrackedIssue` show a
small "linked (3)" indicator instead of appearing three separate times with no
relationship visible.

Table-overflow handling follows *(ui-ux-pro-max)*'s explicit guidance: horizontal
scroll inside its own container, never a page-level breakout — exactly the
pattern `style.css`'s existing `.table-scroll { overflow-x: auto }` already
implements; carried forward unchanged.

### Submission review result (new — doesn't exist in Milestone 9)

```
┌─ Q3 Bridge Financing — submission v2 ───────────────────────────────────────┐
│ Submitted by A. Chen · 2 hours ago · reviewed against: Cap Table v3,        │
│ Term Sheet v1                                                              │
├───────────────────────────────────────────────────────────────────────────┤
│  Claim: "Bridge financing closes within 30 days of term sheet signature"   │
│  ● Supported — Term Sheet v1, p.2, §4.1                                   │
│                                                                             │
│  Claim: "Post-money valuation reflects the Series A discount"              │
│  ● Contradicted — Cap Table v3, Summary!C15 shows a different discount    │
│    basis than assumed                                                     │
│                                                                             │
│  Claim: "Growth continues at the FY25 run rate through the bridge period"  │
│  ● Professional judgment — scenario assumption, not evidence-checkable    │
│                                                                             │
│  Claim: "No other debt-like items exist outside the cap table"             │
│  ● Not assessed — outside the documents selected for this review          │
└───────────────────────────────────────────────────────────────────────────┘
```

Every claim gets exactly one of the five categories from
`02-product-direction.md`, always with either a citation or an explicit "why
not" (outside scope / no source found / judgment call). "Not assessed" is never
silently omitted — the assignment is explicit that missing evidence is not proof
a claim is false, and the UI has to make the difference between "checked, found
nothing" and "didn't check this" impossible to confuse.

## Click-through narratives

### 1. Finding → evidence

Analyst is on the Findings register, clicks a row. It expands in place (no page
navigation, consistent with Milestone 9's existing pattern) showing the
observation's full text, then its citations as badges. Clicking a PDF citation
badge opens that exact document *version* at that exact page in a new tab
(carried over unchanged from Milestone 9's `pdfViewUrl`, which already resolves
through the API rather than trusting a client-supplied path). Clicking an Excel
citation badge shows the resolved sheet/cell reference and its verification
state (✓ verified / ✗ not found / unresolved) inline — no navigation needed,
matching today's behavior exactly.

### 2. Finding → question or task

From the same expanded row, two buttons: **Convert to request** (unchanged from
Milestone 9 — enabled only once the finding is accepted or partially accepted)
and **Create task** (new — assigns follow-up work to a specific person, distinct
from a request because a request implies "ask management," a task implies "one
of us needs to do something," e.g. "re-run the financing model with the
corrected discount rate"). Both keep the originating finding as
`related_finding_or_issue_id`, so the finding's own expanded view later shows
"1 request sent, 1 task assigned" — traceable both directions.

### 3. Submission review

Analyst uploads a document to a workstream's submission slot (a file input, not
a rich editor — per the explicit non-goal, users work in their existing tools and
upload versions). Nothing happens automatically. A **Submit for AI review**
button appears once a submission exists; clicking it opens a confirmation
dialog naming exactly which source-document *versions* will be checked against
(editable — the analyst picks the relevant sources, mirroring Milestone
7/9's existing document-selection-then-confirm pattern) and states plainly that
this sends the submission and the selected sources to Anthropic. Only on
explicit confirmation does the run start — an explicit trigger, never automatic
on upload or on edit, per the assignment's triggered-execution requirement.
Results render as the submission-review layout above and every claim's finding
also appears in the deal's one connected Findings register, tagged with its
originating run.

### 4. How an issue is closed

A `TrackedIssue` (or a lone `FindingObservation` not yet linked to one) carries a
`ReviewDecision` history, rendered as a simple vertical timeline, oldest first:
"Response received (management, 9/10)" → "Evidence received (Cap Table v3,
9/12)" → "Evidence reviewed (A. Chen, 9/12, cites Summary!C15)" → "Closure
approved (Deal lead, 9/12, rationale: 'discount basis now matches term sheet')."
Each entry shows actor, timestamp, and — where relevant — which document/
submission version it relied on. A **Close** action is only available to a deal
lead (see the permission matrix in `05-permissions-and-security.md`) and always
requires a rationale field, matching Milestone 9's existing confirmation-dialog
pattern for consequential actions (delete, approve memo). "Accept residual risk"
is a visibly distinct action from "Close" — a risk can be accepted without
being resolved, and the UI must never conflate the two.

### 5. How an outdated conclusion is identified

When a new `DocumentVersion` is uploaded and confirmed (an explicit trigger —
"approve analysis of a new document version," never automatic), the system
walks every `AnalysisRunInput` row that referenced the *superseded* version,
finds every `FindingObservation` and `MemoVersion` that traced back to one of
those runs, and flags each with a non-destructive badge: "Evidence updated
since this was reviewed." The old `ReviewDecision` and the old approved memo
are never edited or hidden — the timeline in click-through #4 keeps showing
exactly what was decided and when, with the new badge sitting alongside it,
not replacing it. The deal-lead Overview's "Conclusions needing reassessment"
list is this same flag, aggregated. Nothing here claims the old decision *was
wrong* — only that its evidence has moved and a human should look again, exactly
as the assignment specifies.

## Intelligence-behavior contract (investigation vs. submission review)

| | Investigation | Submission review |
| --- | --- | --- |
| Reuses | `pdf_inspection.py` / `xlsx_inspection.py` / `cross_document_analysis.py` / `cross_format_analysis.py` and their citation mechanism, unmodified | The same citation mechanism, new mandate text |
| Input | Selected source document versions | A submission version + selected source document versions |
| Output | `FindingObservation` rows, same as today | `FindingObservation` rows, each one a claim assessed as Supported / Contradicted / Unsupported / Not assessed / Professional judgment |
| What "missing evidence" means | A finding the AI surfaced with no supporting citation — already handled today via the existing "uncertainty" field | A claim with no citation found — explicitly **not** treated as the claim being false; rendered as "Unsupported by the selected evidence," never as "Contradicted" |
| External knowledge | Not used — findings are always what the documents say | May inform commentary/context ("this term is short for the sector"), but a citation is only ever a deal-room reference; external context is visually distinct from cited evidence and never presented as if it came from the data room |
| Trigger | Explicit "Run investigation" | Explicit "Submit for AI review" |
| Scope transparency | Sources-reviewed section, carried over from Milestone 7/9 unchanged | Same, plus which claims were in scope vs. explicitly out of scope for this run |

Both mandates are `MandateVersion` rows (see data model) — versioned prompt
text, not hardcoded strings, so a mandate can be improved without losing
traceability to what an old run actually used.

## Loading, empty, and error states

Per *(ui-ux-pro-max)*'s cancellable-state-transition and deep-linking guidance:
every list (Findings, Documents, Activity) gets a URL-reflected filter state (so
a filtered view is shareable/bookmarkable — carried forward from nothing today,
genuinely new), a skeleton-row loading state (Milestone 9 already does this for
the findings table — extend the same pattern to every new list rather than
inventing a second loading idiom), and an explicit empty state with the primary
action inline ("No findings yet — [Run investigation]"), not just blank space.
Errors surface inline near what failed (a failed submission-review run shows
its error on that run's card, not as a global toast) — consistent with
Milestone 7–9's existing error-card pattern, extended rather than replaced.

## Dense financial evidence, mixed-direction text, long sheet names

- **Arabic and English filenames, mixed-direction text**: apply CSS logical
  properties (`margin-inline-start` rather than `margin-left`, etc.) site-wide
  rather than physical left/right properties, and set `dir="auto"` on any
  element rendering user-supplied text whose direction isn't known ahead of
  time (a filename, a workstream name, a comment body) so the browser's own
  Unicode bidi algorithm picks the right direction per-field rather than one
  direction being forced site-wide. This is standard, current web-platform
  guidance (not a claim from either design skill's local database — the
  ui-ux-pro-max search for this returned no RTL-specific match after two
  attempts, so this paragraph is labeled explicitly as general practice, per
  that skill's own instruction not to present a non-match as a match).
- **Long sheet/document names**: never truncate to the point of losing the
  distinguishing part of a name — matches *(ui-ux-pro-max)*'s explicit
  "essential text truncation" guidance (critical severity in its own data:
  don't clamp headings/names to uniform width if it hides what makes two
  similar names different). Citation badges already handle this today
  (`title.length > 22 ? slice… : title`, with the *full* name always in the
  `title` attribute for hover/assistive-tech access) — extend the same
  full-name-always-available rule to every new truncated label.
- **Dense evidence**: keep the existing monospace treatment for cell
  references and checksums (`ui-monospace, SFMono-Regular, Menlo, monospace`,
  already in `style.css`), keep numbers right-aligned in tables where a column
  is genuinely numeric, and don't widen the type scale for "important"
  numbers — a financial reviewer scanning fifty rows needs consistency more
  than emphasis.

## What stays deferred

No collaborative spreadsheet or document editor — upload-a-version stays the
interaction model. No Gaffer voice, toggle, or scaffolding of any kind — every
signal it would react to is already visible as plain text in the layouts above
(an open critical issue, an unsupported claim, a blocked item), so nothing about
deferring it constrains anything built now.
