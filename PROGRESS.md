# Argus progress

## Current state

M0 source inspection started. The checkout contains project documentation. The application, scanner engine, evaluator adapter, migrations, CI and dashboard have yet to be implemented. No scans, benchmark metrics, cost measurements or runtime test results are recorded.

## Planning history

| Revision | Documented outcome |
|---|---|
| 2 · 2026-11-08 | Advisor-reviewed research design with the official SastBench evaluator, a frozen repository split, restricted analysis and transparent scoring. |
| 3 · 2026-11-22 | Hybrid local-first plan, provider adapters, API-owned PostgreSQL and database-independent benchmark artifacts. |
| 4 · 2026-11-22 | Durable jobs and attempts, retry/cost accounting, enforceable isolation, evidence presentation, evaluation lab and fault-injection gates. Updated the checklist and architecture references. |

## M0 source inspection

- Cloned the official SastBench repository to a temporary directory without a working-tree checkout and inspected commit `b8d95b7720491b21d039b7504999577ba7ebb12b`.
- Confirmed in the pinned source that the evaluator prepares a Git worktree, starts a Dockerized agent, calls `/preprocess` per repository/commit and sends `to_analyzer` to `/analyze` per finding. The evaluator retains ground truth for scoring.
- The evaluator mounts its worktree into the agent container. M0 still needs to prove that Argus can give its repository tools a separate, history-free snapshot and enforce network isolation. The bundled baseline is a comparison agent and does not establish those controls.
- No evaluator or generator runs, model calls, or infrastructure changes yet.

## Next implementation gate

M0 starts with pinned official evaluator and recent generator feasibility, including repository tool isolation. Record the pinned revisions, test commands, observed outcomes, costs and blockers before marking any task complete. [Milestone checklist](TODO.md)
