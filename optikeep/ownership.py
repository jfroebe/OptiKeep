"""Prevent simultaneous authoritative coordinators for either backend."""

import fcntl
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def coordinator_lock(db, state_root: Path):
    """Hold a filesystem lock and a dedicated PostgreSQL session lock."""
    lock_path = state_root / "coordinator.lock"
    if db.engine.dialect.name == "sqlite":
        lock_path = (
            Path(db.engine.url.database).resolve().with_suffix(".coordinator.lock")
        )
    with lock_path.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError(
                "Another coordinator owns this state directory"
            ) from error
        with db.engine.connect() as connection:
            if db.engine.dialect.name == "postgresql":
                held = connection.exec_driver_sql(
                    "SELECT pg_try_advisory_lock(1735287142)"
                ).scalar()
                if not held:
                    raise RuntimeError("Another coordinator owns this database")
            try:
                yield
            finally:
                if db.engine.dialect.name == "postgresql":
                    connection.exec_driver_sql("SELECT pg_advisory_unlock(1735287142)")
                fcntl.flock(stream, fcntl.LOCK_UN)
