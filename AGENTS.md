# Repository workflow

Read SPEC.md, ARCHITECTURE.md, ROADMAP.md, PROGRESS.md and HANDOFF.md before editing.
Historical plans and the preserved prototype do not govern new work.

- Implement one revised milestone per session. Test, update progress/handoff,
  commit on the development branch, then stop.
- Never develop, commit, push or merge on main. Humans merge manually.
- No subagents, automatic merges, service, scheduler, dashboard or database.
- Keep Python runtime dependencies empty. Reuse tested helpers where practical.
- Run `.venv-dev/bin/python -m unittest discover -s tests -v` after installation.
- Tests use owned DisposableRoot fixtures. Never use the reference checkout or
  `/home/ilan/agentic-runner-data` as fixtures; never run root prototype scripts.
- Native Codex uses the trusted Ubuntu VM without a sandbox; model gpt-6.1-sol/high.

When managed by the runner, Codex performs no Git/GitHub operations and leaves
completion to the runner. The human-requested checkpoint workflow used to develop
the runner itself may commit on its development branch.
