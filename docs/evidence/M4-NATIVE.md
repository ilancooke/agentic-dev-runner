> Historical pre-MVP evidence; milestone IDs here refer to the retired plan.
> Current acceptance is recorded in MVP-M3.md.

# M4 acceptance evidence — native trusted VM — complete

M4 is complete under the [explicitly accepted execution revision](../history/TRUSTED_VM_DECISION.md):
Codex runs directly on the dedicated VM with **no sandbox and no approval prompts**.
This replaces the original nested-container requirement. The
[original scope](M4-ORIGINAL-SCOPE.md), container work and diagnosis remain historical;
no old sandbox failure is represented as having passed. M5–M10 are unimplemented.

## Resulting behavior

`NativeExecutor` runs authorized native commands with a literal argv, non-root
checkout ownership, canonical repository locks, live disposable test guards,
current committed scope/configuration approval and durable intent before launch.
The supervisor bounds stdin/output/wall time and terminates process groups on
cancellation, timeout or output exhaustion. Uncertain/invalid agent results preserve
pending identity and partial work; no automatic retry or phase advancement occurs.

`NativeCodexAdapter` checks the installed binary hash, CLI 0.166.0, model catalog
and exec/resume controls. It explicitly uses `gpt-6.1-sol`, high reasoning effort,
`--dangerously-bypass-approvals-and-sandbox`, `danger-full-access` and approval
policy never for fresh and exact-ID resumed sessions. Resume IDs must belong to
the same recorded run. Structured final reports/events retain session/usage metadata,
while prompts/raw output/report prose stay out of public state events. Failed
native Codex validation exposes private process diagnostics to its caller.

Native policy v4 / execution record v2 captures homes, binary/hash, limits and
no-sandbox access. Earlier policy versions remain readable, without silent upgrade.
Namespace/run/approval/event/snapshot schemas stay v1. Publication/completion states
and operational CLI/service wiring are not implemented here.

## Actual checks and outcomes

| Command/check | Observed result |
| --- | --- |
| Initial native baseline, `.venv-dev/bin/python -m unittest discover -s tests -q` | Earlier checkpoint: 118 methods, 111 passed, 7 historical container skips, 17.528 s. |
| `.venv-dev/bin/python -m tests.support.probe_native_m4 --real-codex --docker` | **Passed:** actual fresh Codex task, exact-ID resume, expected generated file writes, deliberate fake-auth readability, generated Docker application build/run/test, no socket mount, implementing phase retained, no pending intent. |
| Targeted read of the newly created session's two turn_context records | **Both:** model `gpt-6.1-sol`, effort `high`, approval policy `never`, sandbox policy `danger-full-access`. Only these metadata fields were printed; no token/prompt/raw model content was exposed. |
| `.venv-dev/bin/python -m unittest tests.test_native_integrations -v` | Python venv/local package build/install/pip-check/unittest passed; Node skipped without its explicit fixture capability, 4.713 s. |
| `.venv-dev/bin/python -m tests.support.run_native_m4_checks --cached-node` | **123 total: 116 passed, 7 historical container tests skipped**, 27.376 s. Includes real native Python and Node dependency/build/test execution; no account/model call. |
| Final `.venv-dev/bin/python -m unittest discover -s tests -v` | **123 total: 115 passed, 8 skipped**, 25.017 s. Skips are seven historical container integrations and the separately selected cached-Node fixture. |
| `.venv-dev/bin/python -m pip check` | No broken requirements; read-only pip-cache warning only. No host runner dependency installation. |
| Python AST/whitespace and TOML check | All **43 Python sources** parse; clean source whitespace; package runtime dependencies remain empty. |
| M1 SHA-256/inventory preservation check | **11 prototype artifacts and 103 reference files unchanged**, under the recorded cache/venv exclusions; no reference inventory additions/removals. |
| Generated Docker resources | Ancestor/label/tag-specific checks found no remaining native Node fixture container or `adr-m4-native-*` image tag. No shared image prune or unrelated cleanup. |

No failing test run occurred during this final M4 completion pass. Native integration
fixtures were authored and inspected before the successful runs. The existing Node
runtime was absent from the VM, so the optional test capability extracted the cached
pinned official runtime to an owned disposable fixture and executed it natively.
No system-wide Node installation, sudo change, daemon change or service was needed.

## Real Codex/session evidence

