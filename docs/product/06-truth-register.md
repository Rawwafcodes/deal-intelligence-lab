# Truth register and open decisions

This register prevents future agents from filling gaps with confident guesses.
It contains no private founder finances, equity details, confidential customer
information, valuation scenarios or deal data because this repository is
public.

## Established product direction

- Workspace is the broader product; deals are continuing engagements inside it.
- Mandates are the AI-work umbrella.
- Flexible, Review, Pipeline and Monitoring are starting structures, not four
  separate execution products.
- Review is a customer workflow; Validation Lab is an internal evaluation
  harness.
- One shared findings lifecycle preserves origin and lineage.
- Collaboration and senior oversight are core, not deployment add-ons.
- AI interprets; deterministic software governs; humans approve consequential
  outcomes.
- React is the permanent customer-facing frontend direction.
- Local product refinement continues before and after hosted deployment.
- No employee surveillance/leaderboards and no autonomous final approval.

## Implemented facts

The detailed, revision-specific implementation record lives in
`docs/workspace-shift/STATUS.md`. The condensed map is in
`05-current-product-map.md`. Agents must re-inspect code rather than assuming a
milestone title proves every intended behavior.

## Working commercial hypotheses

These guide discovery; they are not validated facts:

- A plausible initial segment is a small Saudi/GCC advisory team handling
  bilingual, multi-person financial/deal work.
- A bounded Integrity/Diligence Review for one engagement may be easier to buy
  initially than organization-wide workflow replacement.
- Intelligence can create initial demand; the workspace can create retention.
- Early commercial packaging may be per-engagement or a platform fee with
  included usage, with isolated deployment priced separately.

No repository document may claim customer demand, willingness to pay,
retention, product-market fit or a defensible company valuation without new
evidence.

## Open product decisions

Full milestone-by-milestone detail, entry/exit criteria and an explicit
open-decisions/external-dependencies register for the approved path from
the completed local product (M17) to a secured, hosted, commercially
piloted and repeatably sold one (M18-M25) live in
`docs/workspace-shift/docs/13-post-m17-roadmap.md`
(`docs/workspace-shift/docs/10-decisions.md`'s D17/D18). The items below
are not superseded by that document; M20 is where several of them get
answered with real evidence.

`07-surface-reconciliation.md` is the code-verified status of every
canonical surface in `02-experience-and-information-architecture.md`'s
25-surface table, plus a real conflict it discloses rather than resolves
(four shipped destinations - Readiness, Reassessments, Triggers,
Assertions - outside that table) and three confirmed-absent
administrative surfaces (Team and Access, Organization Settings, Usage
and Billing) already routed to M19/M20/M23 below rather than left
unaccounted for.

- Final product and company name.
- Exact first customer segment and buyer title.
- First paid offer and its deliverable boundary.
- Pricing, usage inclusion and overage policy.
- Which existing mandate templates appear in the first market-facing product.
- The final organization-wide shell and active-deal interaction.
- When old static validation and analysis result pages are fully migrated.
- Which independently reviewed real cases establish acceptable precision,
  recall and false-positive performance.

## Open production decisions

These are the exact inputs M19's own "required architecture decision"
inspects and compares before implementation - see
`docs/workspace-shift/docs/13-post-m17-roadmap.md`'s M19 section.
Provider/hosting selection is deliberately deferred to that milestone;
no mention of any provider anywhere in this repository is a decision.
Production identity provider and Team/Access/Organization-Settings
administration are also where `07-surface-reconciliation.md`'s three
confirmed-missing administrative surfaces (#23-25) land: a working
minimum at M19 for private staging, the full self-serve version at M23.

- Hosting and service boundaries.
- Managed database and object-storage providers.
- Production identity provider and invitation model.
- Data residency and regulated-customer deployment options.
- Provider/model routing and real cost accounting.
- Security review, incident response and availability objectives.
- Incorporation, contracts, privacy terms and professional-liability treatment.

These are not blockers to local product development, but they are blockers to
claiming production readiness for confidential customer use.

## Private company context

Founder governance, ownership, contributions, budgets, acquisition scenarios,
prospect identities, interview notes and private financial models belong in a
separate private company repository. The public application repository should
contain only sanitized decisions that an implementation agent genuinely needs.

If private context changes a product requirement, record the sanitized product
decision here or in `docs/workspace-shift/docs/10-decisions.md`; do not copy the
private source material into this repository.
