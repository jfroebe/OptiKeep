# Unraid development preview

This packages the implemented read-only foundation. Quarantine, deletion,
quality ranking and the complete appliance are not implemented. Media must remain
read-only. Install both coordinator and daemon; the coordinator does not analyze
files on its own.

## Build

On an authorized Linux Docker build worker, from the repository root:

```console
docker build --pull -t optikeep:development .
docker run --rm --entrypoint czkawka_cli optikeep:development --version
docker run --rm --entrypoint python optikeep:development -m pytest -q
```

The Dockerfile currently targets Linux amd64 (the pinned Czkawka binary).
It includes FFmpeg, FFprobe and checksum-verified Czkawka. The templates use
`optikeep:development`, which must exist on the Docker host before installation.
To transfer a worker-built image without publishing it:

```console
docker save -o optikeep-development.tar optikeep:development
```

Copy the archive to the target host and run `docker load -i optikeep-development.tar`.
No registry image has been published by this packaging change. Select a verified
registry tag in both templates if publishing separately.

## Install

Extract the ZIP and run the installer as root from an Unraid terminal:

```console
bash /path/to/extracted/optikeep/install-template.sh
```

The installer verifies the complete bundle against `SHA256SUMS`, installs both
XML templates in `/boot/config/plugins/dockerMan/templates-user/`, and backs up
any different existing templates before replacing them. It can be run from any
working directory. Repeating installation of identical templates makes no changes.
It does not load the Docker image, create containers, or modify appdata/media.

Then in Docker → Add Container, select `OptiKeep` and `OptiKeep-Worker`.

Prepare the coordinator appdata directory before starting it. The default
runtime identity is UID 99, GID 100, configured through `--user=99:100`:

```console
install -d -m 0770 -o 99 -g 100 /mnt/user/appdata/optikeep
```

If using a different identity, change both the directory ownership and the
`--user` setting. The application remains non-root; it does not recursively
change ownership of existing data or media. A startup permissions error means
the selected identity needs write and search access to the appdata directory.

Generate two separate tokens with `openssl rand -hex 32`. Enter the administrator
token and daemon token in the coordinator template. Enter the same daemon token
in the worker template. Tokens are required and have no default. Unraid stores
container environment values in its template configuration; protect boot-drive
backups. Password masking only hides the field in the editor.

Map the same host media directory to `/media` in both containers, read-only.
Set the worker coordinator URL to the coordinator's reachable address and port
18766. Use a trusted local network; remote access requires a TLS reverse proxy.
Open the coordinator WebUI at port 18766 and use the administrator token.

SQLite3 is the default, persisted at `/config/optikeep.sqlite3`. Keep appdata on
local storage with reliable locking, outside scanned media. For PostgreSQL,
replace the database URL with:

```text
postgresql+psycopg://optikeep:URL_ENCODED_PASSWORD@database.example.internal:5432/optikeep
```

Create a dedicated database and user first. PostgreSQL is external to this image.
Do not add database credentials to the worker. Only one coordinator may own a
given database. Stop the coordinator before copying SQLite appdata for backup.

The image healthcheck applies to the coordinator. The worker template disables
that HTTP healthcheck because workers expose no HTTP server. Monitor worker
logs and coordinator task/lease status. The worker restarts unless stopped.

No logo/icon URL is supplied until the approved artwork is checked into a
reachable repository location; the templates must not reference nonexistent art.

## Qualification

The image was built on the existing authorized Linux Meta build worker and
validated on the Meta controller. SQLite3 and disposable PostgreSQL 18 each
passed all 16 functional/safety tests. Ruff and Black passed. Fresh bind-mounted
appdata, UID 99:GID 100, a read-only root filesystem, zero effective capabilities,
health and restart behavior passed for both backends.

Build evidence and the loadable image/template bundle:
https://github.com/jfroebe/chatgpt-dev-control/actions/runs/40243350162

Download and extract the workflow artifact, verify SHA256SUMS, then load the image:

```console
sha256sum -c SHA256SUMS
docker load -i optikeep-development.tar.gz
```

Testing defaults to the existing Meta environment unless explicitly directed
otherwise. Production media and the Unraid host were not accessed. Actual Unraid
UI installation, deliberately unwritable appdata diagnostics and a full packaged
worker scan remain outside this qualification. This is a development preview.
