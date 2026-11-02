# Operator recovery guide

Run the CLI in the foreground or tmux. Stop with Ctrl-C and let it exit; the runner
terminates its subprocess group and retains project files. After abrupt VM/process
loss, confirm the old runner and its children have stopped. A released lock alone
does not prove unsandboxed children have exited. Never run two checkout owners.

## Inspect before resuming

Use the same checkout, account and configuration. Read the CLI issue, PROGRESS.md
and `.git/ralph/setup.json` (setup) or `.git/ralph/checkpoint.json` (run). Captured
command failures leave `last-failure.stdout` and `last-failure.stderr`; invalid
model reports leave `last-report.json`. The checkpoint issue names these private
files. Do not publish raw captures. A hard exit may leave no new issue, so inspect
its phase and refs too. Use read-only Git commands when comparing local/remote refs.

Keep files, checkpoints and any `.tmp-*` metadata. Temporary metadata is ignored,
never adopted as state. Do not delete/edit a checkpoint to bypass a guard. No reset,
clean, rebase, force push, main reconciliation or merge is a recovery step.

## Setup recovery

```sh
/path/to/runner/.venv-dev/bin/agentic-runner setup --config /path/to/project.toml
```

| Setup phase | Preserved effects and next action |
| --- | --- |
| No checkpoint | Correct preflight and rerun. An interrupted Git init may already exist. |
| `preparing` | Git init, identity, private repo creation, origin, baseline or initial main push may have happened. Fix access/transport/plan issues and rerun the same setup; it reconciles the recorded baseline. |
| `switching` | Protection was checked; dev creation/switch/push may have happened. Rerun setup with unchanged config/files. |
| `complete` | Setup can rerun idempotently until a run checkpoint exists. Launch run explicitly. |

Main may already have its baseline published when protection fails. This is
incomplete setup. Enable the required private-repository plan/permissions and
rerun; no unprotected fallback exists. Strengthen incompatible protection manually
while preserving other requirements. Authentication must support both `gh api`
and Git transport. Probes never change account credentials or subscription plans.

Conflicting origins/branches, changed files/documents or unrelated HEAD require
review. Setup never fetches/reconciles another history. An existing run checkpoint
means use run recovery, not setup.

## Run recovery

```sh
/path/to/runner/.venv-dev/bin/agentic-runner run --config /path/to/project.toml
```

| Run phase | What a matching manual rerun does |
| --- | --- |
| No checkpoint | Requires clean prepared dev and matching remote dev. Correct preflight and rerun. |
| `implementing` | Retains partial edits and starts a **fresh** Codex session for the same unfinished milestone. Model interruption/lost response, blocked/invalid reports and failed/interrupted checks all return here. Checks run again after a successful report. |
| `publishing`, HEAD at `base` | Reconciles verified files and original/completed roadmap, stages identified paths, checks bytes/modes and commits the recorded tree. No new agent or verification runs. |
| `publishing`, HEAD advanced | Requires recorded tree, parent and message, plus exact commit ID when recorded. Checks clean files/main/protection and retries dev publication. Lost commit/push responses cannot skip publication or duplicate a milestone. |
| `complete` | Rechecks commit, clean files, controls, local/remote main, remote dev and protection, then selects the next milestone. All-complete reruns still perform these checks. |

Roadmap completion uses atomic replacement: an interrupted write leaves original
or completed text. Temporary bytes stay in `.git/ralph/`, outside publishable files.
Git's own `.lock` files after a kill can require manual inspection; confirm no live
process uses them before operator cleanup. The runner never removes them itself.

Blocked/failed work is never marked complete. Earlier milestones remain published.
Fix the documented blocker without changing checkpoint identity/controls, then
invoke run. Each successful attempt must update PROGRESS.md anew.

## Human review stops

Changed branch/config/controls/Git config, unrelated commits, agent-staged edits,
post-verification edits, or main/dev divergence cannot be accepted by checkpoint
surgery. Back up partial files/private evidence, compare with the recorded base,
tree and commit, then resolve the specific discrepancy manually. Restore matching
inputs only after deciding which edits are intended. Publication must retain its
verified bytes; editing them requires review and a deliberately prepared new run.
A failed non-fast-forward push keeps its commit local; do not force it through.

Rulesets-only protection is unsupported. Missing protection/permission evidence
stops new work/publication. Trusted unsandboxed code has VM-account access; this
is not hostile-code isolation. Process-exit tests do not prove power-loss recovery
on every filesystem. See [testing](TESTING.md) and [M3 evidence](evidence/MVP-M3.md).
