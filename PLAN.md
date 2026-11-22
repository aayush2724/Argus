# Argus — Project Plan

Revision 4 · 2026-11-22 · Owner: aayush2724

Argus runs deterministic scanners, investigates suspicious findings with a restricted read-only LLM agent, produces evidence-backed verdicts, and evaluates triage performance using SastBench. AI-assisted SAST triage already exists. Argus will be judged on whether tool-assisted investigation improves triage enough to justify its cost and latency, and whether the system can demonstrate secure execution, reliable recovery and reproducible measurements. Publish negative and inconclusive results.

The repository is documentation-only today. The proposed `engineering-auditor` layout and all milestones are planned. [Progress](PROGRESS.md)

## 1. Architecture and scope

React, TypeScript, Vite and Tailwind CSS provide the local dashboard. Strict TypeScript, Node.js, Express, Zod and Drizzle own the REST API, job controller and PostgreSQL. The worker starts with one scan slot and a finite queue. Python 3.13+, uv, Pydantic v2, Typer, pinned Semgrep, Tree-sitter and Docker own analysis. Use pytest, Ruff and mypy for engine checks, and lightweight OpenTelemetry in both runtimes from M0. MCP over stdio uses the Python SDK.

The API stores scans and jobs atomically, returns HTTP 202, and serves persisted progress to the polling dashboard. Node claims leased jobs, runs Python through explicit versioned process contracts, and publishes findings transactionally. A restarted worker resumes from validated completed checkpoints under a new attempt. Calls interrupted before settlement may be charged and repeated, so reservations and unknown cost survive recovery. CLI, MCP and the official evaluator reuse the Python engine with file-based artifacts. [Architecture and API](docs/ARCHITECTURE.md) · [Schema and migrations](docs/DATABASE.md) · [ADR-002](docs/ADR-002-production-architecture.md)

| Priority | Scope and rationale |
|---|---|
| P0 | Standalone Python provides reproducible execution and a smaller research dependency graph than the hybrid stack. Use one pinned Semgrep scanner for real inputs. Restricted tools and strict evidence verdicts are required to test the tool-assisted research question safely. Single-shot is the simpler baseline. |
| P0 | Official SastBench and cost accounting support scientific and operational comparisons. Use replay and small dev subsets during development. A custom evaluator would sacrifice protocol comparability. |
| P0 | PostgreSQL jobs and a minimal API demonstrate durable acceptance, fencing, cancellation and recovery. Use a single process manager and one slot. A CLI alone is viable for research, and cannot demonstrate the requested application lifecycle. Core tests make containment, transactions and claims verifiable. |
| P1 | Dashboard, visual evidence chain, evaluation lab, MCP, broader adversarial suite and recovery demos. Each consumes existing contracts. Ship basic tables and drill-downs first. |
| P2 | Redis/BullMQ, push updates, multi-user authentication, hosted deployment, GitHub Actions product integration, automatic fixes and expanded scanners. OSV-Scanner and Gitleaks retain the Revision 3 design of separate untriaged results if added. No target-code execution or DAST. |

Proposed directories are `apps/{api,web}`, `engine/{argus,tests}` with its own Python project, `packages/contracts` for schemas and fixtures, `benchmarks`, `fixtures`, `infrastructure` for Docker Compose and `docs`. Keep image and rules pins in version control and credentials, private datasets and generated run artifacts outside it.

## 2. Agent and provider runtime

At each finding, select the flagged span and a bounded enclosing-function window with deterministic ordering. Investigate attacker-controlled input, propagation, validation, sink, reachability, configuration and preconditions. Seek referenced symbols or callers only when they resolve a concrete gap. Start with JS/TS and Python symbol indexes. Other languages use bounded file reads, directory listing, search and manifest summaries. No whole-repository prompt. Log which retrieval policy and budgets were used. Benchmark effort depends on remaining budget and the approved payload, with scanner severity and labels excluded.

