# Product Direction and First User Journey

## Reconciling the pitch and the lab

The founder's original concept note (`Deal-Room-AI-Native-Banker-Workspace-Revised.pdf`,
supplied directly, not present in the repository) frames the product as two systems
laid over one shared workspace: an **Analyst Layer** ("in-play" — analysts work, AI
checks submissions against the data room as they're produced, sorting claims into
evidenced / unsupported / contradicted) and a **Principal Layer** ("overhead" — a
live, drillable view for the deal lead). Milestones 1–9 built most of the plumbing
the Analyst Layer needs — investigation, citations, a findings register with human
review — but built it as **one workspace per AI analysis run**, with no Principal
Layer, no team, and no submission-review distinct from investigation. Neither
document wins outright; this plan takes the pitch's shape and the lab's proven
plumbing and fills the gap between them.

Where they diverge, this plan follows the newer, more precise instruction and says
so explicitly:

| Pitch says | This plan does | Why |
| --- | --- | --- |
| Three buckets: Evidenced / Unsupported / Contradicted | Five: Supported / Contradicted / Unsupported by selected evidence / Not assessed / Professional judgment | The milestone instructions require this exact refinement, and it closes two real gaps the pitch's three buckets leave open: "not assessed" (an AI run that didn't cover a claim at all is not the same as one that checked it and found nothing) and a professional-judgment tag that is explicitly *never scored* on evidencing, matching the pitch's own "professional judgement is tagged separately from fact and is never scored on evidencing" — same intent, more precise categories. |
| Principal Layer stats: submission timeline, **evidencing rate**, contradiction log, revision cycles | Deal-lead view built from actionable work-item lists (open material issues, unsupported decision-driving assumptions, blocked work, pending reviews, recently changed evidence, conclusions needing reassessment) — **no evidencing-rate leaderboard, no composite score** | The milestone instructions explicitly forbid "employee rankings and unvalidated composite 'deal health' scores." An evidencing-rate-by-analyst stat is a one-line SQL query away from becoming exactly that ranking. The underlying signal (how much of a submission traces to a source) is still computed and still shown *per submission*, in context — just never rolled up into a comparison across people. |
| "Not a VDR... no storage, no permissions, no migration" — sits on top of the firm's existing file estate | Keep the lab's own document storage (already built, checksummed, citation-linked across 9 milestones) as the primary path; treat "connect to an existing VDR/file estate" as an explicitly deferred integration, not a blocker | Building a Box/Egnyte/SharePoint connector before a single real multi-user deal has run through this product would be exactly the kind of scope this milestone was told to avoid ("do not require full... capabilities before this workflow can function"). This is flagged as a founder-approval decision in `00-executive-summary.md`, not decided unilaterally here — it's a real positioning divergence from the original pitch. |
| "Closed-world by design... no market data, no external knowledge, no hallucination surface" | External professional knowledge may inform reasoning (e.g. "a 12-month rolling contract is unusually short for this customer segment"), but must never be presented as if it came from the deal room | The milestone instructions are explicitly more permissive here than the pitch's absolute framing. Applied narrowly: a finding's *evidence* is always deal-room-sourced and cited; its *commentary* may draw on general domain knowledge as long as that's never confused with a citation. See `04-workspace-experience.md`'s intelligence-behavior contract. |
| The Gaffer (a loud, football-commentary notification voice, traffic-light escalation ladder) | Fully deferred; not built, not toggled, not scaffolded | Direct instruction ("must not drive the core workflow"), and the pitch document *already* anticipated this exact deferral in its own closing note: "default on for the founder demo, default off for the procurement deck... it should never be the reason someone cannot sign it off." Deferring costs nothing structurally — every signal a Gaffer voice would react to (an unsupported claim, a contradiction, a deadline) is already something the core data model has to track for the deal-lead view regardless. It becomes a presentation-layer choice applied later on top of state that exists anyway. |

