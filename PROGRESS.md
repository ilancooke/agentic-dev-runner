# Revised MVP progress

## M1 — Working loop for a prepared protected repository

Implemented on `mvp-runner`, based on `2f743da`. This replaces the previous active
M1–M10 orchestration plan with three smaller milestones. Historical plans/handoff
are preserved in docs/history; no historical implementation is claimed as the new MVP.

Retained the roadmap/Markdown parser, subprocess supervisor, durable atomic I/O,
local repository inspection and owned disposable fixture harness. Existing tests
remain intact apart from CLI help expectations. Added four small modules for explicit
project config, fresh headless Codex, the Git boundary and the sequential loop.
Old approval/state/container machinery is outside the run path; retirement is M3.

Implemented `run --config`, five required documents, strict results, explicit native
checks, dev-only commits/pushes, mandatory GitHub main-protection checks and local /
remote main invariants. Codex has no Git/GitHub authority in its instructions;
multi-agent features are explicitly disabled. No Codex sandbox; gpt-6.1-sol/high.
Publication records its intent/tree before commit and reconciles manual reruns.
Failed implementation/checks retain files and record the issue; captured process
failures retain private stdout/stderr under `.git/ralph/`.

Validation:

- Baseline: `.venv-dev/bin/python -m unittest discover -s tests -q` — 123 tests,
  115 passed, 8 documented skips, 25.245 seconds.
- Final: `.venv-dev/bin/python -m unittest discover -s tests -v` — 148 tests,
  140 passed, 8 documented skips, 33.184 seconds.
- `.venv-dev/bin/python -m pip check` — no broken requirements.
- `git diff --check` — clean.
- Local `codex exec --help` and `codex features list` checked without inference;
  documented launch flags and both multi-agent feature names are present.

New account-free tests exercise two successive milestones with real Git commits /
local bare-remote pushes and fake Codex/GitHub; verification failure and fresh manual
resume; blocked/malformed reports; control/branch/HEAD violations; unchanged main;
unsafe files; lock contention; missing documents/config changes; verification mutation;
pre-commit interruption; lost commit/push responses; failed push and publication-first
manual recovery. The headless contract test checks no sandbox, exact model/effort,
structured output and disabled subagents. Main is unchanged in normal/failure runs;
the intentional main-ref violation test detects the injected change and stops.

Limits: no new live Codex or GitHub integration was run. M1 needs an already prepared
repo with compatible branch protection (rulesets alone are unsupported). One-time
setup is M2. Checks use existing native dependencies; remote CI is not polled. Broad
interruption auditing/live acceptance and obsolete-path removal remain M3. No runner
push, merge, service deployment, production mutation or operational-state access.

## M2 — Separate one-time Git and GitHub setup

Implemented on `mvp-runner`, based on revised M1 checkpoint `e598c75`. Added
`setup --config` using the same project config and five-document preflight. Setup
initializes an absent ordinary Git checkout, creates a private GitHub repo or
connects an existing matching origin, and sets repository-local authenticated-account
GitHub noreply identity. New checkouts receive one initial main baseline; existing
history must be clean and is preserved. Existing origin and branch conflicts stop
without replacement. Invalid dev refs and unborn HEAD on dev fail before publication.

Setup alone may create missing main and main protection. It requires repository
admin permission, establishes PR review/admin/no-bypass/no-force/no-delete protection,
reads it back, then creates or safely switches/publishes dev. Existing compatible
policies, including stronger status/review settings, receive no writes. Incompatible
policies require manual strengthening, preserving unknown/additional requirements.
API permission/transport errors do not imply absence, and plan/permission failures
produce actionable diagnostics without an unprotected fallback. Initial main may
already be published when protection fails; setup remains incomplete until fixed.

Reused tested Git commands, config/origin checks, protection validation, file inventory,
repository locking and atomic I/O. `.git/ralph/setup.json` records initial identity,
files/refs, baseline before main-ref creation, and dev/document switch intent. Manual
reruns reconcile interrupted effects and lost responses without duplicate reachable
commits. Setup refuses an existing run checkpoint. Routine run performs no setup
writes. Runtime dependencies remain empty. Updated README, example config,
architecture, roadmap and handoff; M3 remains unfinished.

New account-free tests use owned DisposableRoot fixtures and local bare remotes.
They cover new/existing repositories, matching/mismatched/ambiguous origins, local
noreply identity, idempotency, existing stronger protection, local/remote main/dev
conflicts, missing docs/admin/plan support, protection read-back failure, invalid refs,
changed controls/checkpoints, shared locks and setup followed by a real local run
with main unchanged. Failure/lost-response injection covers Git init/config, private
repo creation, origin connection, commit object creation, main ref creation, main/dev
pushes, branch creation, protection PUT and branch switch. An existing descendant
dev with different documents also resumes after a lost switch response.

