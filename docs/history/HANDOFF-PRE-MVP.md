# M4 complete — stop here; next milestone is M5

M1–M4 are complete. M5–M10 remain unimplemented. Do not begin M5 in this session.
The user explicitly chose **NO Codex sandbox**; the dedicated development VM is
its boundary. Read [ROADMAP.md](ROADMAP-PRE-MVP.md), [the accepted decision](TRUSTED_VM_DECISION.md),
[execution](EXECUTION.md), [M4 evidence](../evidence/M4-NATIVE.md),
[state](STATE.md), [testing](../TESTING.md), architecture and discovery.

## Purpose and agreed authority

Automate the user's existing workflow after interactive Q&A and roadmap approval:
a fresh Codex session implements the next milestone, then tests, controlled GitHub
publication/CI/merge, handoff and the next session. Durable state preserves partial
work and recovery. Only the user's own trusted projects run on this dedicated VM;
no other human operates it. They accept native dependency/build/test commands,
GitHub commands and host Docker authority. Codex runs as the development user with
sandboxing and per-command approval prompts disabled. No custom sandbox profiles,
containerized agent or VM migration is required.

Standing authorization covers required disposable testing. Do not repeatedly ask
for the same permission. Tool-session permissions are external to package launch
settings. Production deployment, new spending, credential/GitHub permission changes,
blanket sudo, persistent services and publishing this runner remain separate gates.
Current runner code has not been committed, pushed, merged or deployed.

## Approval friction encountered during M4

Development was repeatedly interrupted by tool-level approval requests for Docker
and native test commands. The user explicitly granted standing permission for
whatever M4 testing was needed, then had to object again because prompts continued.
Attempts to consolidate commands and request reusable approval rules did not reliably
eliminate the prompts; some approval waits were interrupted. Repeatedly submitting
approval-triggering commands after that clarification created unnecessary friction
and undermined the intended unattended workflow.

Future sessions must preserve existing authorization and avoid asking again for
already-covered tests. Distinguish the current coding tool's externally managed
permissions from the package's Codex launch settings: disabling sandboxing/prompts
in the package does not reconfigure the tool session running development. If that
session still requires approval, explain the specific constraint rather than
suggesting the user has not authorized the work. Use existing permitted execution
paths and consolidate checks where appropriate, without bypassing enforced controls.
The package's fresh/resumed sessions now explicitly use full VM-user access and
approval policy never. Committed-scope approval and the separate gates above remain.

## Current implementation

- Conventional `src/agentic_runner` package; CLI still provides help/version and
  read-only discovery. Operational start/status/pause/resume/service wiring is M9.
- M3 approval, canonical locks, pending intent, append-only events and atomic state
  are retained. Policy v4 / execution v2 explicitly records native no-sandbox mode,
  account homes, pinned Codex binary/hash and process limits. Old policy versions
  remain readable without automatic upgrade. Run/event/snapshot schemas stay v1;
  publication/completion states and boolean gates remain unavailable.
- `NativeExecutor` executes literal argv as the non-root owner after scope/config/
  revision checks and durable intent. It supervises time/input/output/process groups,
  preserves uncertain intent/partial work and omits raw output from public events.
- `NativeCodexAdapter` checks pinned CLI 0.166.0 capabilities and exact requested
  model/high. Fresh/exact-ID resume use `--dangerously-bypass-approvals-and-sandbox`,
  `danger-full-access`, approval policy never, structured reports and recorded session
  identity/available usage. Foreign resume IDs and bad reports fail; no automatic
  retry, smaller model, lower effort or paid provider fallback.
- Python/Node dependencies, builds and tests run natively. Dockerized applications
  use the VM's Docker engine, without mounting its socket into application containers.
  Required runtimes must be on the documented PATH; the Node test provisioned its
  own temporary runtime, not a global host installation.
- Original container adapter/images/tests/diagnosis are preserved as historical/
  optional work. Their seven nested-container checks are not current M4 prerequisites.

## Actual final checks

```bash
.venv-dev/bin/python -m unittest discover -s tests -v
# 123 total: 115 passed, 8 skipped; 25.017 seconds.
# Skips: 7 historical container checks + optional cached-Node fixture.

.venv-dev/bin/python -m tests.support.run_native_m4_checks --cached-node
# 123 total: 116 passed, 7 historical container checks skipped; 27.376 seconds.

.venv-dev/bin/python -m tests.support.probe_native_m4 --real-codex --docker
# Passed: actual fresh task, same-session resume, host Docker app build/run/test.
```

The real session is `01a18ee0-3a61-75d3-913f-8ff015bc67ad`. Its two actual turn_context
records both show `gpt-6.1-sol`, effort high, approval never and danger-full-access.
Safe settings/usage/outcomes are retained in [JSON evidence](../evidence/m4-native-real-check.json).
Normal Codex history remains private in the account; no tokens or raw model output
were published. The task wrote only generated fixture files and preserved implementing
phase/no pending intent. No model prose was treated as publication evidence.

Native Python venv/build/install/pip-check/unittest and native Node npm-ci/install
lifecycle/build/test passed. The Node binary came from the cached pinned official
Node image copied into a disposable fixture; that temporary container and tools were
removed. The generated Docker application image was removed after checking its exact
label; no socket was mounted in the application. No shared image prune ran.

All 43 Python sources parse with clean whitespace. `pip check` reports no broken
requirements; runtime dependencies remain empty. M1 preservation check confirmed
11 prototype and 103 reference files unchanged under existing cache/venv exclusions.
No operational state was read/written or used as a fixture. No host service,
credential/permission change or production deployment occurred.

## Git, recovery and next fresh session

Baseline remains main at `685884d8092745a679a763f9b62e0f3c0f096ded`.
All M4 work is unstaged/uncommitted. Preserve it and inspect status/instructions
before further work. No applicable AGENTS.md was found. Do not execute root-level
prototype scripts. Earlier M1–M3 GitHub publication was separately authorized and
is not permission to publish this milestone.

Next implementation session: **M5 only**, when requested. Read its full deliverables/
acceptance, state protocol and M4 evidence first. It must introduce verified tree
identity, controlled Git/GitHub publication and gate discovery deliberately. Configured
CI cannot fall back to local-only checks. M4 added no publication capability; fresh
project-appropriate verification environment wording reflects the accepted VM design.

For uncertain execution, reopen failed state handles, inspect exact revision,
pending operation, surviving processes/files and known session, then explicitly
reconcile with evidence. Never blindly reissue a model request or truncate history.
Process-group supervision does not clean arbitrary detached services automatically.
Automatic retry/session recovery/scheduling and persistent service operation remain
later milestones. Old policy approvals are not migrated silently.

`/home/ilan/agentic-workspaces/milestone-test` stays read-only.
`/home/ilan/agentic-runner-data` stays operational state, never development storage.
All future tests use live owned generated fixtures. Keep real account integration
selective and explicit; default tests must not consume credentials or model usage.
