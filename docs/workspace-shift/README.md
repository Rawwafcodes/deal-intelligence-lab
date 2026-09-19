# Workspace Shift — portable build specification
Version 1.1.0 · 17 September 2026 · Product direction baseline, extended with the Integrity Review integration (docs-only)

> Adoption status: this package is now part of the application repository.
> Root `AGENTS.md` and `docs/product/README.md` are the current entry points.
> The copy/install/Task 000 instructions below are preserved as historical
> provenance and must not be rerun.

## Start here
This is a specification and agent-handoff repository, **not the application source**.
It formalizes Rawwaf's shift from the Deal Intelligence Lab into a collaborative
AI-native workspace. It builds on, rather than discards, Milestones 1–9.
No application changes, deployments, real-data migrations or paid AI calls were
performed to produce this package.

Terminology: **Workspace** is the product experience; **Organization** is the new
persisted tenant boundary; Milestone 9's per-analysis Workspace remains a legacy record.

Read [the product charter](docs/01-product-charter.md), then
[the baseline](docs/02-existing-baseline.md), then [the roadmap](docs/08-roadmap.md).
Agents must first read [AGENTS.md](AGENTS.md) and [STATUS.md](STATUS.md).

## Definition
A collaborative workspace where professional teams organize engagements and evidence,
commission flexible AI mandates, review human and AI work, resolve issues, and give
senior decision-makers a live, traceable view of submitted work and conclusions.

## Navigation
- [Official direction change and supersession](docs/00-direction-change.md)
- [Product charter and boundaries](docs/01-product-charter.md)
- [Existing assets and evidence limitations](docs/02-existing-baseline.md)
- [Domain model and integrity rules](docs/03-domain-model.md)
- [Mandate engine and AI boundaries](docs/04-mandate-engine.md)
- [Workspace UX and collaboration](docs/05-experience.md)
- [Permissions, security and live state](docs/06-security-and-collaboration.md)
- [Local architecture and migration](docs/07-architecture.md)
- [Dependency-ordered roadmap](docs/08-roadmap.md)
- [Acceptance and evaluation](docs/09-acceptance.md)
- [Decisions and open questions](docs/10-decisions.md)
- [Source provenance](docs/11-sources.md)
- [First agent assignment](tasks/000-adopt-and-audit.md)
- [Reusable task contract](tasks/TEMPLATE.md)
- [Illustrative mandate template](examples/reconciliation-template.json)
- [Agent continuation state](STATUS.md)
- [Change history](CHANGELOG.md)
- [Integrity Review product/roadmap integration (proposed, docs-only, 2026-09-17)](integrations/workspace-integrity-integration-v1.0.0/00-README.md)

## Use with Claude Code, Codex, or another agent
1. Extract this package somewhere permanent.
2. In the existing app repository, add its contents under `docs/workspace-shift/`.
   Do not overwrite the app's root README, AGENTS.md or CLAUDE.md.
3. Ask the agent to read this package's AGENTS.md and execute task 000 only.
   See [START-HERE.md](START-HERE.md) for the exact instruction.
4. Reconcile with real code and existing repository rules. Commit the documentation
   adoption separately from application implementation.
5. Authorize one bounded implementation task at a time. Record results in STATUS.md.

The ZIP is portable without Git. This folder is also initialized as a local Git
repository; no remote has been created or pushed. If integrating into the app,
copy the contents without its nested .git directory.

## Authority
Latest explicit founder instruction > accepted decisions in this package > implementation
tasks > illustrative examples > historical planning. Code is evidence of what exists,
not proof of what the desired product should be. Conflicts with host-repository rules
must be surfaced, not silently overridden.
