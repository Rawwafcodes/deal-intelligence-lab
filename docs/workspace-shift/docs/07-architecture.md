# Local-first architecture
Status: boundaries accepted; specific framework choices require code inspection.

## Shape
Browser UI → application API/domain services → database and private file store.
A separate local worker executes persistent jobs → provider adapters → authorized AI API.
Same repository and domain rules. No microservice estate required.

## Build locally, collaboratively
Local multi-session identities and permissions from the beginning.
Worker persistence, concurrency handling and API isolation are local requirements,
not future hosting tasks. Provide simple documented start commands or a launcher.
Bind development services to loopback; no tunnels or LAN exposure without approval.

## Existing assets
Preserve Python intelligence through adapters. Migrate one representative analysis
flow first and retain legacy links. Add run registry records pointing at legacy tables;
do not force a destructive all-table rewrite.
Inspect React/Vite scaffold and static UI; decide once before permanent new UI.
A component UI is a candidate, not a mandated rewrite.
A maintained Python web framework is a candidate for shared API/session/job needs;
choose based on actual code, not the old no-dependencies constraint.
New dependencies require a concrete purpose, not automatic rejection.

## Database
Run a focused SQLite contention and recovery spike before M11.3 makes collaborative
persistence load-bearing. Exercise two authenticated sessions plus the worker against
representative writes, with WAL both disabled and deliberately configured; test lock
waits, revision conflicts, interrupted transactions, restart recovery and backup.
Record the result and choose rather than assuming.

SQLite can support an isolated local proof if that spike passes. If local worker and
concurrent editing expose limits, adopt Postgres locally; cloud is not required.
Record one deliberate development database strategy. Do not promise indefinite
dual-dialect support or describe Postgres migration as merely swapping a driver.
Use versioned migrations, backup/restore tests and rollback/forward-repair plans.

## Storage
Keep bytes outside code. Separate a document storage interface from path details.
Originals are immutable versions; API inputs use IDs, never arbitrary host paths.
Later object storage/direct uploads are possible without redesigning record identity.

## Efficient AI
Use manifests, scoped context and existing capabilities; allow relevant-source discovery.
Do not force every PDF into extracted text or treat an LLM summary as a lossless source.
Record what was actually opened and omitted. Reuse outputs only with provenance.
Avoid full-room reruns for ordinary comments. No paid AI to compute basic dashboard counts.

## Deferred online transition
Authentication provider, hosting, managed database, object storage, region, residency,
backups, disaster recovery, rate limits and operational monitoring require a later gate.
No service or pricing locked in here. Prior Vercel/Neon/Render figures are historical.
A frontend host with a separate worker is not inherently invalid. Check current primary
documentation when choosing infrastructure; no deployment is authorized by this spec.
