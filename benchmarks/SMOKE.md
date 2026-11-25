# SastBench smoke preparation

This is an offline preparation, not an executable official CLI harness. Do not run
the upstream CLI on either existing Docker context. It has broad startup cleanup,
passes host environment into workers, and may leave a container after a failure.
No runtime isolation or Docker cleanup implementation has been verified.

## Docker review and proposed patch

At pinned revision `b8d95b7720491b21d039b7504999577ba7ebb12b`,
`evaluation_cli.py:run_evaluation` calls two global cleanup helpers before
starting workers. `cleanup_orphaned_docker_networks` stops/removes containers
whose names begin `eval_` and removes networks with that prefix;
`cleanup_neo4j_containers` stops/removes matching `created_by=llm_sast_eval`
containers and removes matching Neo4j volumes. None is scoped to this run.

`start_rest_container` builds the Compose analyzer image, runs a container with
mounts and a loopback-published port, and discovers it using Compose project and
service labels. Compose may create networks, volumes and images according to its
configuration; an arbitrary Compose file can name or reference existing
resources and request privileged mounts. `stop_rest_container` forcibly removes
the discovered ID and invokes Compose `down -v --remove-orphans` for the project.
The generated project name has a random component, but is not a durable run
registry, and caller-supplied names and labels are not authorization. A failure
after container creation but before normal teardown can leave resources behind.
`get_rest_container_logs` reads the supplied container's logs. The unused-by-the-
reviewed-CLI `run_docker_command` helper also runs Compose up/down and removes a
network by a generated name. `check_docker_available` contacts the daemon;
Compose config/build/run and CLI checks also have effects beyond selection.

The proposed [patch](sastbench-disable-global-cleanup.patch) removes only the
two startup calls; it does not change upstream task, scoring or data semantics.
It does not implement ownership labels, run-specific failure cleanup, environment
sanitization, or safe ordinary Compose teardown. It leaves orphans deliberately.
The offline test applies it to a temporary copy of the exact pinned CLI and
checks its AST: neither startup selector can run, regardless of unrelated
container, network, or volume inventories. This is not a test or guarantee for
any other deletion path, nor a real Docker integration test.

Exact next safe command, with the pinned checkout present, is:

```sh
python3 -m unittest discover -s benchmarks -p 'test_cleanup_patch.py' -v
```

To verify applicability without applying it to the pinned checkout:

```sh
git -C /tmp/argus-sastbench-m0 apply --check /home/aayush27/Documents/Projects/Argus/benchmarks/sastbench-disable-global-cleanup.patch
```

Use `git apply` only in a disposable copy, after independently verifying its HEAD
and source integrity. Do not apply it to the pinned checkout to disguise a
modified evaluator; record the patch and checksum in any run manifest.

Possession of the host Docker socket permits daemon-level operations, including
privileged containers and host filesystem mounts; a compromised process can
ignore labels and read credentials or disrupt workloads. Labels and scoped
names are useful for attribution and collision avoidance, not isolation. The
runner also copies its environment and bundled Compose files interpolate
credentials. Resource limits, egress controls, credential exclusion and cleanup
must be verified before an official smoke in either isolation option.

Run the offline tests (the HTTP test requires loopback socket access):

```sh
python3 -m unittest discover -s benchmarks -p 'test_*.py' -v
python3 benchmarks/probe_sastbench_protocol.py /tmp/argus-sastbench-m0
```

`clean_environment` creates a fresh environment without inherited variables;
the caller must supply private directories and a trusted explicit PATH. It does
not itself launch the CLI, inspect an image, validate Compose, or prevent a
configuration file or mounted directory from containing credentials. The fixture
HTTP analyzer implements the protocol without making model calls. Its failure
modes and the separate coverage audit are test tools, not model performance.
The audit retains the original input count and reports missing, failed, invalid,
and label-mismatched results separately. An unidentified error row is reported
separately because it cannot safely be mapped to an input finding.

## Required isolated runtime

### Isolation decision

**Rootless Docker is the first candidate. Feasibility is NOT VERIFIED.**
Use a separate unprivileged account and a disposable daemon for the synthetic
smoke. The dedicated account exists. No daemon or VM has been provisioned.

Fedora 44 package metadata reports Docker CE and CLI 29.10.1, Compose plugin
5.8.0, RootlessKit 3.3.0, pasta and fuse-overlayfs. The rootless extras package
and launcher were absent from the inspected paths. The UID/GID helpers have
the expected file capabilities. Each subordinate ID file has one existing
65,536-ID range or larger, and the allocation policy has room for another.
Verify fresh, nonoverlapping mappings after account creation. Kernel
configuration enables user and network namespaces. Cgroup v2 exposes CPU,
memory, PID and I/O controllers in the inspected user subtree. Delegation
and enforcement under the proposed service remain untested. The sandbox
masked some filesystem metadata and denied the system bus. Host configuration
says SELinux enforcing while sandbox getenforce returned Disabled. Confirm
host enforcement without weakening it.

Proposed containment and checks, subject to approval:

1. Use a locked account with a private home and no privileged groups. Check
   UID/GID mappings and access denial for existing socket and storage paths
   with that identity. Use permission checks and synthetic canaries, and
   never connect to existing daemons.
2. Run the evaluator, worker, RootlessKit, daemon and build helpers under one
   supervised system service as the dedicated account. Use a private mount
   view and a loopback-only outer network namespace (PrivateNetwork=yes),
   with no host homes, daemon sockets, user buses, resolver or proxy sockets,
   GPU or inherited descriptors. Review and test the filesystem allowlist
   from the evaluator process and containers.
3. Use private runtime, execution, data, daemon and CLI configuration paths.
   In the clean environment, explicitly select the private Unix socket with
   DOCKER_HOST, keep context configuration private, and fail closed if the
   endpoint is missing or unexpected. Test RootlessKit port forwarding within
   the outer namespace and confirm the port is absent on the host. Check
   IPv4, IPv6, DNS and host service denial from the evaluator, build and
   container using local canaries.
4. Bound the service with host-enforced CPU, memory, PID and wall-clock limits,
   and place mutable state on capacity-limited storage. Verify child processes
   stay within the limits and test storage exhaustion and bounded logs. Check
   fixture worktree mount ownership and contents. Test teardown after success,
   startup failure and interruption using only the private daemon inventory
   and service cgroup.

If a mandatory check fails and fixing it would require changes to shared
Docker, networking or security configuration, prefer a disposable QEMU/KVM
VM. Use a trusted guest with private Docker, a bounded disposable disk, no
external NIC and no host directories or sockets. Stage pinned inputs,
dependencies and images as read-only media, verify guest-local HTTP and
limits, and export only reviewed artifacts before discarding the disk. QEMU
is installed and the user's host shell showed /dev/kvm. Sandbox visibility
and actual KVM acceleration are unverified. VM creation requires approval.

### Dedicated account preflight

Account creation stopped before any privileged command. Both `getent passwd
argus-sastbench` and `getent group argus-sastbench` returned no record.
`namei -l /var/lib/argus-sastbench` reported `No such file or directory`
for the final component. `/usr/sbin/useradd -D` returned `Cannot open audit
interface - aborting.` This was observed in the Codex sandbox. The result
does not establish whether the host's audit interface works.

The on-disk defaults specify `GROUP=100`, `SKEL=/etc/skel`,
`CREATE_MAIL_SPOOL=yes`, `USERGROUPS_ENAB yes` and `HOME_MODE 0700`.
Regular UID/GID allocation is configured for 1000–60000, with subordinate
UID/GID ranges of 65,536 IDs in 524288–600100000. These are policy values.
Effective defaults, allocation conflicts, and membership guarantees were
not fully verified. The mail spool default is an additional possible
filesystem effect of the approved command and must be accounted for before
creation. No account, group, home, mail spool or mappings were created, and
the post-creation socket comparison did not run.

There is nothing to roll back from this attempt. If the account is later
created and removal is approved, first verify that it owns no active processes
and inventory its exact home, mail spool, private group and subordinate IDs.
Review removal of that account with `userdel` without `--remove`, verify the
resulting group and mapping state, and remove only confirmed Argus-created
files individually. Use `rmdir` for empty Argus directories and review any
remaining private group or mappings separately. Do not remove shared state.

### Approved account creation attempt

The host's `sudo /usr/sbin/useradd -D` succeeded and confirmed `GROUPS=`,
`CREATE_MAIL_SPOOL=yes`, and `LOG_INIT=yes`. The approved command uses
`--system --add-subids-for-system` to skip mail creation while requesting
subordinate IDs, `--skel /var/empty` for an empty home, and `--no-log-init`.

The final preflight again found no account, group, target home, mail spool,
or listed supplementary memberships. It found a free 65,536-ID block in
both subordinate ID files, starting at 589824. The approved invocation
reached the host `sudo` password prompt and was canceled. It exited 1 with
`sudo: a password is required`. Account and group lookups still returned 2,
and the home and mail spool remained absent. Before and after comparisons
matched for the visible passwd, group and subordinate ID files, account
defaults, sampled Docker and containerd configuration, and metadata of the
existing Docker socket paths. No daemon was contacted. No account resources
were created and no rollback is needed.

Run the approved command from an authenticated Fedora terminal if proceeding.
Verify the account, private group and `0700` empty home, locked password,
`nologin`, lack of supplementary groups and nonoverlapping subordinate ranges
before advancing. Provisioning the rootless launcher or supervisor remains a
separate approval step.

### Account verification and proposed launcher staging

