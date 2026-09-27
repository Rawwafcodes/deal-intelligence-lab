# 25-surface information-architecture reconciliation

Status: implemented facts verified directly against the checkout on
2026-09-27, immediately after M17's close (`70f03ca`) and the adoption of
the post-M17 roadmap (`docs/workspace-shift/docs/10-decisions.md` D17).
This is the authoritative, code-verified status of every surface in
`02-experience-and-information-architecture.md`'s target route/page
inventory. That table is the canonical **target**; this file is the
canonical **reconciliation** of target against actual implementation. It
supersedes `05-current-product-map.md`'s "Important gaps" list, which
pre-dated M17 and was stale (see that file's own updated note).

Re-verify against the actual checkout before relying on this file for a
later revision - it is a snapshot, not a live view.

**Note on D19**: the same day, the founder renamed and partly redefined
M21-M25 (`docs/workspace-shift/docs/10-decisions.md` D19) - most visibly,
splitting what D18 called M22 into a learning milestone (M22, produces a
specification) and a delivery milestone (M23, builds it). Every
milestone assignment in this file already lands on M19/M20/M23 for the
absent administrative surfaces and M18 for in-product gaps - none of
those assignments point at the old, now-superseded M22 delivery meaning,
so nothing here needed to change. Where a table cell below says "M22
evidence", it means the product-learning output D19's M22 now produces,
consumed by D19's M23.

**25 pages is not 25 equal navigation tabs.** Six destinations
(Overview, Deals, Mandates, Documents, Findings, Activity) are primary
navigation. Every other canonical surface is a contextual deal-level,
mandate-level, administrative or internal page, drawer, panel or
component reached from inside one of those six - exactly as
`02-experience-and-information-architecture.md` itself already states.
Nothing below proposes new standalone top-level routes merely to reach
the number 25.

## Method

For each of the 25 canonical surfaces: read the actual route registered
in `frontend/src/App.tsx`; read the corresponding route component under
`frontend/src/routes/` (or confirm none exists); grep `server.py` and the
relevant domain module for a real HTTP capability; grep the static
`.html` pages and `frontend/src` for any remaining link to a legacy
static page. No claim below is inferred from a milestone title or an
earlier STATUS.md narrative alone - each was checked directly against
the current source.

## Reconciliation table

Split into three linked tables (by `#`) so each fits legibly: identity/
purpose, implementation status, and planning. Together they cover every
field this reconciliation is required to record: canonical name,
intended user, scope, intended purpose, current route, implementation
status, backend support, frontend support, classification, dependencies,
target milestone, and acceptance test.

### Identity and purpose

| # | Surface | Intended user | Scope | Intended purpose |
|---|---|---|---|---|
| 1 | Public homepage | Prospective customer / public visitor | Public | Explain what the product is, before any sign-in |
| 2 | Product / how it works | Prospective customer | Public | Explain the workflow/value proposition |
| 3 | Security and trust | Prospective customer's security/procurement reviewer | Public | Pre-empt security/compliance questions before a sales conversation |
| 4 | Request pilot / contact | Prospective customer | Public | Capture outbound interest |
| 5 | Sign in | Any user | Access | Authenticate before reaching any organization/deal data |
| 6 | Invitation / onboarding | Newly invited user | Access | Get an invited person into their first organization/deal safely |
| 7 | Workspace Overview | Any authenticated org member | Organization/user | "What requires attention and what could affect a decision?" (5 components, per `02-...md`) |
| 8 | Deals | Any authenticated org member | Organization/user | List/filter every deal the caller can access |
| 9 | Deal Overview | Deal member, incl. restricted `external_executive` | Deal | Latest approved position, urgent matters, responsibilities, active mandates |
| 10 | Mandates | Org member (org-wide) or deal member (deal-scoped) | Organization or deal | Configure/track AI mandates in one place |
| 11 | Mandate Detail | Deal member reviewing/approving a run | Mandate | Plan, approval, run and checkpoint detail for one mandate |
| 12 | Documents | Analyst/reviewer/lead | Active deal | Upload and register source documents/versions |
| 13 | Document Detail | Deal member reviewing one document/version | Document/version | Inspect one document's content, versions and citation backlinks |
| 14 | Findings | Deal member reviewing analytical output | Active deal | One findings register across every analysis origin |
| 15 | Finding Detail | Deal member drilling into one finding | Finding | Full evidence/lineage for one finding |
| 16 | Workstreams and Tasks | Analyst/reviewer/lead executing work | Deal | Assign and track work inside a deal |
| 17 | Submission Review | Reviewer/deal lead | Submission version | Approve/return a specific immutable work-product version |
| 18 | Information Requests | Deal member requesting/responding, incl. `external_executive` | Deal/finding | Ask for and answer specific evidence/clarification |
| 19 | Decision Package | Deal lead/reviewer | Deal/workspace | Produce the reviewed, approved final position |
| 20 | Activity | Deal member auditing history | Active deal | Chronological audit trail for one deal |
| 21 | Validation Cases | Internal quality reviewer (founder/internal QA) - **not the customer** | Internal validation | List internal-only accuracy-validation cases |
| 22 | Validation Case / Report | Internal quality reviewer | Internal validation | One validation case's locked answer key and scored report |
| 23 | Team and Access | Organization/deal administrator | Organization/deal | Invite, role, and revoke people |
| 24 | Organization Settings | Organization administrator | Organization | Create/rename/configure the tenant itself |
| 25 | Usage and Billing | Organization administrator / buyer | Organization | See and control AI/infrastructure usage and cost |

### Implementation status

| # | Current route | Implementation status | Backend support | Frontend support | Classification |
|---|---|---|---|---|---|
| 1 | none | Never built | none | none | missing |
| 2 | none | Never built | none | none | missing |
| 3 | none | Never built | none | none | missing |
| 4 | none | Never built | none | none | missing |
| 5 | none (dev identity switcher only) | Dev-only stand-in used throughout M11-M17, never a real sign-in | `identity.create_session`/`_handle_dev_session_login` (dev-only) | `IdentityFooter`'s dev-identity `<select>` | static-only (dev stub) |
| 6 | none | Never built | `add_organization_membership`/`add_deal_membership` exist as internal functions; no invite/token flow; no route | none | missing |
| 7 | `/` (`Home.tsx`) | Complete, 5-component Overview (Task 17.6) | real, permission-filtered aggregate routes | complete | complete |
| 8 | `/deals` (`Deals.tsx`) | Complete (Task 17.7) | real | complete | complete |
| 9 | `/projects/:id` index (`DealOverview.tsx`) | Complete, incl. restricted `external_executive` view | real | complete | complete |
| 10 | `/mandates` (`MandatesHome.tsx`) + `/projects/:id/mandates` (`MandateList.tsx`) | Complete, two contextual instances of one canonical surface (Task 17.8/17.9) | real, unified composer/registry | complete | complete |
| 11 | `/projects/:id/mandates/:mandateId` (`MandateDetail.tsx`) | Complete | real (plan/approval/run/checkpoint) | complete | complete |
| 12 | `/projects/:id/documents` (`Documents.tsx`) | Complete (upload, list, filter) | real | complete | complete |
| 13 | none dedicated - `href` opens the raw file inline (`.../documents/<id>/download?inline=1`) | Only a raw browser file view; no in-app version history/citation-backlink panel | version storage exists, no detail endpoint | raw file view only | **partial** |
| 14 | `/projects/:id/findings` (`Findings.tsx`) | Complete, unified across cross-format and Integrity Review origins (Task 17.11) | real | complete | complete |
| 15 | inline expansion inside `Findings.tsx`, not a separate route | Complete as a component - correctly not a standalone route | real | complete | complete |
| 16 | `/projects/:id/work` (`Work.tsx`) | Complete | real | complete | complete |
| 17 | inside `Work.tsx`'s `WorkProductItem`, not a separate route | Complete as a component within Work | real (approve/return, capability-gated) | complete | complete |
| 18 | `RequestDialog` modal launched from `Findings.tsx`, not a separate route | Complete as a modal dialog | real (`workspaces.py` request routes, Task 17.1) | complete | complete |
| 19 | `/projects/:id/decision-package` (`DecisionPackage.tsx`) | Complete | real (`decision_package.py`/`deliverables.py`) | complete | complete |
| 20 | `/projects/:id/activity` (`Activity.tsx`) | Complete | real | complete | complete |
| 21 | `static/validation.html` (external link from deal sidebar) | Deliberately static, not migrated - disclosed exception | real, unchanged | static-only, deliberate | static-only (correct - see below) |
| 22 | `static/validation-case.html`, `static/validation-evaluation.html` | Deliberately static, not migrated | real, unchanged | static-only, deliberate | static-only (correct) |
| 23 | none | Deal-level exists, exercised only by tests/curl; org-level has no route at all | deal-level grant/revoke (`_handle_grant_membership`/`_handle_revoke_membership`); org-level `add_organization_membership` has no HTTP route | none - no UI at either level | missing |
| 24 | none | Never built beyond internal seed-time functions | `create_organization`/`get_organization` exist as internal functions; zero HTTP callers confirmed; organizations exist only via seed data | none | missing |
| 25 | none | Only a per-run budget ledger, no org-level view | per-mandate-run budget ledger (`budget_limit`/`budget_consumed`, Task 12.2) only; no org-level usage/cost aggregation, no billing | none | missing |

### Planning

| # | Dependencies | Target milestone | Acceptance test |
|---|---|---|---|
| 1 | A repeatable commercial motion to justify building it (M22 evidence) | M23 | none (out of local-product S01-S20 scope) |
| 2 | Same as #1 | M23 | none |
| 3 | Same as #1; M20's security-questionnaire content can seed its copy | M23 | none |
| 4 | Same as #1; may be pulled forward into M20 if outreach needs it | M23 (optionally M20) | none |
| 5 | M19's architecture/provider decision | M19 | T04 (revoked user loses access); S20 (concurrent identities) |
| 6 | M19's identity provider decision | M20 | S01 (create/enter an organization); S03 (establish users and roles) |
| 7 | none - already complete | M18 (founder acceptance only) | S17 (material changes and activity) |
| 8 | none | M18 | S02 (create/open a deal) |
| 9 | none | M18 | S02; S18 (restricted external-executive experience) |
| 10 | none | M18 | S10 (create and execute mandates); S11 (starting structures) |
| 11 | none | M18 | S10 |
| 12 | none | M18 | S06 (upload documents and document versions) |
| 13 | Founder decision on whether a real detail view is essential before M18 acceptance | M18 (open decision) | S06 |
| 14 | none | M18 | S12 (findings and evidence) |
| 15 | none | M18 | S12 |
| 16 | none | M18 | S05 (workstreams/assignments); S07 (tasks/comments) |
| 17 | none | M18 | S08 (submit work products); S09 (review/return/approve) |
| 18 | none | M18 | S13 (information requests) |
| 19 | none | M18 | S16 (decision package) |
| 20 | none | M18 | S17 |
| 21 | None - preserve as-is, no dependency | none (preserve) | T16 (validation secret marker never leaks into a customer path) |
| 22 | None - preserve as-is | none (preserve) | T16 |
| 23 | M19's identity/authz architecture decision (minimum); M22 evidence (full self-serve) | M19 (minimum), M23 (full) | S03; T04/T05 (permission boundaries) |
| 24 | M19's architecture decision (minimum); M22 evidence (full self-serve) | M19 (minimum), M23 (full) | S01 |
| 25 | M19's rate/budget-limit design (minimum); M20's reporting design; M22 evidence (real billing) | M19 (limits), M20 (reporting), M23 (billing) | none dedicated - covered operationally, not by S01-S20 |

## Surfaces present in the product but outside the canonical 25 — real conflict, founder decision required

Four real, backend-complete, React-native destinations exist in the
shipped product with no corresponding row in
`02-experience-and-information-architecture.md`'s 25-surface table. Per
this reconciliation's own governing instruction ("do not rename, replace
or expand [the canonical list] without identifying a real conflict"),
this is exactly such a conflict, disclosed rather than resolved
unilaterally — the canonical table itself is **not edited by this
file**.

| Surface | Scope | Current route | Backend | Frontend |
|---|---|---|---|---|
| Readiness | Deal | `/projects/:id/readiness` (`Readiness.tsx`) | `readiness.py`/`readiness_assessments.py` (Task 14.4) | complete (Task 17.3) |
| Targeted Reassessment | Deal | `/projects/:id/reassessments` (`Reassessments.tsx`) | `reassessments.py` (Task 15.2) | complete (Task 17.4) |
| Monitoring / Triggers | Deal | `/projects/:id/triggers` (`Triggers.tsx`) | `triggers.py` (Task 15.3) | complete (Task 17.5) |
| Assertions | Deal | `/projects/:id/assertions` (`Assertions.tsx`) | `assertion_ledger.py` (Task 16.2, wired per D15) | complete (Task 17.10) |

All four are deal-scoped deep pages, the same tier as Document Detail or
Decision Package - not primary navigation, and not proposed as new
top-level tabs. Two ways to resolve this, presented rather than chosen:

(a) Amend `02-experience-and-information-architecture.md`'s table to add
    these as canonical surfaces #26-29 (or fold them explicitly as named
    sub-pages of Deal Overview/Findings in the existing rows' own
    descriptions), formally recognizing what M14.4/M15/M16/M17 already
    built and shipped; or
