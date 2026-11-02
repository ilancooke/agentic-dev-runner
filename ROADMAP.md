# Minimal Ralph runner roadmap

This supersedes historical M1–M10. IDs below refer to the revised MVP. Implement
one milestone per fresh development session; test, update progress/handoff, commit
on dev, then stop. No automatic merges.

## Milestone Progress

| Milestone | Status |
| --- | --- |
| M1 | complete |
| M2 | complete |
| M3 | complete |

## M1 — Working loop for a prepared protected repository

### Deliverables

- Review existing code/tests; replace the architecture/roadmap with the MVP,
  reuse tested helpers and preserve historical plans.
- Package-level TOML config, required-document validation, strict structured
  reports and a manual run command for an already prepared protected repository.
- Fresh unsandboxed Codex sessions, independent verification, completion, commit
  and explicit dev-branch push; main/branch/HEAD/document/file checks.
- Exclusive lock, small failure checkpoint and manual continuation, including
  an interrupted push. Preserve all partial implementation work.

### Acceptance criteria

- Disposable integration tests execute two milestones through real Git commits
  and pushes to a bare remote with fake Codex/GitHub; main remains unchanged.
- Invalid reports, agent Git/control edits, unsafe files, branch/protection failures
  and failed/mutating checks cannot publish or begin the next milestone.
- Failed work survives and a fresh manual attempt resumes the same milestone.
  An unpushed commit cannot be skipped or mistaken for published completion.
- CLI and existing useful tests pass without accounts. Record exact checks and
  limitations, commit on dev, and stop this session.

## M2 — Separate one-time Git and GitHub setup

### Deliverables

- Add setup using the same config and document preflight: initialize Git when
  absent; create a private GitHub repo or connect an existing matching origin.
- Configure repository-local GitHub noreply identity from the authenticated account.
- Establish initial main baseline, enforce/read back protection including admins
  and no bypasses, then create or safely switch to the configured dev branch.
- Keep baseline/protection writes out of routine run; never replace conflicts.

### Acceptance criteria

- Account-free tests cover new/existing repos, idempotency, mismatched origins,
  conflicting branches and interrupted setup, preserving existing history.
- Protection failures cannot fall back to unprotected execution or weaken existing
  rules; plan/permission limitations produce actionable diagnostics.
- Setup followed by run passes disposable integration. Update instructions,
  progress/handoff, commit on dev, and stop the session.

## M3 — Recovery acceptance, live evidence and retirement

### Deliverables

- Audit agent/verification/completion/commit/push interruption and lost responses
  with focused tests and a practical operator recovery guide.
- Selective real Codex and disposable protected GitHub acceptance when available;
  label actual evidence and environment limitations.
- Retire obsolete prototype entry points and unused orchestration/container/state
  paths and obsolete tests/docs; preserve useful tests and historical evidence.
- Finish installation/setup/run/resume instructions for a new operator.

### Acceptance criteria

- Multi-milestone acceptance demonstrates complete/blocked/resumed behavior,
  explicit dev publication and unchanged main. Distinguish fake/live evidence.
- No runtime/CLI path merges, updates main during run, starts a service, schedules
  retries or spawns agents. No dead MVP dependencies or stale active instructions.
- Retained tests pass; update progress/handoff, commit on dev and stop. Unavailable
  live checks are recorded as limitations, never claimed as passes.