Limits: no live GitHub creation/protection or real Codex invocation was performed;
all GitHub/model responses in these checks are fake. Rulesets-only protection remains
unsupported. Existing incompatible policies must be strengthened manually. Existing
checkouts must be on main/dev, and unborn checkouts on main; remote history without
main or different main baselines needs manual preparation. Broader recovery auditing,
live acceptance and obsolete-path retirement remain M3. No runner push/merge,
service deployment, production mutation or operational-state access occurred.

Validation:

- `.venv-dev/bin/python -m pip install -e .` — succeeded; no runtime dependencies.
- Final `.venv-dev/bin/python -m unittest discover -s tests -v` — 170 tests,
  162 passed, 8 documented optional skips, 44.230 seconds.
- `.venv-dev/bin/python -m pip check` — no broken requirements.
- Installed CLI `--help` and `setup --help` — succeeded; CLI tests also cover
  setup help and required configuration without accounts or project writes.
- `git diff --check` — clean. Runner main remains `2f743da`; checkpoint is on dev.

## M3 — Recovery acceptance, live evidence and retirement

Implemented on `mvp-runner`, based on revised M2 checkpoint `26312e0`. The revised
three-milestone MVP is complete, with the explicit live GitHub limitation and
external cleanup item below. No new milestone beyond M3 was started.

Recovery auditing found and fixed non-atomic roadmap completion, adoption of edits
made during completion, absent completed-run publication rechecks and substitution
of an already recorded commit by another commit with identical content. Completion
now atomically replaces the roadmap using private temporary metadata, preserves
document permissions, and checks the expected bytes/modes before staging. Complete
reruns validate commit, files, controls, local/remote main, remote dev and protection,
even on all-complete roadmaps. Invalid model reports are retained privately; the
headless prompt/schema now express the one-line proposed commit-message contract.

Added real process-exit recovery acceptance before/after 11 effect boundaries and
inside five checkpoint/five roadmap atomic-write boundaries. Tests retain work,
reacquire locks and complete exactly the intended local dev commits/pushes. Added
blocked-second-milestone/manual-resume acceptance, Ctrl-C, lost/invalid headless
responses, private diagnostics, completion mutation/mode and completed-ref guards.
Default tests use owned DisposableRoot fixtures, real local Git and fake Codex/
GitHub only; no reference checkout or operational state is a fixture.

Retired 32 obsolete implementation/test artifacts (prototype entry points, config,
schema/skill, unused state/approval/container/native adapters and their tests/probes),
plus dead persistence helpers. Retained useful subprocess tests separately and
added focused persistence coverage. Archived eight old contracts, labeled historical
evidence, repaired links and removed stale active instructions. README and
[operator recovery](docs/RECOVERY.md) now cover installation, setup, run, phases,
manual resume and intervention. Runtime dependencies remain empty.

Validation:

- Baseline after editable installation: full suite — 170 tests, 162 passed and
  8 historical optional skips, 43.745s.
- Reinstalled with `.venv-dev/bin/python -m pip install -e .` successfully.
- Final `.venv-dev/bin/python -m unittest discover -s tests -v` — **115 tests,
  all passed, no skips, 55.000s**. Reduced count reflects deliberate retirement.
- `.venv-dev/bin/python -m pip check` — no broken requirements.
- Installed CLI/setup/run and opt-in acceptance help succeeded.
- `git diff --check` — clean. Runner main remains `2f743da`.

Selective real Codex acceptance passed after a report-contract fix: one fresh
requested `gpt-6.1-sol`/high unsandboxed session, independently checked file/progress,
real local dev commit/push, unchanged main and a no-new-session completed rerun.
The first attempt's invalid success report was rejected; neither attempt used real
GitHub protection. No automatic runtime retry was added.

Real GitHub acceptance created a generated private repository and published its
initial main, then correctly stopped on protection HTTP 403 (plan upgrade required).
No dev branch or milestone loop was published there. Full live protected GitHub
acceptance is unavailable, not claimed passed. Cleanup deletion also returned HTTP
403; **manual removal remains** for
[the generated private fixture repository](https://github.com/ilancooke/agentic-runner-acceptance-037c65f152034afb9d9e28c9753a2245).
Only generated fixture files are present. No credentials, visibility or account plan
were changed. [Detailed M3 evidence](docs/evidence/MVP-M3.md) records both live results
and the exact cleanup failure. Local owned fixtures were disposed.

No push/merge of this runner, production mutation, service deployment, scheduler,
database, subagents or operational-state access occurred. The existing user change
adding `tmp/` to `.gitignore` is preserved and excluded from the M3 checkpoint.