(b) Explicitly declare them deliberate, disclosed surfaces adjacent to
    but outside the "primary 25" product-architecture target, on the
    reasoning that the 25-surface table was drafted before M14.4-M17's
    own scope was finalized.

Recorded as an open founder decision in
`docs/workspace-shift/docs/10-decisions.md` (D18) and
`docs/workspace-shift/docs/13-post-m17-roadmap.md`'s open-decisions
register. This reconciliation table's own "25 canonical surfaces" count
is unaffected either way - these four are additional, not substitutes
for any of the 25.

## Superseded static pages (not counted as completed canonical surfaces)

`static/index-legacy.html`, `static/project.html`, `static/workspace.html`,
`static/cross-analysis.html`, `static/inspect.html`, `static/reconcile.html`
and `static/workbook-inspect.html` remain served by `server.py` but are
confirmed orphaned - no link anywhere in `frontend/src` points to any of
them (checked directly, not inferred). None is counted as a completed
implementation of any canonical surface above; each surface's row above
reflects only its real React route. `static/validation.html` and its two
case/report pages are the sole disclosed, deliberate exception (surfaces
21-22 above), per `docs/10-decisions.md` D13 and this repository's
existing Review-vs-Validation-Lab boundary
(`docs/product/06-truth-register.md`).

