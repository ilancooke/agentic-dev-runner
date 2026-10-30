import re
from pathlib import Path

VALID_STATUSES = {"not started", "in progress", "complete"}


def find_next_milestone(roadmap_path: Path):
    text = roadmap_path.read_text(encoding="utf-8")

    match = re.search(
        r"^## Milestone Progress\s*$"
        r"(.*?)(?=^## |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )

    if not match:
        raise ValueError("Milestone Progress section not found")

    milestones = []

    for line in match.group(1).splitlines():
        if not line.startswith("|"):
            continue

        columns = [c.strip() for c in line.strip().strip("|").split("|")]

        if len(columns) != 2:
            continue

        name, status = columns
        status = status.lower()

        if status not in VALID_STATUSES:
            continue

        milestones.append({
            "name": name,
            "status": status,
        })

    if not milestones:
        raise ValueError("No valid milestones found")

    for milestone in milestones:
        if milestone["status"] != "complete":
            return milestone

    return None


if __name__ == "__main__":
    roadmap = Path.home() / "agentic-workspaces/milestone-test/ROADMAP.md"

    milestone = find_next_milestone(roadmap)

    if milestone:
        print(f"Next milestone: {milestone['name']}")
        print(f"Status: {milestone['status']}")
    else:
        print("All milestones complete.")
