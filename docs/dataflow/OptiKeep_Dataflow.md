# Ownership and read only processing

OptiKeep system dataflow and processing specification
Version 1.1 | 25 October 2026 | Companion to system design version 1.1
This specification defines ownership, records and completion boundaries for the implementation. PostgreSQL and SQLite3 implement the same logical flows. Revision 1.0 establishes bounded discovery, read-only daemon analysis, independent Czkawka evidence and journaled coordinator-only actions. Flow IDs F1-F6 trace to design sections D1-D13 and requirements R01-R10.
F1 Discovery and cache admission
Configured allowed roots -> coordinator traversal -> observed file generation -> run manifest -> batched cache lookup -> bounded task admission. The coordinator reads filesystem metadata and writes manifest records. Exclusions are recorded. Queue pressure stops further admission without declaring traversal complete. Identity uncertainty creates verification work, never a fabricated cache hit. Dependencies: D2, D5; R02, R03.
F2 Internal analysis
Task claim -> daemon identity check -> bounded streaming hash or image decode or video probe/frame sampling -> identity recheck -> authenticated result -> coordinator validation -> committed analysis/evidence. Decoded pixels and sampled frames are reused only where the algorithm signature permits. Media bytes normally stay on daemon-readable mounts; task payloads contain mapped references. A mapping failure returns an explicit error. Dependencies: D5-D6, D10; R03, R05, R08.
F3 Czkawka analysis
Reconciled run scope -> capability-checked Czkawka invocation -> supported persistent cache -> parsed independent candidate output -> coordinator endpoint verification -> provenance ledger. Czkawka has read-only source access and isolated scratch/cache access. No deletion arguments are admitted. Compare its actual input scope with the manifest; any unresolved mismatch blocks required coverage. Internal hashes cannot substitute for Czkawka evidence. Dependencies: D6; R04.
Data ownership
User API and web interface -> coordinator -> database adapter -> SQLite3 OR PostgreSQL.
Coordinator task protocol -> analysis daemons -> read-only media mounts.
Coordinator action executor -> permitted media and quarantine roots.
Only the last flow has source-write authority. Daemons cannot access either database directly. Task/result authentication crosses a network trust boundary; the coordinator validates rather than trusting submitted paths or completion flags.

# Completion and filesystem action flows

F4 Evidence to complete plan
Persisted evidence -> indexed candidates -> verified pair relations -> run groups -> confidence -> compatible quality ranking -> direct keeper/member validation -> immutable complete plan. Matching may consume persisted results incrementally, but finalization waits for all selected run inputs and detectors. Do not treat transitive similarity as direct keeper evidence. Plan records bind run, manifest revision, policies, algorithm signatures and affected file generations. Dependencies: D6-D8; R05, R06.
Barrier gate
Discovery sealed AND required analysis complete AND detector coverage verified AND comparisons complete AND groups resolved AND quality/keepers complete AND plan committed -> READY. All terms are durable coordinator checks. Missing rows or unavailable database return false. A required failed task is unresolved even if other detectors agree. Explicit exclusions must originate in run scope policy and remain visible. Overlapping read-only stages never weaken this gate.
F5 Quarantine and recovery
READY plan -> action authorization -> keeper/source revalidation -> committed intent -> filesystem operation -> verified destination -> source removal where required -> committed completion. Every edge is a crash-injection test boundary. On same-filesystem rename, no-overwrite semantics and directory durability are required. Cross-filesystem operation uses copy/verify/publish before source unlink. Source activity outside the coordinator requires a protected mutation window or automatic execution remains disabled. Dependencies: D8-D9; R06, R07.
Recovery decisions
Source present, destination absent: validate original intent and inputs before retry. Source present, verified destination present: determine whether the copy can be completed without overwriting or losing a newer source. Source absent, verified destination present: reconcile the journal to completion. Source absent, destination absent, or mismatching destination: stop for review. Do not infer success from a missing source alone. Verify keeper availability before any further action.
F6 Restore and purge
Authorized request -> quarantine record lookup -> digest/ownership check -> destination reservation -> journaled restore -> verified completion. A collision returns a conflict and preserves the item. Purge checks explicit enablement, item ownership and selected scope before deletion and retains a tombstone. Retention expiration identifies candidates; it is not default deletion authorization. Dependencies: D9; R07.
In every action flow, database unavailability stops new filesystem work. Restart reconciles pending intents before admitting new actions. Scan cancellation before READY produces no source moves. Cancellation during EXECUTING preserves completed records and finishes or journals the active operation for recovery.

