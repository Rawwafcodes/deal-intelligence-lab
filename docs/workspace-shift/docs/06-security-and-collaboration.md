# Collaboration and security

## Local identity
Build identities, scoped memberships and server-side authorization locally.
Development user switching is explicit, disabled outside development, loopback-only,
and absent from production routes. Store actor in a server-validated session;
do not trust a free-text owner or arbitrary user header.
Browser profiles test distinct sessions. Organization admins do not automatically gain
client-deal content rights merely by administering accounts.

## Proposed first permissions (confirm in task 000)
| Action | Analyst | Reviewer | Deal lead | External executive |
| --- | --- | --- | --- | --- |
| Read internal deal work | If deal member | If deal member | If deal member | Shared approved subset |
| Create mandate | Within granted capability/budget | Same | Yes within workspace policy | No by default |
| Submit work | Own/assigned | Own/assigned | Yes | No |
| Comment/respond | Authorized records | Authorized records | Yes | Shared requests only |
| Recommend finding disposition | Yes | Yes | Yes | No |
| Approve submissions | No | Assigned reviewer | Yes | No by default |
| Close material issue/accept risk | No | Recommend | Yes | No by default |
| Approve decision package | No | Recommend | Yes | Explicit grant only |
| Change access | No | No | Authorized deal management | No |

Job title does not confer rights. Membership, content visibility, responsibility and
approval power are distinct. Revocation stops reads, downloads, event streams and new
tool fetches. Previously transmitted provider content cannot be recalled by revocation;
record exposure and stop pending work as policy requires.

## Access enforcement
Apply checks to APIs, downloads, search, aggregates, comments, exports, jobs, citations
and AI source retrieval. Cross-workspace/deal references are rejected.
Do not leak inaccessible filenames or issue counts through overview summaries.
Attaching a private deal document to a workspace record must not widen access.
Validation answer keys are evaluator-only and never accessible to AI, including
planner context, tools, search, summaries and logging.

## Untrusted inputs
Source content is data, not authority. Restrict model tools, network/host access,
destinations and actions. Validate proposed actions server-side. Citation validity
does not defend against injected instructions. Maintain adversarial fixtures.
Render model/user text safely. Protect local mutation endpoints from cross-origin
requests and CSRF; local binding alone is not a full defense.

## Exports
Write free text as literal spreadsheet text without changing legitimate numeric/formula
fields created by the application. Test suspicious prefixes/whitespace and round-trip
cell types. Escape HTML; never export secrets or internal paths.

## Retention
Preserve cited versions by default, but do not promise indefinite retention.
Deletion policy must reconcile user obligations and evidence history. If authorized
purging removes bytes, retain a non-sensitive tombstone and indicate unavailable evidence.
Provider cleanup attempt/status is recorded; Files API deletion is not a blanket
guarantee of immediate erasure from all provider systems. Reverify terms before pilot.

## Spending and approvals
Paid execution and external transmissions require scoped approval. Templates cannot
self-authorize larger budgets. Approval applies to an exact plan/version and content
scope. Internal draft creation is distinguishable from published findings and approved
deliverables. No external messages/sends in the first implementation.
