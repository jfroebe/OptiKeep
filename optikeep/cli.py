"""Coordinator and daemon command line entry points."""

import argparse
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import httpx
import uvicorn

from optikeep.media import analyze


@contextmanager
def renew_lease(client, task):
    """Keep long-running hashes alive and stop renewal before result submission."""
    stopped = threading.Event()
    failures = []

    def heartbeat():
        """Renew at a bounded interval until analysis has finished."""
        while not stopped.wait(15):
            try:
                response = client.post(
                    f"/api/v1/tasks/{task['id']}/heartbeat",
                    json={"lease": task["lease"]},
                )
                response.raise_for_status()
            except Exception as error:
                failures.append(error)
                return

    worker = threading.Thread(target=heartbeat, daemon=True)
    worker.start()
    try:
        yield
        if failures:
            raise RuntimeError("Analysis lease renewal failed")
    finally:
        stopped.set()
        worker.join(timeout=65)


def main():
    """Start a coordinator or a sequential read-only daemon."""
    parser = argparse.ArgumentParser(description="OptiKeep read-only analysis preview")
    parser.add_argument("mode", choices=["serve", "daemon"])
    parser.add_argument("--url", default="http://127.0.0.1:18766")
    parser.add_argument("--media-root", type=Path, default=Path("/media"))
    args = parser.parse_args()
    if args.mode == "serve":
        uvicorn.run(
            "optikeep.api:create_app",
            factory=True,
            host="0.0.0.0",
            port=18766,
            workers=1,
        )
        return
    token = os.environ["OPTIKEEP_DAEMON_TOKEN"]
    with httpx.Client(
        base_url=args.url, headers={"Authorization": "Bearer " + token}, timeout=60
    ) as client:
        while True:
            response = client.post("/api/v1/tasks/claim")
            response.raise_for_status()
            task = response.json()
            if task is None:
                time.sleep(2)
                continue
            try:
                with renew_lease(client, task):
                    result = analyze(args.media_root, task, 40_000_000, 60)
            except Exception as error:
                response = client.post(
                    f"/api/v1/tasks/{task['id']}/failure",
                    json={"lease": task["lease"], "code": type(error).__name__},
                )
            else:
                response = client.post(
                    f"/api/v1/tasks/{task['id']}/results",
                    json={"lease": task["lease"], "result": result},
                )
            response.raise_for_status()
