> Historical pre-MVP document. Its APIs and commands were retired in revised M3.
> Use the root README and docs/RECOVERY.md for current operation.

# Execution contract — trusted development VM

The accepted [design decision](TRUSTED_VM_DECISION.md) replaces mandatory runner
containers and agent sandboxing. The dedicated VM is the containment boundary.
Codex and authorized project commands run with the development user's VM access.
The user explicitly requested **no Codex sandbox**. No custom AppArmor/seccomp
profile, nested sandbox, VM migration or sudo service is required.

## Native adapter

`native_execution.NativeExecutor` runs literal argv with `shell=False`, non-root
checkout ownership, canonical repository locks, current scope approval and durable
intent before process launch. Project dependencies/builds/tests run directly as
that account. Python virtual environments, npm and host Docker commands are allowed.
Docker application containers need no host socket injection or Codex installation.

`native_codex.NativeCodexAdapter` pins the installed CLI binary/hash, verifies model
and effort support and builds both fresh and explicit-ID resume commands with:

```text
--dangerously-bypass-approvals-and-sandbox
```

It also explicitly records `sandbox_mode="danger-full-access"`,
`approval_policy="never"`, `gpt-6.1-sol` and high reasoning effort. There is no
agent permission-profile or filesystem-denial capability test. This setting applies
to sessions launched by the package; it cannot alter the current coding tool's
externally managed permission policy.

No model/effort fallback or automatic retry exists. Reports/events retain session
identity and available usage. Invalid/nonzero/interrupted agent execution retains
pending intent. A report never advances publication, completion or milestone state.
Operational CLI/service wiring remains M9, and controlled publication remains M5.

## Approval and access

Current native execution requires explicit **policy v4**, execution record v2,
with `codex_sandbox: disabled`, account homes, binary hash and process limits.
Earlier control v1, container v2 and experimental sandboxed-native v3 remain
readable. They cannot silently authorize current native execution. Changing policy
requires renewed scope/configuration approval. Run/event/snapshot schemas stay v1;
no publication phases or new boolean permission flags were added.

Existing account-level development auth is intentionally available. Trusted code
may read account files. Child environments omit arbitrary inherited cloud/token/
Git variables, but this is not a credential isolation mechanism. Conventional host
Docker access grants powerful VM authority. The user accepted that trust model.
No protection against malicious same-user project code is claimed.

Test targets still require live owned DisposableRoot capabilities. Reference and
operational runner state remain excluded from test cwd/fixture registration.
Production deployment, new spending, credential/GitHub permission changes, blanket
root access, persistent services and publishing this runner are separately gated.

## Supervision, testing and recovery

The supervisor bounds input/output/time and handles cancellation/process groups.
Interrupted or uncertain results retain pending identity and partial checkout work.
Close/reopen failed persistence handles, inspect current revision/pending ID and
actual effects, then explicitly reconcile; never blindly reissue uncertain commands.

The [native probe](M4_NATIVE_PROBE.md) defaults to credential-free checks in a dummy
repository. Its optional real mode uses one fresh Codex session and one exact-ID
resume with no sandbox and the fixed requested model/effort. An optional Docker
probe builds/runs/removes only a generated, uniquely labeled test image.
M4 acceptance is complete; see [the actual checks](../evidence/M4-NATIVE.md).

The [old container contract](CONTAINER_EXECUTION_HISTORY.md), container adapter,
image/test assets and [diagnosis](../evidence/M4-SANDBOX-DIAGNOSIS.md) are preserved
as historical work. Their blocked nested-sandbox checks are not native prerequisites.

## Runtime setup and limits

Use Python 3.12 and Node 22/npm matching discovery's capability lines. The native
adapter does not install system-wide runtimes: provision them on the VM or supply
project tools on its PATH (`<checkout>/.venv/bin:/usr/local/bin:/usr/bin:/bin`).
`native_dependency_commands` creates a Python venv and installs the local package,
or runs npm ci; optional offline mode is supported. Install any additional declared
dev/test extras explicitly. Missing tools/dependencies stop instead of selecting
another runtime/model or using operational state as storage.

The Node integration copied the cached official Node runtime into an owned temporary
fixture, executed it natively and deleted it afterward. It did not install Node on
the VM. Normal session history from the real Codex probe remains under user HOME.
CLI usage is retained as reported; resumed counters may be cumulative.

Controlled cancellation kills the supervised process group and preserves pending
intent/partial work. Arbitrary daemonized/self-detached services require explicit
project cleanup; a runner/host crash may leave processes requiring observation.
Automatic session recovery/retries, scheduling, CI/publication and service operations
are later milestones. No hostile-code isolation or machine-wide cleanup is claimed.
