# Milestone 10 — Executive Summary

Planning and design only, as scoped. No application code was changed, no
migration was applied, no real deal or validation record was reset or altered,
no cloud resource was provisioned, no paid AI call was made, and nothing was
pushed. This document is the entry point; the six documents it references hold
the substance.

- [`01-baseline-inventory.md`](01-baseline-inventory.md) — actual-state
  inventory and reuse map (re-verified, not assumed; corrects two claims from
  the prior Milestone 9 report)
- [`02-product-direction.md`](02-product-direction.md) — product direction,
  first user journey, and the explicit reconciliation between the founder's
  original pitch and what Milestones 1–9 actually built
- [`03-data-model.md`](03-data-model.md) — the full record set, including the
  stable-finding-identity design
- [`04-workspace-experience.md`](04-workspace-experience.md) — navigation,
  low-fidelity layouts, click-through narratives, the investigation vs.
  submission-review intelligence contract
- [`05-permissions-and-security.md`](05-permissions-and-security.md) —
  permission matrix and every security concern the assignment listed
- [`06-architecture-and-infrastructure.md`](06-architecture-and-infrastructure.md)
  — the hosting decision, sourced current pricing/limits, background-job
  requirements
- [`07-roadmap-and-coding-mandates.md`](07-roadmap-and-coding-mandates.md) —
  Milestone 9 closeout through Milestone 15, every mandate fully specified

## 1. Recommended architecture and why

A **Python web application plus a background-worker deployment from the same
codebase** (concretely: Render or Fly.io hosting a Web Service and a
Background Worker together), with **Neon** for Postgres regardless of which
host is chosen. **Not** the Vercel-plus-worker hybrid the assignment offered
as the second option — sourced this session directly from Vercel's own docs:
its Functions cap request/response bodies at **4.5 MB** (this app's uploads
already reach 500 MB, and a single reconciliation's PDFs alone reach 23.5 MB)
and cap execution duration at **300s on Hobby**, with the **1800s** ceiling
that would even begin to cover this app's own existing worst-case analysis
time available only as a **beta** feature on paid tiers. Building this app's
core critical path on a beta ceiling that exactly equals today's own worst
case, for a codebase that is 100% Python with no production Next.js/Vercel
asset today, is not a foundation worth recommending. Neon's benefits (pooled
serverless Postgres, branching, scale-to-zero idle cost) are independent of
Vercel and are recommended on either option. Full reasoning and sourced
figures: `06-architecture-and-infrastructure.md`.

## 2. What stays unchanged from Milestones 1–9

Every analysis module (`ai_client.py`, `pdf_inspection.py`, `xlsx_inspection.py`,
`cross_document_analysis.py`, `cross_format_analysis.py`, `evaluations.py`'s
parser, `multipart.py`, `store.py`'s connection/dataclass conventions), the
citation mechanism in full (native PDF citations, the Excel citation
convention plus mechanical verification), the Validation Lab's blindness
discipline, and Milestone 9's finding-review/duplicate/request/memo workflow
shape (extended to be deal-scoped, not rewritten). Every existing Milestone 9
URL keeps working unmodified — the deal-level workspace is additive, backfilled
onto existing records, never a replacement for them. Full list:
`01-baseline-inventory.md`'s reuse map.

## 3. What must change

The routing/serving layer (`server.py`'s `http.server` usage — the official
Python docs call it explicitly unfit for production, and its own security
caveats are named and sourced in `06-architecture-and-infrastructure.md`), AI
finding identity (list-position-based today; a real correctness risk, fixed
by content-fingerprint identity in `03-data-model.md`), local-disk document
storage and SQLite (for cloud environments only — local dev is unaffected),
and the addition of an authentication/membership/permission layer that
currently does not exist at all. Full list: `01-baseline-inventory.md`'s "known
gaps," `03-data-model.md`, `05-permissions-and-security.md`.

## 4. The first coding mandate

**Milestone 11.1** (full specification in
`07-roadmap-and-coding-mandates.md`): open the existing Universal Logic
project, create and edit its versioned deal brief, create a workstream,
associate that project's existing Milestone 9 document and finding with it,
reload, confirm persistence — and confirm the existing Milestone 9
`/workspace.html` view is completely unaffected. No AI calls, no cloud
migration, no auth. New tables only, additive, with tests matching this
codebase's own existing conventions (temp-DB unit tests, real-server-thread
HTTP integration tests, forged-ID/cross-project rejection tests) and a
browser-verified acceptance scenario against the real project.

