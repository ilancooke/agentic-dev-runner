# Minimal Ralph runner architecture

This MVP supersedes the previous orchestration plan, preserved in docs/history.
ROADMAP.md and HANDOFF.md define implementation status and the session boundary.

## Component review

| Existing work | Decision |
| --- | --- |
| Python package, CLI, unittest suite | Retain; no runtime dependencies. |
| roadmap.py / markdown.py | Reuse deterministic ordered parsing. |
| supervisor.py | Reuse bounded subprocesses and process-group cleanup. |
| durable.py | Reuse atomic replacement/fsync for one checkpoint. |
| repository.py | Reuse local Git config inspection and ambiguity checks. |
| DisposableRoot / fixtures | Reuse generated repositories and private environments. |
| Native M4 findings | Retain no-sandbox execution and gpt-6.1-sol/high. |
| Discovery/runtime inference | Preserve discover; run uses explicit project config/checks. |
| Approval/event/state framework, binary pinning, exact-session resume | Remove from MVP path; reconstruct fresh sessions from files. |
| Container/nested sandbox adapters | Remove from MVP path; project checks may use Docker. |
| Root prototype scripts/config/schema/skill | Retired in M3; preserve history/evidence, never invoke. |
| PR/merge, CI repair, main reconciliation, scheduler, systemd | Remove from plan. |

M3 retired unused approval/state/native/container adapters, their tests/probes and
prototype entry points. Useful supervisor/persistence/discovery tests remain.
No run code imports the retired framework. Runtime dependencies remain empty.

## Commands and configuration

`agentic-runner run --config /path/to/project.toml` runs in the foreground. Use tmux
to outlive SSH. TOML selects one project and explicit nonempty verification argv
lists, without shell inference. Paths resolve relative to config. M1 requires an
already prepared checkout, local noreply identity, origin, main and dev branches,
and enforceable GitHub protection. M2 provides the separate `setup` command; run never
performs setup implicitly. No daemon or automatic approval workflow is introduced.

Setup reuses config/document validation, Git command/config guards, file inventory,
the repository lock and atomic checkpoint I/O. `.git/ralph/setup.json` records its
identity, original files/refs, baseline commit and switch intent separately from run.
New Git checkouts receive one initial main commit; existing history must be clean.
An initial commit object is recorded before creating its main ref, so lost responses
can be reconciled without adopting unrelated commits. Existing origins/refs are
validated and never replaced. Only setup may publish an absent main baseline.

Authenticated GitHub account metadata supplies a repository-local noreply identity.
The named repo is queried before private creation; HTTP/auth/transport failures do
not imply absence. Setup requires admin permission, writes missing main protection,
reads it back, then creates/switches/publishes dev. Existing compatible protection
is read-only, preserving stronger options; incompatible policies require manual
strengthening instead of replacement. Missing plan/permission support stops setup
and leaves its effects for manual rerun. Setup refuses an existing run checkpoint.

## Loop and Git boundary

Select the first unfinished milestone using the existing parser. Supply the five
documents and selected milestone to a fresh unsandboxed `codex exec`. Its strict
report contains milestone, status (`success`, `blocked`, `failed`), summary, blockers
and proposed commit message. Success requires no blockers and a PROGRESS.md update.
Report claims never replace independent verification commands.

The runner checks configured dev branch and unchanged HEAD before/after execution,
unchanged local/remote main refs, unambiguous matching origin and unchanged controls
(AGENTS/SPEC/ARCHITECTURE/ROADMAP/config). It inventories files, rejects symlinks,
submodules and agent-staged changes, and requires verification to leave the proposed
files unchanged. Ignored build artifacts are excluded from publication.

After verification the runner alone marks completion, stages identified paths,
commits and confirms the exact staged tree. Hooks are disabled for runner Git
commands. Push uses the validated URL and explicit `HEAD:refs/heads/<dev>` refspec,
without force. Branch/protection checks precede publication. No code path merges.

Protection reads GitHub's branch-protection API: PR requirement, administrators
included, no PR bypasses, no force pushes/deletions. Missing permissions, unavailable
protection or incompatible policy stops before Codex. This enforcement plus runner
checks is independent of prompts. Trusted unsandboxed code still has account access;
the design does not claim to make malicious account code incapable of Git operations
or owner permission changes. Violations stop execution without destructive rollback.

## Failure and recovery

An exclusive repository lock prevents concurrent runs. One private atomic checkpoint
in `.git/ralph/` records milestone, initial HEAD/main/config/control identity, phase,
report and publication evidence. It is separate from all legacy operational state.
No journal framework, database or automatic state import is needed.

Before publication, failure retains partial files and records an issue in the
checkpoint and, when safely on dev, PROGRESS.md. A matching manual rerun starts a
fresh session for that same milestone. Arbitrary dirty starts, changed controls,
branch or unrelated commits require intervention. Publication intent precedes
atomic roadmap completion/staging/commit; temporary completion bytes stay in
private Git metadata outside the publishable inventory. Manual rerun reconciles the
exact recorded tree/commit and retries dev push before starting another task. Divergence stops. Never reset,
rebase, clean, force push or adopt unrelated commits. Once recorded, a commit ID
cannot be replaced by another commit with the same tree/parent/message. Completed
reruns recheck commit, files, controls, main/dev refs and protection even when the
roadmap is entirely complete. Invalid model reports stay in private metadata.

## Testing and limits

Owned disposable repositories exercise real commits/pushes to local bare remotes,
with fake Codex/GitHub responses. Test multi-milestone completion, main guards,
failed reports/checks, partial work and abrupt process loss across publication and
atomic-write boundaries. Live-account evidence is distinct and recorded in
docs/evidence/MVP-M3.md; docs/RECOVERY.md documents operator continuation.
Checks use the existing native project environment; provisioning belongs to the operator. Remote CI is not polled by MVP;
any required CI verification must be explicitly configured.

Launch flags were checked against the installed CLI and
[official non-interactive documentation](https://learn.chatgpt.com/docs/non-interactive-mode).
Protection fields follow [GitHub's API](https://docs.github.com/en/rest/branches/branch-protection).
