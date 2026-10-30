# Agentic development runner

M1–M3 provide a Python package, discovery, approval records, durable state and an
isolated fixture harness. M4 adds supervised execution for a single-user dedicated VM:
Codex runs directly **without its sandbox**, and trusted dependency/build/test and
Docker commands run as the VM development account. See the
[accepted decision](docs/TRUSTED_VM_DECISION.md), [execution contract](docs/EXECUTION.md),
[roadmap](ROADMAP.md) and [handoff](HANDOFF.md). M1–M4 are complete as library APIs;
the full autonomous workflow and operational CLI remain later milestones.

Use Python 3.12 or newer and Git. Create a **separate** runner development environment;
leave the prototype's `.venv` and project environments alone:

```bash
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install -e .
.venv-dev/bin/agentic-runner --help
.venv-dev/bin/agentic-runner --version
.venv-dev/bin/python -m agentic_runner --version
.venv-dev/bin/python -m unittest discover -s tests -v
```

Inspect a checkout without running project code or contacting its remote:

```bash
.venv-dev/bin/agentic-runner discover /path/to/checkout
```

The command prints JSON with repository/default-branch evidence, the selected
milestone, runtime/check declarations and source hashes, or an actionable diagnostic
with no partial selection. Read the [discovery contract](docs/DISCOVERY.md) for the
supported roadmap grammar, evidence rules, conservative runtime policy and limits.
No per-project runner configuration file is required.

M3 adds library APIs for explicit start authorization, canonical repository locking,
atomic state, append-only events, pending intent and scope invalidation. Read the
[state/approval contract](docs/STATE.md) for permitted progress edits and recovery.
The CLI remains read-only; operational start/service wiring is planned for M9.

Run setup and tests from this directory. Installation needs setuptools >=68 from
the configured package index (or a pre-provisioned wheel source). Setuptools is
the only build dependency; the package and tests have no third-party runtime
dependencies. `unittest` is part of Python. No activation or global installation
is necessary. The installed console script and module use the same entry point.
With no arguments the CLI prints help. Unknown commands, including `start`, fail
with exit code 2. Help/version do not load project/state data or launch tools.
Discovery performs fixed read-only Git queries and reads documents; it never loads
legacy `config.yaml`, invokes the prototype, executes project code, or writes state.

## Verification

```sh
.venv-dev/bin/python -m unittest discover -s tests -v
```

The root Python scripts, `config.yaml`, `schemas/`, and `skills/` are the preserved
prototype. **Do not run them for development verification**: they target existing
repositories, operational state, Codex, and GitHub. Read the
[prototype inventory](docs/PROTOTYPE.md) before investigating them.

Tests generate new roots under `/tmp/agentic-runner-test-*`, with private repository,
state, HOME and temporary directories. Roots are created by `DisposableRoot`,
never supplied or adopted by a caller. Fixture mutations and fake adapter calls
must go through that root's guard. Use [the harness guide](docs/TESTING.md) when
adding tests. These guards prevent accidental test targeting; they do not sandbox trusted project
code. The default suite is account-free. See [TESTING.md](docs/TESTING.md) for the
native Python/Node integrations and the separately selected real Codex/Docker probe.

A disposable real Codex task and exact-ID resume passed with `gpt-6.1-sol`, high
reasoning effort, no sandbox and approval policy never. A generated Docker application
also passed build/run/testing through the host engine. See [M4 evidence](docs/evidence/M4-NATIVE.md).
No persistent service, production deployment or runner publication was performed.
Discovery remains read-only and does not invoke a model.