## 5. Decisions the founder must approve before further work proceeds

1. **Frontend framework**: keep building on the existing static pages through
   Milestone 11 (no decision needed to start), but explicitly decide, at the
   Milestone 12 boundary, whether to adopt the untracked `frontend/` React
   scaffold — it's more developed and design-matched than expected (working
   build, matches `style.css`'s design tokens by name, faithfully reimplements
   the existing home page against the same API), or to keep extending the
   static-page pattern. Recommendation in `01-baseline-inventory.md` leans
   toward adopting it at that boundary, but doesn't decide it.
2. **Positioning**: keep the lab's own self-contained document storage as the
   primary path (recommended), or pursue "not a VDR — sits on top of the
   firm's existing file estate" as the original pitch framed it. These are
   materially different products to build. See `02-product-direction.md`.
3. **Verification-record handling**: the real Universal Logic workspace still
   carries Milestone 9's verification edits (full row list in
   `01-baseline-inventory.md`). Pick an approach (going-forward tagging vs. an
   explicit, approved reset of just those rows) — nothing is touched until
   this is decided.
4. **Hosting provider specifics**: Render vs. Fly.io for the web+worker pair;
   Neon vs. a single-vendor Postgres (e.g. Render's own, which carries a
   30-day auto-deletion risk on its free tier, sourced this session) — a
   recommendation is made in `06-architecture-and-infrastructure.md`, not a
   unilateral choice.
5. **Object storage provider** — not priced or chosen this session; needs a
   real quote before Milestone 12.4.
6. **Milestone 14's first paid AI calls** — explicit approval required before
   that milestone's submission-review runs happen, per the authorization
   boundaries; flagged again in `07-roadmap-and-coding-mandates.md` at the
   point it applies.

## 6. Findings that could materially change the plan

- **AI finding identity is currently list-position-based, not content-based**
  (`03-data-model.md`) — the single most consequential technical finding here;
  left unaddressed, a future improvement to `evaluations.py`'s parser could
  silently reattach real reviewer decisions to the wrong finding, in every
  existing workspace, with no warning. Scoped as an early Milestone 11 mandate
  specifically because of this.
- **A real, currently-shipped formula-injection gap** in every `.xlsx` export
  (`01-baseline-inventory.md`, `05-permissions-and-security.md`) — free-text
  fields flow into exported cells unsanitized; a value starting with `=`
  executes as a live formula when opened. Needs fixing before any export path
  handles real, multi-user, uncontrolled input.
- **The prior Milestone 9 completion report's test count was measured against
  the working tree, not the committed baseline** — 333 tests actually pass at
  the real committed `HEAD`, not 334; the extra test belongs to another
  session's uncommitted edit. Corrected in `01-baseline-inventory.md`; doesn't
  change any conclusion, but the prior report's own framing ("334 passing
  tests... commit dd10217") conflated two different things worth keeping
  distinct going forward.
- **No authentication, session, or user concept exists anywhere today** —
  expected given the product's local, single-user history, but confirms
  Milestone 12's permission work starts completely from zero, not from
  hardening something partial.
- **Vercel's actual, sourced limits rule out the assignment's second
  architecture option as originally framed** for this specific codebase (see
  §1) — this is why the recommendation departs from a literal middle-ground
  between the two offered options and picks one directly, with reasons.
