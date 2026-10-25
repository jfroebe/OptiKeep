"""Coordinator and daemon command line entry points."""

import argparse
import os
import time
from pathlib import Path

import httpx
import uvicorn

from optikeep.media import analyze


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
