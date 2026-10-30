---
name: milestone-runner
description: Execute one approved software development milestone, verify acceptance criteria, and produce a durable handoff.
---

# Milestone Runner

## Objective

Implement exactly one approved milestone from the project's roadmap.

## Startup

1. Read the repository's AGENTS.md, if present.
2. Read the README and ROADMAP.
3. Identify the first incomplete milestone.
4. Read its dependencies, relevant specifications, and previous handoff.
5. Inspect Git status and preserve existing work.

## Implementation

- Stay within the approved milestone scope.
- Follow existing architecture and coding conventions.
- Write and run relevant automated tests.
- Resolve implementation and test failures when possible.
- Do not begin subsequent milestones.
- Do not commit, push, merge, or deploy.
- Do not perform destructive operations or access production credentials.

## Verification

Before declaring completion:

1. Verify each acceptance criterion against concrete evidence.
2. Run the relevant project test suite.
3. Record tests and commands executed.
4. Identify untested assumptions and remaining risks.
5. Update the roadmap, checkpoint, and handoff documentation.

Do not mark a milestone complete when required verification is missing.

## Completion

Return a structured result matching the orchestrator's
milestone-result.json schema.

Use:
- complete: All acceptance criteria and required checks passed.
- blocked: External action, approval, or missing information is required.
- failed: Implementation or verification failed and cannot be resolved.

Include a concise summary, blockers, and exact next action.
