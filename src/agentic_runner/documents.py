"""Bounded read-only source inventory and local requirement-link closure."""

import hashlib
import os
import re
import stat
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .diagnostics import DiscoveryError
from .markdown import structure


MAX_BYTES = 1024 * 1024
MAX_DOCUMENTS = 256
SKIP_DIRECTORIES = {".git", ".venv", ".venv-dev", "node_modules", "__pycache__", ".tox", ".pytest_cache", "build", "dist"}


def read_file(path: Path) -> bytes:
    try:
        if not stat.S_ISREG(path.stat().st_mode):
            raise DiscoveryError("source.type", "Use a regular file as discovery evidence.", str(path))
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise DiscoveryError("source.size", "Discovery evidence exceeds the 1 MiB per-file limit; split the document.", str(path))
        return data
    except OSError as exc:
        raise DiscoveryError("source.read", "Cannot read required evidence; check the path and permissions.", str(path)) from exc


def read_text(path: Path) -> str:
    try:
        return read_file(path).decode("utf-8")
    except UnicodeError as exc:
        raise DiscoveryError("source.encoding", "Use UTF-8 for textual discovery evidence.", str(path)) from exc


def inside(root: Path, path: Path) -> Path:
    try:
        resolved = path.resolve()
    except (OSError, RuntimeError) as exc:
        raise DiscoveryError("source.path", "Cannot resolve evidence path.", str(path)) from exc
    if not resolved.is_relative_to(root) or ".git" in resolved.relative_to(root).parts:
        raise DiscoveryError("source.escape", "Keep local evidence links inside the worktree and outside Git metadata.", str(path))
    return resolved


def markdown_links(text: str, source: str, *, include_images: bool = False) -> list[str]:
    lines, _, fenced = structure(text, source)
    prose = "\n".join(re.sub(r"`+[^`]*`+", "", line) for i, line in enumerate(lines) if i not in fenced)
    targets = []
    pattern = r"!?\[[^\]\n]*\]\(" if include_images else r"(?<!!)\[[^\]\n]*\]\("
    for match in re.finditer(pattern, prose):
        start = match.end()
        depth = 1
        end = start
        while end < len(prose) and depth:
            char = prose[end]
            if char == "(" and (end == 0 or prose[end - 1] != "\\"):
                depth += 1
            if char == ")" and (end == 0 or prose[end - 1] != "\\"):
                depth -= 1
            end += 1
        if depth == 0:
            value = prose[start:end - 1].strip()
            if value:
                targets.append(value[1:value.index(">")] if value.startswith("<") and ">" in value else value.split()[0])
    for match in re.finditer(r"^ {0,3}\[[^\]]+\]:\s*(<[^>]+>|\S+)", prose, re.M):
        targets.append(match[1].strip("<>"))
    return targets


class Documents:
    def __init__(self, root: Path):
        self.root = root
        self.records: dict[str, dict] = {}
        self.texts: dict[str, str] = {}
        self.external_links: set[str] = set()

    def add(self, path: Path, kind: str, *, ancestor: bool = False, scope: str | None = None) -> str:
        if path.is_symlink() and kind == "instructions":
            raise DiscoveryError("instructions.symlink", "Use a regular AGENTS.md file, not a symlink.", str(path))
        resolved = path if ancestor else inside(self.root, path)
        if path.is_symlink():
            raise DiscoveryError("source.symlink", "Use regular evidence files so their paths and formats are unambiguous.", str(path))
        path = resolved
        key = str(path.relative_to(self.root)) if path.is_relative_to(self.root) else str(path)
        if key in self.records:
            return key
        if len(self.records) >= MAX_DOCUMENTS:
            raise DiscoveryError("source.count", "Reduce evidence to at most 256 files.", str(self.root))
        data = read_file(path)
        record = {"path": key, "kind": kind, "sha256": hashlib.sha256(data).hexdigest(), "scope": scope}
        self.records[key] = record
        if path.suffix.lower() in {".md", ".txt", ".toml", ".json", ".yaml", ".yml"} or path.name in {".python-version", ".node-version", ".nvmrc"}:
            try:
                self.texts[key] = data.decode("utf-8")
            except UnicodeError as exc:
                raise DiscoveryError("source.encoding", "Use UTF-8 for textual discovery evidence.", key) from exc
        return key

    def collect(self) -> None:
        self.add(self.root / "ROADMAP.md", "roadmap")
        for parent in reversed(self.root.parents):
            path = parent / "AGENTS.md"
            if path.exists() or path.is_symlink():
                self.add(path, "instructions", ancestor=True, scope=".")
        def scan_error(error):
            raise DiscoveryError("source.scan", "Cannot scan instructions/documents; check directory permissions.", str(error.filename)) from error

        entries = 0
        for current, directories, files in os.walk(self.root, followlinks=False, onerror=scan_error):
            directories[:] = sorted(d for d in directories if d not in SKIP_DIRECTORIES)
            for directory in directories:
                path = Path(current) / directory
                if path.is_symlink():
                    raise DiscoveryError("source.symlink_directory", "Resolve symlinked source directories explicitly so scoped instructions cannot be skipped.", str(path))
            entries += len(directories) + len(files)
            if entries > 20000:
                raise DiscoveryError("source.scan", "Worktree scan exceeds 20000 entries; exclude generated content using supported directories.", str(self.root))
            directory = Path(current)
            for name in sorted(files):
                path = directory / name
                relative = path.relative_to(self.root)
                if name == "AGENTS.md":
                    self.add(path, "instructions", scope=str(relative.parent))
                elif name in {"README.md", "HANDOFF.md", "CHECKPOINT.md"} or (relative.parts[0] == "docs" and path.suffix == ".md"):
                    self.add(path, "supporting")
                elif relative.parts[:2] == (".github", "workflows") and path.suffix in {".yaml", ".yml"}:
                    self.add(path, "ci")
        # Follow Markdown links recursively, including reference-style definitions.
        visited = set()
        while True:
            pending = [k for k in self.texts if k.endswith(".md") and k not in visited]
            if not pending:
                break
            for key in pending:
                visited.add(key)
                # Ancestor instructions apply, but may refer outside the project;
                # those links require review rather than opening arbitrary host files.
                for target in markdown_links(self.texts[key], key):
                    try:
                        parsed = urlsplit(target)
                    except ValueError as exc:
                        raise DiscoveryError("source.link", "Correct the malformed link target.", key) from exc
                    if parsed.scheme or parsed.netloc:
                        self.external_links.add(target)
                        continue
                    if not parsed.path:
                        continue
                    path = Path(key)
                    origin = path if path.is_absolute() else self.root / path
                    linked = origin.parent / unquote(parsed.path)
                    self.add(linked, "requirement")

    def as_list(self) -> list[dict]:
        return [self.records[k] for k in sorted(self.records)]