# Control observability and failure flows

Configuration and version flow
Defaults -> persisted audited settings -> environment overrides -> CLI overrides -> validated effective snapshot -> run/task signatures. Display all layers in Settings with secret values redacted. A setting change affecting analysis schedules selective invalidation; a change affecting action policy makes the previous plan stale. Database backend changes require maintenance mode and verified export/import; do not apply them to a running scan. Dependencies: D3-D5, D11; R01, R03, R08.
Task state flow
PENDING -> LEASED -> COMMITTED, with FAILED or EXPIRED attempts retained. A result must match the current attempt, lease token and required versions. Timeout makes work reclaimable; an old worker response cannot overwrite the newer attempt. An idempotent identical retry returns its earlier acknowledgement. Persist analysis and task success in the same database transaction before acknowledging. Bound result batches and RPC request bodies independently of media size. Dependencies: D4, D10; R01, R08.
Metrics and logging flow
Stage counters and bounded latency histograms -> coordinator metrics endpoint -> monitoring pull. Structured logs -> bounded local buffering -> persisted diagnostics with rotation. Aggregate by stage, detector and backend, never by every path. Dashboard uses paginated summaries rather than scanning evidence tables on each poll. Audit events record user decisions, settings changes, execution and recovery; diagnostics cannot become substitute evidence. Dependencies: D12; R09, R10.
Failure and shutdown flow
Daemon/tool error -> structured task failure -> bounded retry if transient -> unresolved run status if exhausted -> closed barrier. Storage disappearance pauses the affected scope and invalidates assumptions; it never establishes an empty successful library. Database busy/connection error -> bounded retry/backpressure -> visible degraded health. Cache read failures trigger affected recomputation only; cache corruption does not erase unrelated valid records.
First stop signal -> halt admission -> stop or finish safe in-flight tasks -> commit checkpoints -> close connections and flush diagnostics. Restart -> exclusive coordinator ownership -> schema/version verification -> pending-action reconciliation -> task lease reconciliation -> manifest revalidation -> resume read-only work. A forced stop cannot authorize skipping recovery.
Dataflow acceptance and change control
For each F1-F6 flow, record input/output schemas, row counts, error paths and before/after state in integration tests on both backends. Inject duplicated, reordered and delayed messages; prove that no premature READY state or duplicate action results. Validate memory/backpressure under large manifests. Keep this source and generated documents versioned alongside the design specification; an API, table, state-machine or authority change requires updates to both and links to release evidence. This document describes a design; no integration or performance test is claimed completed.

# Implemented flow boundaries

Revision 1.1 | 25 October 2026

F1 is implemented as synchronous streamed discovery with bounded manifest commits. Each discovered file creates a durable run membership and PENDING or cache-reused COMMITTED task. Directory and I/O failures produce INCOMPLETE; symlinks are skipped. Multiple selected libraries, final reconciliation and a persisted discovery-resume cursor remain pending.

F2 supports task claims, current-lease heartbeats, SHA-256, image hashes/initial measurements and FFprobe metadata. Analysis checks source identity before/after reads; the coordinator validates lease, algorithm and identity before committing result/cache/task state together. A result acknowledgement follows commit. Identical replay returns its original acknowledgement. The daemon uses a separate token and has no database access.

F3 is pending beyond binary packaging/version verification. F4 currently exposes only bounded non-actionable exact-hash candidate lists. Independent evidence aggregation, complete grouping, confidence and keeper plans remain pending. F5 and F6 are absent: no filesystem action endpoint exists.

Every preview run has a closed mutation barrier regardless of internal task completion. /health reports liveness and read-only mode; /ready returns 503 because required pipeline coverage is incomplete. This deliberate distinction must remain until mandatory detector and action recovery qualification is complete.

The implementation uses environment configuration and bootstrap defaults. Persistent settings, complete metrics/logging, daemon registration, durable discovery resume and staged shutdown reconciliation remain target flows. The validation report records which implemented contracts passed checks, without implying qualification of pending flows.
