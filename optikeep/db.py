"""Portable durable manifest, cache, task lease and evidence schema."""

import json
import time
import uuid
from contextlib import contextmanager

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    create_engine,
    event,
    insert,
    select,
    update,
)

metadata = MetaData()
schema = Table(
    "schema_versions", metadata, Column("version", Integer, primary_key=True)
)
runs = Table(
    "scan_runs",
    metadata,
    Column("id", String, primary_key=True),
    Column("state", String, nullable=False),
    Column("created", BigInteger, nullable=False),
    Column("error", Text),
    Column("sealed", Integer, nullable=False, default=0),
)
files = Table(
    "run_files",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("scan_runs.id"), nullable=False),
    Column("path", Text, nullable=False),
    Column("identity", Text, nullable=False),
    Column("kind", String, nullable=False),
    Column("cache_key", String, nullable=False),
    UniqueConstraint("run_id", "path"),
)
records = Table(
    "analysis_records",
    metadata,
    Column("key", String, primary_key=True),
    Column("result", Text, nullable=False),
)
tasks = Table(
    "tasks",
    metadata,
    Column("id", String, primary_key=True),
    Column("file_id", String, ForeignKey("run_files.id"), nullable=False, unique=True),
    Column("state", String, nullable=False),
    Column("attempt", Integer, nullable=False, default=0),
    Column("lease", String),
    Column("expiry", BigInteger, nullable=False, default=0),
    Column("result_digest", String),
    Column("error", Text),
)
evidence = Table(
    "evidence_edges",
    metadata,
    Column("id", String, primary_key=True),
    Column("run_id", String, ForeignKey("scan_runs.id"), nullable=False),
    Column("left_id", String, ForeignKey("run_files.id"), nullable=False),
    Column("right_id", String, ForeignKey("run_files.id"), nullable=False),
    Column("detector", String, nullable=False),
    Column("distance", Integer, nullable=False),
    UniqueConstraint("run_id", "left_id", "right_id", "detector"),
)
Index("ix_tasks_claim", tasks.c.state, tasks.c.expiry)
Index("ix_run_files_cache", files.c.cache_key)
Index("ix_run_files_run", files.c.run_id, files.c.path)


def identifier() -> str:
    """Return an opaque portable identifier."""
    return str(uuid.uuid4())


class Database:
    """Serialize SQLite writes and keep PostgreSQL transactions bounded."""

    def __init__(self, url: str):
        """Create an engine with safe SQLite pragmas and no fallback."""
        options = (
            {"connect_args": {"timeout": 10}}
            if url.startswith("sqlite:")
            else {"pool_size": 4, "max_overflow": 0}
        )
        self.engine = create_engine(url, **options)
        if self.engine.dialect.name == "sqlite":
            event.listen(self.engine, "connect", self._sqlite)

    @staticmethod
    def _sqlite(connection, _record):
        """Enable durability and referential integrity on every connection."""
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA busy_timeout=10000")

    def migrate(self):
        """Initialize schema version one and refuse unknown versions."""
        metadata.create_all(self.engine)
        with self.write() as conn:
            version = conn.execute(select(schema.c.version)).scalar()
            if version is None:
                conn.execute(insert(schema).values(version=1))
            elif version != 1:
                raise RuntimeError("Unsupported database schema version")

    @contextmanager
    def write(self):
        """Claim the SQLite write lock before reading mutable task state."""
        with self.engine.connect() as conn:
            if self.engine.dialect.name == "sqlite":
                conn.exec_driver_sql("BEGIN IMMEDIATE")
            else:
                conn.begin()
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def list_runs(self) -> list[dict]:
        """Return a bounded newest-first run listing."""
        with self.engine.connect() as conn:
            return [
                dict(row)
                for row in conn.execute(
                    select(runs).order_by(runs.c.created.desc()).limit(100)
                ).mappings()
            ]

    def claim(self, seconds: int) -> dict | None:
        """Lease one pending or expired task, atomically across claimants."""
        now = int(time.time())
        with self.write() as conn:
            query = (
                select(
                    tasks,
                    files.c.path,
                    files.c.identity,
                    files.c.kind,
                    files.c.cache_key,
                )
                .join(files, files.c.id == tasks.c.file_id)
                .join(runs, runs.c.id == files.c.run_id)
                .where(
                    runs.c.state.in_(["DISCOVERING", "ANALYZING"]),
                    (tasks.c.state == "PENDING")
                    | ((tasks.c.state == "LEASED") & (tasks.c.expiry < now)),
                )
                .order_by(tasks.c.id)
                .limit(1)
            )
            if self.engine.dialect.name == "postgresql":
                query = query.with_for_update(skip_locked=True, of=tasks)
            row = conn.execute(query).mappings().first()
            if not row:
                return None
            result = dict(row)
            result.update(
                lease=identifier(), attempt=row["attempt"] + 1, expiry=now + seconds
            )
            conn.execute(
                update(tasks)
                .where(tasks.c.id == row["id"])
                .values(
                    state="LEASED",
                    lease=result["lease"],
                    attempt=result["attempt"],
                    expiry=result["expiry"],
                )
            )
            result["identity"] = json.loads(result["identity"])
            return result
