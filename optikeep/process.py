"""Bound subprocess output and runtime without invoking a shell."""

import os
import selectors
import subprocess
import time


def run_tool(arguments: list[str], timeout: int, limit: int = 4_000_000) -> bytes:
    """Drain both pipes, kill on budget exhaustion and reap on every exit."""
    with subprocess.Popen(
        arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ) as process:
        with selectors.DefaultSelector() as selector:
            for stream in (process.stdout, process.stderr):
                selector.register(stream, selectors.EVENT_READ)
            deadline = time.monotonic() + timeout
            output = bytearray()
            total = 0
            try:
                while selector.get_map():
                    if time.monotonic() >= deadline:
                        raise TimeoutError("Tool exceeded runtime budget")
                    for key, _mask in selector.select(timeout=0.2):
                        chunk = os.read(key.fileobj.fileno(), 65536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        total += len(chunk)
                        if total > limit:
                            raise ValueError("Tool exceeded output budget")
                        if key.fileobj is process.stdout:
                            output.extend(chunk)
                process.wait(timeout=max(0.01, deadline - time.monotonic()))
                if process.returncode:
                    raise RuntimeError("Tool returned an unsuccessful exit status")
                return bytes(output)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
