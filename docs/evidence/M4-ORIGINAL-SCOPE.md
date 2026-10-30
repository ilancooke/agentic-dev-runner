# Superseded M4 scope — retained historical requirements

The user revised this design after clarifying the trusted, single-user dedicated-VM workflow.
See [the accepted decision](../TRUSTED_VM_DECISION.md). This text is historical, not current acceptance.

## M4 — Container execution and Codex adapter

Phase: Generalization and architecture. Depends on M3.

### Deliverables

- Runner-provided Python and Node/browser execution environments, constrained
  mounts/networking, dependency setup, and subprocess lifecycle supervision.
- Codex adapter using explicit model and reasoning selection, structured events,
  reports, session identity, available diagnostics, and capability checks.
- Enforced separation of project execution from GitHub credentials, operational
  state, production access, unrelated files and Docker control.

### Acceptance criteria

- An explicitly authorized disposable real Codex check demonstrates the requested
  GPT-6.1-Sol/high settings and sandbox compatibility inside the container.
- Automated boundary tests demonstrate denied access to protected host files,
  credentials, state, Docker socket and prohibited network destinations.
- Dependencies, builds and tests run inside the execution boundary as well as
  agent-generated commands. Host project hooks/scripts are not implicitly run.
- Direct-checkout permissions work without broad host mounts or privileged
  containers. Git metadata is protected from unauthorized agent mutation.
- Unsupported security capabilities fail closed; no downgrade or automatic
  approval of a downgrade prompt exists.
- Authentication exposure and session-resume permission behavior are verified,
  not inferred from the sandbox name. Log redaction is tested.

