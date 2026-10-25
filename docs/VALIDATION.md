# Development preview validation

Date: 25 October 2026. Tested application commit:
`33e0c9b2455e83c153428a322fd155ef308a7153`.

Validation ran exclusively on authorized existing Linux build and integration
workers, using disposable Docker resources and synthetic media. No production
host connection or production library was used. Disposable PostgreSQL containers
and networks were removed by an exit trap; built image layers remain as build cache.

| Check | Result |
| --- | --- |
| Linux development image build | PASS |
| Checksum-pinned Czkawka 12.0.2 version invocation | PASS |
| SQLite3 functional and safety contracts | 16 passed |
| PostgreSQL 18 functional and safety contracts | 16 passed |
| Ruff imports, static analysis and docstrings | PASS |
| Black formatting | PASS |

The suite covers strict versus explicitly trusted cache behavior, changed-file
invalidation, stale leases, expired heartbeats, duplicate result replay, concurrent
task claims, failed-task barrier status, path traversal, symlink rejection,
image pixel limits, administrator/daemon authentication separation, secret
redaction, coordinator ownership, bounded subprocess output/time and indexed
exact-candidate review. API tests request the static interface but do not
constitute browser or visual UI qualification.

Two non-failing pytest cache warnings occurred on each backend because the
non-root container could not write its default application-directory cache.
Run pytest with `-o cache_dir=/tmp/optikeep-pytest-cache` explicitly in CI.
The earlier Starlette/AnyIO compatibility warning was resolved by the tested
AnyIO pin; no application warning filter was added.

The image build uses Python 3.12.15, PostgreSQL 18 for the disposable database,
and the exact direct Python dependency versions in pyproject.toml. Base-image
digests, all transitive wheels and FFmpeg packages are not fully locked yet.

These results qualify only the implemented read-only foundation. They do not
qualify complete Czkawka detector coverage, video fingerprints, quality/keeper
ranking, quarantine/restore/purge, full UI behavior, distributed media identity
mapping, large-corpus scanning performance, backups or production deployment.
No throughput or reclaimable-space accuracy claims are made.
