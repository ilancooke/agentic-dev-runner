# Minimal Ralph development runner

A manually launched Python runner implements ROADMAP.md milestones using fresh
headless Codex sessions, independently verifies changes, and commits/pushes only to
the configured development branch. Humans merge main. No service, automatic merge,
subagents, database or scheduler. See [specification](SPEC.md),
[architecture and component review](ARCHITECTURE.md), [roadmap](ROADMAP.md), and
[current handoff](HANDOFF.md).

Revised M1 provides the loop; M2 adds separate one-time Git/GitHub setup.
M3 covers final recovery/live acceptance and
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

## Configure and set up a project

Copy [project.example.toml](project.example.toml) to a runner-owned location and set
`name` (GitHub owner/repository), `repository`, `development_branch` and `verification`.
Relative repository paths resolve from the config file. Verification is a nonempty
list of literal argv arrays, executed without a shell. Provision dependencies in
advance and use exact executable paths when needed.

Create nonempty root AGENTS.md, SPEC.md, ARCHITECTURE.md, ROADMAP.md and PROGRESS.md
in the project directory. For a new project, setup initializes Git and commits all
unignored files as the initial main baseline; review files and `.gitignore` first.
Keep the runner config outside the checkout when practical. With existing history,
setup requires a clean checkout on main or the configured dev branch; commit intended
document changes yourself before setup. Other branches, detached HEAD, worktrees,
ambiguous origins and conflicting histories require manual resolution.

```sh
.venv-dev/bin/agentic-runner setup --config /path/to/project.toml
```

Setup creates a **private** GitHub repository when origin and the named repository
are absent, or connects an existing matching repository. It never replaces an
origin, changes repository visibility, or replaces existing branch history. It
sets only repository-local identity to the authenticated GitHub login and
`ID+LOGIN@users.noreply.github.com`. Authentication must also support Git transport;
for HTTPS, configure `gh auth setup-git` or your chosen credential helper beforehand.

Setup establishes local/remote main only when missing, requiring an identical
baseline when both exist. An existing remote with history but no main must be
prepared manually. Existing dev must descend from main; its remote must match it.
After protecting main, setup creates or switches to dev and publishes its initial
ref explicitly. Setup does not launch Codex or verification; launch run separately.

Creating protection requires repository administration rights and a GitHub plan
that supports protection for that repository. Private repositories require a
compatible paid plan. Setup creates missing protection with PR review required,
administrators included, empty bypass allowances and force pushes/deletions
disabled. It reads protection back before dev publication. Existing compliant
protection, including additional checks/review rules, is left untouched. An
incompatible existing policy stops setup: strengthen it manually while preserving
other rules, then rerun. See [GitHub protection permissions and plan support](https://docs.github.com/en/rest/branches/branch-protection).

An interruption or permission/plan failure preserves files, refs and
`.git/ralph/setup.json`. Fix the issue and rerun the same setup command; it reconciles
its recorded baseline and publication without duplicate reachable commits. It may
have published the initial main before protection fails; this is incomplete setup,
and run must wait for successful protection. Do not delete setup state to bypass
changed-file/config/document/branch guards. Setup shares the run lock and refuses
to operate after a run checkpoint exists; use run recovery then.

## Run a prepared project

Run requires a clean Git checkout on dev; matching local/remote main
baselines; an origin URL matching the configured GitHub name; a local GitHub noreply
identity; and dev HEAD matching its remote. The existing
[roadmap grammar](docs/DISCOVERY.md) defines the two-column progress table and
matching milestone deliverables/acceptance sections. Only the five root documents
are required by run; historical discover requirements are separate.

Main protection must require PRs, enforce administrators, have no PR bypass
allowances, and prohibit force pushes/deletions. The runner reads it before work
and publication and stops if unavailable. Rulesets alone are not currently
supported; a compatible branch-protection rule is required. Run never changes
protection or establishes main. Only the separate setup command performs those writes.

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
Development acceptance uses local bare remotes and fake GitHub/Codex; live protected
GitHub and Codex acceptance remains M3 work. This runner has not been pushed or merged.

`discover /path/to/checkout` remains available for read-only historical discovery.
Do not execute root prototype scripts or use the reference/operational directories
as test fixtures. Earlier plans are archived under [docs/history](docs/history/).
