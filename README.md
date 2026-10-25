# OptiKeep

Distributed photo and video analysis for Linux and Unraid. Copyright (C) 2026
Jason Froebe. Licensed under the existing [GNU GPLv3](LICENSE).

## Current implementation

Version 0.1.0 is a **read-only development preview**, not the complete appliance.
It implements PostgreSQL and SQLite3 persistence, batched discovery, explicit
metadata-trusted caching, atomic task leases, SHA-256 hashing, image perceptual
hashes, initial image measurements, video probing, exact-candidate review and an
authenticated management API and web interface. Source mounts are read-only.

**No quarantine, restore, purge or source modification is implemented or enabled.**
Mandatory independent Czkawka evidence integration, perceptual matching,
calibrated image/video keeper ranking, automatic scheduling and the journaled
action executor remain qualification milestones. The image contains a
checksum-pinned Czkawka CLI; bundling it does not constitute detector integration.
`/ready` intentionally returns 503 until required capabilities are qualified.

## Run a disposable preview

Build the development image and set distinct strong tokens in your environment:

```console
export OPTIKEEP_API_TOKEN="$(openssl rand -hex 32)"
export OPTIKEEP_DAEMON_TOKEN="$(openssl rand -hex 32)"
export OPTIKEEP_MEDIA_ROOT=/path/to/disposable/synthetic-media
docker compose up --build -d
```

Open `http://127.0.0.1:18766`, enter the administrator token and start a scan.
The daemon analyzes queued files without choosing keepers. Use scan progress to
review completion and exact-candidate review to inspect matching content hashes.
An exact hash candidate is not an approved removal plan.

SQLite3 stores its database in the named `/config` volume. To select PostgreSQL,
set `OPTIKEEP_DATABASE_URL` to
`postgresql+psycopg://USER:PASSWORD@DATABASE_HOST/DATABASE` before starting.
Use a dedicated empty database. No silent fallback occurs on connection failure.
Never place the SQLite database on SMB or NFS. Do not switch an existing populated
installation between backends: logical transfer tooling is not implemented yet.

Run one coordinator. Its state lock prevents duplicate processes; PostgreSQL also
uses a dedicated session advisory lock. Daemons have a separate scoped token and
no direct database credentials. Bind mounts must be readable by UID/GID 1000;
the development image runs non-root. Configured UID/GID remapping and a complete
Unraid template are not yet implemented.

See [configuration](CONFIGURATION.md), [API](API.md), [security](SECURITY.md) and
the [system design](docs/design/OptiKeep_System_Design.md) for contracts and
implementation status. No throughput claims are made before benchmark evidence.
