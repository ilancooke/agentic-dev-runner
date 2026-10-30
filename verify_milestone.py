import json
import subprocess
import sys
from pathlib import Path


PROJECT = Path.home() / "agentic-workspaces/milestone-test"
REPORT = Path.home() / "agentic-runner-data/milestone-test-result.json"
PYTHON = PROJECT / ".venv/bin/python"


def run(command):
    print(f"\n$ {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=PROJECT, check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {command}")
    return result


def main():
    report = json.loads(REPORT.read_text())

    expected = sys.argv[1] if len(sys.argv) > 1 else None

    if not expected:
        sys.exit("FAIL: Expected milestone must be provided.")

    if report["milestone"] != expected:
        sys.exit(
            f"FAIL: Expected {expected!r}, "
            f"received {report['milestone']!r}"
        )

    if not (
        report["status"] == "complete"
        and report["checks_passed"]
        and report["acceptance_criteria_met"]
        and not report["blockers"]
    ):
        sys.exit("FAIL: Codex did not report verified completion.")

    if not PYTHON.is_file():
        sys.exit("FAIL: Project Python environment is missing.")

    run([str(PYTHON), "--version"])
    run([str(PYTHON), "-m", "pytest", "-q"])
    run(["git", "diff", "--check"])

    # Include untracked files in validation by staging them
    # in a temporary Git index, without changing the real index.
    import os
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        env = os.environ.copy()
        env["GIT_INDEX_FILE"] = str(Path(tmp) / "index")

        def git(*args):
            result = subprocess.run(
                ["git", *args],
                cwd=PROJECT,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )
            return result.stdout

        git("read-tree", "HEAD")
        git("add", "-A")
        whitespace_errors = git("diff", "--cached", "--check")

        if whitespace_errors:
            sys.exit(f"FAIL: Whitespace errors:\n{whitespace_errors}")

        staged_changes = git("diff", "--cached", "--name-only")
        if not staged_changes.strip():
            sys.exit("FAIL: No milestone changes found.")

        print("\nFiles verified:")
        print(staged_changes)

    print("\nPASS: Independent milestone checks succeeded.")


if __name__ == "__main__":
    main()
