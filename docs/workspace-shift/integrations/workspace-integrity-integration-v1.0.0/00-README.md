# Workspace Integrity Integration

Version: 1.0.0  
Status: proposed product/roadmap integration  
Prepared from: the current workspace-shift status and roadmap, plus *A Multiplayer Diligence System for Deal Teams*

## Purpose

This package integrates the multiplayer-diligence contribution into the existing AI-native professional workspace without replacing the workspace, mandate runtime, shared findings model, or completed Milestones 1–13.1.

The combined product is:

> A collaborative professional workspace where people and AI execute mandates against shared evidence, while an integrity system reviews sources, submissions and conclusions for contradictions, unsupported assertions and change-driven risk.

## Central decision

The workspace remains the product. Mandates remain the general AI execution mechanism. The friend's contribution becomes a named capability family called **Integrity Review**.

Integrity Review may compare:

- A work-product submission with selected source versions.
- One work product with peer work products.
- A conclusion with the deal brief and explicit assumptions.
- New source versions with previously reviewed findings and conclusions.
- Figures, periods, currencies, entities and derivations across the deal state.

Its results enter the existing shared findings, review, request, task, audit and decision workflows. It must not create a parallel findings silo.

## Adoption order

1. Read `AGENTS.md`.
2. Read `01-current-state.md` and verify it against the live repository.
3. Read `02-product-integration.md` and `03-architecture.md`.
4. Adopt `04-revised-roadmap.md` into the canonical roadmap without deleting historical completion evidence.
5. Continue M13.2, M13.3 and M13.4 in order.
6. Implement the first Integrity Review capability only at M14.2.
7. Use M15 for version dependencies and triggered reassessment.
8. Build the deeper claim ledger and continuous integrity system in M16 only if measured evidence justifies them.

## Files

- `AGENTS.md` — instructions and safety boundaries for an implementing agent.
- `01-current-state.md` — compact verified baseline derived from the supplied status.
- `02-product-integration.md` — product synthesis and terminology.
- `03-architecture.md` — how Integrity Review fits existing modules and data.
- `04-revised-roadmap.md` — dependency-ordered roadmap through M16.
- `05-task-14.2-integrity-review.md` — first bounded implementation mandate.
- `06-m15-change-awareness.md` — dependency and triggered-review mandates.
- `07-m16-continuous-integrity.md` — gated deeper-engine roadmap.
- `08-acceptance-and-evaluation.md` — measurement, validation and release gates.
- `09-decisions-and-non-goals.md` — decisions, deferred questions and prohibited shortcuts.
- `10-adoption-prompt.md` — a ready-to-send instruction for Claude.
- `CHANGELOG.md` — package history.

## Authority

This package proposes an integration. The live repository, its instruction files, canonical status, decisions and actual code remain authoritative. If a statement here conflicts with verified repository state, record the conflict and stop rather than silently forcing this package onto the code.

