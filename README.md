# Agentic development runner

M1–M3 provide a Python package, read-only discovery, approval records, durable run
state and an isolated test harness. Execution is not implemented yet. See
[ROADMAP.md](ROADMAP.md) for scope and [HANDOFF.md](HANDOFF.md) for the next session.

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
adding tests. These guards prevent accidental test targeting; they do not provide
the container security boundary planned for M4.

No persistent service, production execution, real Codex call, or GitHub publication
is part of M1–M3. The requested GPT-6.1-Sol/high configuration remains an M4
capability check; discovery does not select or invoke a model.