The owner created the account from the Fedora terminal and verified UID/GID
957, no supplementary groups, and a `0700` home at `/var/lib/argus-sastbench`.
Local read-only checks confirmed UID/GID 957, sole membership in its private
group, shell `/usr/sbin/nologin`, mode `0700`, and `589824:65536` in both
subordinate ID files. The sandbox masked home ownership and denied listing the
private home or viewing the password status. Verify these on the host with
`sudo stat -c '%a %u:%g %n' /var/lib/argus-sastbench`,
`sudo passwd -S argus-sastbench` (expect `L` or `LK`), and
`sudo ls -A /var/lib/argus-sastbench` (expect empty before staging). The mail
spool path was absent. `nologin` alone does not prove the password is locked.

Docker CE/CLI 29.10.1, Compose 5.8.0, RootlessKit 3.3.0, containerd.io,
`pasta` and the namespace mapping helpers are present. The helpers expose
`cap_setuid` and `cap_setgid`, and the kernel exposes user and network
namespaces and cgroup v2. The rootless extras RPM and launcher are absent.
Exact-match RPM availability was not confirmed. Stage only the upstream
launcher from the [matching Moby release](https://github.com/moby/moby/releases/tag/docker-v29.10.1),
pinned to its full release commit. Download in the operator's normal network
environment, review the file and record its SHA-256 before copying it to the
dedicated account. No package transaction, setup-tool install, restart or
Docker context change is needed.

**Staging is approved. Run this block in an authenticated Fedora terminal.**
The checks stop on any failure. Launching still requires separate approval.

```sh
(
  set -eu
  home=/var/lib/argus-sastbench
  dest="$home/dockerd-rootless.sh"
  expected=200203633806081a401e60aefdf68a8fa73fc7dc80aa854c52a69d47710a3488

  sudo test -d "$home"
  sudo test ! -L "$home"
  test "$(sudo stat -c '%u:%g %a' "$home")" = '957:957 700'
  sudo test ! -e "$dest"
  sudo test ! -L "$dest"

  stage=$(mktemp -d /tmp/argus-rootless-launcher.XXXXXXXX)
  src="$stage/dockerd-rootless.sh"
  trap 'if test -e "$src"; then unlink "$src"; fi; rmdir "$stage"' EXIT
  curl --fail --show-error --silent --proto '=https' --output "$src" \
    https://raw.githubusercontent.com/moby/moby/54cd494d0b39abfc7a958fcc876f706271f8b909/contrib/dockerd-rootless.sh
  printf '%s  %s\n' "$expected" "$src" | sha256sum --check --strict

  sudo test ! -e "$dest"
  sudo test ! -L "$dest"
  sudo install -T -o root -g root -m 0555 "$src" "$dest"
  sudo test -f "$dest"
  sudo test ! -L "$dest"
  meta=$(sudo stat -c '%u:%g %a' "$dest")
  test "$meta" = '0:0 555'
  actual=$(sudo sha256sum "$dest")
  test "${actual%% *}" = "$expected"
  printf '%s %s\n%s\n' "$meta" "$dest" "$actual"
)
```

### Conditional staging verification

Host `stat` confirmed mode `0700` and owner `957:957` for the private home.
The owner then ran `sudo /usr/bin/passwd -S argus-sastbench` in Fedora and
reported `argus-sastbench L 2026-11-25 -1 -1 -1 -1`, confirming the password
lock. Read-only identity and subordinate ID checks still match. The account
conditions passed. The owner subsequently staged the launcher in an authenticated Fedora terminal.
The download passed the checksum check before the copy. The owner verified
`/var/lib/argus-sastbench/dockerd-rootless.sh` is owned by `0:0`, mode
`0555`, with the SHA-256 shown above. No daemon was started. The earlier
noninteractive sudo failure did not perform a copy.

GitHub identifies the signed Moby `docker-v29.10.1` release with commit
`54cd494d0b39abfc7a958fcc876f706271f8b909`. Read-only in-memory fetches of the
release-tag and full-commit paths returned identical bytes and passed `sh -n`.
The owner reported the same SHA-256 for the staged file. Recheck it before
each preflight or launch.

The script needs a private writable `HOME` and `XDG_RUNTIME_DIR`, non-root
execution, RootlessKit, `dockerd`, `newuidmap`/`newgidmap` and the account maps.
The installed Engine and RootlessKit versions and both mapping helpers' file
capabilities were rechecked, along with `nsenter`, `unshare`, `ip` and `sysctl`.
Running the script would create RootlessKit state in the runtime directory,
copy up `/etc` and `/run` inside its mount namespace, and start the daemon.
Staging copies a single file and uses no package manager, installer, context or
service operation. Namespace and networking compatibility remain launch gates.

### Transient supervisor review and commands

**The first no-daemon probe passed its functional checks. Network isolation
for Docker is still NOT VERIFIED.** Fedora's journal confirms UID/GID maps,
CPU 1, 2 GiB memory, zero swap, 256 tasks, capped tmpfs mounts, outer loopback
only, and synthetic HTTP 200. It also recorded the gVisor warnings and an inner
default route via `10.0.2.1`. Failed connections to documentation IPs are not
a security proof. The owner approved the revised no-daemon probe below,
including its temporary host loopback listener. `sudo -n -l` returned
`sudo: a password is required`, so execution is pending in an interactive
Fedora terminal. No new listener or unit was started.

RootlessKit 3.3.0's CLI prints the gVisor warning whenever the option is set.
The same upstream release still passes the flag into the driver, which omits
its explicit gateway-to-127.0.0.1 NAT mapping when the flag is true. This source
behavior does not prove all paths in the Fedora binary. Treat the flag as an
extra check only. The inner gateway is part of a user-mode virtual network.
Its outbound sockets are opened by the parent. Keep the parent inside a
systemd `PrivateNetwork=yes` namespace with only loopback and no uplink, and
verify that the host, outer service, and inner network namespace IDs differ.
Never attach a veth, physical interface or external route to the outer namespace.
The staged launcher and the private socket and storage remain separate from the
host daemon. Keep host socket paths masked, SELinux enforcing, proxy credentials
and ambient client configuration absent, and all helpers in the cgroup.

Keep gVisor for the next no-daemon probe since it already passed HTTP without
installing anything. Fedora has pasta, whose RootlessKit integration supplies
`--no-map-gw` and disables automatic namespace-to-host port mapping with the
loopback flag. Its behavior without an outer uplink is untested. slirp4netns
explicitly supports the flag but the executable is absent. Neither backend is
an independent external egress barrier. Do not increase privileges or add
packages to work around a failure without review.

The next probe uses a host-only loopback canary at 18081, an outer-only canary
at 18082, and forwarded inner HTTP at 18080. Positive checks prove the canaries
are alive. Negative checks then distinguish the real host loopback from the
service loopback and check the gVisor gateway path. Both test listeners are
synthetic, bind to loopback in their own namespaces, and serve only fixed test
files. No existing service is contacted. The physical LAN, internet, and DNS
must stay unreachable by construction: no outer uplink, inherited host
network descriptor, or host proxy. Verify actual namespace membership, links
and routes rather than accepting timeouts as evidence.

The revised probe ran on Fedora at 23:53 local time and reached both PASS
markers. The journal showed distinct host, outer and inner network namespace
IDs (`4026531833`, `4026533057`, `4026533288`). RootlessKit stayed in the outer
namespace and Argus cgroup. The outer namespace had only loopback and no
external route. The canaries' negative checks passed before forwarded inner
HTTP returned 200. The expected gVisor warning still appeared. SELinux was
enforcing after the run. Read-only inspection found the unit collected and
no remaining probe processes, cgroup, listener on ports 18080–18082, host
canary directory, or `/var/tmp/argus`. The system Docker socket still matched
mode 0660, owner/group 0:964 and inode 2791; the Desktop socket remained absent.
This verifies the tested no-daemon network paths and normal cleanup only.
Docker, BuildKit, containers and timeout cleanup remain untested. A reviewed
empty-daemon command and separate approval are required before launch.

The shell checks below require host sudo. The current host has SELinux enforcing,
TUN, and the necessary cgroup v2 controllers. Use a disposable KVM guest with no
NIC if this boundary fails, if preserving it breaks evaluator HTTP, or if Docker
and its build workers cannot be shown to stay inside it. Keep the host kernel
shared only for the controlled fixture. Before any official run, verify
containers and builds under the inherited boundary. Use an internal Compose
network where compatible and prohibit host networking and external resources.
Preload verified base images and dependencies; use no pull and disable networking
for build RUN instructions as extra controls. Frontend, base-image and context
resolution can occur outside RUN, so keep the daemon and all build workers in
the no-uplink service boundary. No external BuildKit daemon or Docker socket.

Read-only teardown after the first probe found the unit `not-found`, `inactive`,
`dead`, `MainPID=0`, with no cgroup. No previous probe PID, process under UID 957
or its subordinate range, Argus socket/listener, visible namespace pin, mount,
transient unit file, or scratch/runtime path remained. `/run/docker.sock` still
had mode 0660, owner/group 0:964 and inode 2791; the Desktop socket was absent.
The staged launcher and account remain by design. The journal records the
intentional child SIGTERM and transport EOF followed by `Deactivated successfully`.
These are records, not running resources. Timeout and unexpected-failure
teardown still need their own tests.

```sh

# BEGIN ARGUS NO-DAEMON PREFLIGHT
(
  set -eu
  unit=argus-sastbench-rootless.service
  launcher=/var/lib/argus-sastbench/dockerd-rootless.sh
  expected=200203633806081a401e60aefdf68a8fa73fc7dc80aa854c52a69d47710a3488

  test "$(id -u argus-sastbench):$(id -g argus-sastbench)" = 957:957
  test "$(id -G argus-sastbench)" = 957
  test -c /dev/net/tun
  test "$(getenforce)" = Enforcing
  test ! -e /var/tmp/argus
  test ! -L /var/tmp/argus
  test "$(systemctl show -p LoadState --value "$unit")" = not-found
  sudo test ! -L "$launcher"
  test "$(sudo stat -c '%u:%g %a' "$launcher")" = '0:0 555'
  actual=$(sudo sha256sum "$launcher")
  test "${actual%% *}" = "$expected"

  socket_metadata() {
    for path in /run/docker.sock "$HOME/.docker/desktop/docker.sock"; do
      if test -S "$path"; then
        stat -c '%a %u:%g %d:%i %Y %Z %n' "$path" || return
      elif test ! -e "$path" && test ! -L "$path"; then
        printf 'absent %s\n' "$path"
      else
        return 1
      fi
    done
  }
  host_netns=$(readlink /proc/self/ns/net)
  before=$(socket_metadata)
  printf 'Host socket baseline:\n%s\n' "$before"
  host_port=$(ss -Hltn '( sport = :18080 or sport = :18081 or sport = :18082 )')
  test -z "$host_port"
  canary_dir=$(mktemp -d /tmp/argus-host-canary.XXXXXXXX)
  canary_pid=
  cleanup_canary() {
    if test -n "$canary_pid"; then
      kill "$canary_pid" 2>/dev/null || :
      wait "$canary_pid" 2>/dev/null || :
    fi
    if test -e "$canary_dir/index.html"; then unlink "$canary_dir/index.html"; fi
    rmdir "$canary_dir"
  }
  trap cleanup_canary EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
  printf 'argus-host-canary' > "$canary_dir/index.html"
  timeout 300s python3 -m http.server 18081 --bind 127.0.0.1 \
    --directory "$canary_dir" >/dev/null 2>&1 &
  canary_pid=$!
  i=0
  until [ "$(curl -q -fsS --noproxy '*' --max-time 1 http://127.0.0.1:18081/ 2>/dev/null)" = argus-host-canary ]; do
    kill -0 "$canary_pid"
    i=$((i+1)); test "$i" -lt 10; sleep 1
  done

  probe_status=0
  sudo systemd-run --slice=system.slice --unit="$unit" --wait --collect --expand-environment=no \
    --property=Type=exec --property=User=argus-sastbench \
    --property=Group=argus-sastbench --property=UMask=0077 \
    --property=PrivateNetwork=yes --property=PrivateIPC=yes \
    --property=ProtectHome=yes --property=ProtectSystem=strict \
    --property=NoNewPrivileges=no \
    --property='CapabilityBoundingSet=CAP_SETUID CAP_SETGID' \
    --property=DevicePolicy=closed --property='DeviceAllow=/dev/net/tun rw' \
    --property='InaccessiblePaths=-/var/lib/docker -/var/lib/containerd -/etc/docker -/etc/containerd -/dev/shm -/dev/mqueue' \
    --property='TemporaryFileSystem=/run:rw,size=64M,mode=0755 /tmp:rw,size=64M,mode=1777 /var/tmp:rw,size=1G,mode=1777' \
    --property=CPUQuota=100% --property=MemoryMax=2G \
    --property=MemorySwapMax=0 --property=TasksMax=256 \
    --property=TimeoutStartSec=5s --property=RuntimeMaxSec=4min50s --property=TimeoutStopSec=5s \
    --property=KillMode=control-group --property=Restart=no \
    --property=LogRateLimitIntervalSec=30s --property=LogRateLimitBurst=100 \
    /usr/bin/env -i PATH=/usr/bin:/usr/sbin LANG=C.UTF-8 ARGUS_HOST_NETNS="$host_netns" /usr/bin/sh -ec '
      test "$(id -u):$(id -g)" = 957:957
      test "$(id -G)" = 957
      test ! -e /run/docker.sock
      test ! -e /var/run/docker.sock
      test ! -r /home/aayush27/.docker
      test ! -r /var/lib/docker
      test ! -r /var/lib/containerd
      test ! -w /var/lib/argus-sastbench
      grep -Eq "^NoNewPrivs:[[:space:]]+0$" /proc/self/status
      test "$(findmnt -n -o FSTYPE --target /run)" = tmpfs
      test "$(findmnt -n -o FSTYPE --target /tmp)" = tmpfs
      test "$(findmnt -n -o FSTYPE --target /var/tmp)" = tmpfs
      for mount in /run /tmp /var/tmp; do
        findmnt -n -o TARGET,OPTIONS --target "$mount"
      done
      for mount in /run /tmp; do
        bytes=$(df -B1 --output=size "$mount" | tail -n 1 | tr -d " ")
        test "$bytes" -le 67108864
      done
      bytes=$(df -B1 --output=size /var/tmp | tail -n 1 | tr -d " ")
      test "$bytes" -le 1073741824

      ARGUS_OUTER_NETNS=$(readlink /proc/self/ns/net)
      export ARGUS_OUTER_NETNS
      test "$ARGUS_HOST_NETNS" != "$ARGUS_OUTER_NETNS"
      printf "Host netns=%s; outer netns=%s\n" "$ARGUS_HOST_NETNS" "$ARGUS_OUTER_NETNS"
      links=$(ip -o link show)
      test "$(printf "%s\n" "$links" | cut -d: -f2 | tr -d " ")" = lo
      routes4=$(ip -4 route show default)
      routes6=$(ip -6 route show default)
      test -z "$routes4$routes6"
      if ip -4 route get 192.0.2.1 >/dev/null 2>&1 ||
         ip -6 route get 2001:db8::1 >/dev/null 2>&1; then exit 1; fi

      cg=$(sed -n "s/^0:://p" /proc/self/cgroup)
      test "${cg##*/}" = argus-sastbench-rootless.service
      cg="/sys/fs/cgroup$cg"
      test "$(cat "$cg/cpu.max")" = "100000 100000"
      test "$(cat "$cg/memory.max")" = 2147483648
      test "$(cat "$cg/memory.swap.max")" = 0
      test "$(cat "$cg/pids.max")" = 256
      for limit in cpu.max memory.max memory.swap.max pids.max; do
        printf "%s=%s\n" "$limit" "$(cat "$cg/$limit")"
      done
      printf "Outer links: %s\n" "$links"
      ip -4 route show table all
      ip -6 route show table all

      base=/var/tmp/argus
      mkdir -m 0700 "$base" "$base/home" "$base/runtime" "$base/tmp" "$base/client" "$base/empty"
      export HOME="$base/home" XDG_RUNTIME_DIR="$base/runtime" TMPDIR="$base/tmp"

      if curl -q -sS --noproxy "*" --max-time 1 http://127.0.0.1:18081/ >/dev/null 2>&1; then exit 1; fi
      mkdir -m 0700 "$base/canary"
      printf "argus-outer-canary" > "$base/canary/index.html"
      python3 -m http.server 18082 --bind 127.0.0.1 --directory "$base/canary" &
      outer_canary=$!
      i=0
      until [ "$(curl -q -fsS --noproxy "*" --max-time 1 http://127.0.0.1:18082/ 2>/dev/null)" = argus-outer-canary ]; do
        kill -0 "$outer_canary"
        i=$((i+1)); test "$i" -lt 10; sleep 1
      done

      rootlesskit --state-dir="$XDG_RUNTIME_DIR/probe" \
        --net=gvisor-tap-vsock --mtu=65520 --port-driver=builtin --disable-host-loopback \
        --copy-up=/etc --copy-up=/run --propagation=rslave --detach-netns \
        -p 127.0.0.1:18080:18080/tcp /usr/bin/sh -ec "
          grep -Eq \"^[[:space:]]*0[[:space:]]+957[[:space:]]+1$\" /proc/self/uid_map
          grep -Eq \"^[[:space:]]*1[[:space:]]+589824[[:space:]]+65536$\" /proc/self/uid_map
          grep -Eq \"^[[:space:]]*0[[:space:]]+957[[:space:]]+1$\" /proc/self/gid_map
          grep -Eq \"^[[:space:]]*1[[:space:]]+589824[[:space:]]+65536$\" /proc/self/gid_map
          grep -qx \"0::/system.slice/argus-sastbench-rootless.service\" /proc/self/cgroup
          test ! -e /run/docker.sock
          test ! -e /var/run/docker.sock
          test ! -r /home/aayush27/.docker
          test ! -r /var/lib/docker
          test ! -r /var/lib/containerd
          inner=\$(nsenter --net=\"\$ROOTLESSKIT_STATE_DIR/netns\" readlink /proc/self/ns/net)
          test \"\$inner\" != \"\$ARGUS_OUTER_NETNS\"
          test \"\$inner\" != \"\$ARGUS_HOST_NETNS\"
          printf \"Inner netns=%s\n\" \"\$inner\"
          if nsenter --net=\"\$ROOTLESSKIT_STATE_DIR/netns\" curl -q -sS --noproxy \"*\" --max-time 1 http://10.0.2.1:18082/ >/dev/null 2>&1 ||
             nsenter --net=\"\$ROOTLESSKIT_STATE_DIR/netns\" curl -q -sS --noproxy \"*\" --max-time 1 http://127.0.0.1:18081/ >/dev/null 2>&1; then exit 1; fi
          nsenter --net=\"\$ROOTLESSKIT_STATE_DIR/netns\" ip -4 route show table all
          nsenter --net=\"\$ROOTLESSKIT_STATE_DIR/netns\" ip -6 route show table all
          if nsenter --net=\"\$ROOTLESSKIT_STATE_DIR/netns\" curl -q -sS --max-time 1 http://192.0.2.1/ >/dev/null 2>&1 ||
             nsenter --net=\"\$ROOTLESSKIT_STATE_DIR/netns\" curl -q -gsS --max-time 1 http://[2001:db8::1]/ >/dev/null 2>&1; then exit 1; fi
          exec nsenter --net=\"\$ROOTLESSKIT_STATE_DIR/netns\" /usr/bin/python3 -m http.server 18080 --bind 0.0.0.0 --directory /var/tmp/argus/empty
        " &
      child=$!
      i=0
      until curl -q --fail --silent --max-time 1 http://127.0.0.1:18080/ >/dev/null; do
        kill -0 "$child"
        i=$((i+1)); test "$i" -lt 20; sleep 1
      done
      printf "%s
" "PASS: mappings, cgroup limits, no outer route, and namespace-local HTTP"
      printf "RootlessKit cgroup: "
      cat "/proc/$child/cgroup"
      cmp -s /proc/self/cgroup "/proc/$child/cgroup"
      test "$(readlink "/proc/$child/ns/net")" = "$ARGUS_OUTER_NETNS"
      test "$(curl -q -fsS --noproxy "*" --max-time 1 http://127.0.0.1:18082/)" = argus-outer-canary
      printf "%s\n" "PASS: mappings, cgroup limits, no outer route, and namespace-local HTTP"
      kill "$child"
      wait "$child" || :
    ' || probe_status=$?

  test "$(curl -q -fsS --noproxy '*' --max-time 1 http://127.0.0.1:18081/)" = argus-host-canary
  cleanup_canary
  trap - EXIT
  after=$(socket_metadata)
  printf 'Host socket after probe:\n%s\n' "$after"
  test "$before" = "$after"
  test "$(getenforce)" = Enforcing
  test "$(systemctl show -p ActiveState --value "$unit")" = inactive
  test ! -e "/sys/fs/cgroup/system.slice/$unit"
  test ! -e /var/tmp/argus
  test ! -L /var/tmp/argus
  host_port=$(ss -Hltn '( sport = :18080 or sport = :18081 or sport = :18082 )')
  test -z "$host_port"
  exit "$probe_status"
)
# END ARGUS NO-DAEMON PREFLIGHT
```

The block checks host socket metadata, SELinux, port absence and cgroup
cleanup even if the unit returns a failure. From an interactive Fedora shell,
copy the exact block above, or run the following from the repository root
after reviewing it:

    bash <(sed -n '/^# BEGIN ARGUS NO-DAEMON PREFLIGHT$/,/^# END ARGUS NO-DAEMON PREFLIGHT$/p' benchmarks/SMOKE.md)

The supervisor budgets up to five seconds for start, four minutes fifty
seconds of service runtime and five seconds for stop. Inspect the limits and
process tree from a second terminal while the unit is active, or read the
journal after collection. The no-daemon probe uses only synthetic HTTP listeners. The outer and inner listeners are stopped by
systemd; the host canary is bounded by timeout and the shell cleanup trap.

```sh
unit=argus-sastbench-rootless.service
sudo systemctl show "$unit" -p User -p Group -p MainPID -p ControlGroup   -p CPUQuotaPerSecUSec -p MemoryMax -p MemorySwapMax -p TasksMax -p RuntimeMaxUSec -p Result
sudo systemd-cgls --unit "$unit"
ss -ltn 'sport = :18080'
sudo journalctl -b -u "$unit" --no-pager -n 100
```

For before/after comparison, run `stat -c '%a %u:%g %i %n' /run/docker.sock`
and the same command on `$HOME/.docker/desktop/docker.sock` if present. This
reads metadata only, and absence is a valid baseline for either path.

CPU, memory, swap and task checks read the service cgroup directly. Match the
process tree to that cgroup, including RootlessKit and any daemon-managed
containerd. The RAM-backed scratch mount is capped at 1 GiB.\nOther listed tmpfs mounts have their own caps; the parent cgroup provides the\naggregate memory limit. This is a no-daemon gate. Builder/container limits,
child egress denial including DNS, arbitrary mount/socket isolation, and
teardown after a container failure still need separate controlled tests.

Likely failures are absent or denied TUN, failed mapping helpers under
file-capability or SELinux restrictions, a RootlessKit port/bridge failure in
the loopback-only outer namespace, SELinux rejection of the launcher's
namespace-local `/run` relabel, or a missing limit controller. Inspect the
unit log and, if needed, `sudo ausearch -m AVC,USER_AVC -ts recent` locally
for the relevant processes. A failure remains a failed gate. Do not relax
host security settings or fall back to the existing Docker endpoint.

For an approved run, cancellation or a failing check is handled by the unit's
control-group kill and mount teardown. If still active, stop only this unit
with `sudo systemctl stop argus-sastbench-rootless.service`. Check
`systemctl show -p LoadState -p ActiveState argus-sastbench-rootless.service`
and that the captured cgroup is gone or empty. Check there is no persistent
host `/var/tmp/argus` or host port created by the run and compare host socket
metadata without connecting. Retain the staged launcher for retries. If its
removal is separately requested, unlink only
`/var/lib/argus-sastbench/dockerd-rootless.sh`. No Docker prune, daemon-wide
cleanup or account removal is part of this rollback.

### Proposed empty-daemon test

**One diagnostic run approved; pending local sudo.** The private hosts
change allowed the daemon to start, but its validation shell exited 1.
The instrumented block passed static review, and the host baseline and
absence of prior Argus resources were rechecked. `sudo -n -l` returned
`sudo: a password is required`. The diagnostic has not run.

The 29.10.1 Engine build matches the staged launcher. The no-daemon test
verified the account mappings, RootlessKit 3.3.0, TUN and the enclosing network
and cgroup. This is a different startup path: SELinux relabel of the private
/run, containerd startup, mount setup and effective runtime limits still must
pass. The shell and Python checks parsed, static systemd unit verification
passed, and Docker's `--validate` reported `configuration OK` without starting
a daemon. The proposed unit masks /etc, /var and /run, re-exposes only the staged
launcher, system account, NSS and SELinux inputs, and a synthetic loopback-only
hosts file. Mount propagation stays private. ProtectHome also masks normal home directories. A clean environment
contains no Docker context, proxy, SSH agent or cloud credential variables.
The device allowlist is for TUN and standard pseudo devices only. The mapping
helpers retain only the ability to set UID/GID via their existing file caps.

The test needs Unix sockets only. It disables the Docker bridge, firewall
management, masquerading, Docker-managed forwarding and port proxying. The
launcher still sets forwarding inside RootlessKit's own network namespace;
the host values are compared before and after. The outer namespace has only
loopback, and the role adds a cgroup IP deny rule and a **live loopback TCP
test** before launch. TCP loopback must be blocked there even though a
listener is present. RootlessKit's Unix control socket remains available.
The daemon uses a fresh data root, and the only Docker API requests are
read-only /_ping and /info against its private Unix socket. There is no build,
pull, registry request, container, or use of the Docker client configuration.

Docker 29 normally defaults to its containerd image store on fresh installs.
This empty test explicitly chooses VFS and disables the containerd image
store, CDI discovery and live restore in the temporary configuration. A
private containerd will still be started by dockerd; hiding the host sockets
and using a fresh XDG runtime prevents system containerd autodetection. Both
processes must be seen in the unit cgroup with host UID/GID 957. The --group=0
flag refers to GID 0 *inside* the RootlessKit user namespace, mapped to 957 on
the host. The API socket must verify as 957:957 with 0660 access permissions
inside a 0700 directory. The only permitted special bit is Docker's sticky
bit, so mode 0660 or 1660 is accepted. Neither grants access to other users.

The block makes no persistent unit, account, configuration, or package
changes. Its temporary resources include a systemd transient unit and
cgroup, RootlessKit user/mount/network namespaces and a TAP interface inside
the unit, capped tmpfs mounts, daemon configuration, pid files, an image
database with zero images, and the Docker and containerd sockets. Only
rate-limited journal records are expected to survive. No TCP port needs to
be published. Read the block before running it.

The first attempt on 2026-11-26 passed the mount, cgroup and TCP-denial
guards. RootlessKit then failed to open /etc/hosts before it could execute
dockerd. The next attempt stopped earlier with 226/NAMESPACE. systemd mounts
the parent /etc tmpfs before its nested bind mounts. That hides the host file
and leaves the new /etc/hosts mount target absent. In systemd 259, tmpfs is
mounted before the final read-only remount, so read-only mode alone does not
explain the error. The Fedora audit record for PID 257529 shows SELinux
denied init_t permission to create the file with label net_conf_t. The bind
then failed with ENOENT. Reordering command-line options does not change
systemd's parent-before-child mount order.

This version drops the synthetic-file bind. It creates a temporary file under
a different name directly in the capped private /etc tmpfs, writes only the
two localhost entries, makes the file mode 0444 and renames it in place.
This avoids the denied creation of a bind target named hosts. No label or
policy is changed. The payload verifies /etc is its own private tmpfs owned
by 957:957 and both hosts and resolv.conf are absent before writing.
It locks the directory down to mode 0555 after setup and verifies the result
before starting RootlessKit. The private /etc mount itself is writable, and
its owner could restore write permission. This is a deliberate change to
temporary configuration protection; the old mount-level read-only property
is not claimed for this private tmpfs. The host's /etc remains masked,
account/NSS/SELinux binds remain read-only, and no host hosts/DNS input is
bound. SELinux may still deny in-unit creation, rename, chmod or subsequent
RootlessKit operations. Stop on a failure. Do not expose host files or relax
the policy to fix it.

Keep mount propagation private despite the separate RootlessKit warning.
The detached namespace check follows the RootlessKit child's mount view via
/proc and requires a real nsfs mount before treating its inode as evidence.

The parent stayed alive while the shell waited 45 seconds for readiness.
The journal then shows a five-second stop-SIGTERM timeout, SIGABRT, a second
timeout, and SIGKILL, all escalation aimed at RootlessKit PID 253706. The
reason the parent did not exit is unverified. The retry explicitly sets
TimeoutStopFailureMode=kill, so systemd sends its final signal after the
existing SIGTERM grace period without a separate abort phase. The test
keeps the same runtime budget and cgroup kill scope.

Read-only host cleanup after the namespace failure and the partial start
confirmed the unit was collected (not-found, inactive, dead,
MainPID=0, no ControlGroup). Read-only process, socket, mount and namespace
inspections found no Argus remnants. The scratch directory, cgroup, transient
unit file and /run/user/957 were absent. The only matching Docker processes
were the existing root-owned containerd (PID 1105) and dockerd (PID 1264).
/run/docker.sock still matched mode 0660, 0:964, inode 2791. The Desktop
socket was absent and the system containerd socket remained present. SELinux
was enforcing and host forwarding remained IPv4 1, IPv6 0. No leftover
synthetic hosts staging directory was found. No existing daemon was contacted.

At 00:43:37.867, private containerd booted. At 00:43:37.989, Docker 29.10.1
with VFS announced the private API socket. Journal credentials put both
processes at UID/GID 957 in the Argus service cgroup. The validation shell
exited with status 1 at 00:43:38.582. Docker received SIGTERM immediately
afterward and reported complete shutdown at 00:43:39.588. There was no final
validation PASS. The shell probably passed readiness: it exited far before
the 45-second timeout while Docker and the RootlessKit parent were alive.
The old block did not log a successful ping.

The leading candidate is the exact socket mode assertion. Pinned Moby sets
0660 access bits and requests the sticky bit on sockets under XDG_RUNTIME_DIR,
which is where this socket was created. There was no logged sticky-bit error
or actual mode. That makes 1660 the best explanation, but not a measured
result. Later silent guards cover mount paths, namespace reads, PID and
cgroup membership, and listener state. The journal's process credentials
support correct identity and membership but do not prove the shell could
read every /proc entry. There was no Python traceback, so a late API metadata
failure is less likely. The revised block logs readiness, actual socket
metadata, stage, failing shell command and status, plus named Python checks.
No ownership, access-bit, private directory, or isolation check is dropped.

Docker's warning refers to per-container cgroups. The parent systemd limits
still measured one CPU, 2 GiB, zero swap and 256 tasks. Do not assume Docker
CPU, memory or PID flags will work without a suitable delegated user systemd
setup. Before a fixture, prove the container and build workers stay inside
the enclosing unit. If the smoke requires separate per-container limits,
this setup has yet to meet that requirement. Do not expose host D-Bus or
enable delegation merely to suppress the warning.

```sh
# BEGIN ARGUS EMPTY DAEMON
(
  set -euo pipefail
  unit=argus-sastbench-empty.service
  launcher=/var/lib/argus-sastbench/dockerd-rootless.sh
  expected=200203633806081a401e60aefdf68a8fa73fc7dc80aa854c52a69d47710a3488

  test "$(id -u argus-sastbench):$(id -g argus-sastbench)" = 957:957
  test "$(id -G argus-sastbench)" = 957
  test "$(getenforce)" = Enforcing
  test -c /dev/net/tun
  test "$(systemctl show -p LoadState --value "$unit")" = not-found
  test ! -e /var/tmp/argus-empty && test ! -L /var/tmp/argus-empty || exit 1
  no_argus_processes() {
    ps -eo pid=,ruid=,euid=,comm= | awk '
      function argus(uid) { return uid == 957 || (uid >= 589824 && uid < 655360) }
      argus($2) || argus($3) { print; bad=1 }
      END { exit bad+0 }
    '
  }
  no_argus_processes
  sudo test ! -L "$launcher"
  test "$(sudo stat -c '%u:%g %a' "$launcher")" = '0:0 555'
  digest=$(sudo sha256sum "$launcher")
  test "$(printf '%s\n' "$digest" | cut -d ' ' -f 1)" = "$expected"
  nss=$(readlink -f /etc/nsswitch.conf)
  test -f "$nss"

  host_snapshot() {
    for path in /run/docker.sock /run/containerd/containerd.sock \
      "$HOME/.docker/desktop/docker.sock"; do
      if test -S "$path"; then
        stat -c '%a %u:%g %d:%i %Y %Z %n' "$path" || return
      elif test ! -e "$path" && test ! -L "$path"; then
        printf 'absent %s\n' "$path"
      else
        return 1
      fi
    done
    stat -c '%a %u:%g %d:%i %Y %Z %n' /etc/hosts /etc/resolv.conf
    sysctl net.ipv4.ip_forward net.ipv6.conf.all.forwarding
  }
  baseline=$(host_snapshot)
  printf 'Host baseline:\n%s\n' "$baseline"
  host_netns=$(readlink /proc/self/ns/net)
  host_mntns=$(readlink /proc/self/ns/mnt)

  payload=$(cat <<'ARGUS_EMPTY_PAYLOAD'
set -Eeuo pipefail
stage=pre-launch
abort() {
  printf '<3>Argus failed [%s]: %s\n' "$stage" "$*" >&2
  exit 1
}
trap 'status=$?; printf "<3>Argus failed [%s] at payload line %s (status %s): %s\n" "$stage" "$LINENO" "$status" "$BASH_COMMAND" >&2' ERR
test "$(id -u):$(id -g)" = 957:957
test "$(id -G)" = 957
test "$(getenforce)" = Enforcing
test "$(awk '/^NoNewPrivs:/ {print $2}' /proc/self/status)" = 0
grep -qx 'argus-sastbench:589824:65536' /etc/subuid
grep -qx 'argus-sastbench:589824:65536' /etc/subgid
for path in /run/docker.sock /run/containerd/containerd.sock \
  /var/run/docker.sock /var/lib/docker /var/lib/containerd \
  /etc/docker /etc/containerd /etc/shadow /home/aayush27/.docker; do
  test ! -e "$path" && test ! -L "$path" || abort "unexpected host path visible: $path"
done
test ! -r /home/aayush27
test ! -r /root
test ! -e /var/tmp/argus-empty
for mount in /etc /var /run /tmp /var/tmp; do
  test "$(findmnt -n -o FSTYPE --target "$mount")" = tmpfs
  test "$(findmnt -n -o PROPAGATION --target "$mount")" = private
  findmnt -n -o TARGET,OPTIONS --target "$mount"
done
test "$(findmnt -n -o PROPAGATION --target /)" = private

# Populate only the unit's own /etc. Any unexpected mount or path stops here.
test "$(findmnt -n -o TARGET --target /etc)" = /etc
test "$(stat -c '%u:%g %a' /etc)" = '957:957 755'
for path in /etc/hosts /etc/resolv.conf; do
  test ! -e "$path" && test ! -L "$path" || abort "unexpected hosts or resolver path: $path"
done
hosts_tmp=$(mktemp /etc/.argus-hosts.XXXXXXXX)
printf '127.0.0.1 localhost\n::1 localhost\n' > "$hosts_tmp"
chmod 0444 "$hosts_tmp"
mv -T --no-clobber "$hosts_tmp" /etc/hosts
test ! -e "$hosts_tmp"
chmod 0555 /etc
test -f /etc/hosts
test ! -L /etc/hosts
test "$(findmnt -n -o TARGET --target /etc/hosts)" = /etc
test "$(stat -c '%u:%g %a' /etc/hosts)" = '957:957 444'
test "$(stat -c '%a' /etc)" = 555
test ! -w /etc
test ! -w /etc/hosts
test ! -e /etc/resolv.conf && test ! -L /etc/resolv.conf || abort "unexpected resolver configuration"
cmp -s /etc/hosts <(printf '127.0.0.1 localhost\n::1 localhost\n')
for mount in /run /tmp /var/tmp; do
  limit=67108864
  if [ "$mount" = /var/tmp ]; then limit=1073741824; fi
  test "$(df -B1 --output=size "$mount" | tail -n 1)" -le "$limit"
done

outer=$(readlink /proc/self/ns/net)
service_mntns=$(readlink /proc/self/ns/mnt)
test "$outer" != "$ARGUS_HOST_NETNS"
test "$service_mntns" != "$ARGUS_HOST_MNTNS"
export ARGUS_OUTER_NETNS="$outer"
export ARGUS_SERVICE_MNTNS="$service_mntns"
links=$(ip -o link show)
test "$(printf '%s\n' "$links" | cut -d: -f2 | tr -d ' ')" = lo
routes4=$(ip -4 route show default)
routes6=$(ip -6 route show default)
test -z "$routes4$routes6"
printf 'host=%s outer=%s\n%s\n' "$ARGUS_HOST_NETNS" "$outer" "$links"
ip -4 route show table all
ip -6 route show table all
cg=/sys/fs/cgroup/system.slice/argus-sastbench-empty.service
test "$(cat /proc/self/cgroup)" = '0::/system.slice/argus-sastbench-empty.service'
test "$(cat "$cg/cpu.max")" = '100000 100000'
test "$(cat "$cg/memory.max")" = 2147483648
test "$(cat "$cg/memory.swap.max")" = 0
test "$(cat "$cg/pids.max")" = 256
for limit in cpu.max memory.max memory.swap.max pids.max; do
  printf '%s=%s\n' "$limit" "$(cat "$cg/$limit")"
done

python3 - <<'ARGUS_IP_TEST'
import socket

for family, address in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
    with socket.socket(family, socket.SOCK_STREAM) as server:
        server.bind((address, 0))
        server.listen()
        with socket.socket(family, socket.SOCK_STREAM) as client:
            client.settimeout(0.6)
            try:
                client.connect(server.getsockname())
            except (TimeoutError, PermissionError):
                print(f"Unit IP policy blocked TCP to a listening socket on {address}")
            else:
                raise SystemExit(f"Unexpected TCP access to {address}")
ARGUS_IP_TEST

base=/var/tmp/argus-empty
mkdir -m 0700 "$base" "$base/home" "$base/runtime" "$base/tmp" "$base/client"
export HOME="$base/home" XDG_RUNTIME_DIR="$base/runtime" TMPDIR="$base/tmp"
export XDG_CONFIG_HOME="$base/home/.config" XDG_DATA_HOME="$base/home/.local/share"
export DOCKER_CONFIG="$base/client" DOCKER_TMPDIR="$base/tmp"
export DOCKERD_ROOTLESS_ROOTLESSKIT_NET=gvisor-tap-vsock
export DOCKERD_ROOTLESS_ROOTLESSKIT_PORT_DRIVER=builtin
export DOCKERD_ROOTLESS_ROOTLESSKIT_DISABLE_HOST_LOOPBACK=true
export DOCKERD_ROOTLESS_ROOTLESSKIT_DETACH_NETNS=true
export DOCKERD_ROOTLESS_ROOTLESSKIT_STATE_DIR="$base/runtime/rootlesskit"
socket="$base/runtime/docker.sock"
test ! -e "$base/runtime/containerd/containerd.sock"
printf '%s\n' '{"features":{"containerd-snapshotter":false,"cdi":false},"live-restore":false}' > "$base/daemon.json"

# The only startup step. Nothing above this line runs the launcher.
stage=private-api-readiness
SECONDS=0
/var/lib/argus-sastbench/dockerd-rootless.sh \
  --rootless --config-file="$base/daemon.json" --host="unix://$socket" --group=0 \
  --data-root="$base/data" --exec-root="$base/exec" \
  --pidfile="$base/runtime/dockerd.pid" --storage-driver=vfs \
  --bridge=none --iptables=false --ip6tables=false --ip-forward=false \
  --ip-masq=false --userland-proxy=false --shutdown-timeout=3 &
launcher_pid=$!
until [ -S "$socket" ] && curl -q --fail --silent --max-time 1 \
  --unix-socket "$socket" http://localhost/_ping | grep -qx OK; do
  kill -0 "$launcher_pid"
  test "$SECONDS" -lt 45
  sleep 1
done
printf 'Argus readiness: private Unix /_ping returned OK\n'
stage=socket-and-storage
test ! -L "$socket"
socket_meta=$(stat -c '%u:%g %a' "$socket")
printf 'Argus socket metadata: %s\n' "$socket_meta"
case "$socket_meta" in
  '957:957 660'|'957:957 1660') ;;
  *) abort "unexpected socket owner or mode: $socket_meta" ;;
esac
test "$(stat -c '%a' "$base/runtime")" = 700
test "$(findmnt -n -o TARGET --target "$base/data")" = /var/tmp
test "$(findmnt -n -o TARGET --target "$base/exec")" = /var/tmp
stage=rootlesskit-namespaces
test "$(readlink "/proc/$launcher_pid/ns/net")" = "$outer"
rk_child=$(cat "$base/runtime/rootlesskit/child_pid")
case "$rk_child" in ''|*[!0-9]*) abort "RootlessKit child PID is not numeric" ;; esac
test "$rk_child" -gt 1
grep -qx "$rk_child" "$cg/cgroup.procs"
netns_path="/proc/$rk_child/root$base/runtime/rootlesskit/netns"
test "$(stat -f -c '%T' "$netns_path")" = nsfs
inner=$(stat -Lc '%i' "$netns_path")
test "net:[$inner]" != "$outer"
test "net:[$inner]" != "$ARGUS_HOST_NETNS"

stage=daemon-process-identities
dockerd_pid=$(cat "$base/runtime/dockerd.pid")
case "$dockerd_pid" in ''|*[!0-9]*) abort "dockerd PID is not numeric" ;; esac
test "$dockerd_pid" -gt 1
test "$(cat "/proc/$dockerd_pid/comm")" = dockerd
grep -qx "$dockerd_pid" "$cg/cgroup.procs"
cmp -s /proc/self/cgroup "/proc/$dockerd_pid/cgroup"
containerd_count=0
while read -r pid; do
  comm=$(cat "/proc/$pid/comm") || abort "could not read cgroup PID $pid"
  case "$comm" in
    dockerd|containerd)
      test "$(awk '/^Uid:/ {print $3}' "/proc/$pid/status")" = 957
      test "$(awk '/^Gid:/ {print $3}' "/proc/$pid/status")" = 957
      cmp -s /proc/self/cgroup "/proc/$pid/cgroup"
      process_net=$(readlink "/proc/$pid/ns/net")
      test "$process_net" = "$outer" || test "$process_net" = "net:[$inner]" || abort "$comm PID $pid is in unexpected netns $process_net"
      grep -Eq '^[[:space:]]*0[[:space:]]+957[[:space:]]+1$' "/proc/$pid/uid_map"
      grep -Eq '^[[:space:]]*0[[:space:]]+957[[:space:]]+1$' "/proc/$pid/gid_map"
      if [ "$comm" = containerd ]; then containerd_count=$((containerd_count+1)); fi
      printf 'Verified %s host uid/gid=957:957, netns=%s, cgroup=%s\n' "$comm" "$process_net" "$(cat "/proc/$pid/cgroup")"
      ;;
    containerd-shim*) abort "unexpected containerd shim PID $pid" ;;
  esac
done < "$cg/cgroup.procs"
test "$containerd_count" -eq 1
stage=network-listeners
listeners=$(ss -H -lntu)
test -z "$listeners" || abort "unexpected TCP or UDP listener: $listeners"
stage=private-api-info
curl -q --fail --silent --show-error --max-time 2 --unix-socket "$socket" \
  http://localhost/info > "$base/info.json"
python3 - "$base/info.json" <<'ARGUS_DOCKER_INFO'
import json
import os
from pathlib import Path
import sys

with open(sys.argv[1]) as stream:
    info = json.load(stream)
assert info["DockerRootDir"] == "/var/tmp/argus-empty/data", f"DockerRootDir={info['DockerRootDir']!r}"
assert info["Driver"] == "vfs", f"Driver={info['Driver']!r}"
assert info["ServerVersion"] == "29.10.1", f"ServerVersion={info['ServerVersion']!r}"
assert info["Containers"] == info["Images"] == 0, f"Containers={info['Containers']} Images={info['Images']}"
assert any("name=rootless" == option for option in info["SecurityOptions"]), "missing rootless security option"
assert not info["LiveRestoreEnabled"], "LiveRestoreEnabled is unexpectedly true"
print(f"Argus daemon CgroupDriver={info.get('CgroupDriver')!r}")
address = info["Containerd"]["Address"].removeprefix("unix://")
private_exec = Path("/var/tmp/argus-empty/exec/containerd").resolve(strict=True)
assert Path(address).resolve(strict=True).is_relative_to(private_exec), f"unexpected containerd address: {address!r}"
assert Path(address).is_socket(), f"containerd address is not a socket: {address!r}"
print("PASS: private rootless Docker 29.10.1, VFS, zero containers and images; private containerd", os.fspath(address))
ARGUS_DOCKER_INFO
stage=shutdown
kill -TERM "$dockerd_pid"
for attempt in 1 2 3 4 5; do
  if ! kill -0 "$launcher_pid" 2>/dev/null; then break; fi
  sleep 1
done
if kill -0 "$launcher_pid" 2>/dev/null; then
  printf '%s\n' 'Daemon did not stop promptly; systemd will terminate the unit.' >&2
  exit 1
fi
wait "$launcher_pid"
ARGUS_EMPTY_PAYLOAD
)

  result=0
  sudo systemd-run --slice=system.slice --unit="$unit" --wait --collect --expand-environment=no \
    --property=Type=exec --property=User=argus-sastbench \
    --property=Group=argus-sastbench --property=UMask=0077 \
    --property=PrivateNetwork=yes --property=PrivateIPC=yes \
    --property=IPAddressDeny=any --property=MountFlags=private \
    --property=ProtectHome=yes --property=ProtectSystem=strict \
    --property=NoNewPrivileges=no \
    --property='CapabilityBoundingSet=CAP_SETUID CAP_SETGID' \
    --property=DevicePolicy=closed --property='DeviceAllow=/dev/net/tun rw' \
    --property='InaccessiblePaths=-/dev/shm -/dev/mqueue -/usr/local -/opt -/srv -/mnt -/media' \
    --property='TemporaryFileSystem=/etc:rw,size=16M,mode=0755,uid=957,gid=957,nosuid,noexec /var:ro,size=16M /run:rw,size=64M,mode=0755 /tmp:rw,size=64M,mode=1777 /var/tmp:rw,size=1G,mode=1777' \
    --property="BindReadOnlyPaths=$launcher /etc/passwd /etc/group /etc/subuid /etc/subgid /etc/login.defs /etc/selinux $nss:/etc/nsswitch.conf" \
    --property=CPUQuota=100% --property=MemoryMax=2G \
    --property=MemorySwapMax=0 --property=TasksMax=256 \
    --property=TimeoutStartSec=5s --property=RuntimeMaxSec=4min50s --property=TimeoutStopSec=5s \
    --property=TimeoutStopFailureMode=kill \
    --property=KillMode=control-group --property=Restart=no \
    --property=LogRateLimitIntervalSec=30s --property=LogRateLimitBurst=100 \
    /usr/bin/env -i PATH=/usr/bin:/usr/sbin LANG=C.UTF-8 \
      ARGUS_HOST_NETNS="$host_netns" ARGUS_HOST_MNTNS="$host_mntns" \
      /usr/bin/bash -c "$payload" || result=$?

  after=$(host_snapshot)
  printf 'Host after test:\n%s\n' "$after"
  test "$baseline" = "$after"
  test "$(getenforce)" = Enforcing
  test "$(systemctl show -p MainPID --value "$unit")" = 0
  test "$(systemctl show -p ActiveState --value "$unit")" = inactive
  test ! -e /sys/fs/cgroup/system.slice/argus-sastbench-empty.service
  test ! -e /var/tmp/argus-empty && test ! -L /var/tmp/argus-empty || exit 1
  no_argus_processes
  findmnt -rn -t nsfs -o TARGET | awk '/argus-empty/ { print; bad=1 } END { exit bad+0 }'
  ss -H -xln | awk '/argus-empty/ { print; bad=1 } END { exit bad+0 }'
  exit "$result"
)
# END ARGUS EMPTY DAEMON
```

Run the approved block once from the repository root in an interactive
Fedora terminal. Inspect status and logs even on failure. Do
not retry automatically:

```sh
sudo -v
bash <(sed -n '/^# BEGIN ARGUS EMPTY DAEMON$/,/^# END ARGUS EMPTY DAEMON$/p' benchmarks/SMOKE.md)
sudo journalctl -b -u argus-sastbench-empty.service --no-pager -n 100
systemctl show argus-sastbench-empty.service -p LoadState -p ActiveState -p MainPID -p ControlGroup
ps -U 957 -u 957 -o pid,ppid,uid,gid,cgroup,comm
findmnt -rn -t nsfs -o TARGET,SOURCE | awk '/argus-empty/'
ss -H -xln | awk '/argus-empty/'
```

If a guard fails, stop and retain the journal. A time bound, mount or cgroup
policy rejection, unavailable mapping capability, SELinux denial, existing
endpoint visibility, missing managed containerd, wrong Unix ownership,
unexpected TCP listener, nonempty inventory, or a surviving Argus resource
is a failed test. Do not widen network access, turn off SELinux, or relax the
mount boundaries to force a pass. Fedora's PID 1 controls the entire service
cgroup even if dockerd faults or is stalled. If the unit is still active,
the rollback is solely:

```sh
sudo systemctl stop argus-sastbench-empty.service
```

Repeat the post-run host checks and inspect the journal. The synthetic hosts
file resides only in the private tmpfs and vanishes with the unit. Do not delete an
unexplained mount, socket or process manually. Retain the staged launcher
and account. The result cannot prove OCI process or bind-mount behavior,
container networking, port publishing, build-worker ownership or egress,
or SastBench compatibility. The empty daemon still shares Fedora's kernel
and uses the installed binaries and mapping helpers. A startup bug can
consume bounded host resources or abort and leave diagnostic logs. A failure
that cannot be fixed without weakening the boundary favors the disposable VM.

Before executing the CLI, implement and review: a deterministic local Git
repository and labeled dataset, a Docker-packaged fixture with bounded resources,
a private run workspace and exact resource inventory, narrowly owned teardown on
normal and abnormal exits, a supervised timeout, and an official CLI launcher
that checks the pin and dataset checksum and uses the clean environment. The
unmodified upstream global cleanup is acceptable only inside a verified
disposable daemon containing no unrelated resources. Confirm container, network,
volume, worktree, and temporary-file cleanup after success, failure and
interruption. Reconcile the official report against all submitted IDs with the
coverage audit, and explicitly check grouping, payloads, predictions, scoring,
invalid output, missing fields, timeouts and partial failures. No exact official
CLI command is supplied until these controls and local fixture inputs exist.

## M0 diagnostic run preflight: blocked before execution

On 2026-11-26, the approved preflight was run before the single diagnostic
attempt. SELinux reported `Enforcing`. `id argus-sastbench` returned UID/GID
957 with only its private group. The transient unit was `LoadState=not-found`,
`ActiveState=inactive`, `MainPID=0`, with an empty `ControlGroup`. Both
`/var/tmp/argus-empty` and `/run/user/957` were absent. Process inspection found
no processes with real or effective UID 957. Read-only mount, nsfs and Unix
socket scans found no Argus remnants.

Existing socket metadata was `/run/docker.sock`: mode 660, owner/group 0:964,
device:inode 31:2791; `/run/containerd/containerd.sock`: mode 660, owner/group
0:0, device:inode 31:3208; Docker Desktop socket absent. Host forwarding was
IPv4 1 and IPv6 0. These matched the recorded baseline. No daemon was contacted.
The script's private network, filesystem, cgroup, CPU, memory, swap, PID,
storage and wall-clock restrictions were statically reviewed; they were not
runtime-measured in this attempt because execution did not begin.

The first unpassed preflight operation was `sudo -n stat` on the staged
launcher; it returned `sudo: a password is required`. `sudo -n -v` also failed.
No transient service, RootlessKit, dockerd or containerd was started. The
launcher checksum and root-owned metadata could not be rechecked. No retry was
made. To perform the already-approved single run, use an interactive Fedora
terminal from the repository root:

```sh
sudo -v
bash <(sed -n '/^# BEGIN ARGUS EMPTY DAEMON$/,/^# END ARGUS EMPTY DAEMON$/p' benchmarks/SMOKE.md)
sudo journalctl -b -u argus-sastbench-empty.service --no-pager -n 100
systemctl show argus-sastbench-empty.service -p LoadState -p ActiveState -p MainPID -p ControlGroup
ps -U 957 -u 957 -o pid,ppid,uid,gid,cgroup,comm
findmnt -rn -t nsfs -o TARGET,SOURCE | awk '/argus-empty/'
ss -H -xln | awk '/argus-empty/'
```

Do not run the block again if the single approved run has already been done
locally. If a guard fails, preserve its output and journal for diagnosis; do not
retry or weaken isolation. Container-level testing remains outside this approval.

## M0 empty-daemon validation reported passed

On 2026-11-26, the owner reported that the diagnostic empty-daemon validation
passed. This records the owner's result; raw command output, journal excerpts,
and measured socket/cgroup values were not supplied in this update, so those
details are not independently reproduced here. The prior empty-daemon test's
assertions cover private API readiness, socket ownership/mode, private storage
and containerd metadata, zero containers/images, RootlessKit namespace separation,
network listeners, daemon process identity/cgroup membership, SELinux, host
socket/forwarding comparison, and teardown. Treat those properties as reported
passed, with the detailed measurements pending archival of the Fedora output.
No container, build, image pull or SastBench run is included in this result.

## Proposed next gate: one offline container isolation test

This is a plan only. It is **not approved for execution**. The test must run
inside a fresh instance of the same transient Argus supervisor and private
rootless daemon. It must not point `DOCKER_HOST` at `/run/docker.sock`, use the
system Docker context, or mount any host socket. The empty-daemon result only
proves daemon startup and its API checks; it does not prove container behavior.

### Image and execution prerequisites

Before the later container-test approval, select a minimal trusted image that
has `/bin/sh`, `id`, `cat`, and (for route inspection) `ip`. Pin it by immutable
image digest and obtain a Docker-format image archive through a separately
reviewed trusted source. Verify the archive SHA-256 and image digest before the
test. Make that archive available as a root-owned, read-only single-file input
to the transient service, bound read-only to `/tmp/argus-fixture.tar` and its
sidecar checksum file to `/tmp/argus-fixture.tar.sha256`. These targets are
inside the service's private capped `/tmp`; check that systemd creates them
without an SELinux denial before starting the daemon. Keep the archive below a
reviewed size bound so the imported image fits the 1 GiB private data budget.
Do not use `docker pull`, a build, a mutable tag, an existing host Docker image
store, or any registry/API access during the test. If the image and archive
provenance/checksum are unavailable, stop before daemon startup. Archive
staging itself requires approval; no image is staged by this plan.

The fresh unit should retain all currently reviewed supervisor settings:
UID/GID 957, private network and mount namespaces, `IPAddressDeny=any`, masked
host `/etc`, `/var`, `/run`, `/tmp`, `/var/tmp` and home paths except the
explicit private inputs, SELinux enforcing, one CPU, 2 GiB memory, zero swap,
256 tasks, capped tmpfs storage and a five-minute whole-cgroup runtime/kill
policy. The payload should verify those effective values before daemon start.
Do not enable systemd delegation or relax these restrictions to make per-
container cgroups appear available.

### Planned test procedure (inside the transient service payload)

The approved implementation should use the private socket explicitly and
fail if the socket path is missing or resolves elsewhere. The only image
operation is loading the checksum-verified local archive:

```sh
export DOCKER_HOST=unix:///var/tmp/argus-empty/runtime/docker.sock
export DOCKER_CONFIG=/var/tmp/argus-empty/client
image_ref='argus-fixture:local'
expected_image_id='sha256:FIXED_CONFIG_DIGEST'
test -S /var/tmp/argus-empty/runtime/docker.sock
test ! -S /run/docker.sock
test ! -S /run/containerd/containerd.sock
image_archive=/tmp/argus-fixture.tar
sha256sum --check /tmp/argus-fixture.tar.sha256
docker load --input "$image_archive"
test "$(docker image inspect --format '{{.Id}}' "$image_ref")" = "$expected_image_id"

cid=$(docker create --pull=never --name argus-m0-isolation \
  --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges \
  --tmpfs /tmp:rw,noexec,nosuid,size=8m \
  "$image_ref" /bin/sh -c '
    set -eu
    test "$(id -u)" = 0
    test ! -S /run/docker.sock
    test ! -S /var/run/docker.sock
    test -w /tmp
    ! touch /root/argus-read-only-probe
    ip -o link show
    test "$(ip -o link show | wc -l)" -eq 1
    test -z "$(ip -4 route show default)"
    test -z "$(ip -6 route show default)"
    sleep 20
  ')
docker start "$cid" >/dev/null
cleanup_container() {
  status=$?
  if [ -n "${cid:-}" ] && docker inspect "$cid" >/dev/null 2>&1; then
    docker rm --force "$cid" >/dev/null || printf 'cleanup by exact ID failed: %s\n' "$cid" >&2
  fi
  return "$status"
}
trap cleanup_container EXIT
pid=$(docker inspect --format '{{.State.Pid}}' "$cid")
test "$pid" -gt 1
test "$(docker inspect --format '{{.HostConfig.NetworkMode}}' "$cid")" = none
test "$(docker inspect --format '{{.HostConfig.Privileged}}' "$cid")" = false
test "$(docker inspect --format '{{.HostConfig.ReadonlyRootfs}}' "$cid")" = true
docker inspect "$cid" > "$base/inspect.json"
python3 - "$base/inspect.json" <<'ARGUS_INSPECT'
import json, sys
obj = json.load(open(sys.argv[1]))[0]
host = obj["HostConfig"]
assert not host["Binds"], host["Binds"]
assert not host["Privileged"]
assert host["ReadonlyRootfs"]
assert "ALL" in host["CapDrop"], host["CapDrop"]
assert any("no-new-privileges" in opt for opt in host["SecurityOpt"]), host["SecurityOpt"]
mounts = obj["Mounts"]
assert len(mounts) == 1 and mounts[0]["Type"] == "tmpfs" and mounts[0]["Destination"] == "/tmp" and mounts[0]["RW"], mounts
assert not host.get("PortBindings"), host.get("PortBindings")
print("PASS: inspect confirms no host mounts, privileged mode, capabilities, or published ports")
ARGUS_INSPECT
grep -qx "$pid" /sys/fs/cgroup/system.slice/argus-sastbench-empty.service/cgroup.procs
test "$(awk '/^Uid:/ {print $3}' "/proc/$pid/status")" -ne 0
test "$(awk '/^Gid:/ {print $3}' "/proc/$pid/status")" -ne 0
awk '($2 == 957 && $3 == 1) || ($2 >= 589824 && $2+$3 <= 655360) {next} {bad=1} END {exit bad}' "/proc/$pid/uid_map"
awk '($2 == 957 && $3 == 1) || ($2 >= 589824 && $2+$3 <= 655360) {next} {bad=1} END {exit bad}' "/proc/$pid/gid_map"
test "$(readlink "/proc/$pid/ns/net")" != "$ARGUS_HOST_NETNS"
test "$(readlink "/proc/$pid/ns/net")" != "$ARGUS_OUTER_NETNS"
test "$(readlink "/proc/$pid/ns/mnt")" != "$ARGUS_HOST_MNTNS"
test "$(readlink "/proc/$pid/ns/mnt")" != "$ARGUS_SERVICE_MNTNS"
test "$(cat /sys/fs/cgroup/system.slice/argus-sastbench-empty.service/cpu.max)" = '100000 100000'
test "$(cat /sys/fs/cgroup/system.slice/argus-sastbench-empty.service/memory.max)" = 2147483648
test "$(cat /sys/fs/cgroup/system.slice/argus-sastbench-empty.service/memory.swap.max)" = 0
test "$(cat /sys/fs/cgroup/system.slice/argus-sastbench-empty.service/pids.max)" = 256
docker logs "$cid"
exit_code=$(docker wait "$cid")
test "$exit_code" = 0
docker rm "$cid" >/dev/null
cid=
trap - EXIT
```

The run command is a reviewed template, not a command to execute now. Before
implementation, validate all options and the exact inspect formatting against
the pinned Engine CLI. Add the two archive files with
`BindReadOnlyPaths=/verified/source/fixture.tar:/tmp/argus-fixture.tar` and
the equivalent checksum-file bind. Resolve the fixed local image tag and
expected config digest from the verified archive before the run. The `Mounts`
inspect assertion must be parsed structurally rather than compared to a JSON
string if the pinned Engine emits a different stable field order; its required
meaning is exactly one `/tmp` tmpfs and no host path. The container command
must finish within its 20-second sleep and must not create listeners.

The previous daemon reported that rootless per-container cgroups were
unavailable. Therefore the procedure intentionally does not request
`--cpus`, `--memory`, or `--pids-limit` from Docker or claim that such flags
work. The enclosing systemd cgroup is the only already verified hard resource
cap and must contain the container process with values `100000 100000`,
`2147483648`, `0`, and `256` for CPU, memory, swap and PIDs. Any claim of
separate per-container limits remains unverified and is a blocker if the test
requires them. Avoid deliberately exhausting memory, PIDs, CPU, or storage.

While the container is alive, the supervising payload should inspect only
this container through the private API and its exact returned PID. Verify:

1. `docker inspect` identifies the exact pinned image/config digest, `NetworkMode=none`,
   `ReadonlyRootfs=true`, `Privileged=false`, all capabilities dropped,
   `no-new-privileges`, no host `Binds`/`Mounts`, and only the test `/tmp`
   tmpfs. Confirm its namespace configuration has no host network mode.
2. The container's host PID exists, has no host-root effective UID/GID, and
   belongs to `/system.slice/argus-sastbench-empty.service`. Read its
   `/proc/<pid>/uid_map` and `gid_map`; verify container root maps only to the
   Argus/rootless user or its allocated subordinate range, never host UID/GID
   0. Verify its network and mount namespaces differ from both host and outer
   service namespaces. Within the container, `ip` reports loopback only and no default
   route. The cgroup path exposes the parent's expected CPU, memory, swap and
   PID limits (`100000 100000`, `2147483648`, `0`, `256`).
3. The private daemon reports the expected private data root and zero
   unexpected containers. The image count is exactly the one imported
   fixture. No network listener is created by the container. Do not use
   failed connections to public/test IPs as evidence of egress denial; rely on
   the host-enforced no-uplink namespace, inherited cgroup IP deny policy, and
   verified namespace/route configuration. The existing no-daemon canary
   evidence covers the supervisor's local boundary; container namespace
   inspection extends that evidence to this container.
4. SELinux remains `Enforcing`; retain and inspect AVC records if any. An AVC
   denial is a test failure. Do not alter labels or policy to make the test pass.
5. Remove only the exact container ID returned by this run (`docker rm --force
   "$cid"` if still present), then verify that the private daemon has no
   containers except none, and that the one expected imported image is the
   only image. Do not run prune, Compose down, broad name/label deletion, or
   cleanup against any other endpoint. Let systemd terminate the daemon and
   destroy its transient storage; verify no Argus process, socket, mount,
   namespace pin, cgroup, or scratch directory remains and compare existing
   Docker/containerd socket metadata and host forwarding with the pre-run
   snapshot.

### Expected result, limitations, and rollback

Expected: one short-lived non-privileged container runs under UID mappings
owned by the rootless account/subordinate range, shares the supervisor's hard
cgroup budget, has a separate loopback-only network namespace, sees no host
socket or host bind mount, and cannot write its root filesystem. The private
daemon and all transient state disappear at service exit. Existing Docker
resources and metadata remain unchanged.

Risks/unknowns: rootless container UID mapping and OCI mount behavior are not
yet measured; Docker's per-container CPU/memory/PID limits may be unavailable;
containerd may create transient helper processes; SELinux may deny operations;
and no test can prove absence of every kernel/runtime bug. The service shares
the Fedora kernel. The container receives a read-only archive and uses the
installed Docker/RootlessKit binaries. Do not proceed if image provenance,
resource inheritance, network policy, mount inventory, or teardown is
ambiguous. A container test does not validate SastBench cleanup semantics,
Compose behavior, build egress, or evaluator compatibility.

On normal completion, remove only the exact test container ID and let the
transient unit collect its cgroup and private tmpfs. On any failure or timeout,
stop only `argus-sastbench-empty.service`, inspect its journal and recheck
processes, socket, mounts, namespaces, cgroup, scratch path, SELinux and host
socket/forwarding baseline. Do not manually delete an unexplained resource or
run any Docker-wide cleanup. The exact implementation and the one-time
execution command require separate review and approval before any image is
staged or container is created.
