# ADR-001 · Hybrid local-first architecture

Status **Accepted for Revision 3 planning**

Date 2026-11-22

## Context

Revision 2 kept the scanner, agent, CLI, evaluator integration and SQLite ledger in Python. That design minimized setup and let a solo developer run the evaluator independently. Its research value came from the official evaluator, admissible input parity, explicit abstention rules and independent evidence checks. Revision 3 adds a local dashboard while preserving those evaluation boundaries.

## Decision

- **Keep Python as the analysis engine.** Python owns scanner adapters, Tree-sitter, model adapters, evidence validation, benchmark execution and MCP. CLI, MCP and the evaluator reuse the same triage and tools. Files hold benchmark artifacts and resumable checkpoints, keeping the evaluator portable.
- **Use Express for the application API.** TypeScript and Zod fit the dashboard-facing contract and keep HTTP concerns, lifecycle management and result queries in one service. The API submits work asynchronously. The initial transport is a controlled Python subprocess with versioned requests, progress messages and result documents.
- **Use PostgreSQL for application data.** Scan claims and result publication benefit from transactions, row-level locking and relational constraints across runs, findings, evidence and usage. Drizzle owns migrations and writes. PostgreSQL adds a local service and setup overhead compared with Revision 2's SQLite ledger. Docker Compose makes that cost explicit and the benchmark path has no database dependency.
- **Keep React optional.** The dashboard makes local triage easier to operate. Headless CLI and official evaluator runs remain first-class and share the same engine and schemas.
- **Defer Redis and BullMQ.** A bounded local manager and PostgreSQL-backed lifecycle cover single-instance processing and recovery. Revisit when distributed workers, independent queue reliability or multiple API instances are demonstrated requirements.
- **Use provider-specific adapters.** Gemini, Groq and Ollama widen access for development and support controlled model comparisons. Providers differ in tool calling, structured output, cache behavior, limits and policy. The common interface exposes those differences explicitly so unsupported configurations fail visibly. Anthropic can be added through the same interface.

## Consequences

The local application has two runtimes and a database. Cross-language contract fixtures, explicit schema versions and a small subprocess protocol limit integration overhead. The API must fence stale worker attempts and handle cancellation, process cleanup and ingestion atomically at the persistence boundary. The benchmark uses independent file artifacts and the official evaluator contract, so application changes can be tested without perturbing the study.

The first technical spike needs to establish that the official evaluator can run Argus with isolated, network-disabled repository tools while the evaluator and configured model client retain necessary connectivity. Live comparisons depend on verified model capabilities, quotas, privacy terms and version provenance. [Revision 3 plan](../PLAN.md)
