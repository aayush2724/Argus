# Argus architecture

Revision 4 design. See [current implementation status](../PROGRESS.md).

```text
React / Vite / TypeScript / Tailwind
        | loopback HTTP, polling
Express / TypeScript strict / Zod
        |                        Node job controller (same app)
        +---- Drizzle / PostgreSQL <-------> claim, lease, ingest
                                         |
                                         | versioned files + NDJSON
                                    Python Argus engine
                              +----------+-----------+
                         isolated scanner/index    provider client
                              |                     |
                       immutable snapshot <-- restricted tools
                              |
                        evidence validator --> checkpoints + final report

Typer CLI / MCP stdio / official evaluator --> same Python core --> file artifacts
```

Node owns the API, queue, job supervision, database and product queries. Python 3.13+, uv, Pydantic v2, Typer, pinned Semgrep, Tree-sitter, Docker and MCP Python SDK own analysis and report semantics. The worker is a module of the Node application. Shutdown and claim recovery run through the same service layer as the REST API. Begin with one application instance and one scan slot. PostgreSQL in Docker Compose is the only required stateful application service. No DB credentials in Python. Keep benchmark data and raw evaluator output outside the application; a local Node import publishes validated summaries. See [database design](DATABASE.md) and [threat model](THREAT_MODEL.md).

## Durable execution protocol

Use three records with separate meanings. The scan is a user-visible intent and final result, the job is its one schedulable work item, and attempts record individual executions. The scan owns public state. Jobs own scheduling and attempts own execution outcomes. Use DB time for deadlines and leases. All multi-row changes lock in job → scan → attempt order; claims select only job rows. Keep transactions bounded and avoid I/O inside locks.

1. **Enqueue.** Validate repository, approved model profile and bounded config. Atomically create the scan and one job. Require a client idempotency key scoped to the repository and compare a canonical request hash. Replay returns the original ID, and changing the request with the same key returns 409. Serialize queue admission with a short transaction-level advisory lock and enforce a finite configurable cap. A committed replay bypasses the cap. Return 202 and a status URL after commit. A local repository request identifies a selected revision or, when explicitly using working-tree input, the first sealed export. Record the resolved snapshot and config digest before scanner or model work. Resume from that sealed copy only.
2. **Claim.** A free worker slot selects the oldest eligible job by `available_at, id`, with `FOR UPDATE OF scan_jobs SKIP LOCKED`. Under the same transaction, recheck the scan state, cancellation and scan deadline. Expire overdue queued or retry-wait jobs to failed without launching work. For an eligible job, increment attempt ordinal, insert an active attempt with a DB-clock lease and set the job's current attempt pointer. Set the scan to running on its first claim. This protects claim races. Admission is single-instance initially, and the row-lock protocol is tested with two claimers. Multi-instance execution budgets and cleanup are future work. [PostgreSQL locking clauses](https://www.postgresql.org/docs/current/sql-select.html#SQL-FOR-UPDATE-SHARE)
3. **Run.** Launch a pinned executable with explicit argument array, `shell: false`, trusted cwd and minimal environment. Write the request to a private job workspace. Allocate and persist a discoverable attempt-scoped execution identity before launch. Use a host-supported whole-job process boundary and job-labeled containers. M0 must prove the launch/fencing handshake covers controller death between registration and spawn, and that restart always discovers or prevents late children. Pass an attempt ID and trace context. Heartbeat only while progress supervision is healthy. Initial tuning defaults are a 10-second heartbeat and 45-second lease, with separate engine wall-time and scan-wide time limits derived from the selected budget. Every heartbeat, progress write, usage authorization and final commit checks the current attempt, expiry and applicable cancellation predicate. A worker that loses its lease stops dispatching and terminates its process group and containers.
4. **Persist partial work.** Commit monotonic stage/count snapshots by attempt and sequence, sanitized failures and metered usage in small transactions. The Python engine atomically writes bounded per-finding checkpoints to a private attempt directory. Keep checkpoint contents out of public findings until final publication. Show durable completed counts separately from in-flight progress. Checkpoints bind to snapshot, config, schema and stable finding key. An attempt may reuse validated completed checkpoints from reconciled attempts. Restart an incomplete investigation from its initial context. Preserve prior call records and consumed budget; an unfinished conversation is never treated as a verdict.
5. **Recover and retry.** An expired lease prevents all further writes by the old attempt except reconciliation through the controller. Reconcile at startup and periodically. Claim cleanup ownership using the job lock and a fenced cleanup lease so reconciliation can itself be resumed. Terminate or verify absence of old processes and containers using trusted execution identity, avoiding bare PID reuse. Until cleanup succeeds keep the slot quarantined, with status and a bounded diagnostic visible. After cleanup reconcile journal records, mark the old attempt lost and schedule another attempt only for transient operational failures, such as worker loss or temporary resource outage. Start with at most three attempts total and bounded exponential backoff with jitter, subject to the original scan deadline and remaining budget. Invalid input, unsupported schemas, failed containment and exhausted budgets are terminal. A controller outage around final commit resolves by rereading DB state and artifact digest. Exit success plus a valid final artifact is required; ordinary cancellation, invalid input and engine failure have distinct exit codes, while the controller classifies timeouts and signals.
6. **Publish.** Validate limits, version, snapshot, run/attempt, uniqueness, references and manifest before the transaction. Lock and recheck the current lease and cancellation. Insert findings, verdicts and evidence, reconcile usage and tool rows, and mark completed with the canonical report digest in one transaction. Successful replay with the same completed scan and digest is a no-op, conflicting digests are rejected and logged. Final checkpoints assembled into the report may originate from validated earlier attempts. Invalid reports leave the final read model empty. Reports are reconstructed from committed rows and their immutable run manifest; derive the JSON ETag from the actual canonical response bytes and generate Markdown/SARIF from the same validated document.
7. **Cancel or stop.** A queued scan cancels atomically. A running scan records a durable cancel request. A retry-wait scan with cleanup already confirmed cancels atomically. Under the same lock order, final publication wins only if it commits before the cancel request. Once cancellation wins, stop new calls, terminate the process group and labeled containers with a bounded graceful window then forced cleanup, reconcile usage and transition to cancelled. Repeated cancellation returns current state. On shutdown stop claims and allow bounded drain, then stop active processes and reconcile as interrupted for recovery. Timeouts follow the same cleanup protocol but use failure/retry policy. Terminal states have no outgoing transitions; a new scan with a new idempotency key is the manual rerun.

