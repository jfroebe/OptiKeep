# API preview

The coordinator serves generated OpenAPI at `/openapi.json` and interactive
documentation at `/docs`. Use HTTPS through a trusted reverse proxy for remote
connections. Administrator and daemon tokens are separate bearer credentials.

| Route | Method | Authority | Result |
| --- | --- | --- | --- |
| /health | GET | Public | Process liveness, read-only mode |
| /ready | GET | Public | 503 while complete pipeline is unqualified |
| /api/v1/settings | GET | Administrator | Redacted bootstrap settings |
| /api/v1/runs | GET | Administrator | Latest 100 runs |
| /api/v1/runs | POST | Administrator | Synchronous discovery; body trust_metadata_cache boolean |
| /api/v1/runs/{id} | GET | Administrator | Task counts and closed safety barrier |
| /api/v1/runs/{id}/exact-candidates | GET | Administrator | Bounded hash candidates, truncation flag, non-actionable |
| /api/v1/tasks/claim | POST | Daemon | One leased task or null |
| /api/v1/tasks/{id}/heartbeat | POST | Daemon | Extend current lease; body lease string |
| /api/v1/tasks/{id}/results | POST | Daemon | Identity/version-validated result; lease and result body |
| /api/v1/tasks/{id}/failure | POST | Daemon | Failed attempt; lease and code body |

Identical result retries on a committed lease return success. Stale or conflicting
submissions return 409; absent records return 404; invalid credentials return 401.
No filesystem-action endpoint exists. The preview does not offer account creation,
per-daemon registration or token rotation through the UI yet.
