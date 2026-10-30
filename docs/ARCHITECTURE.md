# Approved runner architecture

Approved during the architecture interview on 2026-10-30. M1 packaging/test harness,
M2 read-only discovery and M3 approval/durable state are implemented; execution
capabilities are implemented as M4 library APIs. The user explicitly revised execution
to the [trusted dedicated VM](TRUSTED_VM_DECISION.md), with no Codex sandbox. Earlier
container work is preserved as history. Native M4 acceptance passed; M5–M10 remain
unimplemented. No operational CLI/service or publication workflow is deployed.
See [execution](EXECUTION.md) and [M4 evidence](evidence/M4-NATIVE.md).
The roadmap defines deliverables and evidence required before claiming any
capability is implemented. See [M1 evidence](evidence/M1.md) and
[M2 evidence](evidence/M2.md) and [M3 evidence](evidence/M3.md).

## Objective and scope

Automate implementation, verification, commit, push, PR, CI, merge and handoff for
an approved roadmap, one milestone per fresh Codex session. Continue until complete,
a genuine blocker, an explicit pause or an approval boundary. Ubuntu 24.04, Docker
and GitHub are the initial platform. Python and web projects are in scope; native
iOS/macOS verification is deferred. No dashboard, database, distributed framework
or multi-agent framework is planned.

## Decisions and rationale

| Decision | Rationale / revisit condition |
| --- | --- |
| Small Python package and one CLI, minimal dependencies | Maintainability and low overhead. Add abstractions only for demonstrated complexity. |
| One global policy configuration, no per-project runner config | Discover project details from repository evidence. Stop on consequential ambiguity. |
| Execute in the supplied checkout | Sole human operator does not plan manual edits. Require clean new starts, ownership checks for recovery and canonical repository locks. Revisit if concurrent human work becomes normal. |
| Direct execution on the dedicated development VM | Only owner-selected trusted projects; user accepts native dependencies/builds/tests, GitHub commands and host Docker authority. Codex sandboxing is disabled; the VM is the boundary. |
| Deterministic roadmap selection and transitions | Recovery must not depend on model interpretation of ordering or progress. Codex interprets free-form requirements and produces acceptance evidence. |
| start authorizes the current committed roadmap | Avoid repetitive milestone approvals. Record approved revision and referenced scope; scope/acceptance changes require renewed authorization. |
| GPT-6.1-Sol, high reasoning effort | Explicit user choice. No automatic model or effort downgrade, paid fallback, or consent to downgrade prompts. Native M4 verified `gpt-6.1-sol` and high in both actual fresh/resumed turn contexts. |
| Fresh session per milestone | Reconstruct context from project documents. Resume interrupted work within the same milestone by explicit session ID where appropriate; otherwise use a fresh session and durable evidence. |
| Two automatic CI repair attempts per milestone | Recover ordinary failures without human interruption; preserve approved scope and persist the budget across restarts. |
| Automatic default-branch reconciliation | Preserve history without force-pushing; resolve within approved scope, then repeat verification. Bounded attempts; ambiguous conflicts pause. |
| Automatic wait for reliably reported usage resets | Errors/metadata come from the client/service, not an exhausted model's final response. Unknown reset information pauses for explicit resume. Persist scheduling and avoid retry loops. |
| CI mandatory when configured; optional when absent | Existing gates cannot be bypassed. Absent CI permits declared checks in a fresh local verification container, explicitly recorded as local-only. Ambiguous/missing checks stop. |
| One active milestone globally by default | Limits VM resource and account contention. Multiple registered projects are supported; concurrency is a global setting. Each project's milestones remain sequential. |
| File-based durable state and event history | Adequate for a single-host service without database operations. Revisit if measured consistency or scheduling needs exceed this model. |
| systemd service, Codex launched on demand | Survive SSH disconnect/reboot without continuously active Codex. Explicit pauses remain paused. Reconcile previously active runs after restart. |

## Roadmap contract

A root ROADMAP.md has an ordered progress table of stable unique IDs and supported
statuses, with matching milestone sections containing Deliverables and Acceptance
criteria. Content inside those sections can use prose, lists, tables, code and
links to other project documentation. Other repository documentation stays flexible.
The [M2 discovery contract](DISCOVERY.md) specifies exact syntax, examples and
validation diagnostics. Arbitrary formats are not silently converted by an agent.

Code chooses milestones and controls advancement. An agent implements requirements
and reports evidence; reports alone do not authorize publication. Subjective prose
cannot be fully proven mechanically, so planning must resolve consequential
ambiguity and provide concrete verification expectations.

The [M3 state/approval contract](STATE.md) distinguishes progress/evidence edits
from protected scope and acceptance changes, including referenced requirements.
Approval protection does not rely on a model approving its own changes.

## Components and execution

