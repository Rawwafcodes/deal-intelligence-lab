# Official direction change
Status: product direction established from the founder's explicit conversation.
Detailed implementation choices remain proposals where labeled.

## What changes
| Earlier framing | Current direction |
| --- | --- |
| Lab/report is the product | Collaborative professional workspace is the product |
| Workspace per analysis or per deal | Team workspace contains deals and optional deal-independent mandates |
| Investigator and reviewer as the only AI roles | Mandates encompass investigation, review, production, pipelines and monitoring |
| One feature/module/page per service | Shared mandate execution with configured methods and reusable capabilities |
| Collaboration added during staging | Identity, responsibility, permissions and shared state built locally |
| Senior dashboard added at the end | Principal oversight is a core user journey, populated incrementally |
| Cloud milestone as immediate destination | Complete and validate the intended local workflow first |
| More planning creates implementation progress | Only tested code is implementation; specs remain specs |

Product wording remains **workspace**. In the data model, the new tenant boundary is
**Organization** so it cannot be confused with Milestone 9's already-shipped,
per-analysis `workspaces` table. The legacy record remains intact.

## What stays
Original-document access, PDF/Excel understanding, citation lineage, human judgment,
cross-format reconciliation, blind evaluation, findings workflow, requests, memo review,
audit history and the useful assets from Milestones 1–9.

## Explicit supersession
This package replaces conflicting recommendations in the eight earlier M10 planning
documents. They remain historical sources, not executable assignments.
In particular, do not carry forward:
- fingerprint-as-primary-identity and reparsing historical findings on every read;
- a new redundant DealWorkspace record above every Project;
- testing by editing the real Universal Logic workspace;
- two separate intelligence silos;
- frontend selection after building the new permanent UI;
- cloud hosting as a prerequisite for collaborative development;
- a mandated immediate consolidation of all analysis tables;
- citation checking as a sufficient prompt-injection defense;
- a permanently single-user architecture.

## Careful corrections to conversational shorthand
- Flexible does not mean every new service is code-free: new tools and file formats
  require implementation, security review and testing.
- Native inputs are subject to actual model/provider limitations. Do not promise
  arbitrary document counts or whole-workspace comprehension.
- Local app does not mean offline AI. Calling Anthropic transmits selected content.
- An in-progress provider operation may consume money after local cancellation.
- A valid reference is not proof that a conclusion is true.
- Local live multi-user testing is possible; it does not establish internet security.
- Product direction is adopted here; application migration is not yet performed.
