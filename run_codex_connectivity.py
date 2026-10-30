import json
import subprocess
import sys
from pathlib import Path

RUNNER_DIR = Path(__file__).resolve().parent
SCHEMA = RUNNER_DIR / "schemas/milestone-result.json"
OUTPUT = Path.home() / "agentic-runner-data/test-result.json"
WORKSPACE = Path.home() / "agentic-workspaces"

PROMPT = """
This is a structured-output connectivity test.

Do not modify any files or execute commands.

Return a milestone completion report with:
- milestone: "connectivity-test"
- status: "complete"
- summary: "Codex structured output works"
- checks_passed: true
- acceptance_criteria_met: true
- blockers: []
- next_action: "Ready for milestone integration"
"""

def main():
    command = [
        "codex", "exec",
        "--skip-git-repo-check",
        "--sandbox", "read-only",
        "--output-schema", str(SCHEMA),
        "--output-last-message", str(OUTPUT),
        PROMPT,
    ]

    print("Starting Codex structured-output test...", flush=True)

    result = subprocess.run(
        command,
        cwd=WORKSPACE,
        check=False,
    )

    if result.returncode != 0:
        print(f"Codex failed with exit code {result.returncode}")
        sys.exit(result.returncode)

    data = json.loads(OUTPUT.read_text())

    print("\nStructured result:")
    print(json.dumps(data, indent=2))

if __name__ == "__main__":
    main()
