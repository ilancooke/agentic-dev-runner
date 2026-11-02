> Historical pre-MVP document. Its APIs and commands were retired in revised M3.
> Use the root README and docs/RECOVERY.md for current operation.

# Approval and durable state contract (M3, M4 policy extension)

## Current M4 execution-policy revision

The user explicitly requested **no Codex sandbox**, with the dedicated trusted VM
as the boundary. Native execution now requires policy v4 / execution-record v2,
recording `codex_sandbox: disabled`, account homes, binary hash and process limits.
Fresh and resumed launches use `--dangerously-bypass-approvals-and-sandbox` with
approval policy never. Policy v1 (control), v2 (container) and v3 (earlier sandboxed
native prototype) remain readable and cannot silently authorize v4 execution.
Changing policies requires explicit renewed committed authorization. Run, snapshot,
approval, identity and event schemas remain v1; no publication phases were added.
The older M3/container-specific descriptions below retain their historical context;
see [current execution](EXECUTION.md) and [the accepted decision](TRUSTED_VM_DECISION.md).


M3 supplies a library control/persistence layer. The installed CLI still offers
help, version and read-only discovery. `start_run()` below records explicit start
authorization; it does not launch an agent, create a branch, verify code, publish,
install a service or schedule later work. Operational CLI/service wiring is M9.
No real operational namespace was initialized during M3 development.

## Control API

Use a dedicated new private state directory, outside the checkout and Git metadata.
An operational caller explicitly chooses its namespace; there is no legacy/default
state import or automatic migration:

```python
from pathlib import Path
from agentic_runner.state import open_store
from agentic_runner.state_boundary import StateBoundary

# Illustrative operator API; do not run against reference/production test targets.
boundary = StateBoundary(Path("/chosen/private/runner-state-v1"))
with open_store(Path("/chosen/checkout"), boundary) as store:
    state = store.start_run()  # Explicit authorization of the current committed scope.
```

The parent of the state root must already exist. A new root is created with mode
0700; existing roots must have that mode and belong to the current UID. Files are
created with mode 0600. A nonempty directory without the namespace marker is
rejected (orphan `.tmp-*` files from interrupted initialization are retained and
ignored). State must not overlap the worktree/common/private Git directories.
Reference and legacy operational roots, including canonical aliases and ancestors,
are denied. Operational roots/checkouts cannot be in `/tmp` or named disposable
test directories. Namespace markers explicitly distinguish operational/test roles.

Tests use `StateBoundary.for_test(disposable_root, path)` with a **live owned M1
DisposableRoot capability**. Both repository and state paths must be descendants
of that root. They are checked before Git inspection and every state mutation;
an existing arbitrary directory cannot be adopted as a test root. Fake operational
markers used in boundary tests are generated in owned roots, never copied from
an operational environment. Do not expose the test constructor in an operational CLI.

`open_store()` holds cooperating-process locks for its context and closes handles
on exit. `load()` returns a copied current state; `history()` returns copied events.
Neither method authorizes an effect. Mutating requests require the exact integer
`revision` just observed, so a stale request cannot overwrite newer state or
silently reissue an uncertain operation. Reusing a closed/failed-write handle fails.

## Identity and locking

Version-one namespace identity records a UUID, environment role, canonical state
root and (for tests) disposable root. Copying a namespace to another path or role
is rejected. Project identity uses M2's canonical common Git directory plus remote
URL; the binding also records common-directory device/inode, checkout path/inode,
remote identity and namespace UUID. A binding lookup is keyed by common-directory
device/inode. Checkout moves, replacement, changed remotes and cross-project state
copies require explicit future migration; they are never silently adopted.

Repository ownership uses nonblocking POSIX `flock` on an open **common Git directory
inode**, not a lock filename under a user-selected state root. Path aliases, linked
worktrees and different state roots therefore contend for the same repository
lock, even when the remote identity changes. Lock acquisition does not write Git
metadata. A namespace directory lock additionally serializes state access. Locks
are acquired repository first, namespace second; contention diagnoses `state.locked`
instead of waiting indefinitely. Kernel descriptor cleanup releases them after
process termination. Linked worktrees contend for ownership; an existing run stays
bound to its original checkout rather than moving to another worktree implicitly.

These are Linux/POSIX cooperating-runner locks, not protection against a process
that ignores the API or an administrator changing mounts/files concurrently.

## What start authorizes

