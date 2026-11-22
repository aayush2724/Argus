# ADR-002 · Durable local execution and isolated analysis

Status **Accepted for Revision 4 planning**

Date 2026-11-22

## Context

ADR-001 selected a hybrid local-first architecture and kept the official evaluator independent. Its initial lease design attached execution state to the scan and relied on manual retry. Revision 4 needs recoverable attempts, durable partial progress and precise handling of interrupted external calls.

## Decision

- **PostgreSQL coordinates jobs.** A scan and its job commit together. Row locks, leases and fenced attempts recover crashes. Separate attempts preserve diagnostic and usage history while final publication stays atomic. A transient retry is another attempt under the same scan, with the same pinned inputs and remaining budget.
- **Defer Redis and BullMQ.** A second durable store would add deployment, recovery and DB/queue consistency concerns. Reconsider if measured contention or a need for multiple independent worker hosts exceeds the tested local controller.
- **Separate Node coordination from Python analysis.** Node owns durable state, API behavior and process supervision. Python implements scanning, restricted navigation, provider contracts and evidence policy once for UI, CLI, MCP and official evaluation. Versioned process messages and reports are the boundary.
- **Require enforceable isolation.** Untrusted input crosses parsers, scanner tooling and model context. Repository readers and scanners require OS isolation, bounded resources and no egress. Prompt instructions and JSON validation are additional controls. M0 must verify the boundary in the evaluator topology before live evaluation.
- **Keep evaluation independent.** File-based checkpoints and manifests preserve reproducibility and enable headless use. The product imports only validated summaries. Benchmark inputs and labels stay with the evaluator.

## Consequences and alternatives

One local service and one controller limit throughput but keep cancellation and recovery observable. An in-memory queue loses accepted work on restart. A scan-only lease becomes ambiguous when accounting spans attempts. The chosen additional tables earn their cost through bounded recovery and attribution. External model execution remains at least once. The controller budgets dispatches and records unknown outcomes. [Execution protocol](ARCHITECTURE.md) · [Original hybrid decision](ADR-001-hybrid-architecture.md)