Bound tool turns, provider calls, tokens, output bytes, wall time and spend. Start with at most eight tool turns and deterministic truncation with reserved output context. Share tool-call, tool-result, model-message, error and usage types. Separate pure tool validation/dispatch from adapter encoding. Require strict evidence-first verdicts with decision, decision confidence, evidence, preconditions, CWE when known, at most 80 words of reasoning, optional textual fix direction and failure references. Use `true_positive`, `false_positive` and `needs_review`. A positive without validated citations becomes review. Insufficient or contradictory support warrants review. Evidence must reference real bounded lines in the immutable snapshot. Measure relevance and verdict correctness separately. [Threat model](docs/THREAT_MODEL.md) · [Evaluation protocol](docs/EVALUATION.md)

### Provider adapters

Define a Python provider interface for generation, normalized usage and errors, and capabilities per configured provider/model. Initial adapters are Google Gemini API, Groq API and Ollama. Anthropic Claude is a future adapter. Inject configuration into the engine. Record requested and resolved model identifiers or local weights digest, exposed model version, adapter version, effective generation parameters, seed support, context limit and pricing assumptions for each run.

- Track native tool calling, schema enforcement, context limits, usage counters, streaming and caching separately. Use native calls where supported. Schema-validate tool arguments before dispatch regardless of provider. Where native schema output is unavailable, parse bounded JSON and allow a bounded repair within budget. Use single-shot for models without usable tool calls unless a separately tested structured tool protocol is selected and declared as a distinct configuration. Reject unsupported experiment configurations explicitly.
- Single-shot uses a fixed finding and deterministic bounded context policy. The tool loop uses the same verdict and evidence policy and defaults to at most eight investigation turns. Compute effort from remaining budget. Limit each finding's calls, context, aggregate input/output tokens, wall time, tool output and retry spend. Limit each run's reserved spend and token volume, including failed/retried requests. Truncate deterministically and reserve output space before sending. Never switch providers or effective modes silently.
- Use per-provider rate limits with bounded backoff and jitter for transient failures, honoring retry hints within the deadline. Stop on permanent errors, cancellation and exhausted budgets. Keep retries metered. Cache only through supported mechanisms using a stable system prefix and record cached input separately. Batching is optional and measured as a separate configuration.
- Estimate charges from the recorded pricing snapshot and billable token categories, then reconcile actual usage where available. Mark unreported usage or pricing unknown, distinguish measured from estimated totals, and record local inference time and optional energy separately. Preserve per-finding failure codes for budget exhaustion, turn cap, schema retry/failure, tool error, refusal, token cutoff, invalid evidence, provider throttling and timeout.
- Prefer available free tiers during development. Verify model availability, capability, privacy/retention, quotas and pricing before use and record the verification date. Private repository code requires explicit remote-provider opt-in. Start Ollama trials with a small quantized model, short context and one inference at a time on an 8 GB laptop. Measure peak memory and latency with other services active. Expect weaker reasoning and tool adherence on complex findings. A local or fixture-backed path is available for development without paid keys.

Record a dated provider/model capability matrix for native tool calling, schema enforcement, context, token/cost reporting, caching, retry limits and version resolvability. Mark each cell verified, unsupported or unknown. Qualify the model with adapter contract tests and a bounded smoke before evaluation. Benchmark single-shot, tools, providers and retrieval policies as explicit experimental conditions. No silent fallback.

## 3. Signature features and developer experience

- **Visual evidence chain.** Render ordered citation cards linking to actual relative paths and lines. Label nodes as observed citations or explicit assumptions. Label links as observed when supported by a cited transition, inferred when derived from the analysis, or unverified. Every asserted link references evidence IDs and provenance. Leave unsupported edges absent. A plain citation list is the fallback. Investigators can inspect redacted tool summaries, verdicts, cost and usage coverage from the same view.
- **Model Evaluation Lab.** Read stored artifact summaries showing dataset, run ID, model/version, provider, precision/recall/MCC, latency, cost and available confidence intervals. Highlight mismatched protocol fingerprints and disable head-to-head ranking when incompatible. Show undefined measures with a reason. No inference on dashboard load.
- **Adversarial suite.** Exercise prompt injection in source/README, fake roles, misleading comments, traversal, symlinks, oversized files and malformed tools. Record denied requests, unauthorized access, invalid evidence, verdict flips and failures separately. [Test scenarios](docs/THREAT_MODEL.md)

