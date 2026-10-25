"""Portable repository and safety contract tests using disposable media."""

import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select, update

from optikeep.api import create_app
from optikeep.config import Settings
from optikeep.coordinator import Coordinator
from optikeep.db import Database, records, tasks
from optikeep.media import analyze, resolve_media


@pytest.fixture
def environment(tmp_path):
    """Use a fresh schema on the selected disposable backend."""
    root = tmp_path / "media"
    root.mkdir()
    settings = Settings(
        database_url=os.environ.get(
            "OPTIKEEP_TEST_DATABASE_URL", f"sqlite:///{tmp_path}/db.sqlite3"
        ),
        media_root=root,
        state_root=tmp_path,
        api_token="a" * 32,
        daemon_token="d" * 32,
    )
    db = Database(settings.database_url)
    db.migrate()
    yield settings, db, Coordinator(db, settings)
    from optikeep.db import metadata

    metadata.drop_all(db.engine)
    db.engine.dispose()


def make_image(root: Path, name="sample.png"):
    """Write a deterministic synthetic image."""
    Image.new("RGB", (32, 32), "red").save(root / name)


def test_scan_analyze_cache(environment):
    """Strict rescans reanalyze while explicit trusted rescans reuse records."""
    settings, db, coordinator = environment
    make_image(settings.media_root)
    run = coordinator.discover()
    task = db.claim(90)
    result = analyze(settings.media_root, task, settings.image_pixel_limit, 10)
    coordinator.submit(task["id"], task["lease"], result)
    coordinator.submit(task["id"], task["lease"], result)
    assert coordinator.status(run)["tasks"] == {"COMMITTED": 1}
    assert coordinator.status(run)["barrier_open"] is False
    trusted = coordinator.discover(trust_cache=True)
    assert coordinator.status(trusted)["tasks"] == {"COMMITTED": 1}
    strict = coordinator.discover()
    assert coordinator.status(strict)["tasks"] == {"PENDING": 1}


def test_stale_lease(environment):
    """Reject a delayed worker after its task is reclaimed."""
    settings, db, coordinator = environment
    make_image(settings.media_root)
    coordinator.discover()
    old = db.claim(90)
    with db.write() as conn:
        conn.execute(
            update(tasks)
            .where(tasks.c.id == old["id"])
            .values(expiry=int(time.time()) - 1)
        )
    new = db.claim(90)
    assert old["lease"] != new["lease"]
    result = analyze(settings.media_root, old, 10000, 10)
    with pytest.raises(ValueError, match="Stale"):
        coordinator.submit(old["id"], old["lease"], result)
    coordinator.submit(new["id"], new["lease"], result)


def test_identity_replacement(environment):
    """Refuse media replaced after discovery."""
    settings, db, coordinator = environment
    make_image(settings.media_root)
    coordinator.discover()
    task = db.claim(90)
    (settings.media_root / "sample.png").write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed"):
        analyze(settings.media_root, task, 10000, 10)


def test_failed_task_closes_barrier(environment):
    """Failed analysis remains visible and cannot authorize source actions."""
    settings, db, coordinator = environment
    make_image(settings.media_root)
    run = coordinator.discover()
    task = db.claim(90)
    coordinator.fail(task["id"], task["lease"], "DecodeError")
    assert coordinator.status(run)["tasks"] == {"FAILED": 1}
    assert coordinator.status(run)["mutation_enabled"] is False


@pytest.mark.parametrize("relative", ["../secret", "/etc/passwd", "a/../../secret"])
def test_paths(environment, relative):
    """Prevent traversal outside the configured media root."""
    settings, _, _ = environment
    with pytest.raises(ValueError):
        resolve_media(settings.media_root, relative)


def test_symlink(environment):
    """Reject symlinks even when they point inside the source root."""
    settings, _, _ = environment
    make_image(settings.media_root)
    (settings.media_root / "alias.png").symlink_to("sample.png")
    with pytest.raises(ValueError, match="Symlink"):
        resolve_media(settings.media_root, "alias.png")


def test_pixel_budget(environment):
    """Reject excessive image dimensions before full decoding."""
    settings, db, coordinator = environment
    make_image(settings.media_root)
    coordinator.discover()
    with pytest.raises(ValueError, match="pixel budget"):
        analyze(settings.media_root, db.claim(90), 10, 10)


def test_claim_concurrency(environment):
    """Concurrent claimers never receive the same current task lease."""
    settings, db, coordinator = environment
    for index in range(8):
        make_image(settings.media_root, f"{index}.png")
    coordinator.discover()
    with ThreadPoolExecutor(max_workers=4) as pool:
        claims = list(pool.map(lambda _: db.claim(90), range(8)))
    assert len({claim["id"] for claim in claims}) == 8


def test_api_authentication(environment):
    """Separate administrator and daemon authority and redact stored secrets."""
    settings, _, _ = environment
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503
        assert client.get("/api/v1/settings").status_code == 401
        headers = {"Authorization": "Bearer " + settings.api_token}
        response = client.get("/api/v1/settings", headers=headers)
        assert response.status_code == 200
        assert settings.api_token not in response.text
        assert client.post("/api/v1/tasks/claim", headers=headers).status_code == 401
        assert client.get("/").status_code == 200


def test_changed_cache_invalidates(environment):
    """A modified file must not reuse a previous analysis result."""
    settings, db, coordinator = environment
    make_image(settings.media_root)
    coordinator.discover()
    task = db.claim(90)
    coordinator.submit(
        task["id"], task["lease"], analyze(settings.media_root, task, 10000, 10)
    )
    Image.new("RGB", (64, 64), "blue").save(settings.media_root / "sample.png")
    run = coordinator.discover(trust_cache=True)
    assert coordinator.status(run)["tasks"] == {"PENDING": 1}
    with db.engine.connect() as conn:
        assert conn.execute(select(records.c.key)).first() is not None
