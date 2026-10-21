"""Standalone mandate worker process (Task 19.2, M19).

Runs the same durable worker `server.py` runs in-process locally, as its own
process - the hosted deployment's separate worker service, so long analyses
run independently of the web service and survive its restarts. Several can
run at once: runs are claimed atomically and recovered only after their
owner's heartbeat lease expires (see mandates.Worker).

Stops on SIGTERM/SIGINT (what hosting platforms send on redeploy). A
capability call already in flight cannot be interrupted; if the process is
killed before it finishes, the run is recovered by another worker once the
lease expires - as outcome_unknown, never silently retried.
"""

from __future__ import annotations

import os
import signal
import threading

import observability
import server
import store


def non_local_database_without_environment() -> bool:
    """True when DATABASE_URL points at a real hosted database but nothing
    deliberately configured this as a hosted worker - see main()'s own
    guard for why that's refused, not just risky."""
    return bool(
        store.DATABASE_URL
        and not store.is_local_database_url(store.DATABASE_URL)
        and not os.environ.get("DEAL_LAB_ENVIRONMENT")
    )


def main() -> None:
    # Same gap as server.py's own dev-mode guard (Task 19.7/20.4): a
    # developer's .env.local can carry a real hosted DATABASE_URL even
    # though its own comment says "leave unset locally". Running this
    # worker against it would silently claim and execute real mandate
    # runs - real paid AI calls - against staging data from a local
    # machine. DEAL_LAB_ENVIRONMENT is the signal a deliberate hosted
    # worker is already configured with one (set on the real Railway
    # worker service); its absence means nothing intentionally set this
    # up as hosted.
    if non_local_database_without_environment():
        raise SystemExit(
            "Refusing to start: DATABASE_URL points at a non-local database but "
            "DEAL_LAB_ENVIRONMENT is unset, so this doesn't look like a deliberately "
            "configured hosted worker. This would otherwise claim and execute real "
            "mandate runs against that database. If this is deliberate, set "
            "DEAL_LAB_ENVIRONMENT; otherwise unset DATABASE_URL (check .env.local)."
        )
    observability.init("worker")
    server.init_databases()
    worker = server.worker_from_env()
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    worker.start()
    print(f"Mandate worker {worker.worker_id} running. Stop with SIGTERM or Ctrl+C.")
    stop.wait()
    worker.stop()


if __name__ == "__main__":
    main()
