import subprocess
import sys
from pathlib import Path

RUNNER = Path(__file__).resolve().parent
PROJECT = Path.home() / "agentic-workspaces/milestone-test"
BRANCH = "agent/milestone-1-calculator"


def git(*args):
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def main():
    # Verify before making any Git changes.
    result = subprocess.run(
        [sys.executable, str(RUNNER / "verify_milestone.py")],
        check=False,
    )

    if result.returncode != 0:
        sys.exit("Verification failed. No commit created.")

    if git("branch", "--show-current") != "main":
        sys.exit("Expected to start on main. No commit created.")

    if git("status", "--porcelain", "--untracked-files=all").strip() == "":
        sys.exit("No changes to commit.")

    # Preserve main by committing on a dedicated branch.
    git("switch", "-c", BRANCH)
    git("add", "-A")
    git("commit", "-m", "Implement calculator milestone")

    print("\nCommit created successfully.")
    print(f"Branch: {git('branch', '--show-current')}")
    print(f"Commit: {git('rev-parse', '--short', 'HEAD')}")
    print(f"Status: {git('status', '--short') or 'clean'}")


if __name__ == "__main__":
    main()