## Distinguishing full route/page, tab, panel, modal, drawer and component

Per this reconciliation's own governing instruction, form is recorded
explicitly rather than assumed from a canonical row's label:

- **Full page, top-level** (own route, own URL, primary navigation):
  surfaces 7, 8, and one of surface 10's two contextual instances
  (`/mandates`).
- **Full page + tab** (own route, *and* one of `DealShell.tsx`'s real
  `<nav>`/`NavLink` tab strip once inside a deal - checked directly
  against its `TABS` array, not assumed): surfaces 9 (`Overview` tab),
  12 (`Documents`), 14 (`Findings`), the deal-scoped instance of surface
  10 (`Mandates`), and 20 (`Activity`) - **five tabs only**.
- **Full page, linked but not a tab** (own route, reached via a real
  contextual `Link` from inside Overview or Findings rather than the
  persistent tab strip - confirmed by grepping every `Link`/`navigate`
  call, not assumed from any route existing): surface 16 (`Work` - linked
  from `DealOverview.tsx`), surface 19 (`Decision Package` - linked from
  `Findings.tsx`), and all four non-canonical destinations (Readiness,
  Reassessments, Assertions - linked from `Findings.tsx`; Triggers -
  linked from both `DealOverview.tsx` and `MandateComposerDialog.tsx`).
  This is a deliberate pattern, not an oversight: it matches
  `02-experience-and-information-architecture.md`'s own "Deeper routes
  do not need to become primary navigation tabs" - but it does mean a
  caller who lands on one of these routes without going through Overview
  or Findings first (a bookmark, a shared link) has no tab to return to
  the deal's other destinations from; each of these pages does render
  inside `DealShell`, so `DealShell`'s own tab strip is still visible for
  navigating *away*, just not how the caller most likely arrived.
