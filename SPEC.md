# Minimal Ralph runner

A human launches the CLI, which implements successive ROADMAP.md milestones until
complete or blocked. Each milestone gets a fresh headless Codex session. Failed
work survives; the next manual launch resumes from documents and files.

Package-level TOML configuration declares GitHub project name (`owner/repository`),
local checkout, development branch and explicit verification argument vectors.
Required root documents: AGENTS.md, SPEC.md, ARCHITECTURE.md, ROADMAP.md, PROGRESS.md.
All must be nonempty regular files.

One-time setup is separate: validate documents, initialize Git if necessary,
create/connect origin if absent, configure local GitHub noreply identity, establish
and protect main, then create/switch to dev. Never replace existing remotes or
conflicting branches silently. Only setup may establish the initial main baseline.

Codex implements only the selected milestone, runs checks, updates PROGRESS.md and
returns status, summary, blockers and proposed commit message. It performs no Git
or GitHub operations. The runner independently checks the report, branch, HEAD,
documents and changed files and runs configured verification. Only after success
does it mark completion, commit and push explicitly to dev.

Run never checks out, modifies, commits, pushes, reconciles or merges main.
GitHub protection must require PRs, include administrators, exclude PR bypasses,
and prohibit force pushes/deletions. Missing protection evidence stops execution.
Existing protections must never be weakened.

Failures record the milestone and issue and preserve files. No destructive rollback,
force push, PR automation, subagents, automatic retries/quota scheduling, persistent
service, dashboard or database. Selected code and the VM account are trusted;
unsandboxed account access is not hostile-code isolation.
