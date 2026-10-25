"""Coordinator-owned discovery, analysis result validation and run barriers."""

import hashlib
import json
import os
import time
from pathlib import Path

from sqlalchemy import func, insert, select, update

from optikeep.config import Settings
from optikeep.db import Database, files, identifier, records, runs, tasks
from optikeep.media import ALGORITHM, IMAGES, VIDEOS, cache_key, identity


class Coordinator:
    """Keep durable run state authoritative while daemons stay read-only."""

    def __init__(self, db: Database, settings: Settings):
        """Bind persistence and validated resource settings."""
        self.db = db
        self.settings = settings

    def discover(self, trust_cache: bool = False) -> str:
        """Stream a complete manifest with bounded database write batches.

        Trusted cache mode is explicit because stat equality is not byte proof.
        No scan in this implementation permits filesystem mutation.
        """
        run_id = identifier()
        with self.db.write() as conn:
            conn.execute(
                insert(runs).values(
                    id=run_id,
                    state="DISCOVERING",
                    created=time.time_ns() // 1000,
                    sealed=0,
                )
            )
        try:
            root = self.settings.media_root.resolve(strict=True)
            batch = []
            # A depth-first generator avoids retaining the entire directory tree.
            for path in self._walk(root):
                extension = path.suffix.lower()
                if extension not in IMAGES | VIDEOS:
                    continue
                observed = identity(path)
                relative = path.relative_to(root).as_posix()
                batch.append(
                    dict(
                        id=identifier(),
                        run_id=run_id,
                        path=relative,
                        identity=json.dumps(observed, sort_keys=True),
                        kind="image" if extension in IMAGES else "video",
                        cache_key=cache_key(relative, observed),
                    )
                )
                if len(batch) >= self.settings.batch_size:
                    self._persist(batch, trust_cache)
                    batch = []
            if batch:
                self._persist(batch, trust_cache)
            with self.db.write() as conn:
                conn.execute(
                    update(runs)
                    .where(runs.c.id == run_id)
                    .values(state="ANALYZING", sealed=1)
                )
        except BaseException as error:
            with self.db.write() as conn:
                conn.execute(
                    update(runs)
                    .where(runs.c.id == run_id)
                    .values(state="INCOMPLETE", error=type(error).__name__)
                )
            raise
        return run_id

    def _walk(self, root: Path):
        """Traverse depth-first without following symlinks or hiding I/O errors."""
        with os.scandir(root) as entries:
            for entry in entries:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    yield from self._walk(Path(entry.path))
                elif entry.is_file(follow_symlinks=False):
                    yield Path(entry.path)

    def _persist(self, batch: list[dict], trust_cache: bool):
        """Resolve a batch of cache keys with one query rather than N queries."""
        with self.db.write() as conn:
            valid = (
                set(
                    conn.execute(
                        select(records.c.key).where(
                            records.c.key.in_([row["cache_key"] for row in batch])
                        )
                    ).scalars()
                )
                if trust_cache
                else set()
            )
            conn.execute(insert(files), batch)
            conn.execute(
                insert(tasks),
                [
                    dict(
                        id=identifier(),
                        file_id=row["id"],
                        state="COMMITTED" if row["cache_key"] in valid else "PENDING",
                        attempt=0,
                        expiry=0,
                    )
                    for row in batch
                ],
            )

    def submit(self, task_id: str, lease: str, result: dict):
        """Commit only current, identity-compatible results, with retry safety."""
        serialized = json.dumps(result, sort_keys=True, allow_nan=False)
        if len(serialized.encode()) > 4_000_000:
            raise ValueError("Analysis result exceeds payload budget")
        result_digest = hashlib.sha256(serialized.encode()).hexdigest()
        with self.db.write() as conn:
            query = (
                select(tasks, files.c.identity, files.c.cache_key, files.c.run_id)
                .join(files, tasks.c.file_id == files.c.id)
                .where(tasks.c.id == task_id)
            )
            if self.db.engine.dialect.name == "postgresql":
                query = query.with_for_update(of=tasks)
            row = conn.execute(query).mappings().one()
            if (
                row["state"] == "COMMITTED"
                and row["lease"] == lease
                and row["result_digest"] == result_digest
            ):
                return
            if (
                row["state"] != "LEASED"
                or row["lease"] != lease
                or row["expiry"] < time.time()
            ):
                raise ValueError("Stale or conflicting task lease")
            run_state = conn.execute(
                select(runs.c.state).where(runs.c.id == row["run_id"])
            ).scalar_one()
            if run_state not in {"DISCOVERING", "ANALYZING"}:
                raise ValueError("Run no longer accepts results")
            if (
                result.get("identity") != json.loads(row["identity"])
                or result.get("algorithm") != ALGORITHM
            ):
                raise ValueError("Result identity or algorithm mismatch")
            value = result.get("sha256", "")
            if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
                raise ValueError("Missing whole-file SHA-256")
            existing = conn.execute(
                select(records.c.key).where(records.c.key == row["cache_key"])
            ).scalar()
            if existing:
                conn.execute(
                    update(records)
                    .where(records.c.key == existing)
                    .values(result=serialized, sha256=value)
                )
            else:
                conn.execute(
                    insert(records).values(
                        key=row["cache_key"], result=serialized, sha256=value
                    )
                )
            conn.execute(
                update(tasks)
                .where(tasks.c.id == task_id)
                .values(state="COMMITTED", result_digest=result_digest)
            )

    def fail(self, task_id: str, lease: str, code: str):
        """Record failed analysis without ever counting it as complete."""
        with self.db.write() as conn:
            changed = conn.execute(
                update(tasks)
                .where(
                    tasks.c.id == task_id,
                    tasks.c.lease == lease,
                    tasks.c.state == "LEASED",
                )
                .values(state="FAILED", error=code[:100])
            )
            if changed.rowcount != 1:
                raise ValueError("Stale task lease")

    def status(self, run_id: str) -> dict:
        """Expose explicit incomplete capabilities rather than a false READY."""
        with self.db.engine.connect() as conn:
            run = dict(
                conn.execute(select(runs).where(runs.c.id == run_id)).mappings().one()
            )
            counts = dict(
                conn.execute(
                    select(tasks.c.state, func.count())
                    .join(files, files.c.id == tasks.c.file_id)
                    .where(files.c.run_id == run_id)
                    .group_by(tasks.c.state)
                ).all()
            )
        run.update(
            tasks=counts,
            barrier_open=False,
            mutation_enabled=False,
            blockers=[
                "Czkawka evidence qualification",
                "video fingerprints and quality calibration",
                "matching and action executor qualification",
            ],
        )
        return run

    def exact_candidates(self, run_id: str) -> dict:
        """Return bounded exact-hash candidates without ranking or deletion claims."""
        joined = files.join(tasks, tasks.c.file_id == files.c.id).join(
            records, files.c.cache_key == records.c.key
        )
        with self.db.engine.connect() as conn:
            hashes = list(
                conn.execute(
                    select(records.c.sha256)
                    .select_from(joined)
                    .where(
                        files.c.run_id == run_id,
                        tasks.c.state == "COMMITTED",
                    )
                    .group_by(records.c.sha256)
                    .having(func.count() > 1)
                    .order_by(records.c.sha256)
                    .limit(101)
                ).scalars()
            )
            rows = (
                conn.execute(
                    select(files.c.path, records.c.sha256)
                    .select_from(joined)
                    .where(
                        files.c.run_id == run_id,
                        tasks.c.state == "COMMITTED",
                        records.c.sha256.in_(hashes[:100]),
                    )
                    .order_by(records.c.sha256, files.c.path)
                    .limit(1025)
                )
                .mappings()
                .all()
            )
        groups = {}
        for row in rows[:1024]:
            groups.setdefault(row["sha256"], []).append(row["path"])
        return {
            "groups": groups,
            "truncated": len(hashes) > 100 or len(rows) > 1024,
            "actionable": False,
        }
