# Local PostgreSQL (Task 11.3a)

This app's data lives in a local PostgreSQL database instead of SQLite as of
Task 11.3a (see `docs/workspace-shift/docs/10-decisions.md`, decision D11).
There is no system service auto-starting it — start it yourself before
running the app or the tests.

## Where it lives

- Data directory: `pgdata/` (gitignored, created by `initdb`)
- Unix socket directory: `pgsocket/` (gitignored)
- Port: `5544` (chosen to avoid clashing with any other local Postgres)
- Database name: `deal_lab`
- No password (`trust` auth over the local Unix socket only — nothing
  listens on a TCP/network port)

The Postgres server binaries (`initdb`, `pg_ctl`, `postgres`, `psql`,
`createdb`) came from `conda install -c conda-forge postgresql` into the
existing Anaconda environment — no Homebrew, no sudo, no system-level
changes. The Python client driver (`psycopg2-binary`) is a normal
`requirements.txt` dependency in the app's own `venv/`, independent of
where the server binaries live.

## Starting it

```bash
export PATH="/Users/rawwafa/anaconda3/bin:$PATH"
cd ~/Projects/deal-intelligence-lab
pg_ctl -D pgdata -l pgdata.log -o "-p 5544 -k $(pwd)/pgsocket -h ''" start
```

(`-h ''` disables TCP listening entirely — Unix socket only.)

## Stopping it

```bash
export PATH="/Users/rawwafa/anaconda3/bin:$PATH"
cd ~/Projects/deal-intelligence-lab
pg_ctl -D pgdata stop
```

## Connecting with `psql` directly

```bash
export PATH="/Users/rawwafa/anaconda3/bin:$PATH"
cd ~/Projects/deal-intelligence-lab
psql -h "$(pwd)/pgsocket" -p 5544 -d deal_lab
```

## First-time setup (already done once for this checkout)

If `pgdata/` doesn't exist yet (e.g. a fresh clone/checkout):

```bash
export PATH="/Users/rawwafa/anaconda3/bin:$PATH"
cd ~/Projects/deal-intelligence-lab
initdb -D pgdata --auth=trust -U "$USER" -E UTF8 --locale=en_US.UTF-8
mkdir -p pgsocket
pg_ctl -D pgdata -l pgdata.log -o "-p 5544 -k $(pwd)/pgsocket -h ''" start
createdb -h "$(pwd)/pgsocket" -p 5544 deal_lab
```

## Overriding connection settings

`store.py` reads these environment variables (all optional; the defaults
above are baked in and match this checkout's setup exactly):

- `DEAL_LAB_PG_HOST` (default: `<repo>/pgsocket`)
- `DEAL_LAB_PG_PORT` (default: `5544`)
- `DEAL_LAB_PG_DBNAME` (default: `deal_lab`)
- `DEAL_LAB_PG_USER` (default: `$USER`)

## Test isolation

Tests never touch the real `public` schema. Each test file creates its own
throwaway Postgres schema (via `store.ensure_schema(name)` /
`store.SCHEMA = name`), runs entirely inside it, and drops it afterward
(`store.drop_schema(name)`) — the same role a fresh temp SQLite file used
to play, just as a schema instead of a file.

## The old SQLite database

`data/deal_lab.db` (and its Task 11.2 backup, `data/deal_lab.db.bak-*`) are
kept on disk, untouched, as a permanent historical reference — they were
never written to during the Postgres migration, only read from once by
`migrate_sqlite_to_postgres.py`. Nothing in the running app reads them
anymore.