Preserve `argus scan <repo>`, `argus audit <repo>`, `argus runs`, `argus show <run-id>` and `argus bench ...`. Emit Markdown, JSON and SARIF from the same validated records. CLI and benchmarks use immutable manifests and resumable file journals. Document local setup, environment variables, database, scanners, model configuration, API/UI startup, benchmarking, diagnostics and limitations in the implementation README. Verify examples in CI with fixture responses.

### MCP integration (M7 · P1)

After the standalone CLI works end to end, expose the same Python engine through a local MCP server over stdio using the Python SDK. `audit_repo` accepts an approved repository, an optional revision and a bounded finding limit, and returns a structured report. `triage_finding` accepts an approved repository and a schema-validated finding, and returns a verdict with citations. Both reuse the CLI snapshot policy, read-only tool permissions, provider privacy settings and execution budgets. The server runs independently of Express and PostgreSQL. SastBench continues to use its official evaluator adapter.

Smoke-test both tools from a supported MCP client with fixture-backed responses. Confirm that valid calls return schema-valid results while disallowed paths and malformed findings fail before analysis. Reserve stdout for protocol messages and send diagnostics to stderr. Document the client setup and retain the smoke-test transcript for the M7 demo.

## 4. Milestones and acceptance gates

M0–M4 are ordered dependencies. Run M5–M8 in presentation order. M6 measurement depends on M3 and the frozen recipe and can proceed without a web UI. M7 core integrations use M3, and the CI scoring replay uses M6 tooling. Each milestone records a runnable test or artifact and its actual outcome in PROGRESS. The default budget is USD 0 mandatory paid model or hosting spend, assuming an existing laptop. Estimate runtime, disk and retry headroom before live runs. Use mocks, a local small model or verified free tiers with hard caps. A blocked free configuration becomes a reported limitation. No fixed completion date.

