# Revised M1 complete — stop; next session is M2 only

The user's current request supersedes the previous orchestration design. Read
AGENTS.md, SPEC.md, ARCHITECTURE.md, ROADMAP.md and PROGRESS.md. The former handoff,
architecture and roadmap are archived in docs/history for context only. Do not
resume historical M5 or reintroduce automatic merges, scheduling, services or agents.

This session implemented only revised M1: a working sequential CLI loop for an
already prepared protected project. M2/M3 are unfinished. Do not begin M2 within
this session. The development branch is `mvp-runner`, created from clean main
`2f743da`. The checkpoint commit is titled `Complete revised M1: minimal verified development loop`;
use `git log -1` for its ID. Do not push this runner or merge.

## Current paths

- `project.py`: explicit stdlib TOML config, five required root documents.
- `headless.py`: fresh structured `codex exec`, no sandbox, gpt-6.1-sol/high,
  both multi-agent feature flags disabled; no exact-session resume or fallback.
- `git_boundary.py`: matching origin, local noreply identity, explicit branch checks,
  GitHub main-protection reads, file inventory, literal Git operations and dev push.
- `runner.py`: selection, independent verification, completion, controlled commit,
  push, lock and one atomic checkpoint under `.git/ralph/`.
- CLI now supports `run --config` alongside historical read-only `discover`.
  `project.example.toml` shows configuration. `setup` intentionally does not exist yet.

Reused roadmap/Markdown parsing, supervisor, DurableIO, Repository config inspection,
DisposableRoot and fixture helpers. Old approval/run-state/container paths are not
imported by the new execution path; preserve them until deliberate M3 retirement.
Never run root prototype scripts; their hardcoded targets/automatic merging remain
unsafe for development verification.

## Evidence and limitations

PROGRESS.md records exact final validation. Default tests require no accounts; new
integration tests perform real local commits/pushes with fake Codex/GitHub. Installed
CLI flags/features were inspected, but no real model call or GitHub publication /
protection change was performed. Existing M4 live findings remain historical evidence,
not a live acceptance claim for this new loop. No services were installed.

Run requires a clean dev branch matching its remote, matching local/remote main,
root documents, unambiguous GitHub origin, local noreply identity and compatible
branch-protection evidence. On failure it retains files/checkpoint; on manual rerun
it resumes implementation or reconciles the recorded commit/push before another task.
Unsafe branch/config/control changes and unrelated commits stop for human review.
There is no reset/clean/rebase/force push or automatic merge. Captured failing command
output is private in `.git/ralph/last-failure.stdout` and `last-failure.stderr`.

The trusted Ubuntu VM is the execution boundary; do not add a Codex sandbox or claim
hostile-code isolation. Runtime checks and GitHub protection are independent of
prompts, but unsandboxed trusted-account code retains that account's privileges.
Rulesets-only protection and remote CI polling are outside current support.

## Next fresh session: M2 only

Implement the separate setup command from revised ROADMAP.md. Reuse the project
configuration and Git boundary; keep main initialization/protection writes out of
run. Cover new/existing repositories, local GitHub noreply identity, private origin
creation/connection, main baseline and read-back protection, safe dev branch switch,
idempotency/conflicts and interrupted setup. Never silently overwrite a remote or
branch or weaken protection. Missing GitHub plan/permission support is a clear blocker.
Then run tests, update roadmap/progress/handoff, commit on dev and stop.

Use generated owned fixtures. `/home/ilan/agentic-workspaces/milestone-test` stays
read-only; `/home/ilan/agentic-runner-data` remains operational state, never a fixture.
Standing authorization for necessary disposable tests persists. Managed tool-session
filesystem permissions still apply: `.git` writes in this session required escalation
because its mount is read-only inside the tool sandbox. That is separate from the
runner's explicitly unsandboxed Codex launch.
