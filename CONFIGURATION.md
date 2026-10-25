# Configuration

The preview uses environment overrides over validated defaults. Persistent web
settings and general CLI overrides are planned, not implemented. Settings in the
UI show implemented effective values read-only; token values and DSNs are redacted.
All changes require a restart. Do not put credentials in URLs sent to browsers.

| Environment key | Default | Meaning |
| --- | --- | --- |
| OPTIKEEP_DATABASE_URL | sqlite:////config/optikeep.sqlite3 | SQLite local file or PostgreSQL psycopg URL |
| OPTIKEEP_MEDIA_ROOT | /media | Coordinator source namespace |
| OPTIKEEP_STATE_ROOT | /config | Writable application data and ownership lock |
| OPTIKEEP_API_TOKEN | Required | Administrator bearer token, at least 24 characters |
| OPTIKEEP_DAEMON_TOKEN | Required | Separate daemon bearer token, at least 24 characters |
| OPTIKEEP_BATCH_SIZE | 128 | Manifest rows per transaction, 1 to 512 |
| OPTIKEEP_LEASE_SECONDS | 90 | Task lease, 30 to 3600 seconds |
| OPTIKEEP_IMAGE_PIXEL_LIMIT | 40000000 | Maximum image pixels accepted by coordinator settings |
| OPTIKEEP_PROCESS_TIMEOUT | 300 | Configured subprocess timeout, 1 to 3600 seconds |

The current daemon runs sequentially, with a 40 million pixel budget and 60-second
probe timeout; dynamic configuration propagation to remote daemons remains pending.
Daemon roots are set with `optikeep daemon --media-root /media --url URL`.
Do not set coordinator budgets expecting this preview daemon to inherit them.

Strict scans are the default. `trust_metadata_cache=true` explicitly permits
cache reuse under a stable, controlled-library assumption. Cache keys include
relative path, device, inode, size, nanosecond modification/change times and
algorithm version. Stat equality does not prove byte equality. No preview mode
authorizes media mutation. Changes to this cache contract require an algorithm
version bump.