New starts require the local default-branch checkout, a committed HEAD, an index
equal to its tree, matching raw worktree bytes/modes and no untracked files according
to Git's standard ignore rules. Only fixed Git reads are used: tree/index inventory,
raw object sizes/blobs and HEAD/ref reads. No filter, textconv, hook, pager, project
script, network operation or publication occurs. Committed symlinks/submodules and
files over 1 MiB are diagnosed. Cleanliness inspection is capped at 20000 files.
CRLF/filter normalization is not executed to make an otherwise dirty start pass.

The approval record retains the exact authorized commit and **committed blob OIDs,
SHA-256 hashes and base64 bytes** for the roadmap and protected local requirements.
Captured bytes are compared to raw committed objects before authorization is
persisted. Repeated source reads must agree. Ancestor AGENTS files outside the
worktree are captured separately as supplementary path/hash/bytes attestations,
explicitly marked uncommitted; changes to them invalidate authorization too.
They are not represented as part of the project commit.

M2's complete document/runtime/CI inventory forms the initial protected scope,
with exactly these exceptions:

- In `ROADMAP.md`, only status-cell values in the validated progress table are
  masked for scope comparison. IDs, row order, titles, all requirement text,
  surrounding context and formatting remain protected. Updated status values must
  still satisfy the M2 grammar. Status edits never advance run phase or milestone.
- Unreferenced `HANDOFF.md`, `CHECKPOINT.md` and `.md` files below `docs/evidence/`
  may be added/edited/deleted as non-authoritative evidence. They cannot override
  scope or verification. An AGENTS file is **always protected**, including below
  evidence directories. Runtime/Verification declarations make an evidence file
  protected as well.
- Any local link from protected material to an evidence file makes that entire
  file and its transitive local references protected. There is no filename-based
  exemption for referenced requirements. Newly discovered ordinary documentation,
  instructions, metadata, CI or linked artifacts change the protected file set.

Approval closure also captures local inline image/assets and Markdown references
that discovery's informational inventory omits. Their committed bytes are protected;
external assets fail approval rather than remaining mutable uncaptured requirements.

All other protected files are compared byte-for-byte. New evidence links introducing
additional discovered source files also change that set and need renewed approval.
This conservative rule preserves ordinary Markdown requirements without deciding
which prose is important. It can protect a source-code file if requirements link to
it; changing such a file requires renewed approval. It does not authorize edits to
acceptance criteria merely because a model calls them progress/evidence changes.

External links are not fetched or silently approved. M3 start refuses them until
requirements are captured as committed local files. This applies conservatively
to all links in the discovery closure; distinguishing informational external links
needs an explicit future policy. Unstructured instruction prose remains human/agent
review context and is hashed, not semantically reconciled by this scanner.

Execution configuration is captured alongside the scope: versioned global policy,
requested GPT-6.1-Sol/high, repair budget (2), concurrency, discovered runtime and
literal verification declarations. Native M4 verified CLI `gpt-6.1-sol` and high in
real fresh/resumed turn contexts. Configuration changes invalidate authorization.

M4 keeps namespace, identity, approval, event, snapshot and run schemas at v1.
Publication/completion phases and new root boolean gates were not added.
Execution policy versions are validated explicitly:

| Policy | Meaning |
| --- | --- |
| v1 | Original M3 control/scope approval; no execution authority. |
| v2 | Preserved container adapter, pinned image and constrained boundary. |
| v3 | Earlier sandboxed-native prototype, readable but not launchable by the current native adapter. |
| v4 | Current trusted-VM native execution with sandbox disabled, explicit homes/binary hash/process limits (execution record v2). |

Native callers explicitly supply
`RunnerPolicy(execution=NativePolicy(home=..., codex_home=...).record())` when opening
a store. Existing approvals are not upgraded. Changing versions/settings invalidates
the old scope/configuration authorization and requires explicit committed renewal.
Old readers reject versions they do not know. No automatic namespace/history
migration is implemented. Default M3 control APIs still emit policy v1.

Native commands use existing implement/verify intents. Details record execution
version 2, mode, exact policy, command/input hashes and safe adapter metadata before
launch. Codex validation retains confirmed session ID/model/effort/available usage
and a report hash, while omitting prompts, summaries and raw stdout/stderr from
public events. Private process diagnostics are attached to native Codex exceptions.
A completed command/report never changes phase or grants publication authority.
Interrupted/uncertain execution retains its original pending ID until explicitly
reconciled. See [EXECUTION.md](EXECUTION.md) for recovery and limits.

`check_authorization(revision)` compares current scope/configuration, repository,
checkout, remote/default branch and ancestry of the approved commit. Failure
durably enters `approval_required`, preserving the old approval, run ID and any
pending operation. Protected files are not modified by invalidation. `load()` is
inspection only; future effect adapters must check authorization before acting.