- **Deep page** (own route, nested under a deal, not in the tab strip and
  not directly linked from Overview/Findings): surface 11 (`Mandate
  Detail`, reached from the `Mandates` tab's own list, not itself a tab
  or a direct Overview/Findings link).
- **Modal dialog** (opened from a page, no own URL, blocks the
  background): surface 18 (`RequestDialog`), the document-upload dialog
  on surface 12 (`DocumentUploadDialog`).
- **Inline expansion component** (not a route, not an overlay, renders
  in place within a list): surface 15 (finding detail rows inside
  `Findings.tsx`), surface 17 (submission review inside `Work.tsx`'s
  task cards).
- **Static page, deliberately not migrated**: surfaces 21-22.
- **Raw browser view, not an application page**: surface 13's current
  state (a direct file `href`, not an in-app detail view) - this is
  exactly why it is classified partial rather than complete.
- **Drawer**: not used by any canonical surface's current implementation
  - `02-experience-and-information-architecture.md` allows a drawer as
    an option for create/edit/upload/select-evidence actions and detail
    views, but every surface that needed this pattern (12, 18) used a
    modal dialog instead, and 15/17 used inline expansion instead. No
    gap follows from this - the guidance names drawer/dialog as
    interchangeable options, not a requirement for either specifically.

No canonical surface was implemented as an unnecessary standalone route
merely to reach the count of 25; several (15, 17, 18) are deliberately
components/modals, not pages, matching
`02-experience-and-information-architecture.md`'s own "Deeper routes do
not need to become primary navigation tabs" and "should usually use a
focused drawer or dialog" guidance.

