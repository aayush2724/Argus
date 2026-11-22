# Argus implementation checklist

All milestones are pending. [Revision 4](PLAN.md#4-milestones-and-acceptance-gates) defines dependencies, costs and demo evidence. Record completed acceptance tests, artifacts and measured costs in [PROGRESS.md](PROGRESS.md).

## M0 · Feasibility and foundation

**P0 · Start here.**

- [ ] Pin SastBench and smoke-test the official evaluator with a bundled agent on about five findings.
- [ ] Generate a one-month recent slice and record prerequisites, provenance and checksums.
- [ ] Verify repository/commit grouping, payload parity, single-commit export and network isolation for analyzer tools.
- [ ] Freeze the seeded repository-level split and keep held-out scoring separate.
- [ ] Scaffold Python and strict TypeScript projects, Compose PostgreSQL, CI, trace propagation and lint/type/test commands.
- [ ] Establish versioned JSON Schema contracts and Pydantic/Zod parity fixtures.

## M1 · Deterministic scanner

**P0 · Requires M0.**

- [ ] Build snapshot ingestion, pinned offline Semgrep execution and normalized finding IDs.
- [ ] Add scan CLI, basic reports, SARIF round-trip and recorded product filters.
- [ ] Test redaction and report scanner scope and omissions.
- [ ] Verify expected findings, resource bounds and isolation on inert fixtures.

## M2 · Single-shot AI triage

**P0 · Requires M1.**

- [ ] Add provider interface and Gemini, Groq and Ollama adapters with capability checks.
- [ ] Implement single-shot verdicts, evidence validation and usage/cost accounting.
- [ ] Run the Python adapter through the official evaluator with API, UI and PostgreSQL absent.
- [ ] Run the matched dev gate and record schema, budget and evidence failures.

## M3 · Agentic code investigation

**P0 restricted tooling and P1 expanded fixtures · Requires M2.**

- [ ] Implement jailed file tools and JS/TS/Python symbol lookup with Tree-sitter.
- [ ] Add the multi-step loop, checkpoints and turn, token, time and tool limits.
- [ ] Test traversal, symlinks, resource bounds and prompt-injection behavior.
- [ ] Assess the paired dev ablation and record any research scope revision.

## M4 · Durable backend

**P0 · Requires M3.**

- [ ] Define Drizzle tables and migrations and test against local PostgreSQL.
- [ ] Implement repository, scan, findings and evaluation endpoints with Zod validation.
- [ ] Implement scan/job/attempt transactions, bounded claims, leases, heartbeats, polling and backoff.
- [ ] Test shutdown, timeout, cleanup, cancellation and resume after killing a worker during an authorized call. Assert unknown cost is reserved and late writes fail.
- [ ] Test HTTP 202, duplicate job admission, concurrent claims, guarded partial writes, transactional rollback, conflicting report replay and schema mismatch.

## M5 · Product interface

**P1 · Requires M4.**

- [ ] Build React repository management, scan launch/cancel and progress polling.
- [ ] Add findings, redacted investigation details, usage/cost, a cited visual chain and history.
- [ ] Add the artifact-only Evaluation Lab and flag incompatible comparisons.
- [ ] Smoke-test terminal states, client errors, pagination and rendering of untrusted text.

## M6 · Evaluation and reliability

**P0 evaluation and P1 recovery demo · Requires M0 split, M3 engine and M4 for the recovery demo.**

- [ ] Freeze model/configuration manifests and scoring rules before held-out scoring.
- [ ] Run official matched single-shot, tool-loop and free-model configurations within explicit caps.
- [ ] Verify leakage checks, scoring, score coverage, costs and artifact-based reproduction.
- [ ] Sample evidence relevance separately from verdict correctness and citation validity.
- [ ] Demonstrate restart without duplicate final results and publish benchmark outcomes with run IDs.

## M7 · Developer integrations

**P0 core regression and P1 integrations · Requires M3 and M6 scoring tooling.**

- [ ] After the CLI works end to end, expose `audit_repo` and `triage_finding` through the Python MCP SDK over stdio.
- [ ] Smoke-test both tools from a supported client with fixture responses and Express/PostgreSQL stopped. Verify schema-valid responses and rejection of disallowed paths and malformed findings.
- [ ] Document local client setup and save the smoke-test transcript for the M7 demo.
- [ ] Verify Markdown, JSON and SARIF output and isolate diagnostics from stdio protocol messages.
- [ ] Wire the fixed 20-finding dev replay regression and document the capped live smoke.

## M8 · Research and final presentation

**P1 · Requires M6/M7.**

- [ ] Expand the held-out evaluation with repeats, confidence intervals and matched baselines.
- [ ] Run the post-cutoff slice when model cutoff provenance supports it.
- [ ] Publish reproducible language/CWE breakdowns, failure analysis and technical write-up.
- [ ] Include architecture diagrams, a clean-start demo and measured resume claims with run or test references.

## P2 · Deferred

- [ ] Revisit Redis/BullMQ or streaming progress only when measurements justify them.
- [ ] Revisit hosted operation, authentication, GitHub Actions product integration and expanded scanners separately.
- [ ] Treat automatic fixes as a separate design change. Preserve separate untriaged sections if OSV-Scanner or Gitleaks are added.

