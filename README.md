# Minimal Ralph development runner

A manually launched Python runner implements ROADMAP.md milestones using fresh
headless Codex sessions, independently verifies changes, and commits/pushes only to
the configured development branch. Humans merge main. No service, automatic merge,
subagents, database or scheduler. See [specification](SPEC.md),
[architecture and component review](ARCHITECTURE.md), [roadmap](ROADMAP.md), and
[current handoff](HANDOFF.md).

Revised M1 provides the loop for **already prepared, protected repositories**.
M2 will add separate one-time setup. M3 covers final recovery/live acceptance and
retirement of obsolete paths. The existing prototype and older library APIs are
preserved for now and are not invoked by run.

## Install and verify

Ubuntu, Python 3.12+, Git, authenticated `gh` and authenticated `codex` are expected.
Use a separate environment for runner development:

```sh
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install -e .
.venv-dev/bin/agentic-runner --help
.venv-dev/bin/python -m unittest discover -s tests -v
```

There are no Python runtime dependencies. Default tests use generated owned
fixtures, real local Git and fake Codex/GitHub responses; they consume no model or
GitHub account. The eight optional native/container checks keep their existing skips.
[Historical testing instructions](docs/TESTING.md) describe those checks.

## Run a prepared project

Copy [project.example.toml](project.example.toml) to a runner-owned location and set
`name` (GitHub owner/repository), `repository`, `development_branch` and `verification`.
Relative repository paths resolve from the config file. Verification is a nonempty
list of literal argv arrays, executed without a shell. Provision dependencies in
advance and use exact executable paths when needed.

The project must already have nonempty root AGENTS.md, SPEC.md, ARCHITECTURE.md,
ROADMAP.md and PROGRESS.md; a clean Git checkout on dev; matching local/remote main
baselines; an origin URL matching the configured GitHub name; a local GitHub noreply
identity; and dev HEAD matching its remote. The existing
[roadmap grammar](docs/DISCOVERY.md) defines the two-column progress table and
matching milestone deliverables/acceptance sections. Only the five root documents
are required by run; historical discover requirements are separate.

Main protection must require PRs, enforce administrators, have no PR bypass
allowances, and prohibit force pushes/deletions. The runner reads it before work
and publication and stops if unavailable. Rulesets alone are not currently
supported; a compatible branch-protection rule is required. Run never changes
protection or establishes main. M2 will automate setup separately.

```sh
.venv-dev/bin/agentic-runner run --config /path/to/project.toml
```

Codex runs directly as the trusted VM user, **without its sandbox**, using
`gpt-6.1-sol` and high effort. Each milestone gets a fresh session with the project
texts and explicit verification commands. Codex updates PROGRESS.md and reports;
the runner checks files/branch/HEAD, runs verification, marks completion, commits
and explicitly pushes dev. The loop continues until complete or blocked.

Run stays in the foreground; tmux can preserve it across SSH disconnects. Ctrl-C
stops and retains work. Verification runs in the existing native project environment;
there is no automatic remote CI polling. Add any required CI command explicitly.

## Failure and manual resume

Read the CLI issue, PROGRESS.md and `.git/ralph/checkpoint.json`. Fix the blocker
and rerun the same command. A matching partial checkpoint allows a dirty checkout
and starts a fresh session for the unfinished milestone. A recorded publication is
reconciled and pushed before starting the next one. Failed/uncertain work is never
reset, cleaned, rebased or force-pushed. Exit codes: 0 complete, 1 intervention,
2 usage error, 130 interrupted.

Branch, protected-document, config or unrelated-commit changes require human
review. Do not delete the checkpoint to bypass a guard, stage files manually during
an implementing checkpoint, or silently switch its configured identity. If the
runner stops before creating a checkpoint, correct preflight and rerun. When project
writes are unsafe, only the checkpoint records the failure.

The trusted VM/account is the execution boundary. Unsandboxed code can access that
account; runner checks and GitHub protection do not provide hostile-code isolation.
No main updates, merges, live publication of this runner or persistent services
were performed during M1 development.

`discover /path/to/checkout` remains available for read-only historical discovery.
Do not execute root prototype scripts or use the reference/operational directories
as test fixtures. Earlier plans are archived under [docs/history](docs/history/).