Session: `01a18ee0-3a61-75d3-913f-8ff015bc67ad`.
The [machine-readable record](m4-native-real-check.json) contains the observed
settings, CLI token counters, outcomes and cleanup scope. The raw normal Codex
history remains private under the development account; fixture repositories/state
were deleted by their live owned DisposableRoot lifecycle.

Installed Codex binary SHA-256:
`b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8`.
The fake-auth fixture was deliberately readable and its content was excluded from
public events. No actual credential was copied to a fixture, printed or manually
changed. Existing account authentication was used through normal Codex behavior.
The full-access fresh/resume commands were reasserted identically and both actual
turn contexts confirmed the settings. Available CLI usage is retained as reported;
resumed counters may be cumulative and are not summed into a billing claim.

## Native runtime and Docker evidence

Python created a new venv, built and installed a generated stdlib-only wheel backend,
passed pip check and ran unittest against the installed module. Build markers were
absent before the authorized command and present afterward. No external dependency
fetch was needed. The default dependency helper supports ordinary online installation;
selective fixture tests use offline mode.

Node 22/npm came from
`node@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da`.
The native binary SHA-256 was
`94efd062ed066c1a0b332e18249859c905e920eeada5df55d24c99b919629a90`.
The source container was never started; exact image/unique label were checked and
it was removed after copying only Node/npm into owned temporary paths. npm ci,
install lifecycle, build and node --test all ran **on the VM**, with one real passing
Node test. This is not a container-only substitute for native runtime verification.

The separate Docker application probe built a tiny generated image from the cached
pinned Python base, ran its test, asserted `/var/run/docker.sock` absent and removed
its uniquely labeled image tag. The application ran non-root with no host mounts,
no network and normal Docker confinement. Codex itself ran directly on the VM.

## Acceptance mapping

| Current approved M4 criterion | Evidence |
| --- | --- |
| Authorized real native Codex, exact model/high and exact-ID resume | Real two-turn probe passed; both effective turn contexts inspected and retained as safe metadata. |
| Native Python/Node dependency/build/test; supervision and interruption | Real venv/wheel/install/test and npm lifecycle/build/test passed; actual cancellation, timeout, output exhaustion, stdin bounds and process-group unit checks passed. Pending identity survives close/reopen and explicit reconciliation. |
| Live fixture guards; discovery stays read-only | Retained M1–M3 alias/reference/state/root guards and M4 native unowned-HOME/scope/root checks passed before launch. CLI remains read-only discovery. |
| No extra agent sandbox; same fresh/resume settings, no downgrade | Actual VM-user writes in two owned fixture directories and effective full-access/never/high contexts pass; fresh/resume argv and legacy refusal tests pass. |
| Auth/Docker authority accurately documented; fake creds and private logs | Accepted trusted-account model documented; fake file readability and omitted inherited secrets verified; raw prompts/reports/diagnostics absent from public events. No hostile-code isolation claim. |
| Host Docker project build/run/test; no application socket mount | Generated application probe passed and asserted socket absent. No Docker-in-Docker or custom security profiles used. |
| Approval/intent before effects; uncertainty retains work, no report-driven publication | Native/M3 tests verify pending-before-launch, scope invalidation, exact revisions, bad-report retention, cancellation/output limits, partial files and unchanged implementing phase. |
| No implied production/root/service/publication authority | No runner commit/push/merge, production operation, credential/permission change or service installation occurred. Fixture Git commits are generated local setup only; no transport/publication. |

## Limits, cleanup and recovery

This is a single-user **trusted-code VM** design. Codex/project code has ordinary
account access, and host Docker carries powerful VM authority. Account files are
not isolated from malicious same-user code; the user explicitly accepted that model.
Native runtimes must be provisioned on the VM or project PATH. The Node test did
not leave a global installation. Additional project-specific dev/test extras are
explicit setup inputs, not guessed by the dependency helper.

Process groups cover ordinary supervised children; daemonized/detached project
services need explicit cleanup. A host/orchestrator crash may leave processes or
an uncertain model request. Reopen state, inspect the retained operation/session
and surviving work, and reconcile with evidence before retrying. Automatic session
recovery/retry scheduling is M7; verified publication is M5; no such behavior is
claimed complete here. Reports alone cannot authorize publication/completion.

No operational runner namespace was created. The reference checkout was read only
for preservation hashes, and existing operational runner state was not used as a
fixture. Old runner/container images and build cache remain development artifacts;
no unrelated resource was removed. M1–M4 are complete. Stop here; M5 requires a
fresh user-requested implementation session.
