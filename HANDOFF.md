# Revised M3 complete — stop; no further milestone is planned

Read AGENTS.md, SPEC.md, ARCHITECTURE.md, ROADMAP.md and PROGRESS.md. The revised
M1–M3 roadmap governs work; all three milestones are complete. Historical plans and
retired prototype APIs do not govern current operation. No automatic merges,
scheduler, service, database or subagents. Never execute retired prototype scripts.

This session implemented only M3: recovery acceptance, selective live evidence,
retirement and operator instructions. Development branch is `mvp-runner`, based on
M2 `26312e0`; main is unchanged at `2f743da`. The checkpoint message is
`Complete revised M3: recovery acceptance and obsolete-path retirement`;
use `git log -1` for its ID. Do not push or merge this runner. Humans merge manually.
Stop after this development checkpoint. Further implementation needs a new
human-requested roadmap; no M4 is implied by historical documents.

## Current implementation

CLI exposes setup, run and retained read-only discover. Runtime dependencies are
empty. Setup alone establishes an initial main baseline/protection; routine run
only implements/verifies/commits/pushes the configured dev branch. Codex uses fresh
unsandboxed requested `gpt-6.1-sol`/high sessions with disabled multi-agent features
and no Git/GitHub authority. Partial implementation/check failures retain work and
resume in fresh sessions. Publication intent precedes completion/staging/commit.

M3 makes roadmap completion atomic, preserves permissions, rejects changes during
completion, requires exact already-recorded commit IDs and rechecks completed
publication before returning/selecting another milestone. Invalid model reports
are retained privately. Ctrl-C, lost responses and abrupt exits are covered by
owned disposable Git acceptance. See docs/RECOVERY.md for the phase-by-phase guide.

Root prototype/config/schema/skill, unused state/approval/container/native adapter
modules and obsolete tests/probes are retired. Useful supervisor/persistence/
discovery helpers and tests remain. Eight old contracts are archived under
`docs/history`; historical evidence remains with clear labels. Old sources can be
retrieved at `26312e0`, but must not be run against reference/operational directories.

## Validation and live limitations

PROGRESS.md and docs/evidence/MVP-M3.md record exact commands/results. Final suite
passed **115 tests, no skips, 55.000s** after editable reinstallation. Dependency,
CLI help and whitespace checks passed. Default tests consume no model/GitHub
account and use newly owned DisposableRoot repositories and local bare remotes.
They cover two milestones, blocked/resumed behavior, main guards, interruption and
lost responses with real local Git and fake Codex/GitHub.

A selective real Codex check passed after tightening the report contract: one
session, file/progress update, independent check, local dev commit/push, unchanged
main and a completed rerun without another session. Launch settings were requested;
server-side turn metadata was not separately audited. GitHub responses in that
check were fake. No full live Codex-plus-protected-GitHub pass is claimed.

The real private GitHub probe successfully created its generated repository and
published initial main, then stopped at protection HTTP 403 requiring a compatible
GitHub plan. Subsequent API reads confirmed private visibility and only main.
There was no dev publication or milestone execution on GitHub. Rulesets-only
protection remains unsupported. CI must be configured explicitly; no remote polling.

## Outstanding external cleanup

GitHub refused deletion of the exact generated private acceptance repository with
HTTP 403 despite reporting account admin permission. It remains for **manual
removal** through a credential/account that can delete repositories:

[ilancooke/agentic-runner-acceptance-037c65f152034afb9d9e28c9753a2245](https://github.com/ilancooke/agentic-runner-acceptance-037c65f152034afb9d9e28c9753a2245)

It contains only generated fixture docs/initial main. No existing remote project,
credential, visibility or subscription plan was changed. Do not rerun that probe
until private protection and deletion permissions are available; see testing and
M3 evidence for exact behavior. This is a documented environment/cleanup limitation,
not a passed live protection check. Local owned fixtures were disposed.

The pre-existing `.gitignore` addition of `tmp/` is preserved outside the checkpoint.
Tool-session filesystem restrictions are separate from runner unsandboxed execution;
development `.git` mutations may need tool escalation. No runner push/merge,
production/service changes or operational-state access occurred.