Explicit `renew_approval(revision)` captures a new committed approval for the same
run/milestone after pending effects are reconciled. M3 renewal conservatively uses
the same clean/default-branch requirements as start. It cannot silently skip to
another milestone. The journal retains the original approval and every renewal;
restoring old files alone does not erase an invalidation or resume execution.

## Explicit phases and pending operations

The complete M3 transition table is:

| Current phase | Supported control action/result |
| --- | --- |
| none | Explicit start creates `approved`. |
| approved | Transition to `implementing`, `paused` or `failed`. |
| implementing | Transition to `verification_pending`, `paused` or `failed`. |
| verification_pending | Transition to `implementing`, `paused` or `failed`. |
| paused | Explicit resume restores the recorded prior phase, after scope check and pending reconciliation. |
| approval_required | Explicit renewal returns to `approved`, after committed scope review and pending reconciliation. |
| failed | Terminal in M3; later failure recovery is not implemented here. |

Scope invalidation can enter `approval_required` from any non-failed phase.
`verification_pending` means checks are needed, not that verification succeeded.
Publication/merge/completion phases are **unrepresentable** in schema v1; later
milestones must introduce their verified gates with an explicit schema decision.
Unknown phases, root-level flags, schema versions and implicit migrations fail.
No `checks_passed`, `auto_merge` or other boolean combination grants publication.

`begin_operation(revision, kind, details)` records one durable intent with a UUID,
project/run identity and expected approved commit **before** the future caller may
perform an external effect. M3 supports `branch` in approved/implementing,
`implement` in implementing, and `verify` in verification_pending. It performs none
of them. New intents and ordinary phase changes are blocked while intent is
pending. Pause retains intent; resume waits for reconciliation.

`resolve_operation(revision, id, outcome, evidence)` requires the exact pending ID,
nonempty evidence and outcome `confirmed`, `not_applied`, or `unknown`. The first
two clear intent and retain reconciliation evidence in the journal; `unknown`
retains it as uncertain. Resolution never changes phase or creates publication
permission. An invalidated/paused run may reconcile an already issued effect.
M6 must supply trustworthy operation-specific observations; this generic record
layer does not prove caller-supplied reconciliation evidence or retry effects.

## Disk protocol and recovery

The namespace contains `namespace.json`, inode-keyed binding JSON files and one
directory per project ID. Each project holds:

- `events.jsonl`: append-only authoritative events with version, sequence, UUID,
  UTC timestamp, kind, previous-event hash, full next state, details and SHA-256.
- `state.json`: atomic materialized snapshot, linked to an exact complete event.
- Possible `.tmp-*` remnants: retained non-authoritative interrupted snapshot files.

For each mutation, validate schema/transition and expected revision; append one
complete newline-terminated event with `O_APPEND`; write all bytes; fsync the file
and project directory; then write a unique exclusive temporary snapshot, fsync it,
atomically replace `state.json` and fsync the parent. Directory creation and
namespace/binding writes synchronize their containing directories too. Reopening
also syncs namespace/project directory entries left by interrupted initialization.
Symlink/hard-linked state files are refused. Every write uses the namespace guard.

Recovery checks the **entire** versioned sequence, hash chain, schemas, run identity
and transition history. A valid lagging/missing snapshot is reconstructed only from
complete journal events, after re-syncing the event file and directory. A complete
event with a lost response is adopted once; stale control requests then fail, and
retained intent must be reconciled rather than reissued. A persistence exception
poisons the handle; close/reopen before any further action.

An incomplete trailing event, malformed/hash-mismatched history, incompatible
version, or snapshot not equal to a known event causes a diagnostic. There is no
automatic truncation, destructive cleanup, legacy import or history deletion.
The last complete snapshot remains evidence. Preserve both files and pause for
reviewed offline repair/migration; no repair command is implemented in M3.

The journal is capped below the 64 MiB read limit, individual events at 8 MiB and
captured approvals at 4 MiB. Exhaustion stops before append. Explicit archival and
long-term retention management are future operational work. Hash chains detect
corruption; they are not signatures against a privileged writer rewriting history.
Captured requirement text/evidence is private state, not a public log payload.

Tests exercise write failures and real disposable child-process termination at
all nine journal/snapshot checkpoints, partial writes, interrupted initialization,
lost responses, sync ordering and kernel lock release. These are local filesystem
tests, not power-loss/VM reboot/service or container security demonstrations.
