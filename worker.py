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

import signal
import threading

import server


def main() -> None:
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