| Public state | Meaning and transitions |
|---|---|
| queued | Durable job waiting for first claim. Goes to running, failed on admission deadline expiry, or cancelled. |
| running | Active, recovering or backing off between automatic attempts. Publish a phase and next eligible time for retry wait. Goes to completed, failed or cancelled. |
| completed | Atomic validated report ready, potentially containing per-finding review or failure records. |
| failed | Scan execution ended without a report, after nonretryable error or retry exhaustion. |
| cancelled | User cancellation finalized, with no final report. |

## Accounting and external side effects

Processing is at least once. Commit a stable, attempt-scoped call ID and worst-case budget reservation before each outbound dispatch. The engine requests this through a bounded control message and waits for an acknowledgement before sending. Replaying a reservation may return its ledger status, but grants no second dispatch. A deliberate retransmission is a new call ID and reservation. Ledger entries settle idempotently with billable tokens/provider request ID when known, and immutable terminal values reject conflicts. Include adapter retries and repair calls. Use the same reserve/settle behavior in standalone mode with an atomic local journal.

If the worker dies after authorization and before settlement, first recover any completed usage journal entry. Otherwise mark the call indeterminate, retain the reservation against the scan cap, and report unknown actual cost and the reserved bound separately. A subsequent attempt can repeat a call under a new ID only within the remaining budget. Completed findings can be reused even when earlier calls were repeated. Use provider idempotency where documented as an optimization. Never infer exactly-once external execution or zero charge from a timeout. For $0 development profiles, use only local or explicitly verified no-charge usage with a request/token cap.

## Versioned interfaces

Store strict JSON Schemas with parity fixtures in `packages/contracts`. Match Zod and Pydantic behavior on shared valid and invalid examples, including major-version rejection, nullable fields, length/counts and finite numbers. Pin a canonical hashing procedure with cross-runtime golden vectors. Each envelope has schema version, IDs appropriate to its scope, UTC timestamp and sequence or stable record key.

