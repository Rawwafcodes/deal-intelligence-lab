# Canonical product context

Status: established product direction unless a statement is explicitly labelled
otherwise.

This folder is the shortest reliable explanation of what this repository is
building. It does not replace the detailed specifications under
`docs/workspace-shift/`; it gives founders and implementation agents a stable
entry point into them.

## Read order

1. [Product definition](01-product-definition.md)
2. [Experience and information architecture](02-experience-and-information-architecture.md)
3. [Mandates and intelligence](03-mandates-and-intelligence.md)
4. [Build and delivery rules](04-build-and-delivery-rules.md)
5. [Current product map](05-current-product-map.md)
6. [Truth register and open decisions](06-truth-register.md)

Then read the relevant detailed sources:

- `docs/workspace-shift/docs/03-domain-model.md` for persistent concepts and integrity rules.
- `docs/workspace-shift/docs/06-security-and-collaboration.md` for permissions.
- `docs/workspace-shift/docs/08-roadmap.md` for dependency ordering.
- `docs/workspace-shift/docs/10-decisions.md` for accepted and proposed decisions.
- `docs/workspace-shift/STATUS.md` for verified implementation history and current limitations.
- The selected task file in `docs/workspace-shift/tasks/` before implementing it.

## Authority

When sources disagree, use this order:

1. The founder's latest explicit instruction.
2. Accepted decisions in `docs/workspace-shift/docs/10-decisions.md`.
3. This canonical product context.
4. The active bounded task specification.
5. Older milestone plans, summaries and prototypes.

Code proves what exists; it does not by itself redefine what the product should
be. A visual prototype proves a design intention; it does not prove that the
corresponding workflow is implemented.

## Claim labels

These documents use the following meanings:

- **Established direction**: explicitly accepted product intent.
- **Implemented fact**: verified in the repository at the recorded revision.
- **Working hypothesis**: plausible but not validated commercially or operationally.
- **Open decision**: founder choice or evidence still required.
- **Deferred**: deliberately outside the present implementation scope.

Do not silently promote a hypothesis into a fact or an open decision into an
implementation mandate.