Everything else in the pitch is preserved directly: one shared workspace (not one
per AI run), a central AI layer rather than per-analyst isolated prompting, "the AI
is not another tab" (findings/questions/submissions live in the workspace's own
navigation, not a chat sidebar), evidence traceable from every output back to a
specific page/cell, and human judgment as final authority — the AI recommends,
adjudicates against evidence, and cites; it never approves.

## Product direction, one paragraph

**A shared deal workspace where AI investigates the evidence, checks the team's
work, and tracks how outstanding issues are resolved — with one connected findings
register instead of separate ones per run, one workspace per deal instead of one
per analysis, and every AI output traceable back to the exact document, page, cell,
or submission version it came from.**

## Who this is for, first

Per the milestone's assumption (nothing in the repository contradicts it — there is
no user/org model yet to contradict it with): a small advisory team running
financial diligence and financing review — a deal lead and one or more analysts.
Workstreams are a configurable organizational grouping (a table row: name +
description), not a claim that legal/commercial/operational/IT/ESG review methods
already exist. The pitch's "six zones" is the long-run shape; this plan scopes the
first working slice to whatever workstreams the deal lead actually creates for a
financial/financing engagement, with the schema open to more later.

## The first shared workflow

This is the assignment's ten-step workflow, annotated with which Milestone 9
component each step reuses and which is genuinely new:

| # | Step | Reuses | New |
| --- | --- | --- | --- |
| 1 | Create a deal and define the engagement | `store.Project` becomes (or sits alongside) `Deal` | Deal brief + version (who/what the transaction concerns) |
| 2 | Upload approved source documents | `documents.py` upload/checksum/path-safety | Document *versions* (immutable, linked to a parent document) |
| 3 | Set up workstreams and assign responsibilities | — | Workstream table; deal membership + role |
| 4 | Run an explicit AI investigation | `pdf_inspection.py` / `xlsx_inspection.py` / `cross_format_analysis.py`, the whole citation mechanism | An investigation becomes one *run* inside a persistent deal workspace, not the workspace's entire reason to exist |
| 5 | Review findings, create information requests | `workspaces.py`'s review/duplicate/request model almost entirely | Findings become deal-scoped, stably identified, and attributable to whichever run produced them |
| 6 | Submit an analyst-produced work product | — | Work product + immutable submission version (new record type) |
| 7 | Check that submission against selected evidence | The same evidencing/citation mechanism `cross_format_analysis.py` already proves works | A *second* analysis mandate — "submission review" — distinct from investigation (see `04-workspace-experience.md`) |
| 8 | Resolve or accept outstanding risks | `workspaces.py`'s resolution-status vocabulary, extended | The response/evidence/review/closure state-machine in `03-data-model.md` |
| 9 | Approve a versioned conclusion or memo | `workspaces.py`'s memo approve/edit-reverts-to-draft lifecycle, almost entirely | Memo becomes deal-scoped and versioned (today it's one memo per analysis workspace) |
| 10 | Revisit affected conclusions when evidence changes | — | Change-aware reassessment flagging (Milestone 15) |

Roughly two-thirds of this workflow is already proven, working code from Milestones
7–9. The genuinely new surface is: deal-level persistence above the analysis-run
level, document/submission versioning, a second AI assignment type (submission
review), and change-aware reassessment. That scoping is deliberate — it's why the
roadmap (`07-roadmap-and-coding-mandates.md`) front-loads the deal-workspace
foundation (Milestone 11) as a narrow, low-risk vertical slice before touching
authentication, hosting, or a second AI capability at all.

## Explicit non-goals for this phase

Carried directly from the assignment, restated once here so every other document can
just point back to it instead of repeating it: no collaborative spreadsheet/document
editor (upload versions, work in existing tools), no full five-specialist-zone
coverage requirement to unblock the first workflow, no Gaffer-driven core workflow,
no automatic re-analysis on every edit, no employee rankings or composite deal-health
scores, no silent overwriting or reinterpretation of an existing Milestone 9 record,
no real-deal cloud migration without a separate approval gate.
