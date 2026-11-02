> Historical pre-MVP document. Its APIs and commands were retired in revised M3.
> Use the root README and docs/RECOVERY.md for current operation.

# Preserved prototype inventory

Inspected as source for M1 on 2026-10-30; none of these scripts was run or imported.
The original files stay in place, byte-for-byte. Packaging includes only
`src/agentic_runner`; it does not expose a legacy entry point. The baseline Git
repository has no commits and the prototype is untracked. No files have been
staged, committed or published as cleanup.

| Artifact | Observed behavior and dependencies |
| --- | --- |
| `orchestrator.py` | Single-project CLI for `milestone-test`; reads YAML config and JSON schema, takes an `fcntl` lock, selects a progress-table milestone, branches, invokes Codex, validates reports, independently runs project pytest, optionally commits/pushes/creates PR, polls GitHub checks, squash merges and pulls main. Uses PyYAML, jsonschema, Python standard library, Git, gh, Codex and a project `.venv/bin/python` with pytest. |
| `config.yaml` | Hardcoded workspace and operational state roots; currently enables auto commit/push/merge. Codex model is `default`; retry and safety settings are not enforced by the prototype. Never loaded by the new package. |
| `milestone_discovery.py` | Earlier progress-table parser; direct invocation reads the fixed reference roadmap. Standard library only. |
| `create_milestone_branch.py` | Earlier branch step; imports the earlier parser and runs Git in the fixed reference checkout. Standard library plus local module. |
| `run_codex.py` | Hardcoded multiplication milestone prompt, workspace, report/schema and skill paths; deletes an existing report then invokes Codex. Standard library plus Codex CLI. |
| `run_codex_connectivity.py` | Real Codex structured-output probe with fixed workspace and operational report path. Standard library plus Codex CLI; not a unit test. |
| `verify_milestone.py` | Reads an operational report, runs reference project Python/pytest, Git diff and temporary-index staging. Standard library, Git and reference environment's pytest. |
| `commit_milestone.py` | Calls the earlier verifier, requires clean staged assumptions on main, branches, stages all files and commits in the reference checkout. Standard library and Git. |
| `verify_ci.py` | Calls gh API for a fixed GitHub repository/PR and a `test` check on its exact head. Standard library and authenticated gh CLI; live read, not a unit test. |
| `schemas/milestone-result.json` | Draft-07 report with milestone, status, summary, verification booleans, blockers and next action. |
| `skills/milestone-runner/SKILL.md` | Agent workflow: one milestone, preserve work, no publication/deployment, record verification and report. Preserved as prototype data; no legacy workflow was invoked. |

The older scripts are independent workflow experiments, not safe wrappers around
the new package. Their observed runtime requirements are inventoried here, not
installed into `.venv-dev`. Existing environment dependency versions were not
audited. Git/GitHub hooks, credentials and inherited environment behavior remain
legacy risks.

Known gaps confirmed by source inspection:

- Branch creation precedes durable execution-state recording.
- `awaiting_merge` assumes the merge succeeded; an unissued merge cannot reconcile.
- Commit adoption checks ancestry/count/cleanliness without proving ownership/tree.
- Sync requires HEAD equal the earlier merge commit, rejecting later main commits.
- Retry/model/approval configuration is unused; environment and subprocess calls
  inherit host settings. Project pytest runs independently outside Codex isolation.
- Project/file/check/default-branch identities are hardcoded. Reports are not an
  execution or publication security boundary. Durable state lacks versioning,
  parent-directory synchronization and retained completion history.

These are observations, not an exhaustive audit or repaired behavior. Future
milestones implement approved capabilities in the package rather than enabling
the prototype.

[Preservation manifest](../evidence/m1-preservation.json) records SHA-256 for all 11
prototype artifacts and 103 reference files, including Git metadata. The reference
snapshot excludes `.venv`, `__pycache__` and `.pytest_cache`; those directories were
not executed or modified. Operational state was not read, snapshotted or used as
a fixture. Final hash comparison is recorded in the M1 evidence.
