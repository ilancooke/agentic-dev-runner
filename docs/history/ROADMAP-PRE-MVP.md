# Autonomous Codex Development Runner

Approved architecture and implementation plan, 2026-10-30. See
[architecture](ARCHITECTURE.md) and [session handoff](HANDOFF-PRE-MVP.md).
Implement one milestone per fresh session. Do not advance without recording
acceptance evidence. M1–M4 are complete under the accepted trusted-VM design;
M5–M10 remain unimplemented. See [M4 acceptance evidence](../evidence/M4-NATIVE.md),
[M1 acceptance evidence](../evidence/M1.md), [M2 evidence](../evidence/M2.md),
and [M3 evidence](../evidence/M3.md).

This document uses the proposed roadmap convention: a progress table with stable
IDs and matching milestone sections containing Deliverables and Acceptance
criteria. [The discovery contract](../DISCOVERY.md) specifies the supported
Markdown grammar. The preserved prototype parser does not support this document
as an execution input; use the new package for read-only parsing/discovery.

## Milestone Progress

| Milestone | Status |
| --- | --- |
| M1 | complete |
| M2 | complete |
| M3 | complete |
| M4 | complete |
| M5 | not started |
| M6 | not started |
| M7 | not started |
| M8 | not started |
| M9 | not started |
| M10 | not started |

## M1 — Baseline, package, and isolated test harness

Phase: Generalization and architecture.

### Deliverables

- Preserve the prototype and inventory its behavior and dependencies.
- Establish a conventional Python package, single CLI skeleton, and separate
  development environment with minimal dependencies and documented setup.
- Create temporary repository/state fixture factories and fake external adapters.
- Establish test isolation guards before adding execution tests.

### Acceptance criteria

- The new CLI can be invoked using the documented development setup without
  invoking the legacy orchestrator or changing operational state.
- Tests operate only in explicit disposable roots. Attempts to target the
  reference repository, shared operational state, and other non-test paths are
  rejected before mutation. Include path aliases and symlinks in guard tests.
- Prototype code and known-good reference artifacts remain preserved.
- Relevant automated checks execute successfully; commands and results are
  recorded in the handoff. No operational environment is used as a fixture.

## M2 — Repository and roadmap discovery

Phase: Generalization and architecture. Depends on M1.

### Deliverables

- Read-only preflight discovering repository identity, remote, default branch,
  applicable AGENTS.md, supporting documents, runtime and verification commands.
- A documented, deterministic roadmap grammar with stable IDs, ordered progress,
  milestone sections, deliverables and acceptance criteria.
- Inspectable discovery results and actionable ambiguity diagnostics.
- Python and Node/web environment selection from repository evidence.

### Acceptance criteria

- Fixtures cover Python, web, a default branch other than main, malformed and
  duplicate milestone IDs, inconsistent progress, conflicting instructions,
  ambiguous remotes, and unsupported runtime requirements.
- Each valid milestone has exactly one matching section; invalid or ambiguous
  inputs cannot silently select a milestone or verification command.
- Requirement prose supports ordinary Markdown and references to other files.
- Discovery does not mutate the target repository or execute project code.
- No per-project runner configuration file is required.

## M3 — Approval records and durable state

Phase: Generalization and architecture. Depends on M2.

### Deliverables

- Versioned project/run identity, explicit transitions, repository locks, atomic
  persisted state, pending-operation records, and append-only event history.
- Record the committed roadmap and referenced requirements authorized by start.
- Define permissible progress/evidence edits separately from protected scope and
  acceptance criteria. Record configuration governing each execution.

### Acceptance criteria

- Injected write failures and termination leave a valid prior or next state;
  incomplete events and incompatible state versions produce safe diagnostics.
- File and parent-directory synchronization are implemented where needed.
- Aliased paths cannot bypass repository locking; projects cannot share state
  accidentally. Operational and test roots cannot collide.
- Scope changes invalidate authorization; permitted progress changes do not.
- No undocumented boolean combination can advance publication state.