Use conventional modules for CLI/control, discovery, policies, state/events,
container execution, Codex, verification, Git/GitHub and scheduling. Exact filenames
are implementation details, not a required abstraction hierarchy.

The trusted orchestrator controls publication. Codex, dependency installation,
build scripts and tests run natively as the trusted VM development account. Project
containers are used when appropriate to the application. Verification uses a fresh
project-appropriate environment and records the exact proposed tree. Publication
still needs explicit controlled staging/checks and must avoid implicit hooks/filters.

The workflow is discovery/authorization, implementation/recovery, verification,
commit, push/PR, applicable CI, merge, synchronization/completion, then the next
milestone. Each externally visible effect has durable intent and recovery
reconciliation; a command returning an error does not establish that its remote
effect failed. Partial work is preserved. No force push or destructive cleanup.

Operational state lives outside managed repositories with versioned schemas,
canonical project identity, locks, atomic replacement and synchronization of files
and directories where required. Events and completion records remain available
after active execution finishes. Test roots and operational roots must never mix.

## Security and approval boundaries

The [accepted trusted-VM revision](TRUSTED_VM_DECISION.md) supersedes the original
nested-container isolation requirement. One owner selects trusted projects; no
other human operates the VM. Codex runs directly with sandboxing and per-command
approval prompts disabled, using the development account's VM permissions.

- Existing development-account GitHub/Codex auth and host Docker use are authorized.
  Account files may be readable to trusted project code; no hostile-code secret
  isolation is promised. Arbitrary inherited token/cloud variables are omitted.
- Native dependencies/build/test scripts may execute. Discovery remains read-only.
  Application containers receive only project-specific inputs, without a mounted
  unrestricted Docker socket. Host Docker authority is an accepted powerful capability.
- Preserve scope approval, canonical locks, durable intent, bounded supervision,
  model/effort selection, exact-session resume and private/redacted diagnostics.
- Reference checkout and existing operational runner state remain excluded from
  testing. Use live owned generated fixtures; do not adopt arbitrary directories.
- Production deployment, new spending, destructive cleanup, credential/GitHub
  permission changes, blanket root access and persistent services remain separate
  gates. Standing permission for necessary disposable testing persists.
- Read current execution policy before effects. Earlier container/native-sandbox
  approvals are not upgraded silently. Reports do not authorize publication.

## Service behavior

Conceptual commands are start, status, logs, pause and resume, with optional explicit
project selection and single-milestone mode. Continuous mode is the default. Exact
flags may be settled during implementation without changing authorization semantics.
Pause prevents new work and safely interrupts active work when necessary, retaining
recoverable state. Approval waits and user pauses survive restart. Active runs are
reconciled before resuming after service interruption/reboot.

Transient errors use bounded retries and backoff. Context exhaustion, account usage
limits and unknown failures are distinguished only with reliable evidence. A reset
timestamp permits a delayed attempt, not an assumption that quota is now available.
Preservation never relies on a final model-generated checkpoint.

## Migration, tests and operational assumptions

Preserve the original prototype. Use a new state namespace and separate runner
development environment. No automatic legacy-state import or cleanup. The reference
repository /home/ilan/agentic-workspaces/milestone-test stays read-only unless the
user explicitly authorizes changes. Existing /home/ilan/agentic-runner-data is not
a fixture or a target for development experiments.

Use generated temporary repositories, fake adapters and injected failures for most
tests. Exercise real container boundaries. Use separate disposable GitHub resources
for selective integrations, with explicit authorization for new resources/costs
where needed. Never modify production repositories or AWS infrastructure during
development testing. Preserve test-generated credentials and state isolation.

Real service installation and real-host reboot testing require separate operational
authorization. Do not deploy a persistent service merely because unit definitions
are ready. Report simulated tests and actual operational checks separately.

## Observed baseline, not implementation guarantees

- Runner source was entirely untracked on main with no commits at discovery.
- Reference checkout was clean on main, matching locally recorded origin/main.
  Three calculator milestones and retained reports support the successful POC.
  Reference tests were read, not rerun during planning; live GitHub CI was not audited.
- Installed codex-cli reports 0.166.0 with exec resume, JSONL and structured-output
  options. Reset/error contracts and recovery safety still require capability tests.
- Docker Engine 29.9.2 and Compose 5.6.1 were observed. Docker/containerd services
  were active/enabled, with AppArmor, seccomp and cgroups v2. A hello-world container
  ran with no network/mounts, non-root user, read-only root, dropped capabilities,
  no-new-privileges and resource limits; it was automatically removed. No Docker
  configuration was changed. Codex-inside-container was not tested.
- Official references: https://learn.chatgpt.com/docs/non-interactive-mode,
  https://learn.chatgpt.com/docs/app-server,
  https://docs.docker.com/engine/security/.