| Milestone and goal | Deliverables and dependencies | Acceptance and required tests | Risks and cost constraints | Demo evidence |
|---|---|---|---|---|
| M0 · Prove feasibility | Pin evaluator and generator, freeze split, scaffold projects, Compose, strict lint/type/test and CI, trace scaffolding and parity fixtures. Start here. | Five-sample official smoke, one-month generator smoke, isolated checkout and tool proof, cross-runtime schema fixtures and DB readiness. Record upstream scoring/error behavior. | Upstream drift and Docker isolation; local bandwidth and disk, no paid calls. | Evaluator log, generator checksum, split and canary test. |
| M1 · Produce trusted scanner output | M0. Seal snapshots, pin offline Semgrep, normalize and dedupe, CLI/basic reports and product filter audit. | Known fixture results, deterministic IDs, SARIF round-trip fixture, scanner timeout and sandbox tests. Never execute target code. | Rule drift and scanner memory; local compute, no model. | Replayed fixture scan with immutable manifest. |
| M2 · Establish a triage baseline | M1. Provider adapters, single-shot, evidence checks, usage journal and standalone official adapter. | Mock capabilities/retries and redaction tests, qualify live configs, ten-finding dev/adaptor smoke with app down, measure original single-shot dev gate. | Refusals, model changes and quotas; bounded dev sample and USD 0 paid cap. | CLI verdict, metered journal and official dev artifact. |
| M3 · Test investigation value | M2. Restricted tools, symbol index, loop, budgets and adversarial suite. | Jail, parsing, time/budget and invalid citation tests. Retain no-flip target on the controlled fixture. Run matched dev ablation and document gate outcome before held-out scoring. | Injection and context growth; limited local/free pilot. | Citation trail, paired dev outcome and denied tool trace. |
| M4 · Prove durable backend | M3. Drizzle schema, strict API, worker, retries, atomic ingestion and correlated traces. | Real DB validation, clean/upgrade migrations, duplicate submissions, two claimers, lease expiry, rollback, malformed/partial results, cancel/timeout/shutdown, and recovery across a more-than-once model call. Demonstrate 202 before completion. | Stale children, duplicate charges, unavailable DB; one local DB and fake model. | Kill/restart trace, SQL invariants and same-key replay. |
| M5 · Deliver useful UI | M4. Repository management, polling, findings, chain, history and report routes. Build Evaluation Lab against fixture imports. | Browser flow starts and cancels a scan, handles failure, pagination, hostile content and evidence navigation. No model calls on reads. | Stale progress and unsafe rendering; fixture model and local stack. | Scan progress to cited evidence and compared fixture evaluations. |
| M6 · Measure quality and reliability | M3 and frozen M0 split. Freeze held-out recipe, matched official runs and free-model comparisons, import summaries, complete recovery demonstration against M4. | Metric/error/abstention/leakage and cost tests, blinded relevance sample, artifact replay, end-to-end worker failure with no duplicated final results. | Model drift and low free-tier throughput; use small matched cohorts and disclose coverage. | Reproduced metric table, failure trace and run IDs. |
| M7 · Make integrations usable | M3 and M6 scoring. MCP stdio, CLI polish, Markdown/JSON/SARIF, docs and CI replay. | Same jail through MCP, client smoke, fixture-backed setup, SARIF validation, fixed 20-dev replay and budget regression. | Client compatibility; local or mock execution. | Stdio client transcript and reproducible CLI-to-report demo. |
| M8 · Publish research and demo | M6/M7. Frozen results, uncertainty, recent/post-cutoff slice, diagrams, article and measured portfolio claims. | Recompute checksums, cluster bootstrap and figures. Publish original/recent, language/CWE, limitations and negative results. Verify demo from a clean local setup. | Unknown cutoffs and sparse classes; expand only within feasible local/free capacity. | Published artifact IDs, replay recipe and recorded recovery demo. |

### Release quality gates

- Backend passes fault injection with real PostgreSQL. Accepted submissions survive process loss. Stale attempts cannot publish, cancellation and timeout release resources after verified cleanup, and replay produces one immutable final result.
- Security tests detect unauthorized access and fail on a jail escape. Untrusted content cannot widen permissions. Secret canaries stay out of model payloads, artifacts and telemetry. Test the actual supported boundary and do not generalize beyond it.
- Every surfaced finding has validated evidence or an explicit review state. Track model/usage failures including unknown charges. Evaluate like-for-like and keep engineering completion separate from research success.
- Every published number resolves to pinned run artifacts. The held-out split remains untouched during tuning. Publish reproducibility limits, denominators and unsupported comparisons.

## 5. Final architecture review

| Review area | Decision and verification |
|---|---|
| Complexity and simpler alternatives | Two runtimes and one DB are justified by the product and portable engine. One worker module, polling and table-based graphs avoid a separate broker, worker service, live-update stack and graph store. The dashboard can be removed from a research run. |
| Responsibility and data ownership | Node exclusively owns PostgreSQL and worker coordination. Python owns analysis. Contract parity fixtures and standalone evaluator runs demonstrate the boundary. |
| Crashes and retries | Fenced leases, cleanup ownership, stable result keys and durable call reservations handle restarts. Kill a worker during inference and near commit. Confirm repeated external calls and unknown costs remain visible. |
| Sandbox | The plan requires OS controls and tests, with feasibility unverified until M0. An unsupported host fails closed. Test no egress, no host access, no credential leakage and resource limits. |
| Providers and cost | Adapters expose capability differences. Free/local execution and mocks cover development, while model availability, 8 GB capacity and throughput can limit study scope. |
| Scientific defensibility | Official evaluator, frozen split, parity probes and matched experiments remain required. Approximate negatives, unknown cutoffs and model nondeterminism are stated limitations. |
| User value and incremental delivery | The UI locates evidence and history and compares stored runs. The scanner and CLI are usable earlier, and a small evaluation and one local worker keep P0 realistic for one developer. |
| Interview verification | Show an isolation canary, stale-worker and cancellation tests, exact run manifests and replayable metric tables. Use measured claims only. |

