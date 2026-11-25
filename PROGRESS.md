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

## M0 feasibility inspection · 2026-11-24

- Cloned `https://github.com/RivalSecurity/sastbench.git` into a temporary directory and checked out `b8d95b7720491b21d039b7504999577ba7ebb12b`. This is the revision inspected, not yet a completed evaluator run or a frozen generator selection.
- The dataset at `data/sastbench-v0.1-original.json` has SHA-256 `57c765633bdefc2130d3725dd9648bc49b85456e4dd733c55f49d44d883c9487`. A local JSON count found 2,737 findings, 151 distinct repository URLs and 275 repository/commit pairs: 299 true positives and 2,438 approximate negatives. No split was created.
- Docker 29.9.2 and Compose 5.6.1 are available; access to the Docker socket required execution outside the sandbox. Universal Ctags 6.2.1 is installed; Semgrep was not found on `PATH`. The generator additionally requires Python dependencies and network access to NVD and source repositories.
- The official runner calls `cleanup_orphaned_docker_networks()` at startup. At this revision it stops and removes containers whose names start with `eval_` and removes similarly named networks without proving they belong to the current run. It also has a cleanup routine for labeled Neo4j resources. Use an isolated Docker daemon or a reviewed run-scoped mitigation before executing it on a shared daemon. The bundled analyzers are configured for remote model providers; a no-paid-call configuration still needs to be established.
- The upstream README references `data/sastbench-v0.1-jan2024-jun2024.json`, but this checkout contains `data/sastbench-v0.1-original.json` instead. Verify the intended dataset and use its actual path in the smoke command.
- No evaluator or generator run, isolation test, model call, benchmark result or paid spend occurred in this inspection. M0 acceptance items remain open.

## M0 offline protocol probe · 2026-11-24

- Ran `python3 benchmarks/probe_sastbench_protocol.py /tmp/argus-sastbench-m0` against the pinned checkout. It passed: the real upstream `process_commit` task made one preprocess call and two analyze calls for two fixture findings, forwarded their `to_analyzer` objects, and compared returned predictions with the held-back labels.
- The probe substitutes Celery, repository, Docker and HTTP interactions; it does not execute the official CLI or establish grouping, container isolation, score aggregation or end-to-end feasibility. No model call or paid spend occurred.
- The available Docker contexts point at existing daemons rather than an established dedicated test daemon. The upstream task also forwards selected host credential variables to the analyzer container. A safe official run still requires an isolated daemon or reviewed run-scoped cleanup, and a credential-free analyzer configuration.

## M0 official smoke inspection · 2026-11-24

**Stop condition reached:** no dedicated disposable Docker daemon or VM has been established. `docker context ls` lists `default` (system socket) and `desktop-linux` (Docker Desktop socket); neither is known to be isolated from other workloads. No daemon was used, no official CLI was run, and no smoke harness was implemented in this inspection.

- Rechecked `git rev-parse HEAD` and `sha256sum data/sastbench-v0.1-original.json` in the temporary upstream checkout: both match the pinned commit and dataset hash above. `git diff --exit-code b8d95b7720491b21d039b7504999577ba7ebb12b -- evaluation agents data/sastbench-v0.1-original.json` found no tracked changes to the inspected sources or dataset. The checkout has an untracked Python bytecode cache from the earlier probe.
- Source trace: `evaluation/evaluation_cli.py` copies the host environment to the Celery worker, runs global cleanup, groups by `(repo_url, commit_hash)`, submits one `process_commit` task per group, and computes and reports metrics. `evaluation/tasks.py` creates a worktree, starts the analyzer, calls `/health`, `/preprocess`, and `/analyze` for each payload. The result compares `prediction` against the label. The earlier probe exercised only the mocked task path; the CLI, grouping and scoring remain unverified at runtime.
- Credential paths: `evaluation/tasks.py` explicitly forwards nonempty `GCP_CREDENTIALS_PATH`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, `VERTEXAI_PROJECT`, and `VERTEXAI_LOCATION` to containers. An agent config can also mount a file referenced by `api_key` and set Google credential paths; config files themselves are mounted. The bundled oneshot and simple React Compose files additionally interpolate those six variables and may mount `GOOGLE_APPLICATION_CREDENTIALS`; mini SWE agent Compose interpolates `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GOOGLE_APPLICATION_CREDENTIALS`, `VERTEXAI_PROJECT`, and `VERTEXAI_LOCATION`. Image-defined environment and a selected analyzer's Compose file can add more; no blanket credential-free guarantee has been established. No variable values were inspected or recorded.
- Cleanup and failures: startup cleanup selects resources by broad `eval_` names or `created_by=llm_sast_eval` labels, not by current-run ownership. Normal task completion calls per-project cleanup, but an exception after container creation can bypass that call because its `finally` only attempts worktree cleanup. The runner also deletes fixed Celery SQLite filenames from its working and evaluation directories. A separate run directory and failure-safe resource ownership are necessary.
- Scoring risk to test: `_calculate_metrics` selects successful rows by `status` and constructs confusion cells only for recognized label/prediction pairs; `process_commit` sets status success even when a response has an absent or invalid prediction. This requires a real CLI test, including error denominators and partial failures, before relying on scores. No benchmark accuracy is claimed.
- Safe next step: provision a dedicated disposable VM or daemon with no access to the host's existing Docker sockets or credentials; use a credential-free environment and fixture analyzer, preloaded dependencies/images and local fixture repositories to avoid external networking. Verify independent egress denial, resource limits, unique run ownership, teardown on success/failure, and unchanged unrelated resources before any official smoke. This is a proposed design, not a verified execution path. Approval is required before installing privileged services or using an existing daemon.

