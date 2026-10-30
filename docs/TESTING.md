# Runner development tests

Use the setup and exact test command in [README.md](../README.md). Discover only
`tests/`; do not run root prototype scripts, project tests, or connectivity probes.
M1–M3 tests cover scaffold, discovery, approvals/state and generated fixtures only. They do not require
Docker, Codex, gh, network access, credentials or an operational environment.

Create fixture paths through an owned root:

```python
from tests.support.fixtures import FixtureFactory
from tests.support.isolation import DisposableRoot
from tests.support.fakes import FakeExternalAdapter

with DisposableRoot() as root:
    fixtures = FixtureFactory(root)
    repository = fixtures.repository()  # New empty Git repository, no remote.
    state = fixtures.state()            # Separate new directory, no legacy import.
    root.write_text(repository / "README.md", "Generated example\n")
    codex = FakeExternalAdapter(root, {"status": "complete"})
    report = codex.call("implement", repository)
```

The root is a newly allocated private directory under canonical `/tmp`, independent
of `TMPDIR`. An existing directory cannot be registered. Before mutations, guards
check the root's device/inode and canonical identity, resolve the entire target,
reject the root itself and anything outside it, and explicitly reject overlap
with the reference repository and operational state. Symlinks pointing within the
owned root are allowed; links or traversal escaping it are rejected, including
dangling links. Writes reject existing hard-linked files. Closed or replaced roots
are rejected. Cleanup removes only the allocated root using Python's temporary
directory lifecycle.

Git fixture initialization uses Git from the system default PATH, an empty template,
no hooks or global/system Git config, no remote and a private HOME. M2's
`tests/support/projects.py` adds guarded local commits/refs and linked worktrees
inside disposable roots. Its remotes use `example.invalid`; no transport is run.
All test subprocesses use a minimal
allowlisted environment from `FixtureFactory.environment()`, excluding inherited
Git variables, cloud/GitHub credentials and project tool settings. The CLI smoke
checks run the installed entry point with a disposable current directory.

`FakeExternalAdapter` supplies copied scripted results, injected exceptions, and
recorded operations; an unscripted call raises. It performs no external I/O and
rejects unsafe targets before recording/consuming a response. Named instances can
stand in for Codex, GitHub or container operations. This helper does not define
future production adapter contracts or simulate a complete runner lifecycle.

When extending the harness, guard every mutable target (repository, report,
state and subprocess cwd), use generated files only, and avoid arbitrary shell
execution. Add a dedicated constrained adapter for any new external effects.
Never enroll `/home/ilan/agentic-workspaces/milestone-test`,
`/home/ilan/agentic-runner-data`, another checkout or any user-selected existing path.

This is an accidental-targeting guard for trusted tests. It is not an OS sandbox,
does not eliminate check/use races against concurrent hostile filesystem changes,
and cannot constrain arbitrary Python code that bypasses the helpers. Container
security and hostile project execution belong to M4 and later boundary tests.

M2's discovery tests snapshot file bytes, modes and modification times, including
Git metadata, before and after preflight. Separate sentinels check that hooks,
fsmonitor, setup code and package test scripts never run. Fixtures cover Python,
web, non-main/default refs, linked worktrees, packed refs, instruction conflicts,
remote ambiguity and unsupported runtime/verification evidence. Roadmap tests use
in-memory Markdown strings; no reference checkout is an execution input. Discovery
performs static system Git reads only. See [the discovery contract](DISCOVERY.md).

M3's `tests/test_state.py` creates `StateBoundary.for_test(root, root.path / "state")`
inside a live DisposableRoot. State creation/writes re-check this capability, and
unowned repository targets are rejected before Git inspection. Do not use the
operational constructor to make temporary tests work. Namespace role markers used
for negative tests are generated fakes, not operational data.

State tests include deterministic persistence exceptions at nine checkpoints and
nine real child exits (`os._exit`) inside disposable workers. They also cover partial
appends/snapshot writes, interruption during initialization, stale/lost responses,
scope/configuration changes, process/alias/worktree lock contention and schema
diagnostics. Linux/POSIX `fork`/`flock` and local fsync/atomic-rename semantics are
required. No process performs a real agent/publication effect. See the
[state/approval contract](STATE.md) for the protocol and untested limits.
