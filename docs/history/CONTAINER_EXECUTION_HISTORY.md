> Historical pre-MVP document. Its APIs and commands were retired in revised M3.
> Use the root README and docs/RECOVERY.md for current operation.

# Historical container execution contract — superseded

The user replaced this execution design with the [dedicated VM decision](TRUSTED_VM_DECISION.md).
The following describes the preserved earlier implementation, not the active native adapter.

# M4 execution contract — partial, fail closed

M4 is **in progress**, not complete. Python and Node dependency/build/test commands
have passed real offline container checks. Codex and Chromium cannot create their
required sandbox namespaces under the tested host/container policy. Real model
usage, authentication exposure and session-resume permissions remain unverified.
`CodexAdapter.generate()` always refuses; there is no operational execution CLI.
Approved M4 acceptance text in ROADMAP.md is unchanged.

## Trusted launcher and boundary

`execution.ContainerExecutor` accepts an open M3 store and its current revision,
an explicit argument vector, and a pinned `ContainerPolicy`. New execution requires
that exact policy under approved policy v2; v1 is inspection/control only. The
existing repository lock remains held throughout execution. Run/check/operation
identities and configuration are recorded durably before container creation.

Only `/usr/bin/docker --host unix:///var/run/docker.sock` runs on the trusted host,
with a fixed allowlisted environment. The host owns daemon access. Project/agent
containers never receive a Docker socket, daemon API, host credentials, operational
state, host HOME, host networking, privileged mode or unrelated host directories.
No project Dockerfile, hook, package manager or shell startup file runs on the host.

The launcher checks Linux, Docker's builtin seccomp policy, default AppArmor and
cgroups v2. It requires a locally available immutable runner-image ID with the
M4 environment label. It creates an explicitly named/labeled container, inspects
the created configuration before starting it, and checks the runtime AppArmor
profile after execution. An unsupported/mismatched capability stops execution.
Docker assigns the runtime AppArmor field at startup; the explicit default-profile
request is checked before start. Resource constraints include memory/swap, CPUs,
PIDs, open files, timeout and bounded captured output.

The only host bind is the canonical checkout at `/workspace`, writable as its
non-root owner UID/GID. The root filesystem is read-only. All capabilities are
dropped, no-new-privileges is set, and network mode is `none`. Private ephemeral
HOME and `/tmp` tmpfs mounts hold execution scratch data. A read-only empty tmpfs
over `/workspace/.git` hides original Git objects/config/hooks and prevents Git
metadata writes or replacement. This deliberately supplies no Git view to Codex;
the prepared command uses `--skip-git-repo-check` and trusted run context must
identify the approved base. The host orchestrator retains real Git access.

Ordinary owned checkouts are supported. Linked worktrees, sensitive config paths
(`.env*`, `.aws`, `.ssh`, `.codex`, `.npmrc`, etc.), nested Git directories, special
files, hard links, nested host mounts and escaping symlinks diagnose before launch.
Internal project symlinks are allowed. Reference/legacy state overlaps and unowned
test targets are rejected before effects. These scans supplement OS isolation;
they assume the trusted owner does not concurrently replace host paths. Arbitrary
secrets deliberately placed in project source cannot be recognized by filename.

## Environment and dependencies

The runner-owned Dockerfile in `containers/m4` supplies Python 3.12, Node 22/npm,
Chromium, bubblewrap and Git. Only its Dockerfile and the installed trusted Codex
binary enter the generated build context. Base images are pinned by digest.
Setuptools/wheel are pinned. Debian security package versions are resolved at
build time, so rebuilding may yield a different image ID; inspect and explicitly
approve that ID, never follow a mutable tag at execution time.

`dependency_commands()` provides a copied Python `.venv` plus offline pip install,
or `npm ci --offline`. Commands, lifecycle scripts, builds and tests all go through
the same container adapter. Python's runner-provided setuptools/wheel are available
through `--system-site-packages` inside the image. No host site-packages are mounted.
The standard `.venv` discovery exclusion prevents generated environment documents
from becoming requirements. The project's own pre-existing environment is not
trusted as a host executable; escaping links are refused.

Network retrieval is intentionally unavailable. Missing external dependencies
require reviewed local wheels/npm cache or a future separately constrained fetch
path; they cannot trigger host pip/npm or an open-network fallback. The real
fixtures use a local Python build and npm lifecycle scripts without external
dependencies. General online dependency retrieval remains a limitation.

## Codex capability/report contract

The installed binary and bundled catalog establish CLI 0.166.0, model
`gpt-6.1-sol`, and `model_reasoning_effort="high"`. The adapter pins that version's
contract, checks required exec/resume help controls and requires an actual sandbox
sentinel. A different version/model/effort or unsupported sandbox fails closed.
Catalog support is not proof of account access or successful real inference.

Settings use a named permission profile, approval policy `never`, command network
disabled, workspace writes, denied Git/Codex-home/proc/API-transport paths, and an
allowlisted shell environment. There is no automatic approval/review, legacy
Landlock, unrestricted sandbox, model fallback or downgrade response. Fresh/resume
command builders reassert the same settings; resume requires an exact UUID.
Fresh ephemeral HOME contains no user config or credentials, and project Codex
configuration is refused. The prepared exec invocation ignores user config/rules.

`parse_events` validates newline-delimited structured events, a single session UUID,
turn completion, nonnegative available token usage and a milestone-matched final
JSON report. Missing/truncated/unknown/failure events stop. Reports never authorize
verification, completion or publication. Raw captures/reports remain private caller
data; `public_process` logs only exit/stop status and byte counts. Pattern/literal
redaction is tested, but arbitrary sensitive model text is omitted from public logs.

There is **no implemented credential-bearing live transport**. No auth file/token
was read, copied, mounted, refreshed or sent during M4 tests. Absence of credentials
in offline jobs does not satisfy the roadmap's real authentication-exposure test.
Resume command construction is unit-tested; actual inherited/overridden permissions
are unverified. See [the concrete probe plan](M4_CODEX_PROBE.md) before requesting
real-check authorization. A CLI sandbox label/help output is insufficient.

## Supervision and recovery

`supervise` runs an explicit trusted argument vector in a new process group with
bounded stdin/stdout/stderr and wall time. Cancellation, timeout and output overflow
terminate then kill the group; descendant-held pipes cannot hang indefinitely.
The container adapter separately observes container termination and cleans up on
an ordinary result. A nonzero project exit is a completed command, not success.

On interruption, the adapter best-effort kills the recorded container and retains
the pending intent even if kill succeeds. A host crash may leave it running. Close
and reopen a failed/poisoned store; read current revision and pending ID. Inspect
only its recorded `adr-m4-<UUID>` container by exact name, matching the operation
label, immutable image and checkout mount. Stop/remove only that confirmed owned
container. Preserve partial checkout changes and private diagnostics. Review the
observed state before explicitly resolving the original intent with evidence;
never infer that a missing container means the command never ran. No automatic
retry, checkpoint reconstruction, session recovery or effect reconciliation exists.
M5/M6/M7 remain future work.

Test cleanup separately verifies container identity/image and its live owned fixture
mount before removal. It runs before DisposableRoot cleanup. No operational state
namespace was created. Final evidence records container cleanup and preservation.
