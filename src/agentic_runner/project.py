"""Explicit project configuration for the small foreground runner."""

import hashlib
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


DOCUMENTS = ("AGENTS.md", "SPEC.md", "ARCHITECTURE.md", "ROADMAP.md", "PROGRESS.md")
CONTROLS = DOCUMENTS[:-1]


class RunnerError(ValueError):
    """Stop, retain work, and explain what the operator must resolve."""


def require(condition, message):
    if not condition:
        raise RunnerError(message)


def check_process(result, description):
    if result.stopped or result.returncode:
        error = RunnerError(f"{description} (exit {result.returncode}, stopped={result.stopped}); partial work retained.")
        error.process = result
        raise error


def fingerprint(data):
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True)
class Project:
    name: str
    repository: Path
    development_branch: str
    verification: tuple[tuple[str, ...], ...]
    config: Path
    config_hash: str

    @classmethod
    def load(cls, filename):
        path = Path(filename).resolve(strict=True)
        data = path.read_bytes()
        value = tomllib.loads(data.decode())
        require(set(value) == {"project"} and isinstance(value["project"], dict), "Use one [project] table.")
        value = value["project"]
        require(set(value) == {"name", "repository", "development_branch", "verification"},
                "Project requires name, repository, development_branch and verification only.")
        name, branch, repo, commands = (value[k] for k in ("name", "development_branch", "repository", "verification"))
        require(isinstance(name, str) and re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", name), "Name must be GitHub owner/repository.")
        require(isinstance(branch, str) and branch.lower() != "main" and
                re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_/-]*", branch) and "//" not in branch,
                "Use a simple development branch distinct from main.")
        require(isinstance(repo, str) and repo.strip(), "Repository path is required.")
        require(isinstance(commands, list) and commands and all(isinstance(c, list) and c and
                all(isinstance(a, str) and a and "\0" not in a for a in c) for c in commands),
                "Verification must be a nonempty list of nonempty argv lists.")
        return cls(name, (path.parent / repo).resolve(), branch, tuple(tuple(c) for c in commands), path, fingerprint(data))

    def documents(self):
        result = {}
        for name in DOCUMENTS:
            path = self.repository / name
            require(path.is_file() and not path.is_symlink() and path.stat().st_nlink == 1,
                    f"Required document must be a regular unaliased file: {name}")
            result[name] = path.read_text()
            require(result[name].strip(), f"Required document is empty: {name}")
        return result