Checklist: **PASS** pin and dataset integrity; **PASS (mocked only)** task payload and label comparison; **NOT TESTED** official CLI, grouping, aggregation, malformed/missing fields, invalid predictions, timeouts and partial failures; **NOT ESTABLISHED** isolation, credential exclusion and cleanup; **M1 not ready** because M0 feasibility gates remain open. The safe existing probe can be reproduced with `python3 benchmarks/probe_sastbench_protocol.py /tmp/argus-sastbench-m0`; it is not an official smoke test. No safe official smoke command is available yet.

## M0 offline smoke building blocks · 2026-11-24

- Read-only inspection found QEMU, Podman, `unshare`, `newuidmap`, and `newgidmap` on PATH, but no `dockerd-rootless.sh`. No dedicated guest or daemon was established or accessed. No privileged service was installed and no existing Docker workload was accessed.
- Added an offline fixture HTTP analyzer, fresh allowlisted process-environment builder, unique run ID generator and input-based coverage audit. These are components, not a CLI launcher or a Docker cleanup implementation. The environment builder was tested using fake credential variables; container images, mounts and actual CLI execution remain unverified.
- `python3 -m unittest discover -s benchmarks -p 'test_*.py' -v`: the sandbox denied loopback socket creation; rerunning with permission for loopback passed all five tests, including fixture prediction, missing response field, HTTP failure and timeout cases. No external network or Docker was used. The audit tests include an unmatched error and retain every input in the denominator. Neither upstream score aggregation nor official error handling was executed.
- [Offline instructions and isolation prerequisites](benchmarks/SMOKE.md) describe the proposed VM, dependencies, and outstanding implementation. No full fixture repository, official CLI invocation, ownership inventory, or cleanup test exists yet. M0 remains incomplete and M1 is not ready.

## M0 Docker cleanup review

- Inspected all Docker references in pinned `evaluation/` and bundled analyzer Compose files without contacting a Docker daemon. Startup has two daemon-wide selectors; the normal task builds and runs a Compose service, discovers a container by project/service labels, and later removes it and tears down the Compose project. A failure can bypass teardown. An additional `run_docker_command` helper has Compose teardown and name-based network removal, but has no callers in the inspected checkout. Compose configuration can itself specify mounts, privileges and named resources.
- Added `benchmarks/sastbench-disable-global-cleanup.patch` as a minimal proposal that removes the two global startup cleanup calls from a copy of the pinned CLI. It is not applied to the upstream checkout and does not make the remaining teardown safe, handle orphans, or isolate credentials. Unique names and labels reduce accidents but cannot constrain a process with daemon access; use a disposable VM with a private daemon.
- `python3 -m unittest discover -s benchmarks -p 'test_cleanup_patch.py' -v` passed (one offline test). The test checked the exact pinned CLI contents, applied the patch in a temporary directory, and verified neither broad startup cleanup function is called. This prevents selection by those two startup paths for any inventory; normal cleanup and real Docker resources were not tested. See [SMOKE.md](benchmarks/SMOKE.md) for the next safe command, remaining risks, and reproduction steps. No official evaluator run occurred; M0 is incomplete.