## Essential product-facing gaps flagged for M18

Per M18's exit-gate requirement (`docs/workspace-shift/docs/
13-post-m17-roadmap.md`) that every essential local-product surface
either pass founder acceptance or receive an explicit approved later
milestone, the founder must decide on:

1. **Document Detail (#13)** - is a raw inline file view sufficient for
   local-product acceptance, or does citation-backlink/version-history
   context belong in M18 before founder acceptance? Recommendation: this
   is a genuine usability gap surfaced by Track A's own S06 scenario
   (upload documents and document versions), not a cosmetic one - but
   building it is implementation, which this reconciliation (a
   documentation/planning task) does not do.
2. **The four non-canonical surfaces above** - amend the canonical table
   (option a) or declare them a disclosed exception (option b)?
3. **Team and Access / Organization Settings / Usage and Billing
   (#23-25)** - confirmed genuinely absent, not merely unlinked. M18
   Track A's S01 (create/enter an organization) and S03 (establish users
   and roles) will surface this directly during acceptance testing; this
   reconciliation records the gap in advance so Track A does not
   discover it cold. These three are correctly targeted at M19/M23, not
   M18, per this reconciliation's own milestone assignment - M18 does
   not need to build them, only to record that their absence is an
   approved deferral, not an oversight.

None of these three items is resolved by this document. Each is carried
into `docs/workspace-shift/docs/10-decisions.md` (D18) and
`13-post-m17-roadmap.md`'s open-decisions register as an explicit,
undecided founder question - not silently approved and not silently
deleted.
