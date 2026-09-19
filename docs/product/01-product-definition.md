# Product definition

## Established direction

The product is a **collaborative AI-native workspace for high-stakes
professional work**. It allows a team to organize engagements, evidence and
human work; commission flexible AI mandates; review findings and submissions;
resolve outstanding matters; and maintain an approved, traceable position for
senior decision-makers.

A deal is an important engagement type inside the workspace. It is not the
outer limit of the workspace concept. The current implementation is deliberately
focused on deals, diligence, financial models and advisory work because that is
where the existing capabilities and evidence are strongest.

The product should not be reduced to any one of these:

- a data room;
- a one-shot deal report;
- a chat wrapper;
- a PDF or spreadsheet parser;
- a task tracker;
- an AI reviewer;
- a document editor.

Its value comes from connecting evidence, AI work, human work, review,
resolution and approved decisions within one continuing workspace.

## Product hierarchy

1. **Organization** — the persisted tenant and access boundary.
2. **Workspace** — the overall product experience across authorized work.
3. **Engagement / deal** — a continuing body of work with a brief, sources,
   people, workstreams, mandates, findings and deliverables.
4. **Workstream** — a configurable area of responsibility such as financial,
   legal or commercial work.
5. **Task and submission** — work assigned to a person and the immutable
   versions they submit.
6. **Mandate** — work commissioned to AI through an approved plan.
7. **Finding, request and decision** — matters discovered, investigated,
   resolved or accepted.
8. **Deliverable** — an approved work product or decision package.
9. **Monitoring / reassessment** — explicit, scoped reactions to later changes.

`Workspace` is also the product term. The existing `workspaces` database table
from Milestone 9 is a preserved per-analysis record and must not be confused
with the organization-wide product concept.

## Users

- **Analyst**: performs assigned work, uses evidence and mandates, submits
  versions and responds to review.
- **Reviewer**: challenges work, records review decisions, requests revisions
  and evaluates supporting evidence.
- **Deal lead / principal**: owns priorities, unresolved exposure, approvals
  and the current decision-ready position.
- **External executive**: sees only deliberately approved/shared material by
  default.
- **Administrator**: manages organization membership, policy and product
  configuration without inheriting unrestricted substantive authority merely
  from being an administrator.

The product is inherently collaborative. Local development may use development
identities, but the domain must not be designed as single-user software.

## Core value loop

1. Establish the engagement brief and authorized evidence.
2. Assign human work or commission an AI mandate.
3. Produce findings, submissions or deliverables with visible provenance.
4. Review the exact version and its evidence.
5. Resolve, revise, approve or accept residual risk.
6. Preserve history and identify what later evidence may have made stale.

The intelligence attracts users by finding and checking important matters. The
workspace retains them by coordinating how those matters are investigated,
resolved and approved.

## Product principles

- The engagement—not an analysis run—is the persistent centre of work.
- One findings register receives AI, integrity-review and human-origin matters
  with explicit lineage.
- Human response, evidence receipt, evidence review, work-product correction
  and closure approval are separate events.
- Senior oversight shows decision exposure and review coverage, not employee
  surveillance or simplistic productivity scores.
- The interface must distinguish draft, proposed, reviewed, approved, rejected,
  stale and unresolved states.
- The system must disclose uncertainty and missing evidence instead of creating
  false completeness.

## Non-goals

- Rebuilding Microsoft Office or Google Workspace.
- Replacing every virtual data room feature.
- Autonomous publication or final approval.
- Hidden monitoring of every edit.
- Employee rankings based on citations, revisions or AI judgments.
- A universal pipeline/DAG editor before real workflows require one.
- A new page, execution engine or findings silo for every service.
