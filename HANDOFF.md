# Revised M2 complete — stop; next session is M3 only

Read AGENTS.md, SPEC.md, ARCHITECTURE.md, ROADMAP.md and PROGRESS.md. The revised
three-milestone MVP governs work; historical plans/prototype do not. No automatic
merges, scheduling, services, database or agents. Never run root prototype scripts.

This session implemented only revised M2: separate one-time Git/GitHub setup.
M1/M2 are complete; M3 is unfinished. Do not begin M3 in this session. The development
branch remains `mvp-runner`, based on unchanged main `2f743da`. This checkpoint is
`Complete revised M2: separate safe Git and GitHub setup`; use `git log -1` for its
ID. Do not push this runner or merge. Humans merge manually.

## Current implementation

- `setup.py`: `Setup` validates documents/config and ordinary owned checkout,
  initializes absent Git, creates a private GitHub repo or connects a matching
  existing origin, and configures local authenticated-account noreply identity.
- Setup records identity/files/refs and a baseline commit before creating main's
  ref. Existing history must be clean; existing main and remote main must match.
  It never replaces a remote or existing branch history. Remote history without
  main and unrelated/detached branches require manual preparation.
- Setup writes absent main protection and reads it back before dev switch/push.
  PR review, administrators, empty bypass allowances and disabled force pushes /
  deletions are required. Existing compliant protection is left untouched, including
  stronger checks/review settings. Incompatible policies stop with instructions to
  strengthen them manually rather than risk replacing additional rules.
- `.git/ralph/setup.json` is private and atomic, distinct from run's checkpoint.
  Setup shares the repository lock. Reruns reconcile lost creation/commit/ref/push /
  protection/switch responses. Target document identity is recorded before switching
  to an existing descendant dev branch. A run checkpoint prevents further setup.
- `git_boundary.py`: shared Git commands, local config/origin checks and protection
  validation are reused by setup and run. Routine run never invokes setup writes.
- CLI supports `setup --config`, `run --config` and historical read-only `discover`.
  README and project.example.toml now document setup, plan/permission failures and
  manual setup continuation. Python runtime dependencies remain empty.

Existing M1 project/headless/loop behavior remains: explicit verification argv,
unsandboxed `gpt-6.1-sol` / high, disabled subagents, fresh sessions, independent
checks, runner-owned dev commits/pushes, main invariants and preserved failed work.
Old orchestration/container/state paths remain outside the MVP execution path;
retirement is M3. No prototype or operational state was used for tests.

## Evidence and limits

PROGRESS.md records installation, exact final test results and checks. New tests
use owned DisposableRoot directories, real local commits/bare-remote pushes and
fake GitHub/Codex. They exercise new/existing repositories, idempotency, identity,
stronger-protection preservation, origin/branch conflicts, permission/plan failures,
read-back failure, setup interruption/lost responses, and setup followed by run
with unchanged main. No live GitHub repository/protection was created or modified,
no real Codex session ran, and no push/merge/service deployment of this runner occurred.

GitHub authentication must also work for Git transport. Setup requires admin rights
and a plan supporting private-repository branch protection. If initial main is
published and protection fails, setup remains incomplete; fix access/plan and rerun
setup before run. Rulesets-only protection is unsupported. Setup never weakens an
existing policy; incompatible policies require a human to strengthen them while
preserving additional settings. Existing Git must be on main/dev; unborn Git must
be on main. Different local/remote baselines are not fetched/reconciled implicitly.

The VM/account is trusted and unsandboxed; this does not isolate malicious code.
Keep the reference checkout and `/home/ilan/agentic-runner-data` out of fixtures.
Tool-session filesystem restrictions are separate from runner Codex's unsandboxed
execution. Development `.git` mutations may need tool escalation.

## Next fresh session: M3 only

Audit agent/verification/completion/commit/push interruption and lost responses;
add focused recovery acceptance and a practical operator guide. Selectively run
real Codex and disposable protected GitHub acceptance when available, labeling
actual evidence and environmental limits. Retire obsolete prototype entry points,
unused orchestration/container/state code and obsolete tests/docs while preserving
useful helpers/tests and historical evidence. Finish new-operator instructions.
Run retained tests, update roadmap/progress/handoff, commit on dev, and stop.
