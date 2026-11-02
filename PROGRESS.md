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
