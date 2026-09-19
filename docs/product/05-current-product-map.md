# Current product map

Status: implemented facts verified against repository revision `692676f` before
the React legacy-exit closure; commit `a7e3fbe` subsequently adds React-native
document upload, brief editing and work/task management. Re-verify against the
current checkout before relying on this map.

## Existing engine and domain assets

The repository already contains substantial working foundations for:

- organizations, users, memberships and development identity sessions;
- deals/projects, versioned briefs, workstreams, assignments and tasks;
- original documents and immutable document versions;
- immutable work-product submission versions and version-specific review;
- PDF, multi-PDF, Excel and cross-format analysis;
- findings, requests, management responses, memo/decision-package workflows,
  exports and audit trails;
- Validation Lab cases, locked answer keys, human scoring and reports;
- mandate templates, plans, approval, durable runs, attempts, checkpoints,
  cancellation, recovery and budget ledger;
- Work-product Integrity Review;
- readiness, decision packages, version dependencies, staleness,
  reassessment and opt-in triggers;
- golden-set, assertion-ledger, deterministic-reconciliation and semantic
  benchmark foundations.

## Current React surface

Verified routes include:

- `/` — deal/project list with a limited attention summary;
- `/projects/:projectId` — Deal Overview;
- `/projects/:projectId/documents` — document register and upload;
- `/projects/:projectId/findings` — reconciliation-backed findings view;
- `/projects/:projectId/mandates` — mandate list;
- `/projects/:projectId/mandates/:mandateId` — planning, approval, run and
  checkpoint detail;
- `/projects/:projectId/work` — workstreams, tasks, comments, submissions and
  review controls;
- `/projects/:projectId/activity` — deal activity.

The React application is built into `static/` and served by the Python server
on port 8765. Older static workflows still exist and must be migrated or
retired deliberately; their existence is not permission to expose a fragmented
user experience.

## Important gaps

- Workspace Overview does not yet provide the complete five-component view.
- Organization-wide Deals and Mandates need the final active-deal/product-shell
  design.
- Findings is not yet the complete unified register across every origin and
  workflow.
- Document and finding details need cohesive React-native experiences.
- Requests, decision packages, validation and team/access administration are
  not yet fully consolidated into React.
- Production authentication, billing, deployment, observability, rate limiting
  and hosted storage are not implemented merely because the local domain model
  exists.
- Frontend automated coverage remains materially thinner than backend coverage.
- The root README historically described an early milestone and must not be
  treated as the complete product definition.

## Migration rule

For every remaining static workflow:

1. Inventory its real user actions and API contracts.
2. Build the React-native equivalent using the same backend source of truth.
3. Test permissions, error states and the browser journey.
4. Remove user-facing links to the static surface.
5. Retain the old page only until parity and rollback confidence exist.
6. Delete it in a later explicit cleanup task.

Removing a link without replacing required behavior is not migration. Keeping
two visible products indefinitely is not acceptable either.
