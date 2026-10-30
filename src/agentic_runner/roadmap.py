"""Deterministic ROADMAP.md grammar and ordered milestone validation."""

import re
from dataclasses import asdict, dataclass

from .diagnostics import DiscoveryError
from .markdown import structure


@dataclass(frozen=True)
class Milestone:
    id: str
    title: str
    status: str
    deliverables: str
    acceptance_criteria: str
    line: int


@dataclass(frozen=True)
class Roadmap:
    milestones: tuple[Milestone, ...]

    @property
    def next_milestone(self) -> str | None:
        return next((m.id for m in self.milestones if m.status != "complete"), None)

    def as_dict(self) -> dict:
        return {"milestones": [asdict(m) for m in self.milestones], "next_milestone": self.next_milestone}


def parse_roadmap(text: str, source: str = "ROADMAP.md") -> Roadmap:
    lines, headings, _ = structure(text, source)

    def fail(code, message, index=0):
        raise DiscoveryError(f"roadmap.{code}", message, source, index + 1)

    top = [h for h in headings if h.level == 2]
    progress = [h for h in top if h.title == "Milestone Progress"]
    if len(progress) != 1:
        fail("progress", "Provide exactly one '## Milestone Progress' section.")
    heading = progress[0]
    if any(h.level == 1 and h.index > heading.index for h in headings):
        fail("heading", "Keep level-one document titles before the progress section; use level-four or deeper headings within requirements.", heading.index)
    end = next((h.index for h in top if h.index > heading.index), len(lines))
    rows = [(i, line.strip()) for i, line in enumerate(lines[heading.index + 1:end], heading.index + 1) if line.strip()]
    if len(rows) < 3 or rows[0][1] != "| Milestone | Status |" or not re.fullmatch(r"\|\s*:?-{3,}:?\s*\|\s*:?-{3,}:?\s*\|", rows[1][1]):
        fail("table", "Use a two-column '| Milestone | Status |' table with a separator and at least one row.", heading.index)
    statuses = {}
    incomplete = False
    for index, row in rows[2:]:
        match = re.fullmatch(r"\|\s*(M[1-9][0-9]*)\s*\|\s*(complete|in progress|not started)\s*\|", row)
        if not match:
            fail("row", "Use an ID M1, M2, … (no leading zeros) and status complete, in progress, or not started.", index)
        identifier, status = match.groups()
        if identifier in statuses:
            fail("duplicate", f"Remove the duplicate progress ID {identifier}.", index)
        if (incomplete and status in {"complete", "in progress"}):
            fail("order", "Completed rows must form a prefix; only the first incomplete row may be in progress.", index)
        incomplete |= status != "complete"
        statuses[identifier] = status
    milestones = []
    seen = set()
    for pos, heading in enumerate(top):
        if heading.title == "Milestone Progress":
            continue
        match = re.fullmatch(r"(M[1-9][0-9]*) — (\S.*)", heading.title)
        if not match:
            if re.match(r"M\d|M\S*\s+—|Milestone\b", heading.title, re.I):
                fail("heading", "Use milestone headings '## M1 — Title' with a nonempty title and an em dash.", heading.index)
            continue
        identifier, title = match.groups()
        if identifier in seen:
            fail("duplicate", f"Remove the duplicate section {identifier}.", heading.index)
        seen.add(identifier)
        end = top[pos + 1].index if pos + 1 < len(top) else len(lines)
        required = {}
        subheads = [h for h in headings if heading.index < h.index < end and h.level == 3]
        for name in ("Deliverables", "Acceptance criteria"):
            hits = [h for h in subheads if h.title == name]
            if len(hits) != 1:
                fail("requirements", f"{identifier} needs exactly one '### {name}' subsection.", heading.index)
            start = hits[0].index
            stop = next((h.index for h in subheads if h.index > start), end)
            body = "\n".join(lines[start + 1:stop]).strip()
            if not body:
                fail("requirements", f"Add nonempty {name} for {identifier}.", start)
            required[name] = body
        milestones.append(Milestone(identifier, title, statuses.get(identifier, ""), required["Deliverables"], required["Acceptance criteria"], heading.index + 1))
    if [m.id for m in milestones] != list(statuses):
        fail("sections", "Progress IDs and milestone section IDs must match exactly once, in the same order.")
    if any(m.line <= progress[0].index + 1 for m in milestones):
        fail("sections", "Put milestone sections after the progress table.")
    return Roadmap(tuple(milestones))
