# Engineering Auditor — Project Plan

Working name: **Argus** (rename freely; folder is `engineering-auditor`).
Date: 2026-11-08 · Status: **locked, revision 2** (after advisor review; changes listed in Part 5)
Owner: aayush2724

One line: an agentic AppSec auditor that runs deterministic scanners on a repository, then uses an
LLM agent with **read-only, path-jailed** code tools to verify each finding with an evidence chain,
and publishes **measured** precision, recall, MCC and cost on SastBench under conditions that are
comparable to the published paper.

The product is the triage, not the detection. Detection is a crowded market (Semgrep, Snyk,
Corgea, Endor Labs). Noise is the unsolved problem: SastBench measures real SAST output at 8.15
false positives per true positive, and the best published agent reaches only **MCC 0.148**.

**Honest positioning.** "Semgrep plus Claude to kill false positives" already exists as a toy on
GitHub several times over, and Endor Labs ships an AI SAST-triage plugin for coding agents. None
of them publish benchmark results. Argus is differentiated by methodology and numbers, not by the
idea. If the numbers are bad, the write-up says so and explains why; that is still a credible
project for the audience.

---

## Part 1 — Discovery

### 1.1 Problem and users

| Who | Pain today | What Argus gives them |
|---|---|---|
| You and your OWASP chapter | Semgrep on a student repo returns dozens of findings; nobody reads them | A short report of verified issues, each with file:line evidence and why it is exploitable |
| Any developer with a repo | Same noise, plus no time | `argus audit <repo>` locally, or the `argus` MCP tool inside Claude Code / Cursor |
| SaaS AppSec and AI-engineering hiring teams (the write-up's audience) | Need people who can design evals and manage LLM cost | Benchmark numbers with confidence intervals, ablations, cost per verified finding, failure taxonomy, limitations |

### 1.2 Hard non-goals for MVP

- Not a new vulnerability detector. Scanners find; the agent verifies.
- No autofix. Fix suggestions are text only.
- No web dashboard. CLI, Markdown/SARIF/JSON reports, MCP server over stdio.
- No DAST and no execution of the target repository's code, ever.
- No GitHub Action, no hosted service, no multi-user.

### 1.3 MVP boundaries

**In:** repo ingest at a given commit (single-commit fetch); Semgrep OSS findings triaged by the
agent; osv-scanner and gitleaks findings reported **untriaged** in their own sections (they cannot
be judged by reading code); normalised `Finding` schema with SARIF in/out; triage agent with
read-only tools and per-finding budgets; reports; SQLite run store with cost ledger and failure
taxonomy; **SastBench agent adapter** so Argus runs inside the official evaluator; a fresh
post-cutoff SastBench slice built with the official generator; a tiny CI regression eval; MCP
server (stdio); write-up.

**Optional if time allows (not in the plan's critical path):** OpenSSF CVE Benchmark runner
(repo last pushed March 2024, all CVEs pre-2024 and contaminated), eyeballvul detection runs (it
has no line-level labels; it is a detection benchmark scored by an LLM matcher), GitHub Action,
Streamable HTTP for MCP, autofix for one CWE.

### 1.4 Languages

Tree-sitter symbol tools for JavaScript/TypeScript and Python. Everything else gets `read_file`,
`grep` and `list_dir` only. SastBench spans 38 languages (mostly PHP, JS/TS, Python), so **every
result is reported per language**, and the "with symbol tools" claim is made only for JS/TS/Python.

### 1.5 External dependencies

| Dependency | Role | Licence | Verified facts (2026-11-08) |
|---|---|---|---|
| **SastBench** `github.com/RivalSecurity/sastbench` | primary benchmark and evaluator | Apache-2.0, pushed 2026-05 | Paper arXiv 2601.02941 (Rival Security, Jan 2026). `data/sastbench-v0.1-original.json` = 2,737 findings (299 TP real CVEs, 2,438 FP from Semgrep OSS on the pre-fix commit), 8.15:1. Evaluator (`evaluation/evaluation_cli.py run --agent-dir … --dataset … --output …`) groups by `(repo_url, commit_hash)`, checks out the commit, calls the agent's `preprocess` once per commit and `analyze(processed_data_path, finding_data)` once per finding over a Dockerised REST API; agent returns `prediction ∈ {true_positive, false_positive, error}` + `confidence`. `finding_data` (`to_analyzer`) is the **same shape for both classes**: `vulnerability_type`, `vulnerability_name`, `description`, `locations[{file, function, line_start, line_end}]`, `commit_context`. Bundled agents: `oneshot_analyzer`, `simple_react_agent`, `mini_sweagent_agent`, each taking a `--model` string. `dataset_generation` builds new slices from NVD + PyDriller + Semgrep: `python -m dataset_generation.cli build-benchmark --start-date YYYY-MM --end-date YYYY-MM` (needs `semgrep`, ctags, `GITHUB_TOKEN`; default cap 300 CVEs, seed 42). Published results: Gemini 2.5 Pro MCC 0.148 / P 0.169 / R 0.582; Claude Sonnet 4.5 MCC 0.110 / P 0.140 / R 0.722 |
| Semgrep OSS (`pip install semgrep`) | product-path SAST | LGPL CLI, free registry rules | pin the version; use `p/default`, `p/javascript`, `p/python`, `p/owasp-top-ten` |
| osv-scanner, gitleaks | dependency CVEs, secrets | Apache-2, MIT | reported untriaged; gitleaks snippets **redacted** before any model call |
| Docker | scanner sandbox; required by the SastBench evaluator | free | |
| Anthropic API | triage agent | `claude-opus-5` $5/$25 per MTok (cache read ≈ $0.50); `claude-sonnet-5` $2/$10; Batch API 50% off | provider abstracted behind one interface |
| `tree-sitter` + JS/TS/Python grammars | symbol and caller lookup | MIT | |
| MCP Python SDK (`mcp`) | expose Argus as a tool | MIT | stdio only in MVP |

### 1.6 Cost model (planning numbers; M0 spike measures the real ones)

Per finding. Tool-loop input accumulates across turns; with incremental cache breakpoints most of
it is cache reads.

| Mode | Tokens | Opus 5 | Sonnet 5 |
|---|---|---|---|
| Single-shot (finding + function span + neighbours) | ~6k in / 1k out | $0.055 (Batch: $0.03) | $0.022 (Batch: $0.011) |
| Tool loop, ≤ 8 turns, ~120k cumulative input of which ~85% cached | ~18k uncached + ~100k cached / 3k out | $0.25–0.45 | $0.10–0.18 |

| Run | Samples | Mode | Estimate |
|---|---|---|---|
| Dev iteration | 150 (dev split) | Sonnet tool loop | $15–27 per run; budget 10 runs ≈ $150–270 |
| Test, headline | 600 stratified from the test split, 3 seeds | Opus tool loop | $450–810 |
| Test, full | all test-split samples (~2,400), 1 seed | Sonnet tool loop | $240–430 |
| Fresh-slice contamination check | ~300 | Opus tool loop | $75–135 |
| Paper-style baselines on same model and subset | 600 × 2 agents | Opus | ~$150–300 |

Budget tiers for D2 below: **minimum credible ≈ $350** (Sonnet dev, one Opus 600-sample test run,
one Sonnet full-test run, baselines on Sonnet); **recommended ≈ $900–1,200** (adds 3 Opus seeds and
the fresh slice).

### 1.7 Assumptions

1. Solo, 6–8 weeks part-time, laptop plus Docker.
2. Ground truth comes only from SastBench labels; spot checks are for sanity, not for scoring.
3. The agent never executes repository code; all tools are read-only and jailed to the checkout
   with `.git` excluded; the checkout is a single-commit fetch so later commits (including the
   fix) are not present.
4. The agent sees exactly the benchmark's `to_analyzer` payload plus what its tools read. It never
   sees `source`, `ground_truth`, Semgrep rule ids, rule text or severities during benchmark runs.
5. One primary abstention rule, fixed before any scoring: **surfaced = predicted positive**, so a
   `needs_review` verdict counts as `true_positive` in the primary metric. The abstention rate and
   the alternative accounting (abstain = negative) are always reported alongside.

### 1.8 Risks

| Risk | Mitigation |
|---|---|
| Label leakage through asymmetric inputs | Input parity by construction (payload only). Metadata-only probe: a classifier trained on payload fields without code must score ≈ random, and the probe result is published |
| Git-history leakage (the fix is in a later commit) | `git fetch --depth 1 <commit>`, `.git` outside the tool jail, no `git_blame` tool |
| Contamination inflates recall on famous CVEs, not on FPs | Fresh slice built with the official generator from CVEs published after the model's cutoff; report original-slice and fresh-slice numbers separately |
| Tuning on the test set | Repo-level dev/test split made in M0 and frozen; dev = 150 samples; test touched only at M4 and M5 |
| Wrapper trap | M3→M4 ablation with a quantified gate (Part 3). If tools do not help, the project reports why |
| Statistics on ~65 TPs | MCC with repo-cluster bootstrap 95% CI, PR-AUC, paired bootstrap for ablations, 3 seeds per configuration |
| Evidence hallucination | Deterministic check that every cited file:line exists and lies in the checkout; invalid-evidence rate is a reported metric and invalidates a `true_positive` to `needs_review` |
| Cost blow-up | Per-finding token and turn budgets, per-run cap, resumable runs with rate limiting, Batch API for single-shot sweeps, Sonnet for dev |
| Prompt injection from repo content | Repo text as delimited untrusted data; no write or exec tools; schema-constrained output; fixture repo with injection comments in CI; flip rate reported |
| Over-claiming or unfair comparison | Every README number cites a run id; comparisons to the paper only on matching model, agent and subset; language coverage stated |

### 1.9 Decisions to confirm before M0

| # | Question | Recommended default |
|---|---|---|
| D1 | Symbol-tool languages | JS/TS and Python; others get file tools only |
| D2 | Models and budget | Sonnet 5 for development on the dev split; Opus 5 for test-split headline runs and the fresh slice. Budget tier: recommended (~$900–1,200) if affordable, else minimum (~$350) |
| D3 | Delivery surface | CLI + Markdown/SARIF/JSON + MCP over stdio; no UI, no Action |

---

## Part 2 — Architecture

### 2.1 Two paths through one core

```
Product path:   argus audit <repo> [--commit SHA] [--max-findings N]
   ingest (single-commit fetch, lang detect, size guard)
   → scan (semgrep | osv | gitleaks, in Docker) → normalise (Finding, SARIF) → Stage 0 filters
   → triage agent on Semgrep findings → report (md / sarif / json) ; osv + gitleaks sections untriaged

Benchmark path: SastBench evaluator → Argus agent container (REST)
   preprocess(repo_path): index symbols (tree-sitter), manifest summary, jail setup
   analyze(processed, finding_data): build Finding from `to_analyzer` → triage agent → prediction

Shared: triage agent, tools, budgets, provider, SQLite ledger (runs, findings, verdicts,
tool calls, costs, failures), OpenTelemetry spans, metrics module.
```

### 2.2 Core schema (Pydantic; `Verdict` is also the structured LLM output)

```python
class Finding(BaseModel):
    id: str; tool: Literal["semgrep", "osv", "gitleaks", "benchmark"]
    cwe: list[str]; title: str; description: str
    locations: list[Location]            # file, function | None, start_line, end_line
    # product path only, never in benchmark mode:
    rule_id: str | None = None; severity: str | None = None; snippet: str | None = None

class Evidence(BaseModel):
    file: str; start_line: int; end_line: int
    role: Literal["source", "propagation", "sanitizer", "sink", "config", "test", "other"]
    note: str

class Verdict(BaseModel):                 # field order is deliberate: think, then decide
    evidence: list[Evidence]
    preconditions: list[str]
    reasoning_summary: str                # ≤ 80 words
    decision: Literal["true_positive", "false_positive", "needs_review"]
    confidence: float
    cwe: str | None
    fix_direction: str | None             # text only
```

Post-validation in code: every `Evidence` location must exist in the checkout; a `true_positive`
with zero valid evidence becomes `needs_review` and increments `invalid_evidence`.

### 2.3 Triage agent

- **Tools, all read-only, jailed to the checkout (minus `.git`), size-capped:** `read_file(path,
  start, end)`, `grep(pattern, glob)`, `list_dir(path)`, `read_manifest()`, and for JS/TS/Python
  `find_symbol(name)` and `callers(name)` from the tree-sitter index built in `preprocess`. No
  shell, network, write, or git.
- **Loop:** Anthropic Messages API, `strict` tools, hard turn cap 8, per-finding token budget,
  structured output into `Verdict`. Effort is set by **remaining budget**, never by severity
  (severity is absent in benchmark mode and would leak the label).
- **Caching:** frozen system block first (persona, verdict rules, evidence rules, abstention
  rule); then the per-finding conversation with an incremental `cache_control` breakpoint on the
  latest turn so each turn reads the previous prefix. Cache hit rate is logged per finding; if the
  prefix is below the model's minimum cacheable length the marker is dropped automatically.
- **Stage 0 (product path only):** deterministic filters: test paths, vendored or generated code,
  informational rules. Each filtered finding is recorded with its reason. Not applied in benchmark
  mode, where the payload carries no rule metadata.
- **Failure taxonomy** recorded per finding: `budget_exhausted`, `turn_cap`, `schema_retry`,
  `tool_error`, `refusal`, `max_tokens`, `invalid_evidence`. Reported as rates in every run.
- **Resumable runs:** every finding's result is written immediately; re-running a run id skips
  completed findings; client-side rate limiting and SDK retries on 429/5xx.

### 2.4 Evaluation methodology

| Element | Rule |
|---|---|
| Benchmark | SastBench v0.1 original (2,737) via the **official evaluator**, Argus packaged as an agent directory with the same Dockerfile/REST contract as `agents/oneshot_analyzer` |
| Split | Repo-level dev/test split, seeded, frozen in M0 and committed as a file. Dev ≈ 150 findings. Test is never used to tune prompts or budgets |
| Inputs | Exactly `to_analyzer` plus tool reads. No rule text recovery, no severity, no `source` |
| Leakage probe | Logistic regression on payload-only features (CWE, description length, location count, language) must be ≈ random on test; result published |
| Primary metric | MCC (as the paper). Secondary: precision, recall, F1, **PR-AUC** from `confidence`, abstention rate, invalid-evidence rate, cost per finding, **cost per surfaced true positive**, p50/p95 latency, failure-taxonomy rates |
| Uncertainty | Bootstrap over repo clusters (95% CI); paired bootstrap for ablations; 3 seeds per configuration on the headline subset |
| Breakdowns | Per language (with and without symbol tools) and per CWE family |
| Like-for-like comparison | The paper's 0.148 is Gemini 2.5 Pro on all 2,737. Argus is compared to the paper only when run on the full set with the same abstention rule; otherwise the comparison is to the bundled `oneshot_analyzer` and `simple_react_agent` **run on the same model and the same subset** |
| Contamination | Build `sastbench-v0.1-<recent months>` with the official generator from CVEs published after the model cutoff; report both slices; the gap is a headline result |
| Baselines, every table | all-positive, all-negative, random at base rate, Argus single-shot (M3), Argus tool loop (M4), paper-style agents on same model |
| Regression eval in CI | 20 dev findings run on Sonnet with a fixed seed; MCC and cost must stay within tolerance for a PR to pass |

### 2.5 Reports

- `report.md`: verified Semgrep issues first, grouped by CWE, each with evidence table and
  preconditions; `needs_review`; dismissed with one-line reasons; untriaged osv and gitleaks
  sections; cost, tokens, model, prompt hash, run id.
- `report.sarif`: verdict, confidence and evidence as result properties.
- `report.json`: raw `Verdict` list plus failure taxonomy.
- `argus runs`, `argus show <run>`: metrics tables from SQLite.

### 2.6 MCP server (stdio)

`argus-mcp` exposes `audit_repo(path, commit?, max_findings?)` and `triage_finding(finding_json,
repo_path)` and returns the JSON report. Works from Claude Code or Cursor on a local repo.

### 2.7 Stack

Python 3.13+, `uv`, Typer, Pydantic v2, `anthropic` SDK 2.x, `tree-sitter` with grammars,
`semgrep` (pinned), `osv-scanner` and `gitleaks` in Docker, SQLAlchemy 2 on SQLite, structlog,
OpenTelemetry SDK (console exporter; Langfuse optional), `mcp`, pytest, ruff, mypy. No Postgres,
no queue, no UI.

### 2.8 Security of the auditor itself (talking point)

Threat model: a malicious repository tries to make the auditor dismiss a real vulnerability or
exfiltrate data. Controls: read-only jailed tools without `.git`; no execution or network;
repository text wrapped as untrusted data; schema-constrained verdicts with evidence validation;
gitleaks hits redacted before any model call; a fixture repo with injection comments in CI and a
reported verdict-flip rate.

---

## Part 3 — Milestones

| # | Milestone | Deliverables | Acceptance criteria (gates) |
|---|---|---|---|
| M0 | Scaffold + **data spike** | `uv` project, Typer CLI, SQLite + migrations, structlog, OTel spans, fixture repo (`fixtures/vuln-express`: SQLi, path traversal, sanitised look-alike, injection comment), `argus doctor`, pytest/ruff/mypy. **Spike:** clone SastBench, run its evaluator with the bundled `oneshot_analyzer` on 5 findings using the Anthropic model string, confirm the REST contract and `--model` handling; build the repo-level dev/test split file; run `build-benchmark` on a 1-month recent window to confirm the generator works | Evaluator runs end to end on 5 findings; split file committed; generator produces a slice; tests green |
| M1 | Scanner layer (product path) | Semgrep/osv/gitleaks adapters in Docker, `Finding`, SARIF in/out, dedupe, Stage 0 filters, `report.md` without LLM, redaction | `argus scan fixtures/vuln-express` lists expected findings; gitleaks snippets redacted; run stored |
| M2 | Benchmark adapter + metrics | Argus agent directory for the SastBench evaluator (`preprocess`, `analyze`, Dockerfile), single-commit fetch + jail, metrics module (MCC, PR-AUC, cluster bootstrap, paired bootstrap), baselines, leakage probe, cost ledger, resumable runs | `argus bench --mode all-positive` and `--mode random` reproduce expected MCC ≈ 0; leakage probe ≈ random on test; a 10-finding Argus dry run completes through the official evaluator |
| M3 | Triage v1, single-shot | Provider, cached system prefix, `Verdict` output, evidence validation, failure taxonomy, Batch API path | On dev (150, Sonnet): MCC with CI above random **and** at least matching the bundled `oneshot_analyzer` on the same model and subset; invalid-evidence rate < 10%; injection fixture does not flip verdicts |
| M4 | Triage v2, tool loop (**go/no-go**) | Jailed tool set, tree-sitter index in `preprocess`, turn/token budgets, budget-based effort, incremental caching, rate limiting | On dev: paired-bootstrap 95% CI of ΔMCC (v2 − v1) excludes 0, **or** v2 matches v1's MCC at ≥ 30% lower cost per finding. Otherwise the plan is revised before M5 and the write-up's thesis changes |
| M5 | Test-set evaluation | Frozen prompts; headline 600-sample test runs (Opus, 3 seeds); full test on Sonnet; paper-style agents on same model and subset; fresh post-cutoff slice; per-language and per-CWE tables; calibration curve | README tables filled from run ids with CIs; original vs fresh slice gap reported; comparison claims match conditions |
| M6 | MCP + report polish | `argus-mcp` over stdio, SARIF properties, Markdown polish, CI regression eval wired | Works from Claude Code on a local repo; SARIF validates; CI eval passes |
| M7 | Write-up and demo | README with methodology, numbers, limitations, cost; blog post; OWASP chapter demo on three members' repos | Three real repos audited live; write-up published with run ids |

Order is strict. M0's spike is the first thing done in the new session, because every later
estimate depends on the evaluator and generator actually running.

### Resume line template (fill from run ids)

"Built Argus, an agentic SAST triage system (Semgrep → Claude agent with jailed read-only code
tools → evidence-validated verdicts). On SastBench (2,737 real findings, 8:1 noise) reached MCC
__ [CI __–__] vs __ for the paper-style agent on the same model and subset, at $__ per finding and
$__ per verified true positive; post-cutoff slice MCC __. Shipped as CLI, SARIF and MCP server."

---

## Part 4 — Kickoff for the new session

Open a new Claude Code session in this folder and paste:

> Read PLAN.md fully. It is the locked plan (revision 2) for Argus, an agentic SAST triage auditor.
> Start at milestone M0 exactly as specified in Part 3, beginning with the data spike against the
> SastBench evaluator and generator, one milestone at a time, with tests at each step, and
> summarise at the end of each milestone (implemented, files, tests run, measured costs,
> limitations, next). Confirm decisions D1–D3 with me only if you disagree with the defaults.
> Keep TODO.md and PROGRESS.md. Never use the test split before M5. Record tokens and cost on
> every model call from the first one, and never let the agent see `source`, `ground_truth`, rule
> ids or severities in benchmark mode.

Conventions carried over from the XBot build that worked well: `uv`, strict ruff and mypy from
day one, real integration tests where the thing under test is a database or a CLI, absolute
paths in scripts, and one commit per milestone with the summary in PROGRESS.md.

---

## Part 5 — Revision log

**Rev 2 (2026-11-08, after advisor review and reading the SastBench repository).** Switched the
SastBench harness to the official evaluator with Argus as an agent directory, which also gives
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
