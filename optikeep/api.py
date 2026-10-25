"""Authenticated coordinator API and a static management interface."""

import secrets
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.exc import NoResultFound

from optikeep.config import Settings
from optikeep.coordinator import Coordinator
from optikeep.db import Database
from optikeep.ownership import coordinator_lock


class Submission(BaseModel):
    """A result bound to an opaque current task lease."""

    lease: str = Field(max_length=64)
    result: dict


class Failure(BaseModel):
    """A bounded failure code without subprocess output or credentials."""

    lease: str = Field(max_length=64)
    code: str = Field(max_length=100)


class ScanRequest(BaseModel):
    """Explicit trust policy for analysis reuse."""

    trust_metadata_cache: bool = False


class Heartbeat(BaseModel):
    """Bind lease extension to the task currently owned by the daemon."""

    lease: str = Field(max_length=64)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the coordinator service without opening connections at import."""
    settings = settings or Settings.from_env()
    db = Database(settings.database_url)
    coordinator = Coordinator(db, settings)

    @asynccontextmanager
    async def lifespan(_app):
        """Initialize persistent schema and close the engine on shutdown."""
        settings.state_root.mkdir(parents=True, exist_ok=True)
        with coordinator_lock(db, settings.state_root):
            db.migrate()
            try:
                yield
            finally:
                db.engine.dispose()

    app = FastAPI(title="OptiKeep", version="0.1.0", lifespan=lifespan)
    app.state.coordinator = coordinator

    def authorize(expected: str, authorization: str | None):
        """Use constant-time checks and avoid placing credentials in URLs."""
        if not authorization or not secrets.compare_digest(
            authorization, "Bearer " + expected
        ):
            raise HTTPException(401, "Authentication required")

    def user(authorization: str | None = Header(default=None)):
        """Require the administrator token for management operations."""
        authorize(settings.api_token, authorization)

    def daemon(authorization: str | None = Header(default=None)):
        """Require the separate daemon token for analysis operations."""
        authorize(settings.daemon_token, authorization)

    @app.exception_handler(ValueError)
    async def bad_value(_request: Request, _error: ValueError):
        """Return a conflict without leaking local paths or raw exceptions."""
        return JSONResponse(
            status_code=409, content={"detail": "Invalid input or stale task state"}
        )

    @app.exception_handler(NoResultFound)
    async def missing(_request: Request, _error: NoResultFound):
        """Report absent records consistently."""
        return JSONResponse(status_code=404, content={"detail": "Record not found"})

    @app.get("/health")
    def health():
        """Report liveness independently from detector qualification."""
        return {"status": "alive", "mode": "read-only"}

    @app.get("/ready")
    def ready():
        """Keep release readiness closed until mandatory detectors qualify."""
        return JSONResponse(
            status_code=503,
            content={
                "ready": False,
                "mode": "read-only",
                "reason": "Analysis and action qualification incomplete",
            },
        )

    @app.get("/api/v1/settings", dependencies=[Depends(user)])
    def configuration():
        """Show all implemented bootstrap settings with secrets redacted."""
        return {
            "effective": settings.public(),
            "editable": False,
            "source": "environment or defaults",
            "restart_required": True,
        }

    @app.get("/api/v1/runs", dependencies=[Depends(user)])
    def list_runs():
        """List bounded scan history."""
        return db.list_runs()

    @app.post("/api/v1/runs", dependencies=[Depends(user)])
    def start_scan(body: ScanRequest):
        """Discover a read-only scan and return its durable ID."""
        return {"id": coordinator.discover(body.trust_metadata_cache)}

    @app.get("/api/v1/runs/{run_id}", dependencies=[Depends(user)])
    def run_status(run_id: str):
        """Show progress and unsatisfied safety requirements."""
        return coordinator.status(run_id)

    @app.get("/api/v1/runs/{run_id}/exact-candidates", dependencies=[Depends(user)])
    def exact_candidates(run_id: str):
        """List indexed whole-file hash candidates for read-only review."""
        return coordinator.exact_candidates(run_id)

    @app.post("/api/v1/tasks/claim", dependencies=[Depends(daemon)])
    def claim():
        """Lease one task for a read-only daemon."""
        return db.claim(settings.lease_seconds)

    @app.post("/api/v1/tasks/{task_id}/results", dependencies=[Depends(daemon)])
    def submit(task_id: str, body: Submission):
        """Persist a validated result and return an idempotent acknowledgement."""
        coordinator.submit(task_id, body.lease, body.result)
        return {"accepted": True}

    @app.post("/api/v1/tasks/{task_id}/heartbeat", dependencies=[Depends(daemon)])
    def heartbeat(task_id: str, body: Heartbeat):
        """Renew a current task lease while expensive analysis runs."""
        db.heartbeat(task_id, body.lease, settings.lease_seconds)
        return {"accepted": True}

    @app.post("/api/v1/tasks/{task_id}/failure", dependencies=[Depends(daemon)])
    def failure(task_id: str, body: Failure):
        """Persist a failed attempt without releasing the safety barrier."""
        coordinator.fail(task_id, body.lease, body.code)
        return {"accepted": True}

    static = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/", include_in_schema=False)
    def home():
        """Serve the management interface without embedding credentials."""
        return FileResponse(static / "index.html")

    return app