## M0 Docker safety assessment

- Rechecked the pinned evaluator commit and dataset SHA-256; both match the values above. Reviewed CLI, task, utility, analyzer and Compose Docker references without contacting any daemon or external service. The startup cleanup patch leaves per-project `docker rm -f` and Compose `down -v --remove-orphans`, configuration-defined resources, image builds, credential forwarding and failed-start cleanup gaps untouched.
- A private rootless daemon can separate Docker inventories if configured with independent socket and storage, but does not by itself isolate same-user host files, credentials, kernel or resource use. A mock is useful for offline tests but does not exercise real Docker. The recommended real smoke boundary remains a disposable VM with a private daemon, offline inputs, no host mounts/socket or credentials, and verified egress and resource controls. See [SMOKE.md](benchmarks/SMOKE.md) for assumptions and remaining implementation.
- `python3 -m unittest discover -s benchmarks -p 'test_*.py' -v`: the sandboxed run had five passing tests and one setup error because socket creation was denied. The permitted loopback-only rerun passed all six tests, with no failures or skips. No Docker resources were touched. The official CLI, real cleanup, container credential isolation and score aggregation remain untested; M0 remains incomplete.

## M0 rootless Docker feasibility · 2026-11-25

- **NOT VERIFIED.** A separate rootless daemon remains the first candidate for the synthetic smoke. Fedora package and kernel inspection found Docker/Compose, RootlessKit, UID/GID helpers with capabilities, subordinate-ID allocation room, user and network namespaces, and cgroup v2 controllers. The rootless launcher is missing. The sandbox could not confirm the host service configuration, SELinux enforcement, socket permissions for a dedicated account, or KVM acceleration.
- Reviewed the fixture, protocol probe and startup cleanup patch. The patch removes two global calls only. Earlier source findings on forced project cleanup, orphan risks, mounts and credential forwarding still apply. GitHub confirmed the pinned commit, but the local checkout is absent, so the dataset hash and patch applicability were not rechecked. Docker/Compose behavior and all isolation controls remain unverified.
- Offline tests: four helper tests passed in the sandbox, HTTP setup hit a sandbox socket restriction, and the pinned patch test skipped. The permitted loopback rerun had five passes and one skip (missing pinned checkout). No daemon or evaluator was contacted.
- Updated the [smoke runbook](benchmarks/SMOKE.md) with the rootless checks and VM fallback. No host setup changed. The next change requires approval before account creation or provisioning. The official smoke is not ready.

## M0 dedicated account preflight

