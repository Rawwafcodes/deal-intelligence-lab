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

## Summary table

| # | Surface | Scope | Current route | Backend | Frontend | Classification | Target milestone |
|---|---|---|---|---|---|---|---|
| 1 | Public homepage | Public | none | none | none | missing | M23 |
| 2 | Product / how it works | Public | none | none | none | missing | M23 |
| 3 | Security and trust | Public | none | none | none | missing | M23 |
| 4 | Request pilot / contact | Public | none | none | none | missing | M23 |
| 5 | Sign in | Access | none (dev identity switcher only) | dev-only session (`identity.create_session`/`_handle_dev_session_login`) | `IdentityFooter`'s dev-identity `<select>`, not a sign-in page | static-only (dev stub) | M19 |
| 6 | Invitation / onboarding | Access | none | `add_organization_membership`/`add_deal_membership` exist, no invite/token flow, no route | none | missing | M20 |
| 7 | Workspace Overview | Organization/user | `/` (`Home.tsx`) | real, permission-filtered aggregate routes | complete (5-component Overview, Task 17.6) | complete | M18 (founder acceptance) |
| 8 | Deals | Organization/user | `/deals` (`Deals.tsx`) | real | complete (Task 17.7) | complete | M18 |
| 9 | Deal Overview | Deal | `/projects/:id` index (`DealOverview.tsx`) | real | complete, incl. restricted `external_executive` view | complete | M18 |
| 10 | Mandates | Organization or deal | `/mandates` (`MandatesHome.tsx`) + `/projects/:id/mandates` (`MandateList.tsx`) | real, unified composer/registry | complete, two contextual instances of one canonical surface (Task 17.8/17.9) | complete | M18 |
| 11 | Mandate Detail | Mandate | `/projects/:id/mandates/:mandateId` (`MandateDetail.tsx`) | real (plan/approval/run/checkpoint) | complete | complete | M18 |
| 12 | Documents | Active deal | `/projects/:id/documents` (`Documents.tsx`) | real | complete (upload, list, filter) | complete | M18 |
| 13 | Document Detail | Document/version | none dedicated - `href` opens the raw file inline (`.../documents/<id>/download?inline=1`) | version storage exists, no detail endpoint | raw browser file view only, no in-app version history/citation-backlink panel | **partial** | M18 (essential-gap decision) |
| 14 | Findings | Active deal | `/projects/:id/findings` (`Findings.tsx`) | real, unified across cross-format and Integrity Review origins (Task 17.11) | complete | complete | M18 |
| 15 | Finding Detail | Finding | inline expansion inside `Findings.tsx`, not a separate route | real | complete as an inline component (not a page - correctly not a standalone route) | complete | M18 |
| 16 | Workstreams and Tasks | Deal | `/projects/:id/work` (`Work.tsx`) | real | complete | complete | M18 |
| 17 | Submission Review | Submission version | inside `Work.tsx`'s `WorkProductItem`, not a separate route | real (approve/return, capability-gated) | complete as a component within Work | complete | M18 |
| 18 | Information Requests | Deal/finding | `RequestDialog` panel launched from `Findings.tsx`, not a separate route | real (`workspaces.py` request routes, Task 17.1) | complete as a panel | complete | M18 |
| 19 | Decision Package | Deal/workspace | `/projects/:id/decision-package` (`DecisionPackage.tsx`) | real (`decision_package.py`/`deliverables.py`) | complete | complete | M18 |
| 20 | Activity | Active deal | `/projects/:id/activity` (`Activity.tsx`) | real | complete | complete | M18 |
| 21 | Validation Cases | Internal validation | `static/validation.html` (external link from deal sidebar) | real, unchanged | static-only, deliberate | static-only (correct, see below) | none - preserve as-is |
| 22 | Validation Case / Report | Internal validation | `static/validation-case.html`, `static/validation-evaluation.html` | real, unchanged | static-only, deliberate | static-only (correct) | none - preserve as-is |
| 23 | Team and Access | Organization/deal | none | deal-level grant/revoke exists (`_handle_grant_membership`/`_handle_revoke_membership`); org-level `add_organization_membership` has no HTTP route at all | none - deal-level endpoints exercised only by tests/curl, never a UI | missing | M19 (minimum for staging), M23 (full self-serve) |
| 24 | Organization Settings | Organization | none | `create_organization`/`get_organization` exist as internal functions; no create/update HTTP route; organizations exist only via seed data | none | missing | M19 (minimum), M23 (full self-serve) |
| 25 | Usage and Billing | Organization | none | only a per-mandate-run budget ledger (`budget_limit`/`budget_consumed`, Task 12.2); no org-level usage/cost aggregation, no billing anything | none | missing | M19 (budget/rate limits only), M20 (usage/cost reporting), M23 (real billing) |

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

## Distinguishing page, panel, drawer, tab and component

Per this reconciliation's own governing instruction, form is recorded
explicitly rather than assumed from a canonical row's label:

- **Full page** (own route, own URL): surfaces 7-12, 14, 16, 19, 20,
  21-22 (static), and both contextual instances of surface 10.
- **Deep page** (own route, nested under a deal): surface 11.
- **Panel/dialog** (opened from a page, no own URL): surface 18
  (`RequestDialog`), the document-upload dialog on surface 12.
- **Inline expansion component** (not a route, not an overlay): surface
  15 (finding detail rows inside `Findings.tsx`), surface 17 (submission
  review inside `Work.tsx`'s task cards).
- **Raw browser view, not an application page**: surface 13's current
  state (a direct file `href`, not an in-app detail view) - this is
  exactly why it is classified partial rather than complete.

No canonical surface was implemented as an unnecessary standalone route
merely to reach the count of 25; several (15, 17, 18) are deliberately
components/panels, not pages, matching
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
