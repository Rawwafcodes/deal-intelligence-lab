# Multi-firm-per-deal ("Path B") — architecture decision report

Status: proposal awaiting founder approval. Nothing in this report has been
implemented. Mirrors the process `tasks/19.1-architecture-decision-report.md`
used for M19: compare options, recommend an approach, costs and risks named
up front, no schema or code change until the founder approves it.

## Where this came from, and where it sits in the roadmap

This was not planned work. It surfaced from comparing Ghassan's investor
deck against the real product: the deck's "every firm that runs a deal
through it becomes a user" vision (p.11) and "Client Room" (p.6–8) imply
several separate organizations collaborating inside one deal. The founder
chose "Path B" — build toward that, properly, rather than the cheaper
"guest member" workaround ("Path A") discussed first.

**This is not in `08-roadmap.md` or `13-post-m17-roadmap.md` at all.**
Those documents assume a single-organization-per-deal model throughout.
Whether this becomes its own milestone, folds into M20, or runs alongside
it is an open question this report does not answer — that's the founder's
to place, not an engineering decision.

## The current model, exactly as built

- `project_organizations(project_id PRIMARY KEY, organization_id, ...)` —
  a deal belongs to **exactly one** organization. The primary key makes a
  second row for the same deal impossible without a schema change.
- `deal_memberships(id, project_id, user_id, role, revoked_at)` — flat
  per-user role (`analyst` / `reviewer` / `deal_lead` / `external_executive`).
  No organization reference on the row itself.
- The tenant-isolation check (Task 19.5, `server.py` around line 2359) is
  one specific line: granting deal access requires
  `identity.get_organization_role(org_id, user_id) is not None`, where
  `org_id` is the deal's single owning organization. This is what makes
  cross-organization access impossible today, and it's a deliberate,
  tested boundary (`P04`, `10-decisions.md`): cross-organization and
  cross-deal denial is explicitly covered by `test_authorization_matrix.py`.

**One thing worth knowing before scoping this as bigger than it is**:
`organization_memberships` has no constraint limiting a user to one
organization — `list_organization_memberships_for_user()` already returns
a list, plural. The data model already tolerates a user belonging to
several organizations. The actual blocker is narrower than "rebuild
tenancy" — it's specifically: (1) a deal can only ever belong to one org,
and (2) deal membership doesn't record which org a member is representing
on that specific deal.

## Recommended approach: additive, phased, reversible

### Phase 1 (what this report asks approval for)

1. **New table `deal_parties`**: `(id, project_id, organization_id,
   party_role, created_at)`, `UNIQUE(project_id, organization_id)`. Holds
   every organization with access to a deal beyond its owning org —
   `party_role` a small fixed set to start (`counterparty`, `legal_counsel`,
   `lender`, `other`), not free text, so the UI and any future
   party-based rule can rely on a known vocabulary.
2. **`deal_memberships` gets a new `organization_id` column** (nullable,
   backfilled at grant time from the member's resolved org), recording
   which firm a given member represents on that specific deal.
3. **The one grant-check line changes**: from "member of the deal's single
   owning org" to "member of the owning org **or** of an org listed as a
   `deal_party` for this project." This is a narrow, explicit, per-deal
   carve-out — not a blanket cross-org allowance. An organization must be
   deliberately added as a party to a specific deal (a new, separate,
   more consequential action than adding a member) before anyone from it
   can be granted access. Default-deny for every other organization is
   unchanged, and `test_authorization_matrix.py`'s existing cross-org
   denial tests should still pass unmodified for any org never added as a
   party — only new tests for the explicit-party-grant path are additive.
4. **A new capability, gated more tightly than ordinary membership
   management**: who can add a *new organization* as a deal party at all.
   Recommended: the deal lead only, same as membership management today —
   this is bringing in an entire outside firm's future members, not one
   person.
5. **Billing stays simple**: the deal's existing owning organization
   (`project_organizations`, unchanged) remains the sole cost owner for AI
   usage regardless of which party commissions a mandate. Not solving
   multi-payer billing now.
6. **Authorization matrix is unchanged** in Phase 1. Every party's members
   still get one of today's four flat roles, applied exactly as today —
   no party-based document/workstream visibility yet. This is deliberately
   the cheap, real slice: it already satisfies the deck's literal
   scenario (an invited counterparty contact answering a scoped request)
   without yet solving "legal counsel should never see the financial
   model regardless of role," which is a harder, separate problem.

Migration: purely additive. Every existing deal gets no new row at all in
`deal_parties` (it doesn't need one — its own org is still reachable via
the unchanged `project_organizations` check) and needs no backfill for
existing `deal_memberships` rows beyond optionally setting their new
`organization_id` to the deal's existing single org for consistency.
Nothing about an existing deal's behavior changes.

### Phase 2 (explicitly deferred — its own future decision, not part of this approval)

- Party-role-aware authorization: document/workstream visibility scoped to
  which party a role belongs to, not just the flat role.
- A real multi-payer billing/cost-ownership model, if "owning org always
  pays" turns out not to be enough.
- Updating `01-product-definition.md`'s product hierarchy, which currently
  states Organization strictly above Engagement/deal — Phase 1 doesn't
  technically violate this (a deal still has exactly one *owning*
  organization), but Phase 2's full vision would, and that's a product-
  definition change that deserves its own explicit founder sign-off, not
  a side effect of a schema migration.

## Risk and cost

Low. Two new/changed tables, additive and nullable, no destructive
migration. One behavior-changing line in `server.py`, directly adjacent to
existing, passing tenant-isolation tests that would need new cases added
(not modified) to cover the explicit-party-grant path. No infrastructure,
deployment, or cost impact — this is a local schema/code change, not a
staging change.

## Open questions for the founder, not decided here

1. Where does this sit relative to the roadmap — its own milestone,
   folded into M20, or run alongside it?
2. Is the fixed `party_role` vocabulary (`counterparty` / `legal_counsel`
   / `lender` / `other`) enough to start, or does it need to be
   configurable sooner?
3. Deal lead only for adding a new organization as a party, or should an
   organization admin also be able to?
4. Confirm "owning org always pays" is acceptable for now.

## What approval means

Approving this report authorizes Phase 1 only: the schema change, the
grant-check change, and the new capability for adding a deal party —
built and tested locally, same as every other change in this repo.
Nothing here authorizes touching staging, since this is domain-model work,
not infrastructure. Phase 2 is out of scope for this approval entirely and
returns as its own report if and when it's wanted.
