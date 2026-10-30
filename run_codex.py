import json
import subprocess
import sys
from pathlib import Path

RUNNER_DIR = Path(__file__).resolve().parent
WORKSPACE = Path.home() / "agentic-workspaces/milestone-test"
OUTPUT = Path.home() / "agentic-runner-data/milestone-test-result.json"
SCHEMA = RUNNER_DIR / "schemas/milestone-result.json"
SKILL = RUNNER_DIR / "skills/milestone-runner/SKILL.md"

PROMPT = f"""
Execute Milestone 2 — Multiplication from ROADMAP.md.

Follow the milestone execution procedure in:
{SKILL}

This repository is already on its dedicated milestone branch.

Requirements:
- Implement only Milestone 2.
- Preserve existing calculator behavior.
- Use the existing Python 3.11 virtual environment.
- Run tests using .venv/bin/python -m pytest -q.
- Update ROADMAP.md and relevant documentation.
- Do not commit, push, merge, or deploy.
- Do not modify files outside this repository.
- Return a structured completion report matching the supplied schema.
"""


def main():
    if OUTPUT.exists():
        OUTPUT.unlink()

    command = [
        "codex", "exec",
        "--sandbox", "workspace-write",
        "--output-schema", str(SCHEMA),
        "--output-last-message", str(OUTPUT),
        PROMPT,
    ]

    print(f"Running milestone in {WORKSPACE}", flush=True)

    result = subprocess.run(
        command,
        cwd=WORKSPACE,
        check=False,
    )

    if result.returncode != 0:
        print(f"Codex exited with code {result.returncode}")
        sys.exit(result.returncode)

    if not OUTPUT.is_file():
        sys.exit("Codex did not produce a completion report.")

    data = json.loads(OUTPUT.read_text())

    print("\nMilestone result:")
    print(json.dumps(data, indent=2))

    if (
        data["status"] != "complete"
        or not data["checks_passed"]
        or not data["acceptance_criteria_met"]
    ):
        sys.exit("Milestone not verified as complete.")

if __name__ == "__main__":
    main()