## M4 — Native VM execution and Codex adapter

Phase: Generalization and architecture. Depends on M3.
Revised with explicit user agreement to the [trusted dedicated-VM design](TRUSTED_VM_DECISION.md).
The [original container scope](../evidence/M4-ORIGINAL-SCOPE.md) is retained as history.

### Deliverables

- Supervised native execution as the development account for trusted, owner-selected
  Python/Node projects: project dependency environments, builds and tests.
- Codex adapter with sandboxing explicitly disabled under the trusted-VM policy,
  explicit GPT-6.1-Sol/high,
  structured events/reports, session identity and installed capability checks.
- Support Docker-based project builds/tests through the VM's Docker engine;
  application containers do not require Codex to run inside a container.
- Explicitly versioned approval of execution/auth/network settings, bounded process
  lifecycle, private diagnostics and documented trusted-code limitations.

### Acceptance criteria

- An authorized disposable native Codex check demonstrates exact `gpt-6.1-sol`/high
  settings, actual VM-user commands and exact-session resume with sandboxing disabled
  and the same settings reasserted.
- Automated tests exercise Python/Node dependency/build/test execution, timeout,
  cancellation, bounded output, partial-work retention and pending-operation recovery.
- Live disposable-root guards reject reference, operational-state and unowned test
  targets before native process launch. Discovery remains read-only/non-executing.
- Fresh and resumed Codex commands demonstrate the agreed VM-user access without
  an additional agent sandbox. The model and reasoning effort cannot downgrade.
  Test probes write only inside generated disposable fixtures.
- Existing development-account authentication and Docker authority are documented
  accurately and checked with fake credentials in automated tests. Arbitrary
  inherited secrets are omitted; raw tool/model output is excluded from public logs.
- A disposable Docker application build/run/test works from the host when Docker
  is available. No Docker socket is injected into application containers.
- Approved configuration and intent precede effects. Uncertain/interrupted execution
  retains identity and partial work; reports do not authorize publication/completion.
- No production deployment, credential/permission change, blanket root access,
  persistent service or publication of this runner is implied by development execution.

## M5 — Verification and controlled publication

Phase: Reliability, recovery, verification and security. Depends on M4.

### Deliverables

- Fresh verification environments appropriate to the project, tied to an identified proposed Git tree.
- Controlled staging, commit, push, PR creation and GitHub gate discovery.
- Verification policy: configured CI is mandatory; absent CI allows local-only
  verification; missing or ambiguous verification requirements stop execution.

### Acceptance criteria

- Tests reject unexpected changes, content changed after verification, mismatched
  repository/base/head identities, unsafe Git behavior and ambiguous checks.
- Required checks/status contexts and applicable repository rules are accounted
  for; missing, paginated, stale or incomplete evidence cannot authorize merging.
- Configured CI failure or unavailability never falls back to local-only checks.
- A no-CI fixture can publish only after declared checks pass in a fresh container,
  and its evidence explicitly records local-only verification.
- Commit contents equal the verified tree. Git hooks, filters, configuration and
  credential helpers cannot turn trusted publication into project code execution.

## M6 — Git and GitHub interruption recovery

Phase: Reliability, recovery, verification and security. Depends on M5.

### Deliverables

- Reconciliation for branch creation, commit, push, PR creation, merge, local
  synchronization and completion recording, using durable operation intent.
- Persistent completion evidence rather than deleting all execution history.

### Acceptance criteria

- Failure injection covers interruption immediately before and after every
  external effect, including success with lost response and failed persistence.
- Recovery neither duplicates publication nor adopts unrelated commits or PRs.
- Both an unissued merge request and an already successful merge recover safely.
- Later default-branch commits do not incorrectly require local HEAD to equal
  the earlier merge commit; ancestry and completion are reconciled safely.
- Interrupted cleanup cannot erase the evidence needed to determine completion.

## M7 — Codex failure recovery and usage scheduling

Phase: Reliability, recovery, verification and security. Depends on M6.

### Deliverables

