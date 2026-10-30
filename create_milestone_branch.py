import re
import subprocess
from pathlib import Path

from milestone_discovery import find_next_milestone

PROJECT = Path.home() / "agentic-workspaces/milestone-test"


def git(*args):
    return subprocess.run(
        ["git", *args],
        cwd=PROJECT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def main():
    if git("branch", "--show-current") != "main":
        raise RuntimeError("Expected main branch")

    if git("status", "--porcelain"):
        raise RuntimeError("Working tree is not clean")

    milestone = find_next_milestone(PROJECT / "ROADMAP.md")

    if milestone is None:
        print("All milestones complete.")
        return

    name = milestone["name"]

    number = re.match(r"^(\d+)", name)
    if not number:
        raise ValueError(f"Invalid milestone name: {name}")

    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    branch = f"agent/{slug}"

    # Refuse to overwrite an existing branch.
    existing = git("branch", "--list", branch)
    if existing:
        raise RuntimeError(f"Branch already exists: {branch}")

    git("switch", "-c", branch)

    print(f"Created branch: {branch}")
    print(f"Milestone: {name}")
    print(f"Starting commit: {git('rev-parse', '--short', 'HEAD')}")


if __name__ == "__main__":
    main()
