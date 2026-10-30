"""Small structural Markdown scanner; requirement bodies remain unmodified text."""

import re
from dataclasses import dataclass

from .diagnostics import DiscoveryError


@dataclass(frozen=True)
class Heading:
    level: int
    title: str
    index: int


def structure(text: str, source: str) -> tuple[list[str], list[Heading], set[int]]:
    lines = text.splitlines()
    headings = []
    fenced = set()
    fence = None
    for index, line in enumerate(lines):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            fenced.add(index)
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
            continue
        if match:
            fence = match[1]
            fenced.add(index)
            continue
        heading = re.match(r"^ {0,3}(#{1,6}) (.+?)\s*$", line)
        if heading:
            headings.append(Heading(len(heading[1]), heading[2], index))
    if fence:
        raise DiscoveryError("markdown.fence", "Close the unterminated fenced code block.", source, len(lines))
    return lines, headings, fenced


def section_texts(text: str, title: str, source: str) -> list[str]:
    lines, headings, _ = structure(text, source)
    result = []
    for pos, heading in enumerate(headings):
        if heading.level == 2 and heading.title == title:
            end = next((h.index for h in headings[pos + 1:] if h.level <= 2), len(lines))
            result.append("\n".join(lines[heading.index + 1:end]).strip())
    return result
