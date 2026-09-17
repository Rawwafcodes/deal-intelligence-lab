# Architecture Decision and Migration Plan

All figures below are from official documentation, fetched directly this session
(dates/sources cited inline); anything not sourced this way is explicitly marked as
an assumption. Nothing in this document provisions, deploys, or purchases
anything — it's a recommendation for founder approval.

## The two options, compared against this specific codebase

### Option 1 — Python web app + background-worker deployment

One Python codebase, two service processes from the same deploy (a web service
answering HTTP requests, a background worker running analysis jobs), one
managed Postgres. Concretely: [Render](https://render.com) or
[Fly.io](https://fly.io) hosting both a "Web Service" and a "Background Worker"
resource from the same repo, sharing one environment-variable group; Postgres
either from the same provider or from [Neon](https://neon.com).

### Option 2 — Vercel (interface) + Neon (Postgres) + a separate Python worker

The interface (today's static pages, or the `frontend/` React scaffold if
adopted) and any thin API routes on Vercel; the actual long-running analysis
work on a separately hosted Python worker (Render/Fly, as above); Neon for
Postgres either way.

### Why Option 1 fits this codebase and Option 2 doesn't, concretely

| Constraint | Evidence | Verdict |
| --- | --- | --- |
| Analysis calls already run up to **1800 seconds** by this app's own existing timeout (`ANALYSIS_CLIENT_TIMEOUT_SECONDS = 1800.0` in `xlsx_inspection.py`/`cross_format_analysis.py`, sometimes with multiple `pause_turn` continuations in sequence — genuinely long, not a hypothetical) | Vercel Functions: 300s default/max on **Hobby**; 800s max on Pro/Enterprise **generally available**; 1800s only as an **extended maximum currently in beta**, requiring function-level config and specific runtime versions ([Vercel Functions Limits](https://vercel.com/docs/functions/limitations), fetched this session) | Building this app's actual critical path on a beta ceiling that exactly equals today's own worst case, with no margin, is not a foundation to recommend. A real background worker has no such ceiling. |
| Uploads today reach **500 MB** per request (`documents.MAX_UPLOAD_BYTES`), and a single reconciliation's combined PDFs alone are capped at **23.5 MB** (`pdf_inspection.MAX_PDF_SOURCE_BYTES`) | Vercel Functions: **4.5 MB hard cap** on request/response body, full stop (same source) | Every existing upload and every existing analysis-submission flow in this app already exceeds Vercel's function body limit by 5–100×. A Vercel-fronted version would need every upload rewritten to a direct-to-storage presigned-URL flow before Vercel could touch it at all — real rework with no offsetting benefit, since the worker still has to exist regardless. |
| The whole codebase is Python; there is no existing Next.js/Vercel-specific asset in production today (`frontend/` is real but unintegrated and its adoption is a deferred Milestone 12 decision per `01-baseline-inventory.md`, not a Vercel dependency even if adopted — a static React build is servable from anywhere) | — | Splitting "interface" onto a second platform and runtime buys nothing today and adds a second deploy pipeline, a second secrets store, and CORS/session-sharing across two origins — direct, avoidable cost against the explicit "operational burden for a nontechnical founder" requirement. |
| Postgres connection-pooling-at-scale, which the hybrid's Neon choice specifically solves for | Neon's pooled connection string uses PgBouncer in transaction mode, supporting up to **10,000 client connections** ([Neon connection pooling docs](https://neon.com/docs/connect/connection-pooling), fetched this session) | This benefit is **independent of Vercel** — Option 1 can and should use Neon for exactly the same reason (below), without needing Vercel to get it. |

**Recommendation: Option 1**, using Neon for Postgres regardless (its pooling
and branching are valuable for both options — see below), with the web+worker
pair on Render as the concrete first choice and Fly.io named as a credible
alternative if regional/networking needs change later. This is not "reject
everything Vercel offers" — it's "the one piece of the hybrid worth keeping
(Neon) doesn't require adopting the other piece (Vercel) that this specific
app's own request/duration limits make a poor fit."

## Why Neon specifically, on either option

- **Scale-to-zero on the free tier** (idle compute suspends after 5 minutes;
  configurable on paid tiers) keeps staging's idle cost near zero between work
  sessions — a real fit for a pre-revenue, intermittently-used staging
  environment. ([Neon plans](https://neon.com/docs/introduction/plans), fetched
  this session)
- **Branching** (10 branches included even on Launch) gives a genuinely useful
  operational pattern this app doesn't have today: a disposable database branch
  per test run or per PR, instead of hand-rolled `tempfile.TemporaryDirectory()`
  SQLite databases (which is what the test suite does today — correct for unit
  tests, but doesn't exercise real Postgres-specific behavior).
- **Contrast with Render's own managed Postgres**: Render's *free* Postgres tier
  is deleted after 30 days with no warning ([Render Postgres pricing, via
  search this session] — a real operational trap for a founder who might not
  be watching closely); its paid Starter is $7/month for 256 MB RAM / 1 GB
  storage plus $0.30/GB-month overage. Neon's free tier persists indefinitely
  (just suspends when idle) and its paid Launch tier is pure pay-as-you-go
  ($0.106/CU-hour compute, $0.35/GB-month storage, no flat minimum) — better
  matched to unpredictable early usage than a flat monthly floor. If a single
  vendor for both hosting and database is preferred for billing/operational
  simplicity, Render's own Postgres is a reasonable fallback once past the
  free tier's 30-day deletion risk — named here as the explicit trade-off, not
  hidden.

## What "long-running job support" requires, concretely (the assignment's list)

None of this exists today (confirmed — `server.py` runs every analysis inline,
synchronously, inside the HTTP request handler). Design, not implementation:

- **Persistent status and progress** — an `AnalysisRun` row (per the data model)
  with a `status` column (`queued` → `running` → `succeeded`/`failed`/
  `timed_out`), updated by the worker as it progresses, polled by the browser
  (a simple `GET /runs/{id}` poll is enough at this scale — no need for
  WebSockets yet).
- **Input-version manifests** — `AnalysisRunInput` (per the data model), written
  *before* the job starts, so "what exactly did this run see" is answerable
  even if the job later fails.
- **Timeouts and cancellation** — the existing `ANALYSIS_CLIENT_TIMEOUT_SECONDS`
  pattern carries over directly to the worker process; add an explicit
  "Cancel" action that sets a flag the worker checks between provider calls
  (an in-flight Anthropic request itself can't be interrupted mid-call, but a
  multi-step `pause_turn` continuation loop can stop between steps).
- **Bounded retries** — `MAX_PAUSE_CONTINUATIONS` already exists as a concept
  (`xlsx_inspection.py`, `cross_format_analysis.py`); extend the same bound to
  worker-level retries after an infrastructure failure (worker crash, not a
  provider error), capped and logged, never silent or unbounded.
- **Duplicate-submission protection** — a unique constraint on
  `(work_product_id, submission_version, mandate_version_id)` for an in-flight
  run, so double-clicking "Submit for review" can't start two runs against the
  same input.
- **Recovery from worker interruption** — on worker restart, any run still
  marked `running` with no recent heartbeat gets marked `interrupted`, not
  silently retried — see the next point.
- **Explicit handling of uncertain provider outcomes before retrying** — the
  assignment is specific that retrying an interrupted request is not
  automatically free or safe. If a worker crashes *after* a provider call
  completed (Anthropic has already processed it, possibly already billed
  usage) but *before* the result was persisted, blindly retrying risks a
  duplicate paid call for work that already happened. Design: every provider
  call is preceded by writing a `run_attempt` row with a client-generated
  idempotency reference *before* the call, and the worker's crash-recovery
  path surfaces an `interrupted, outcome unknown` run for a human to
  explicitly choose "retry" or "mark failed" — it never auto-retries an
  interrupted run on its own.
- **Per-run usage records and configurable spending limits** — the raw
  material already exists (`input_tokens`/`output_tokens` columns on every
  analysis table today); add a `cost_usd` estimate per run (computable from
  the recorded model + token counts against Anthropic's published per-model
  pricing) and an organization-level `spending_limit_usd` that a pre-flight
  check compares the current period's summed `cost_usd` against before
  allowing a new run to start.
- **Provider-file cleanup tracking** — already exists and already works
  (`xlsx_inspection.py`'s per-workbook Files-API deletion tracking, recorded
  per attempt) — carries over unchanged onto the worker.

## What must change vs. what's preserved

| Layer | Disposition |
| --- | --- |
| `ai_client.py`, `anthropic_errors.py`, `pdf_inspection.py`, `xlsx_inspection.py`, `cross_document_analysis.py`, `cross_format_analysis.py`, `evaluations.py`, `workspaces.py`, `workspace_exports.py`, `multipart.py`, `store.py`'s dataclass/`to_dict()` convention | **Preserved.** This is "the existing analytical engine" and its supporting modules — moves into the worker process largely unchanged; SQL calls swap from `sqlite3` to a Postgres driver, but the module boundaries don't change. |
| `server.py`'s `http.server`/`BaseHTTPRequestHandler`/regex-dispatch routing | **Replaced**, per the official Python documentation's own warning ("`http.server` is not recommended for production. It only implements basic security checks" — [Python docs](https://docs.python.org/3/library/http.server.html), fetched this session) and its specific, named risks (symlink-following outside the served directory; header injection via unsanitized `send_header()` input). Recommend **FastAPI**: async-native (fits a job-polling API naturally), automatic request validation, and every existing handler method is already a small, single-purpose function that maps directly onto a FastAPI route — this is a mechanical port of routing, not a rewrite of logic. |
| Document storage on local disk (`documents.DATA_DIR`) | **Replaced** for the cloud environments only — object storage (any S3-compatible provider; which one is a founder-approval decision, not fixed here) behind the same `stored_file_path()`-style abstraction, so the rest of the code doesn't need to know where bytes physically live. Local development keeps local disk. |
| SQLite (`store.DB_PATH`) | **Replaced** for staging/pilot — Postgres (Neon, per above). Local development keeps SQLite; the test suite's existing pattern (temp DB per test class) already isolates cleanly and doesn't need to change for local work. |

## Environments

Three, never sharing credentials, databases, or document storage:

1. **Local** — exactly what exists today (SQLite, local disk, `.env.local`).
   Unchanged.
2. **Staging** — synthetic/test data only, Neon Postgres (separate project from
   pilot), separate object-storage bucket, separate Anthropic API key with a low
   spending limit. Every Milestone 12/13/14 acceptance check runs here.
3. **Private pilot** — real users, still not real deal documents until the
   Milestone 15 gate is explicitly approved. Separate Neon project, separate
   bucket, separate API key and spending limit from staging.

No automatic migration of existing real deal documents into any cloud
environment — an explicit, separate, founder-approved step if and when it
happens, per the assignment.

## Cost estimate (idle vs. usage-driven) — labeled assumptions

| Item | Idle (near-zero usage) | Light usage (a handful of deals, occasional runs) |
| --- | --- | --- |
| Render Web Service (Starter) | ~$7/mo | ~$7–25/mo depending on tier |
| Render Background Worker (Starter) | ~$7/mo | ~$7–25/mo depending on tier |
| Neon Postgres | $0 (free tier, scale-to-zero) | Likely still $0–single digits on Launch pay-as-you-go at this scale (0.5 GB storage / 100 CU-hours covers a lot of intermittent staging use) |
| Object storage | Assumption: a few dollars/month at this document volume — not independently priced this session; get a real quote before committing to a provider | Assumption, same caveat |
| Anthropic API usage | $0 (no calls in staging without an explicit, approved run) | Entirely usage-driven — this is the actual variable cost, bounded by the spending-limit design above |
| **Estimated staging floor** | **~$14/month** (two Render services; Neon and storage effectively free at this scale) | Grows primarily with Anthropic usage, not infrastructure |

This is a rough planning estimate, not a quote — actual object-storage and
higher Render/Neon tiers were not independently priced to the same depth as the
figures cited with sources above; get current numbers before committing spend.

## Regions, data handling, backups, logs, secrets — as far as this session can responsibly go

These are real operational requirements but weren't independently re-verified
against current per-provider documentation to the same depth as the pricing/
limits figures above, given this milestone's time budget — flagged here as
**open items for the founder-approval list** rather than asserted as fact:
Render/Fly/Neon region selection and any data-residency requirements the
target customers (banks, advisory firms) might have; Neon's backup/point-in-
time-restore window on each tier; Render's log retention and whether it's
sufficient for audit purposes on its own or needs shipping to a longer-retention
store; secret management (both providers offer environment-variable secrets
with dashboard access control — sufficient for pilot scale, revisit for actual
enterprise customers who may require a dedicated secrets manager).
