"""Validate that a SQLite database uses an eligible local filesystem."""

from pathlib import Path


def validate_sqlite_path(database: str):
    """Reject relative paths and known network filesystems before connecting."""
    path = Path(database)
    if not path.is_absolute():
        raise ValueError("SQLite requires an absolute local database path")
    resolved = path.resolve()
    best = (0, "")
    for line in Path("/proc/self/mountinfo").read_text().splitlines():
        before, after = line.split(" - ", 1)
        mount = Path(before.split()[4].replace("\\040", " ").replace("\\134", "\\"))
        if resolved.is_relative_to(mount) and len(str(mount)) > best[0]:
            best = (len(str(mount)), after.split()[0])
    if not best[0] or best[1] in {
        "nfs",
        "nfs4",
        "cifs",
        "smb3",
        "9p",
        "fuse.sshfs",
        "fuse.smbnetfs",
    }:
        raise ValueError("SQLite requires a verified local filesystem")
