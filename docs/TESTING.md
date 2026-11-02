# Testing the revised MVP

Install and run from a checkout of this runner:

```sh
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install -e .
.venv-dev/bin/python -m unittest discover -s tests -v
.venv-dev/bin/python -m pip check
git diff --check
```

Python 3.12+, Git and Linux/POSIX fork/flock/fsync semantics are required. Runtime
dependencies are empty. Default discovery runs no real model, GitHub request,
Docker command, prototype script or operational project code. Historical optional
container/native adapter checks have been retired.

Tests use newly owned `DisposableRoot` directories under canonical `/tmp`, private
HOME/TMPDIR, disabled global/system Git config and generated files. Never adopt
an existing checkout, the reference project or operational state. Guard every
mutable target and subprocess cwd with the owned fixture boundary. Its checks
prevent targeting mistakes; they do not isolate hostile code.

Retained coverage includes read-only discovery/roadmap/runtime parsing, fixtures,
subprocess supervision, atomic persistence, setup and the verified loop. Setup/run
use real local Git and bare remotes with fake GitHub/model responses. Recovery
kills workers before/after agent, verification, completion, staging, commit and
push effects, and inside atomic checkpoint/roadmap writes. It covers blocked second
milestones, manual continuation, lost responses, recorded-commit replacement and
completed-run ref/protection rechecks. Main invariants and intentional violation
tests are distinguished. Ctrl-C and subprocess group cleanup have separate checks.

## Selective account-backed checks

These opt-in commands are never part of unittest discovery:

```sh
.venv-dev/bin/python -m tests.support.live_acceptance --real-codex
.venv-dev/bin/python -m tests.support.live_acceptance --github-owner YOUR_LOGIN
```

`--real-codex` uses the existing account for one fresh `gpt-6.1-sol`/high
unsandboxed session against a generated repository. It requests a tiny file and
progress update, independently checks bytes, commits/pushes to a **local bare
remote**, then reruns without another session. GitHub responses are fake here.
No credentials are copied into fixture files.

`--github-owner` requires the authenticated login. It creates one uniquely named
**private** `agentic-runner-acceptance-<uuid>` repository, exercises real setup,
protection read/write/read-back and dev Git transport, with two fake-agent
milestones, a blocked second milestone and manual resume. It never targets an
existing project or changes visibility. A checkout-local gh credential helper
supplies Git transport; global credentials stay unchanged. It attempts deletion
only of the exact repository whose creation succeeded. The token must also permit
repository deletion. Cleanup failures print the exact name for manual removal.
Do not run this probe if temporary repositories or cleanup limitations are
unacceptable. Unsupported protection stops; no public/unprotected fallback exists.

Each command prints JSON evidence and returns nonzero on failure or required manual
cleanup. Local fixtures are disposed afterward, including on probe failure.
Production failures retain files as described in [recovery](RECOVERY.md).
Actual results and limitations appear in [M3 evidence](evidence/MVP-M3.md).

Historical evidence under `docs/evidence` and retired contracts under `docs/history`
describe the earlier plan. Old APIs, image builders, probes and state tests are
retired; retrieve old sources at Git revision `26312e0` for investigation. Never
execute them against the reference checkout or `/home/ilan/agentic-runner-data`.
