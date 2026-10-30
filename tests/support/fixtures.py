"""Generated repositories/state and clean subprocess environments for runner tests."""

import os
import shutil
import subprocess
from pathlib import Path

from .isolation import DisposableRoot, IsolationError


class FixtureFactory:
    def __init__(self, root: DisposableRoot) -> None:
        self.root = root

    def environment(self) -> dict[str, str]:
        home = self.root.mkdir("home")
        tmp = self.root.mkdir("tmp")
        return {
            "PATH": os.defpath,
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "TMPDIR": str(tmp),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }

    def state(self, target: str | Path = "state") -> Path:
        return self.root.mkdir(target)

    def repository(self, target: str | Path = "repositories/project") -> Path:
        # Check before mkdir, environment creation, or invoking Git.
        path = self.root.require(target)
        if path.exists():
            raise IsolationError("Repository fixture must be a new directory")
        executable = shutil.which("git", path=os.defpath)
        if executable is None:
            raise RuntimeError("Git is required for disposable repository fixtures")
        env = self.environment()
        path = self.root.mkdir(path)
        self.root.require(path)
        subprocess.run(
            [executable, "-c", "core.hooksPath=/dev/null", "init", "--template=", "--initial-branch=main", str(path)],
            cwd=self.root.require(path), env=env, check=True, capture_output=True, text=True,
        )
        # Empty repository by design: future discovery tests supply their own content.
        return path
