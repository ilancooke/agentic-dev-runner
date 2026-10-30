# Accepted execution-design revision — 2026-10-30

The user clarified the original purpose: automate an existing personal development
loop after interactive requirements/design Q&A. A detailed roadmap enables each
fresh Codex session to implement the next milestone; the runner replaces repeated
manual commit/merge/session-reset/reprompt steps and adds reliable recovery.

The user owns and selects every project, is the only human operator, and dedicated
a Proxmox VM to this work. They explicitly accept agent GitHub commands, dependency
installation, builds/tests and host Docker use. After discussing native execution
and Dockerized project testing, the user stated: "I agree with your recommendations."

## Current decision

Run the runner and Codex directly as the development account on this VM. The
user then explicitly clarified: "no sandbox. I thought we agreed". Codex sandboxing
and per-command approval prompts are disabled; the dedicated VM is the containment
boundary. Keep explicit model/effort and recorded execution/network settings. Dependency/build/test commands may execute natively as the same
account. Use Python virtual environments and the project's Node package manager.
Network access needed for development is allowed by this trust model.

Existing account-level development authentication is intentionally available to
Codex/gh. This is **not** hostile-project credential isolation. File-backed auth
may be readable to trusted same-user code. Arbitrary inherited token/cloud/Git
variables are omitted from child environments, but that does not hide account files.
Do not claim sandboxing protects the VM from deliberately malicious trusted code.

Dockerized applications are built/tested with the VM's Docker engine while Codex
runs on the host. Conventional daemon access grants powerful, effectively root-level
VM authority. The user accepted this implication. Do not inject the daemon socket
into application containers or assume the project requires Docker-in-Docker.
Applications using browsers/nested namespaces may have their own runtime needs.

No mandatory runner container, nested Codex sandbox, custom AppArmor/seccomp policy,
global sysctl change or VM migration is required. Preserve the earlier container
prototype, tests and diagnosis as historical/optional work; do not pursue those
profiles as a prerequisite for native M4.

## Requirements and schema consequences

The current ROADMAP M4 text deliberately supersedes its original container-specific
acceptance. The original text is retained in [historical scope](evidence/M4-ORIGINAL-SCOPE.md).
This is an explicitly accepted architecture revision, not a claim that the old
container checks passed. Planned M5 verification wording now allows an environment
appropriate to the project; no M5 implementation is included in M4.

Native execution uses explicit policy v4 (execution record v2) for no-sandbox
VM-user access. Policy v1, container v2 and the earlier native-sandbox v3 remain
readable without implicit migration; v3 cannot launch through the current adapter. Changing execution policy requires renewed committed
scope/configuration approval. Run/event/snapshot schemas stay v1; no publication/
completion phases or boolean gates are added. Trusted project execution and Codex
reports cannot establish that publication gates passed.

Keep test fixtures generated and owned, reference checkout read-only and existing
operational runner state out of development. Retain durable intent, canonical locks,
partial work, explicit-ID session resume, supervised processes and redacted logs.
Production deployments, new spending, credential/GitHub-permission changes, blanket
sudo, service installation and publishing this runner remain separately gated.
Standing authorization for necessary disposable M4 testing persists; do not ask
again for the same tests. The normal user account is `ilan`; no root daemon is added.
