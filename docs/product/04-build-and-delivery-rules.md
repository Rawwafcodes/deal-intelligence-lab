# Build and delivery rules

## Repository as the permanent brain

Chat history is not the product specification. The repository contains the
canonical product context, decisions, tasks, implementation status, tests and
rollback history. Coding agents are replaceable executors.

Every substantial change follows:

1. Read root instructions and canonical product context.
2. Inspect the current repository and dirty state.
3. Select one bounded user workflow.
4. State preserved behavior and exclusions.
5. Implement with the smallest necessary architecture change.
6. Test logic, API contracts and the real browser workflow when applicable.
7. Record limitations and update status.
8. Commit separately; push only with explicit authorization.

## Local-first does not mean single-user

Build and validate the coherent product locally first. Identity, roles,
permissions, concurrency, durable jobs and shared state are product features
even before cloud hosting. Development identities are not production
authentication.

The current local architecture should remain usable while the product is
refined. Cloud migration is not a prerequisite for changing the engine,
capabilities or UX later.

## Frontend direction

- React + TypeScript is the permanent application frontend.
- Reuse the existing backend APIs and domain rules.
- Do not build new customer-facing static HTML pages.
- Port old static workflows incrementally, then remove their visible links.
- Keep one coherent navigation and design system.
- Rebuild interactions as React components; do not paste vanilla DOM code into
  React.
- After frontend changes, run the frontend build and copy the production output
  into `static/` using `scripts/build-frontend-into-static.sh` until CI replaces
  that manual step.

## Backend direction

- Preserve the tested Python intelligence modules and narrow capability
  adapters; do not rewrite them merely to adopt a fashionable stack.
- PostgreSQL is the current local source of truth.
- Long-running analysis runs as durable work, not a browser request that dies
  when the tab closes.
- Every endpoint independently verifies identity, organization/deal membership,
  source ownership and allowed transitions.
- Uploaded bytes remain outside Git. Never commit real deal data, provider
  traces, secrets or database dumps.

## Deployment sequence

Product development remains possible before deployment and after deployment.
The practical sequence is:

1. Coherent local product and representative workflows.
2. Production-readiness audit and architecture decision.
3. Separate local, staging and private-pilot environments.
4. Production authentication, secrets, storage, background work, observability,
   backups, rate limits and incident controls.
5. Controlled market launch and continued capability/UX iteration.

Do not choose Vercel, Neon, Supabase or another provider merely because it was
mentioned in conversation. Select infrastructure against verified runtime,
data-residency, security, cost and operational requirements. The Python
analysis engine may remain a service even if the web frontend uses another
hosting platform.

## Online-readiness areas

Before confidential customer use over the internet, explicitly address:

- production authentication and invitations;
- authorization and tenant isolation tests;
- private object storage and encryption;
- managed PostgreSQL and migrations;
- durable worker/queue execution;
- secrets management;
- CSRF, upload and prompt-injection controls;
- rate limiting and usage controls;
- logs, error tracking and audit retention;
- backups, restoration and availability targets;
- CI/CD, preview/staging separation and rollback;
- data location, retention, deletion and provider terms.

No milestone number alone certifies production safety. Production readiness is
a separate evidence-based gate.

## Scope discipline

- Do not combine a product feature, framework migration and cloud deployment in
  one mandate unless unavoidable.
- Do not turn every possible future need into infrastructure now.
- Do not claim a mocked test proves a live provider integration.
- Do not mutate real deal data for acceptance testing.
- Do not make paid model calls or transmit documents without explicit authority.