## 6. Revision log

**Rev 4 (2026-11-22).** Preserved the hybrid decision and benchmark design. Split scan state, schedulable jobs and execution attempts. Added fenced retry and cleanup, idempotent admission, private checkpoints, persisted partial telemetry and pre-dispatch reservations for at-least-once external execution. Specified normalized evaluation/failure rows and schema migration tests. Added versioned API/process details, observability, recovery tests, evidence-chain provenance and an artifact-only evaluation lab. Moved detailed architecture, data, evaluation and threats into linked documents. Introduced P0/P1/P2 priorities, milestone demo evidence and objective gates. Kept security and research gates independent. Expanded explicit evidence relevance assessment and provider qualification without changing the benchmark input or primary scoring policy.

**Rev 3 (2026-11-22).** Adopted Argus naming and the hybrid local-first stack. Added an optional React dashboard and Express REST application with PostgreSQL and Drizzle ownership. Replaced the shared SQLite ledger with API-owned relational persistence and independent file-based CLI/benchmark artifacts. Defined versioned contracts, asynchronous job submission, polling, bounded subprocess execution, fenced attempts, cancellation, recovery, partial-result handling and transactional replay. Deferred Redis/BullMQ until local processing requirements change.

Generalized model selection from fixed Anthropic runs to Gemini, Groq and Ollama, with Anthropic optional. Replaced provider-specific caching, batching and cost assumptions with capability checks, usage records and enforceable budgets. Added OS and filesystem controls for malicious content, path escapes, process execution and resource exhaustion. Retained untriaged scanner sections, deterministic evidence checks, MCP stdio and report formats.

Preserved official evaluator integration, input parity, repository split, abstention mapping, benchmarks and research gates. Replaced PR-AUC from verdict confidence with an explicit positive-class score and defined error sensitivity and score coverage. Made recent-slice claims conditional on verified cutoff and comparable conditions. Moved held-out evaluation to M6 and expanded research to M8, retaining the original larger-run design subject to quotas and reproducibility. Changed the tiny live fixed-provider CI gate to deterministic replay plus a capped live smoke. Replaced the fixed timeline and paid-model estimates with staged tests, dependency gates and measured cost forecasts. Added the monorepo plan, checklist and ADR.

**Rev 2 (2026-11-08, after advisor review and reading the SastBench repository).** Switched the
SastBench harness to the official evaluator with SASTTrace as an agent directory, which also gives
input parity between classes and like-for-like baselines. Removed rule-text recovery, severity-
based effort and the `git_blame` tool (label and history leakage). Single-commit fetch with `.git`
outside the jail. Repo-level dev/test split frozen in M0; dev on Sonnet, test on Opus. Fixed the
abstention rule and added abstention-rate reporting. Metrics: cluster bootstrap CIs, PR-AUC,
paired bootstrap, 3 seeds, per-language and per-CWE breakdowns, leakage probe, invalid-evidence
rate, failure taxonomy, cost per surfaced true positive. Contamination control is now a fresh
SastBench slice from the official generator; OpenSSF CVE Benchmark (stale since March 2024) and
eyeballvul (no line-level labels) moved to optional. Evidence placed before decision in the
schema with deterministic validation. Incremental caching across turns; corrected the cost table
for accumulated input; Batch API for single-shot sweeps; development budget stated. Cut GitHub
Action, Streamable HTTP and the Opus frontier plot. M0 now contains the data spike; M3 and M4
gates quantified; osv and gitleaks findings reported untriaged. Added the honest-positioning
paragraph about existing toy repos and Endor Labs' plugin.
