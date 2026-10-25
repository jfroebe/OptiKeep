# Qualification contract

Run all checks only on the authorized existing Linux runner infrastructure.
Use disposable containers, databases, networks, synthetic images and short generated videos.
Use concurrency one and project-scoped cleanup; never prune unrelated resources.

Required commands inside the built image:

```console
python -m pytest -q
ruff check optikeep tests
black --check optikeep tests
```

Repeat the tests with `OPTIKEEP_TEST_DATABASE_URL` set to a dedicated disposable
PostgreSQL database. Never point this variable at existing application databases.
Both backend runs are mandatory. A green foundational test suite does not qualify
the complete appliance: see the implementation status in the design documents.
