# Security and development boundary

Mount media read-only in both coordinator and daemon. The development preview
cannot quarantine or delete. Use synthetic, disposable media while qualifying it.
Do not expose its port directly to an untrusted network. Put authenticated HTTPS
at the reverse proxy boundary and impose request-body and connection limits there.

Use separate randomly generated administrator and daemon tokens. Credentials stay
in environment configuration and are never returned by Settings. The browser
keeps its token in page memory, not persistent browser storage. This preview uses
administrator bearer authentication rather than cookie sessions.

Treat daemons as trusted analysis principals. Results check expected identity,
algorithm, whole-file hash syntax, active lease and current run state. The current
protocol does not prove a daemon actually read the media. A malicious daemon can
misreport measurements; this is one reason evidence is never actionable in the
preview. Per-daemon credentials, roles, audit history, resource sandboxing and
full qualification remain required for a production release.

Subprocesses use fixed argument arrays without a shell, bounded output and timeout.
Media path validation rejects absolute paths, parent traversal and symlinks.
Read-only filesystem access remains essential to constrain external path races.
Only a qualified future coordinator action executor may modify source media.

The existing repository GPLv3 license remains in force. Czkawka and FFmpeg are
third-party software; preserve their license notices when distributing binaries.
No public image or production release is asserted by this development branch.
