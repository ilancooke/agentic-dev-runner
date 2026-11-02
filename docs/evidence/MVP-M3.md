# Revised M3 acceptance — 2026-11-02

This evidence concerns the revised three-milestone MVP. Other M1–M4 files in this
folder describe the retired plan. Development starts at `26312e0` on `mvp-runner`;
runner main remains `2f743daf9596ec8541d4d0708116b91fe8d9174e`. This runner was not
pushed or merged. All execution targets were newly owned disposable fixtures.

## Account-free evidence

Baseline after editable installation:

- `.venv-dev/bin/python -m unittest discover -s tests -v`: 170 tests in 43.745s,
  successful with 8 historical optional skips.

Final after retirement and editable reinstallation:

- `.venv-dev/bin/python -m unittest discover -s tests -v`: **115 tests in 55.000s,
  all passed, no skips**.
- `.venv-dev/bin/python -m pip check`: no broken requirements.
- Installed CLI help, setup/run help and opt-in live-probe help succeeded.
- `git diff --check`: clean.

The reduced count reflects deliberate retirement of obsolete state/approval,
container and native adapter contracts, including all eight optional checks. Useful
subprocess tests moved to test_supervisor.py. New persistence and recovery tests
cover the current implementation rather than the removed framework.

Recovery tests exercise 22 real child exits (before/after 11 effect boundaries),
five exits inside atomic roadmap completion and five inside atomic publication
checkpoint writes. Exits use `os._exit`, bypassing exception cleanup; a fresh
manual run reacquires the lock, preserves partial files, finishes exactly two
commits/pushes, and preserves local/remote main. The boundaries are initial state,
agent, verification, publication intent, completion, staging, recorded tree,
commit, recorded commit, push and recorded completion.

Additional checks cover blocked second-milestone continuation, Ctrl-C during agent
and verification, timeout/lost/invalid headless results, private retained report/
process evidence, mutation during completion, executable document permissions,
replacement of a recorded commit by identical content, and completed-rerun guards
for remote main/dev, protection and unrelated HEAD. Existing setup interruption,
lost commit/push response, file/control/branch checks and multi-milestone local
publication tests remain. GitHub and model responses in this suite are fake; Git
commits and local bare-remote pushes are real.

## Selective real Codex

Command (explicit account-backed opt-in, not a default test):

```sh
.venv-dev/bin/python -m tests.support.live_acceptance --real-codex
```

The first invocation reached report validation and failed the success report's
blocker/commit-message constraint. No fixture publication was accepted. Its exact
invalid report was not retained by that version of the probe. The prompt now
states the full contract, the schema constrains commit-message characters/length,
and invalid reports are retained privately by production recovery. The schema uses
supported string patterns documented in [official OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

A second, manually launched check after those changes **passed**, with:

```json
{
  "check": "real-codex-local-publication",
  "status": "passed",
  "model": "gpt-6.1-sol",
  "effort": "high",
  "sandbox": "disabled",
  "sessions": ["M1"],
  "main_unchanged": true,
  "publication": "real local bare remote; fake GitHub protection",
  "commit": "263fe7b6bb7aa24e994824756421b6aff7b0ddab"
}
```

Installed CLI was `codex-cli 0.166.0`. The real process was called through the
production headless adapter using existing account authentication. Model, effort
and sandbox fields above describe the requested launch settings; this selective
check did not independently audit server-side per-turn metadata. The fake launch
contract test also asserts exact flags and disabled multi-agent features. The real
session created answer.txt with exactly `42\n`, updated progress, passed independent
Python byte verification, and was committed/pushed only to a local bare dev ref.
The completed rerun made no new model call. Local/remote main were unchanged.
GitHub protection was fake here; this is not live GitHub end-to-end evidence.
Local fixtures were disposed; ordinary account session history was not removed.

## Private GitHub protection limitation and cleanup

Command:

```sh
.venv-dev/bin/python -m tests.support.live_acceptance --github-owner ilancooke
```

Real account access, private repository creation, local noreply identity, origin
connection, baseline creation and initial main Git publication succeeded. Main
protection GET returned HTTP 403:

> Upgrade to GitHub Pro or make this repository public to enable this feature.

The probe stopped without a public/unprotected fallback. A subsequent real API
read confirmed private visibility, account admin permission, and **only main**;
no development branch was published and no milestone model/fake-agent loop ran
against GitHub. Therefore live protected GitHub setup/run/blocked/resume acceptance
is **unavailable under the tested plan**, not passed. Account-free tests cover it.
No subscription, credential or repository-visibility changes were attempted.

The generated repository still requires **manual deletion**:

[ilancooke/agentic-runner-acceptance-037c65f152034afb9d9e28c9753a2245](https://github.com/ilancooke/agentic-runner-acceptance-037c65f152034afb9d9e28c9753a2245)

Probe cleanup and a direct deletion of that exact generated repository were both
refused. `gh api --method DELETE repos/<exact-name>` returned HTTP 403, “Must have
admin rights to Repository,” despite the metadata read reporting admin permission.
The current credential could create/push but could not delete it; the precise
account/token permission cause was not established. It contains only generated
fixture documents and initial main. Remove it through an account/credential that
can delete repositories; do not delete any existing project. Local owned probe
fixtures were disposed. This residual private repo is the sole external cleanup
item from this session.

## Retirement and remaining limits

Removed 32 obsolete implementation/test artifacts: root prototype scripts/config/
schema/skill; nine unused orchestration/state/container/native modules; their tests
and probe/image helpers. Removed unused journal/recursive-directory helpers from
durable.py. Archived eight old contracts under docs/history, labeled older evidence
historical, and repaired active discovery instructions. Historical source remains
retrievable at Git revision `26312e0`; none was executed during this milestone.

The runtime has no Python dependencies, service, scheduler, database, subagents,
PR automation or merge path. Routine run does not write main. Trusted VM execution
is unsandboxed account access, not malicious-code isolation. Tests establish
process-loss behavior with local filesystem rename/fsync, not arbitrary power-loss
or concurrent hostile changes. Git-created stale lock files need operator review.
Rulesets-only protection and automatic remote CI polling remain unsupported.
See [operator recovery](../RECOVERY.md) for matching manual continuation.