- Supported failure classification, bounded retries/backoff, context recovery,
  usage-limit waits, durable partial-work checkpoints and token diagnostics.
- Prefer explicit session-ID resume when supported and safe; otherwise reconstruct
  the same milestone in a fresh session from durable records and repository state.

### Acceptance criteria

- Simulations cover crashes, unexpected termination, missing/invalid completion
  reports, context exhaustion, account exhaustion and provider/transport failures.
- Partial work survives without requiring a final agent-written handoff.
- The same milestone resumes; failure never advances roadmap execution.
- A reliable usage reset schedules a delayed attempt; absent/ambiguous reset data
  pauses for explicit resume. Reset is not assumed to guarantee available quota.
- Retry budgets survive restart; repeated exhaustion cannot cause a tight loop.
- No paid fallback, smaller model, or lower reasoning effort is selected.
- Installed CLI behavior is capability-tested. If exec lacks required signals,
  evaluate the supported app-server interface rather than inventing contracts.

## M8 — CI repair, branch reconciliation and security hardening

Phase: Reliability, recovery, verification and security. Depends on M7.

### Deliverables

- Up to two automatic CI repair attempts per milestone, within approved scope.
- Bounded automatic incorporation of an advancing default branch without force
  pushes, followed by renewed local verification and CI.
- Persistent budgets, explicit approval gates and adversarial boundary tests.

### Acceptance criteria

- Tests cover pending, failed, timed-out and incomplete CI; conflict resolution;
  changed requirements; and exhaustion of persisted repair/reconciliation budgets.
- Ambiguous conflicts pause and preserve work. Resolution cannot silently weaken
  approved acceptance criteria or verification policy.
- Credential-access attempts, repository-controlled execution, malicious Git
  configuration/hooks, path escapes and unexpected file changes are exercised.
- Destructive operations, production deployment and separately gated external
  spending cannot proceed through start authorization or prompt compliance alone.
- No merge precedes successful verification of the final resulting commit.
- Define constrained support for project tests that launch containers; never
  expose the unrestricted host Docker socket to project execution.

## M9 — Persistent service and operational CLI

Phase: Service deployment and operations. Depends on M8.

### Deliverables

- systemd service definitions, durable control requests, status/log inspection,
  pause/resume, single-milestone and default continuous execution.
- Multiple registered projects with one active milestone globally by default,
  configurable concurrency, and sequential milestones within each project.
- Document graceful pause, forced interruption, approval waits, reboot recovery,
  resource limits, state backup and diagnostic retention.

### Acceptance criteria

- Isolated service tests demonstrate continued operation after CLI disconnect,
  worker restart, serialized scheduling and recovery of pending operations.
- Explicit pauses/approval gates survive restart; previously active runs reconcile
  before continuing. No Codex session remains active merely to keep service alive.
- Status and logs identify project, milestone, state, wait reason and next action
  without leaking credentials or sensitive raw payloads.
- Service installation/enabling on the real VM requires separate deployment
  authorization; creating unit files does not authorize installation.

## M10 — Disposable integration testing and migration

Phase: Service deployment, operations and final integration. Depends on M9.

### Deliverables

- Dedicated disposable GitHub resources and Python/web end-to-end scenarios.
- Selective real interruption tests, operational/runbook documentation, migration
  instructions and an explicit prototype retirement procedure.

### Acceptance criteria

- Authorized integration runs demonstrate multiple sequential milestones through
  merge, CI repair, restart recovery, approval pauses and local-only verification.
- Evidence identifies executed commands, exact verified/merged commits, external
  usage, retained records and any untested limitations.
- Reference repository and existing shared operational state remain unchanged.
- New state namespace cannot overwrite or silently import legacy state. Legacy
  scripts remain preserved until explicit retirement.
- A fresh session/operator can follow documented setup, start, inspect, pause,
  resume and recovery procedures without conversational context.
- Real VM reboot/service deployment checks run only after explicit authorization;
  isolated simulations and real-host checks are distinguished in evidence.