- **Stopped before creation.** `getent passwd argus-sastbench` and `getent group argus-sastbench` returned no records. `namei -l /var/lib/argus-sastbench` reported `No such file or directory`. The read-only `/usr/sbin/useradd -D` check returned `Cannot open audit interface - aborting.` in the Codex sandbox.
- Read the account allocation policy and found `HOME_MODE 0700`, 65,536-ID subordinate ranges, and `CREATE_MAIL_SPOOL=yes`. The live defaults and UID/GID conflicts were not fully verified. A mail spool is a possible side effect to account for before retrying.
- No privileged command ran, no host account or files changed, and no daemon was contacted. No post-creation verification or rollback was needed. See [the dedicated account preflight](benchmarks/SMOKE.md#dedicated-account-preflight) for the stop condition and proposed rollback.

## M0 approved account creation attempt

- Final preflight passed. The account, group, home and mail spool were absent, no supplementary membership was listed, and a 65,536-ID block starting at 589824 was available in both subordinate ID files.
- The approved `sudo /usr/sbin/useradd` invocation stopped for the host password. Canceled the prompt. Exit 1 reported `sudo: a password is required`; account and group lookups still returned 2. No account resources were created and no rollback is needed.
- The checked account databases and defaults, Docker and containerd configuration, and Docker socket metadata matched the before-attempt baseline. No daemon was contacted. Account creation requires local sudo authentication. See [the approved attempt](benchmarks/SMOKE.md#approved-account-creation-attempt).

## M0 dedicated account created from Fedora terminal

- The owner created `argus-sastbench` and verified UID/GID 957, a private `0700` home at `/var/lib/argus-sastbench`, no supplementary groups and subordinate UID/GID `589824:65536`. Local `getent`, `id`, `stat` and mapping checks confirmed the identity, private group, mode, maps and `/usr/sbin/nologin`. The mail spool path is absent. Home ownership was masked in the sandbox. The password-status query was denied and the private home contents were inaccessible, so host verification is still required for both before staging.
- Rootless prerequisites rechecked: Docker CE/CLI 29.10.1, Compose 5.8.0, RootlessKit 3.3.0, mapping helper file capabilities, user/network namespaces and cgroup v2 are present. The launcher is absent. The matching Moby release provides a launcher that can be staged as a single file without changing existing packages or Docker configuration.
- Added proposed [staging, transient launch and rollback commands](benchmarks/SMOKE.md#account-verification-and-proposed-launcher-staging). No launcher was downloaded to the host, no service was started, and no daemon or evaluator was contacted. Runtime feasibility remains **NOT VERIFIED**. Next approval covers launcher staging only.

## M0 conditional launcher staging verification

- Host metadata confirmed `/var/lib/argus-sastbench` is `0700`, owned by `957:957`. Host `sudo -n /usr/bin/passwd -S argus-sastbench` returned `sudo: a password is required`, so password-lock verification blocked the authorized copy. No launcher was staged or executed.
- The official Moby release identifies `54cd494d0b39abfc7a958fcc876f706271f8b909`. The tag and exact-commit source bytes matched in memory, passed shell syntax checking, and yielded SHA-256 `200203633806081a401e60aefdf68a8fa73fc7dc80aa854c52a69d47710a3488`. The runbook now checks this digest before staging and calls for checking it again afterward. Engine, RootlessKit, namespace tools and mapping-helper capabilities were rechecked. No Docker daemon, package installation or service change was involved.

## M0 launcher staging approved, pending local sudo

- Fedora host output supplied by the owner was `argus-sastbench L 2026-11-25 -1 -1 -1 -1`, confirming the password lock. Local read-only lookups still show UID/GID 957, the private group, `/usr/sbin/nologin`, and both `589824:65536` mappings.
- The protected single-file copy needs local sudo authentication. No copy was attempted. The [host terminal procedure](benchmarks/SMOKE.md#account-verification-and-proposed-launcher-staging) checks the home and destination, verifies the pinned source SHA-256, copies only the launcher, and checks root ownership, mode 0555 and the installed checksum. Post-copy verification is pending. No package, service, network or Docker action occurred.

## M0 launcher staged and transient supervisor reviewed

- The owner successfully staged the verified Moby launcher at `/var/lib/argus-sastbench/dockerd-rootless.sh` on Fedora. Pre-copy checksum passed. Reported installed owner/group is `0:0`, mode `0555`, SHA-256 `200203633806081a401e60aefdf68a8fa73fc7dc80aa854c52a69d47710a3488`. No daemon was started.
- Static review checked the account, mapping helper capabilities, systemd 259, cgroup v2 controllers, RootlessKit driver options and the pinned launcher's namespace setup. Read-only host checks found SELinux enforcing, `/dev/net/tun` present (character device, mode 0666, `0:0`), and the proposed unit name unused. Shell syntax and static `systemd-analyze verify` checks passed. The unit's SELinux and namespace behavior remains untested.
- The [transient supervisor runbook](benchmarks/SMOKE.md#transient-supervisor-review-and-commands) now has a no-daemon probe, a separately approved empty-daemon mode, validation commands and rollback. Runtime checks are **NOT VERIFIED**. No daemon, container, package or system configuration action was performed in this review.

## M0 no-daemon preflight approved, pending local sudo

- Rechecked the Fedora host before execution. SELinux was `Enforcing`, TUN was present, cgroup v2 exposed CPU, memory and PID controllers, and the Argus unit was `not-found`/`inactive`. The system Docker socket was `0660`, `0:964`, inode `2791`; Docker Desktop's socket was absent. Port 18080 and the host scratch path were unused. The ID mapping helpers retained their file capabilities.
- Removed the empty-daemon branch from the approved command. The standalone probe checks outer and inner isolation, the effective cgroup and tmpfs limits, subordinate mappings, synthetic HTTP and host metadata before and after. Shell syntax and static systemd property verification passed. These checks were static, with no transient unit started.
- Host `sudo -n -l` failed with `sudo: a password is required`. No probe was started. Resource, namespace, route, SELinux compatibility and teardown measurements remain **NOT VERIFIED**. The exact [local command](benchmarks/SMOKE.md#transient-supervisor-review-and-commands) requires an interactive Fedora terminal. The empty daemon remains outside this approval.

## M0 first no-daemon probe and network investigation

- The Fedora journal confirms the owner's successful probe: mappings, 1 CPU, 2 GiB RAM, zero swap, 256 tasks, capped tmpfs mounts, outer loopback only, and synthetic HTTP 200. It also contains the gVisor loopback warning and inner default route via `10.0.2.1`. The unsuccessful test-IP connections do not establish egress denial. No daemon was launched.
- Installed RootlessKit is 3.3.0. Upstream for that version warns in the CLI but passes the flag to the gVisor driver, which conditionally omits gateway-to-loopback NAT. That is source evidence rather than a runtime guarantee. pasta is installed; slirp4netns is absent. Use the no-uplink outer systemd namespace as the independent barrier. The revised [no-daemon command](benchmarks/SMOKE.md#transient-supervisor-review-and-commands) adds host and outer loopback canaries and explicit namespace comparisons. It was syntax-checked, not run, and requires new approval.
- Read-only teardown found the unit collected (`not-found`, `inactive`, `dead`, `MainPID=0`), no probe PIDs or account/subordinate processes, no listed Argus mounts, namespace pins, sockets, listeners, cgroup, or scratch path. The staged launcher and journal remain intentionally. System Docker socket metadata matched the prior baseline and the Desktop socket remained absent. Normal exit left no observed runtime resources; forced-failure and timeout cleanup remain untested. No daemon was contacted and no host resources were changed during this review.
- The owner approved the revised no-daemon probe, including the temporary loopback listener. `sudo -n -l` returned `sudo: a password is required`. The probe did not start and needs local authentication. The empty-daemon launch remains outside this approval.

## M0 revised no-daemon network probe passed

- The owner ran the revised probe from Fedora. The 23:53 journal confirms distinct host, outer and inner network namespaces, an outer namespace with loopback only, negative canary checks followed by inner HTTP 200, and RootlessKit in the Argus cgroup. CPU, RAM, swap, PID and tmpfs limits matched the thresholds. The gVisor warning persisted; the tested gateway-to-outer-loopback path was blocked despite it.
- The unit deactivated and was collected. Read-only follow-up found no Argus process, cgroup, port 18080–18082 listener, scratch directory or host canary directory. SELinux remained enforcing. The system Docker socket retained mode 0660, owner/group 0:964 and inode 2791. Desktop socket absent. No existing daemon was contacted.
- Network isolation passed for the synthetic RootlessKit probe. Docker, BuildKit, container networking and cleanup under failure or timeout remain unverified. Review the exact empty-daemon command and obtain separate approval before starting it.

## M0 empty rootless daemon safety review

- Confirmed installed Engine 29.10.1 build `54cd494` matches the staged launcher. Reviewed Moby's automatic containerd selection, launcher mount and network handling, and Docker 29's default image store. The proposal uses a fresh VFS data root, masked host socket and credential paths, and verifies a private managed containerd. The empty test needs Unix sockets only, so it adds a cgroup IP deny rule with an in-unit TCP test and disables bridge/firewall/proxy setup. SELinux stays enforcing.
- The exact [empty-daemon command and rollback](benchmarks/SMOKE.md#proposed-empty-daemon-test) include pre-launch guards, read-only queries to the new private socket only, and post-exit checks for orphaned processes, mounts, socket metadata and host forwarding settings. Shell/Python syntax checks, static systemd verification and config-only `dockerd --validate` passed. No RootlessKit, daemon, container, or build was started. Launch requires separate approval. Container/build behavior and fault or timeout cleanup remain unverified.

## M0 empty-daemon startup failure and teardown review

- Fedora's 2026-11-26 journal shows the resource and IPv4/IPv6 TCP-denial checks passed. RootlessKit's child then hit `open /etc/hosts: no such file or directory` while preparing its namespace, before dockerd started. The private /etc tmpfs hid the file. The parent survived the 45-second readiness wait, the five-second stop-SIGTERM phase and SIGABRT. systemd sent SIGKILL to RootlessKit PID 253706 and collected the unit. The reason the parent did not exit is unverified.
- User cleanup results and read-only host checks agree. Unit `not-found`/`inactive`/`dead`, `MainPID=0`, no cgroup, no observed Argus processes, sockets, mounts, namespace references, or scratch/runtime paths. Only root-owned containerd PID 1105 and dockerd PID 1264 matched. System Docker socket metadata matched the baseline, the Desktop socket was absent, and SELinux was enforcing. No daemon was contacted.
- The revised [empty-daemon command](benchmarks/SMOKE.md#proposed-empty-daemon-test) supplies a synthetic, read-only loopback hosts file, makes the final stop signal explicit, and verifies the detached network namespace through RootlessKit's child mount view. Shell syntax and static systemd property verification passed. The retry was not run and requires approval.

## M0 revised empty-daemon test conditionally approved

- Rechecked the approved block: the synthetic hosts file is temporary and read-only inside the unit, inherited isolation and limits are unchanged, and the timeout policy applies to the whole service cgroup. The only Docker API requests are `/_ping` and `/info` over the new private Unix socket. No pull, build, container, or registry operation is in the block.
- Read-only Fedora preflight passed. SELinux remained enforcing, TUN and both mapping helpers were present, and the previous Argus unit was `not-found`/`inactive` with `MainPID=0` and no cgroup. No Argus runtime processes, sockets, mounts, namespace references or scratch inputs were found. System socket metadata remained unchanged.
- `sudo -n -l` returned `sudo: a password is required`. The revised run did not start and needs local Fedora authentication. Startup and post-run checks remain pending. Container-level testing is outside the current approval.

## M0 empty-daemon mount namespace failure and private hosts fix

- The next Fedora run never entered the service payload. systemd reported 226/NAMESPACE while binding the synthetic hosts file under the private /etc. The matching SELinux audit event (PID 257529) shows init_t denied file creation for hosts with label net_conf_t. systemd had ordered the parent tmpfs before its nested bind; the missing target could not be created. Upstream v259 applies the tmpfs read-only flag later, so read-only mode alone does not explain the failure.
- Read-only cleanup checks found the unit collected, MainPID=0, no cgroup, Argus processes, sockets, mounts, namespace pins, scratch paths or hosts staging directories. Host Docker/containerd socket metadata was unchanged, host forwarding remained IPv4 1 and IPv6 0, and SELinux was enforcing. No Docker daemon was contacted.
- The updated [empty-daemon command](benchmarks/SMOKE.md#proposed-empty-daemon-test) avoids the hosts bind, creates the file under a temporary name inside the capped unit-only /etc, renames it and checks mode 0444. The private directory is set to 0555 after setup; its mount remains writable and the owner can restore write access. Host /etc and DNS files remain hidden. No other isolation or limit was relaxed. Shell and Python syntax, unit properties and guard order passed static checks. In-unit SELinux and startup behavior remain unverified. No unit or launcher ran during this review, and fresh approval is required.

## M0 private hosts retry conditionally approved

- Reviewed the exact approved block. The private mount and ownership guards precede the hosts write, the payload compares the result to exactly two localhost records, and host configuration inputs are not writable binds. Network, resource and time limits and whole-cgroup termination are unchanged. No SELinux policy or enforcement change is in the block. Static shell and isolation checks passed.
- Fedora preflight found no prior Argus processes, sockets, cgroup, mounts, namespace references or temporary inputs. The unit was `not-found`/`inactive`, `MainPID=0`. SELinux was enforcing, TUN and mapping helper capabilities were present, host socket metadata was unchanged, and forwarding remained IPv4 1 and IPv6 0.
- Cached sudo authentication was unavailable (`sudo: a password is required`). The revised run did not start. Startup and cleanup measurements remain pending a single authenticated run from a Fedora terminal. Container and build tests remain outside the approval.

## M0 private daemon started; validation diagnosis pending

- The Fedora 00:43 run started private containerd and Docker 29.10.1 with VFS. Journal credentials put both at host UID/GID 957 in the Argus service cgroup. Docker announced the private Unix socket at 00:43:37.989, the validation shell exited 1 at 00:43:38.582, and Docker completed shutdown at 00:43:39.588. There was no readiness or final inventory marker. Timing strongly suggests a post-readiness assertion failure, but the first failed check was not logged.
- The leading hypothesis is the old exact socket mode check: pinned Moby adds a sticky bit to the Unix socket under `XDG_RUNTIME_DIR`, so expected access bits `0660` may have been reported as mode `1660`. No actual mode survives in the record. Other early mount, namespace and identity checks remain possible. The [instrumented retry](benchmarks/SMOKE.md#proposed-empty-daemon-test) logs readiness, socket metadata and failure location. It still requires owner/group 957:957 and access bits 0660, allowing only the documented sticky bit. No isolation guard was removed.
- The per-container cgroup warning does not negate the enclosing systemd cgroup. Its one CPU, 2 GiB, zero swap and 256-task limits were observed before startup. Docker-level resource flags and actual container/build placement remain unverified and are outside this retry.
- Read-only cleanup found the collected unit, `MainPID=0`, no Argus processes, sockets, mounts, namespace references, cgroup or temporary paths. Existing Docker and containerd socket metadata matched the baseline, SELinux stayed enforcing, and host forwarding stayed IPv4 1 / IPv6 0. The daemon was not rerun during diagnosis. Fresh approval is required for a diagnostic run.

## M0 diagnostic run approved, pending local sudo

- Reviewed the approved block. Syntax, unit restrictions, exact 957:957 socket ownership with modes 0660 or 1660 only, and readiness and failure logging passed static checks. No credential-bearing environment is passed into the unit.
- Read-only host preflight found no Argus processes, sockets, mounts, namespaces, cgroups or scratch paths. SELinux was enforcing. Existing host socket metadata and forwarding matched the baseline.
- Cached sudo authentication was unavailable. No diagnostic unit started. Runtime results remain pending one authenticated Fedora run; container tests remain outside approval.
- On recheck, the latest journal was still the 00:43 partial startup, with no instrumented readiness or socket-mode entries. The unit and scratch path remained absent, SELinux was enforcing, socket and forwarding metadata matched, and sudo still required local authentication.

## M0 diagnostic run preflight passed; run blocked on sudo

- Read the current `benchmarks/SMOKE.md` run block and verified the approved invocation and its unchanged isolation/limit settings. Host preflight returned SELinux `Enforcing`; account UID/GID and sole group 957; transient unit `not-found`/`inactive`, MainPID 0 and no ControlGroup; absent `/var/tmp/argus-empty` and `/run/user/957`; no UID 957 process, Argus mount, nsfs path or Unix socket.
- Existing socket metadata matched baseline: `/run/docker.sock` 660, `0:964`, device:inode `31:2791`; `/run/containerd/containerd.sock` 660, `0:0`, device:inode `31:3208`; Docker Desktop socket absent. Forwarding remained IPv4 1 / IPv6 0. No Docker daemon was contacted.
- The first unpassed preflight step attempted read-only launcher metadata with `sudo -n stat`; it returned `sudo: a password is required`. `sudo -n -v` confirmed authentication is unavailable in this execution context. The one approved diagnostic run was **not started**; RootlessKit and Docker readiness, socket mode, process identities, runtime cgroups/namespaces, API metadata and post-run cleanup therefore remain unmeasured. Launcher hash/metadata could not be freshly verified.
- No retry was made. The owner can run the approved block once from an authenticated Fedora terminal using the exact commands recorded in [SMOKE.md](benchmarks/SMOKE.md#m0-diagnostic-run-preflight-blocked-before-execution). No system change, daemon start or Docker resource access occurred. Container-level testing remains out of scope.

## M0 empty-daemon validation passed; container gate planned

- The owner reports the diagnostic empty-daemon validation passed. No raw
  journal or command output accompanied the report, so exact socket mode,
  process/cgroup measurements, Docker API values and teardown evidence are
  recorded as reported rather than independently re-measured. No containers,
  builds, image pulls or SastBench execution were part of that result.
- Added a plan-only next gate to [SMOKE.md](benchmarks/SMOKE.md#proposed-next-gate-one-offline-container-isolation-test): one short-lived, non-privileged container from a trusted, immutable, checksum-verified local image archive; no external network, host mounts or existing Docker endpoint. The test inspects the exact container, host PID/UID mappings, network namespace and route, inherited systemd cgroup limits, SELinux state, and teardown. Cleanup is by exact container ID only; no prune/Compose/global cleanup.
- Do not claim per-container CPU/memory/PID limits: the prior daemon warned that rootless per-container cgroups were unavailable. The plan verifies inheritance of the enclosing one-CPU, 2 GiB, zero-swap, 256-task service cgroup and avoids stress/exhaustion. Image acquisition/staging and the container run each require explicit approval. No image was pulled/staged and no container was created. The diagnostic runbook's evidence requirements and risk section identify shared-kernel and unverified OCI behavior.
