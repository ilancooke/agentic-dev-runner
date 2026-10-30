"""Generated M2 projects and guarded Git metadata setup; never use real remotes."""

import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from .fixtures import FixtureFactory
from .isolation import DisposableRoot


ROADMAP = """# Example project

## Milestone Progress

| Milestone | Status |
| --- | --- |
| M1 | complete |
| M2 | not started |

## M1 — Baseline

### Deliverables

Preserve the baseline.

### Acceptance criteria

Baseline passes.

## M2 — Feature

### Deliverables

Implement the feature.

### Acceptance criteria

The declared checks pass.
"""


def git_fixture(root: DisposableRoot, repository: Path, *arguments: str) -> str:
    """Trusted fixture setup only, with no transport or project execution verbs."""
    if not arguments or arguments[0] not in {"add", "commit", "symbolic-ref", "update-ref", "pack-refs"}:
        raise ValueError("Unsupported fixture Git operation")
    cwd = root.require(repository)
    root.require(cwd / ".git")
    executable = shutil.which("git", path=os.defpath)
    result = subprocess.run(
        [executable, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", *arguments],
        cwd=cwd, env=FixtureFactory(root).environment(), capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def make_project(root: DisposableRoot, *, family="python", branch="main", target="repositories/project") -> Path:
    if not re.fullmatch(r"[a-z][a-z0-9-]*(?:/[a-z][a-z0-9-]*)*", branch):
        raise ValueError("Use a simple fixture branch name")
    project = FixtureFactory(root).repository(target)
    root.write_text(project / "ROADMAP.md", ROADMAP)
    if family == "python":
        root.write_text(project / "pyproject.toml", '[project]\nname = "fixture"\nversion = "0.0.0"\nrequires-python = ">=3.11,<3.13"\n')
        root.write_text(project / "README.md", "# Python fixture\n\n## Verification\n\n```sh\npython -m pytest -q\n```\n")
        manifest = "pyproject.toml"
    elif family == "node":
        root.write_text(project / "package.json", json.dumps({"name": "web-fixture", "engines": {"node": ">=22 <23"}, "scripts": {"test": "node --test"}}) + "\n")
        root.write_text(project / "README.md", "# Web fixture\n")
        manifest = "package.json"
    else:
        raise ValueError("Unknown fixture family")
    config = project / ".git/config"
    root.write_text(config, config.read_text() + '[user]\n\tname = Fixture\n\temail = fixture@example.invalid\n[remote "origin"]\n\turl = https://example.invalid/fixtures/project.git\n\tfetch = +refs/heads/*:refs/remotes/origin/*\n')
    git_fixture(root, project, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    git_fixture(root, project, "add", "--", "README.md", "ROADMAP.md", manifest)
    git_fixture(root, project, "commit", "--no-gpg-sign", "-m", "Generated fixture baseline")
    git_fixture(root, project, "update-ref", f"refs/remotes/origin/{branch}", "HEAD")
    git_fixture(root, project, "symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{branch}")
    return project


def make_worktree(root: DisposableRoot, project: Path) -> Path:
    target = root.require("worktrees/linked")
    root.mkdir(target.parent)
    executable = shutil.which("git", path=os.defpath)
    subprocess.run(
        [executable, "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false", "worktree", "add", "--detach", str(root.require(target)), "HEAD"],
        cwd=root.require(project), env=FixtureFactory(root).environment(), capture_output=True, text=True, check=True,
    )
    return target