| Document | Core contract |
|---|---|
| Scan request | Scan/job/attempt IDs, approved source and profile, immutable config digest, snapshot if resolved, deadlines, limits, artifact protocol version and trace context. |
| Progress and controls | Bounded stdout NDJSON with sequence, stage/counters, usage reservations/settlements and sanitized failures. Separate bounded acknowledgements/control input via stdin. Bounded stderr for diagnostics. |
| Findings | Stable key from snapshot, scanner/config, canonical locations and rule or normalized finding identity. Product-only rule/severity fields are excluded by benchmark input projection. |
| Evidence and verdict | Stable citation ordinals, relative locations, bounded summary, preconditions, decision and confidence, optional positive score/CWE/fix direction, referenced failure IDs. Evidence records role and validation outcome. Optional graph edges use citation IDs and explicit provenance. |
| Report and evaluation artifacts | Terminal report sums, immutable inputs, findings, verdicts, accounting and failures. Separate benchmark run manifest and metric records, with digest, denominators and conditions. Publish file atomically before exit. |

Reject invalid envelopes and identity mismatches before persistence. Changes with incompatible semantics require a major contract version. Declare readable versions and test roll-forward and replay of old artifacts. File access stays under private job roots with bounded reads and no symlink following.

## REST surface

Use `/api` endpoints and response schema version 1. Bind to loopback with same-origin production UI or a local Vite proxy. Keep mutations JSON-only and validate origin and host. Validate request bodies, typed IDs, enum filters, supported media and sizes with Zod. Errors carry stable `code`, safe `message`, `request_id` and optional invalid fields. Use 400 validation, 404 missing resource, 409 state or idempotency conflict, 413 size limit, 415 media type, 429 queue full with retry hint, 503 DB or worker admission unavailable and bounded request/query timeouts. A timeout around an unknown submission outcome is replayable with the same key.

| Endpoint | Behavior |
|---|---|
| `POST /api/repositories`, `GET /api/repositories`, `PATCH /api/repositories/:id` | Register approved source (201), list (200), rename/archive (200). Archival blocks new submissions while preserving existing scans. |
| `POST /api/repositories/:id/scans` | 202 with ID and Location. Same key and hash returns prior ID with current state. |
| `GET /api/scans`, `GET /api/scans/:id` | History and pollable progress, phase, usage coverage and sanitized status. |
| `POST /api/scans/:id/cancel` | 202 pending cleanup, 200 when already cancelled or cancelled synchronously, 409 for completed/failed. |
| `GET /api/scans/:id/findings`, `GET /api/scans/:id/report` | Read committed results (200) or report unavailable (409 with scan state). Bounded JSON, Markdown and SARIF formats. |
| `GET /api/findings/:id`, `GET /api/findings/:id/evidence` | Inspect verdict, redacted investigation details and bounded cited excerpts. Use snapshot-scoped citations, never arbitrary file reads. |
| `GET /api/evaluations`, `GET /api/evaluations/:id` | List and inspect imported summaries. Rendering never triggers live inference. |

Use keyset pagination by creation time and ID for histories and stable per-scan IDs for findings, with bounded page sizes and cursor scope bound to filters. Initial filters cover repository, status, decision, scanner and evaluation dataset/provider/model where applicable. Poll with backoff, stop on terminal state, and refresh on user focus. Defer push transport until measured.

## Observability and failure tests

Instrument from M0 with structured logs and lightweight OpenTelemetry in both runtimes, local output and no collector required. Propagate trace context through job payloads with attempt spans linked to submission. Emit `scan_request → job_created → job_claimed → repository_ingestion → semgrep_scan → findings_normalized → agent_investigation` with model request, tool call and evidence validation spans, followed by verdict persistence and report generation. Correlate scan/attempt/finding IDs in events, and record model/provider, tokens, estimated/known/unknown cost, duration, retry count and normalized errors. Keep identifiers out of metric labels and omit sensitive payloads.

Record completion and retry rates, expired leases and time-to-recovery, replay/conflict counts, queue latency and p50/p95 end-to-end scan latency, model failures and invalid evidence. Publish denominators and distinguish completed durations from timeout counts. Use a scripted demo with a fake model and fault injection at claim, during inference, before/after publication, at DB loss and on cancellation. Assert no duplicate final rows, bounded spend reservations, consistent resumed checkpoints, and no late writes from the old attempt. [Threat model](THREAT_MODEL.md)
