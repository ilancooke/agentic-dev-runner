# M3 complete — stop here; next fresh session implements M4 only

The approved architecture/ten-milestone roadmap was accepted on 2026-10-30.
M1–M3 are complete; M4–M10 remain unimplemented. Read [ROADMAP.md](ROADMAP.md),
[architecture](docs/ARCHITECTURE.md), [M3 evidence](docs/evidence/M3.md),
[the state/approval contract](docs/STATE.md), and
[the discovery contract](docs/DISCOVERY.md).

## GitHub checkpoint authorization

After M3, the user explicitly authorized a new private repository at
[ilancooke/agentic-dev-runner](https://github.com/ilancooke/agentic-dev-runner)
and an initial M1–M3 checkpoint directly on main, including the preserved prototype.
Use current Git status/log/remotes for the publication baseline. Earlier milestone
evidence records the historical untracked, pre-publication state. Environments,
credentials and environment-managed directories are excluded from this checkpoint.

## Current implementation

- `src/agentic_runner` is a conventional package. The installed `agentic-runner`
  CLI (also `python -m agentic_runner`) still provides help/version and read-only
  `discover <checkout>` JSON only. No operational execution command was added.
- M3's `open_store()`/`start_run()` library API records explicit authorization of
  committed scope and configuration. It does not launch an agent, create a real
  branch or publish. Read STATE.md before using/extending it.
- State v1 has private versioned namespace/project bindings, canonical common-Git
  directory inode locks, strict run/intent schemas, append-only authoritative
  events and atomic snapshots. Stale revisions and uncertain writes cannot be
  retried blindly. Complete journal events recover lagging snapshots; torn or
  incompatible history diagnoses without truncation.
- Approval retains committed roadmap/requirement/asset bytes and blob IDs. Only
  progress status values and narrowly defined unreferenced evidence are exempt.
  AGENTS files, acceptance text, referenced evidence, runtime/check declarations
  and execution configuration stay protected. Scope changes durably invalidate
  approval; explicit renewal retains previous approvals in history.
- M3 phases are approved, implementing, verification_pending, paused,
  approval_required and failed. Publication/completion phases and commit/push/merge
  intents are unavailable until later verified gates/schema evolution. Resolving
  an intent never advances phase. Reports/booleans cannot authorize publication.
- `.venv-dev` remains the separate Python 3.12.3 runner environment; stdlib-only
  runtime/tests. Existing `.venv` and all prototype files remain preserved.
- Tests use live M1 DisposableRoot capabilities and generated local Git fixtures,
  fake external adapters and private test state. Read [TESTING.md](docs/TESTING.md).
  Never use an operational namespace to work around a test guard.

## Verification and preservation

```bash
.venv-dev/bin/python -m unittest discover -s tests -v
# 84 tests passed (50 M1–M2 checks plus 34 M3 methods).
.venv-dev/bin/python -m pip check
# No broken requirements found.
```

Tests include nine deterministic error checkpoints and nine actual disposable
child exits without Python cleanup, partial journal/snapshot writes, interrupted
initialization, lost intent responses, stale controls, sync ordering, identity/
role conflicts, process/alias/worktree locks, scope invalidation and renewal.
This is local process/filesystem evidence, not host power-loss/container validation.
An initial state-test fixture placed a link inside the reserved Verification block;
the fixture was corrected and subsequent state/full suites passed. All actual
commands/results and limitations are in the M3 evidence.

AST/whitespace checks passed for 28 Python sources; dependencies remain empty.
The M1 SHA-256 manifest comparison again confirmed 11 prototype artifacts and 103
reference files unchanged, with no reference inventory additions/removals. Its
reference venv/cache exclusions remain explicit. Operational state contents were
not read/written or used as a fixture. No real Codex, GitHub, Docker, AWS, service,
deployment, reboot or production validation ran. No dependencies were installed.

## Next fresh session: M4 only

1. Inspect Git status/log/remotes and applicable instructions. Initial M1–M3 checkpoint
   publication was explicitly authorized after M3; preserve any subsequent local work.
   Do not include credentials, environments or unrelated files in future commits.
2. Read M4 deliverables/acceptance, architecture, STATE.md, discovery contract and
   previous evidence. Keep approved acceptance criteria unchanged.
3. Use `.venv-dev/bin/python` and the documented runner suite. Do not run prototype
   scripts or their operational connectivity/project tests. This unborn/no-remote
   development checkout is intentionally not a valid full preflight/start fixture;
   generated repositories have real local commits/cached default refs.
4. Implement runner-provided constrained Python/Node execution, dependency/build/
   test isolation and supervised Codex adapter/capability checks in the package.
   Carry explicit intent/identity/configuration through the M3 layer. Add any schema
   evolution deliberately; v1 rejects unknown fields/phases rather than migrating.
5. Prepare disposable boundary tests and a concrete real Codex capability probe.
   The M4 real Codex check requires explicit authorization per the roadmap; obtain
   it after making the exact disposable probe/settings reviewable if it is not
   already authorized. Verify GPT-6.1-Sol/high CLI identifiers and sandbox behavior
   from installed capabilities, not the old observed CLI version or assumptions.
6. Record commands, acceptance evidence, limitations and next recovery instructions,
   update progress/handoff and stop without beginning M5.

No interrupted operational run needs recovery: M3 wrote only disposable test state,
removed with owned fixtures. No runner state namespace was deployed. For an M3 test
namespace with uncertain persistence, close/reopen via open_store; inspect its exact
revision/pending ID before acting. Complete history can rebuild a missing/lagging
snapshot. Torn/incompatible history requires preserved evidence and reviewed offline
repair/migration; no automatic repair/truncation command exists.

## Boundaries and remaining limits

- `/home/ilan/agentic-workspaces/milestone-test` stays the read-only known-good
  reference. `/home/ilan/agentic-runner-data` is existing operational state, never
  test storage. Prototype scripts/config/schema/skill are preserved and unsafe to
  invoke for development. No legacy state is imported.
- Generate separate disposable repositories/state. Enforce live owned roots before
  mutation, including aliases/symlinks. Never adopt arbitrary existing test roots.
  No production repositories, AWS infrastructure, credentials or GitHub permissions
  may change without explicit authorization.
- Do not install/enable a persistent service without separate deployment approval.
  Do not disable sandboxing or mount an unrestricted Docker socket into agent or
  project execution containers. M4 must enforce credential/file/network boundaries,
  including dependency/build/test execution, not just prompt restrictions.
- Requested model remains GPT-6.1-Sol with high reasoning effort. M3 records the
  requested label only; exact CLI representation remains unverified. No smaller
  model, lower effort, paid fallback or automatic downgrade consent.
- M3 locks coordinate trusted Linux/POSIX processes; they do not sandbox hostile
  code or stop administrators replacing filesystem paths. Hash chains are corruption
  checks, not signatures. No host reboot/storage power-loss test occurred.
- Approval conservatively refuses uncaptured external links/assets. Ancestor AGENTS
  bytes are separate uncommitted attestations. Natural-language consistency still
  requires review; structured declarations/hashes alone do not prove acceptance.
  Renewal currently requires clean default-branch committed scope for the same
  run/milestone. CI files remain inventory only; M5 must interpret required gates.
- No automatic history repair/migration/archival or completed-run advancement exists.
  Journal/event/approval size limits stop safely. Execution, verified publication,
  external-effect reconciliation, scheduling and service operations remain future
  milestones. Implement one milestone per fresh session, record evidence, then stop.
