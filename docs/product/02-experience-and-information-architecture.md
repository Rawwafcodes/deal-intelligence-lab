# Experience and information architecture

## Established direction

The product has one coherent application surface. React is the permanent
frontend direction. Existing static pages may remain temporarily as migration
references or internal fallbacks, but normal users must not be sent between two
different products or shown labels such as "legacy page".

## Primary navigation

The intended peer destinations are:

1. **Overview**
2. **Deals**
3. **Mandates**
4. **Documents**
5. **Findings**
6. **Activity**

Overview, Deals and the organization-wide Mandates view operate across the
user's authorized work. Documents, Findings and Activity use a persistent
active-deal context. Deeper routes do not need to become primary navigation
tabs.

## Workspace Overview

The Overview answers "What requires attention and what could affect a
decision?" It contains five principal components:

1. **My attention** — approvals, questions, submitted work, failed mandates,
   blocked assignments and overdue actions that the current user can act on.
2. **Mandates** — running, awaiting input/approval, under review, recently
   completed and failed mandates.
3. **Active engagements** — owner, stage, material unresolved matters and next
   action for each accessible deal.
4. **Quick actions** — create a mandate or deal, upload evidence and open an
   assigned review.
5. **Material changes** — new evidence/submissions, reopened findings,
   approvals and changes that may make prior conclusions stale.

Every count must derive from real, permission-filtered records. Do not display
invented deal-health percentages.

## Deal experience

A deal is a continuing workspace with:

- a versioned brief;
- people, roles and workstream responsibilities;
- source documents and immutable versions;
- assigned tasks and immutable work-product submissions;
- AI mandates and their approved plans/runs;
- one findings register;
- information requests and responses;
- reviewed conclusions and approved deliverables;
- activity and audit history;
- dependency and staleness information.

The Deal Overview prioritizes the latest approved position, urgent matters,
responsibilities, active mandates, material findings, requests, recent changes
and deliverables. An AI draft must never impersonate an approved human position.

## Target route/page inventory

This is a target information architecture, not a claim that 29 independent
screens are implemented or that all should appear in navigation.

| # | Surface | Scope | Intended form |
| --- | --- | --- | --- |
| 1 | Public homepage | Public | Page |
| 2 | Product / how it works | Public | Page |
| 3 | Security and trust | Public | Page |
| 4 | Request pilot / contact | Public | Page |
| 5 | Sign in | Access | Page |
| 6 | Invitation / onboarding | Access | Page |
| 7 | Workspace Overview | Organization/user | Primary page |
| 8 | Deals | Organization/user | Primary page |
| 9 | Deal Overview | Deal | Page |
| 10 | Mandates | Organization or deal | Primary page |
| 11 | Mandate Detail | Mandate | Deep page |
| 12 | Documents | Active deal | Primary page |
| 13 | Document Detail | Document/version | Deep page or drawer |
| 14 | Findings | Active deal | Primary page |
| 15 | Finding Detail | Finding | Deep page or drawer |
| 16 | Workstreams and Tasks | Deal | Deep page |
| 17 | Submission Review | Submission version | Deep page |
| 18 | Information Requests | Deal/finding | Deep page or panel |
| 19 | Decision Package | Deal/workspace | Deep page |
| 20 | Activity | Active deal | Primary page |
| 21 | Validation Cases | Internal validation | Page |
| 22 | Validation Case / Report | Internal validation | Deep page |
| 23 | Team and Access | Organization/deal | Administration page |
| 24 | Organization Settings | Organization | Administration page |
| 25 | Usage and Billing | Organization | Administration page |
| 26 | Readiness | Deal/workspace | Deep page (contextual link from Findings) |
| 27 | Reassessments | Deal | Deep page (contextual link from Findings) |
| 28 | Assertions | Deal | Deep page (contextual link from Findings) |
| 29 | Triggers | Deal | Deep page (reached from the Monitoring mandate structure) |

Surfaces 26-29 were added 2026-09-27 by founder decision D22: they were
built and routed before this table knew about them (see
`07-surface-reconciliation.md`'s non-canonical section) and are now part of
the canonical inventory rather than a disclosed exception.

Create/edit/upload/select-evidence actions should usually use a focused drawer
or dialog rather than spawning another full page.

**Reconciliation note (2026-09-27)**: `07-surface-reconciliation.md` checks
every row above against the actual implementation (route, backend
capability, frontend capability, form - page/panel/drawer/component) and
records one real conflict this table does not yet resolve: four shipped,
backend-complete deal-level destinations (Readiness, Targeted
Reassessment, Monitoring/Triggers, Assertions) exist with no row here.
That file presents options; it does not itself amend this table - the 25
rows above are unchanged pending an explicit founder decision
(`docs/workspace-shift/docs/10-decisions.md` D18).

## Mandate composer experience

The Mandates surface begins with:

- **What do you need accomplished?** — the objective.
- **Context** — the selected engagement/deal and its versioned brief.
- **Evidence** — exact authorized document/submission versions.
- **Starting structure** — Flexible, Review, Pipeline or Monitoring.
- **Controls** — require citations, require human approval before publishing,
  and an honest usage limit when real cost accounting supports it.

The product then displays a readable proposed plan for amendment and approval.
Active mandates remain visible below or in a linked register.

## Interface quality

- Dark Meridian is the current visual direction; clarity and professional
  credibility outrank decorative motion.
- Arabic/English mixed content, narrow widths, keyboard use, focus management,
  reduced motion and accessible status/evidence controls are required.
- Use one design system and shared components for cards, tables, evidence,
  statuses, approvals, empty/loading/error states and dialogs.
- Do not copy a prototype's state-switching mechanism when real routes provide
  better deep links and browser history.
