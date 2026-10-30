"""Local Git identity discovery, with fixed read-only operations and no transport."""

import hashlib
import os
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from .diagnostics import DiscoveryError
from .documents import read_file, read_text


class Repository:
    def __init__(self, target: Path):
        try:
            target = target.resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise DiscoveryError("repository.path", "Supply an existing checkout directory.", str(target)) from exc
        if not target.is_dir():
            raise DiscoveryError("repository.path", "Supply a checkout directory, not a file.", str(target))
        self.root = next((p for p in (target, *target.parents) if (p / ".git").exists()), None)
        if self.root is None:
            raise DiscoveryError("repository.missing", "Initialize or select a non-bare Git checkout.", str(target))
        marker = self.root / ".git"
        if marker.is_symlink():
            raise DiscoveryError("repository.gitdir", "A symlinked .git is unsupported; use a directory or worktree gitdir file.", str(marker))
        if marker.is_file():
            value = read_text(marker).strip()
            if not value.startswith("gitdir: "):
                raise DiscoveryError("repository.gitdir", "Expected a Git worktree gitdir pointer.", str(marker))
            self.git_dir = (self.root / value[8:]).resolve()
        else:
            self.git_dir = marker.resolve()
        common = self.git_dir / "commondir"
        self.common_dir = (self.git_dir / read_text(common).strip()).resolve() if common.exists() else self.git_dir
        self.executable = shutil.which("git", path=os.defpath)
        if not self.executable:
            raise DiscoveryError("repository.git", "Install Git before running discovery.", str(self.root))
        config = self.common_dir / "config"
        read_file(config)  # Bound config size before asking system Git to parse it.
        entries = self._run(["config", "--file", str(config), "--no-includes", "--null", "--list"])
        self.config: dict[str, list[str]] = {}
        for entry in entries.split("\0"):
            if entry:
                key, _, value = entry.partition("\n")
                self.config.setdefault(key, []).append(value)
        if any(k.startswith(("include.", "includeif.", "url.")) for k in self.config):
            raise DiscoveryError("repository.config", "Resolve include/URL-rewrite ambiguity into explicit local metadata before discovery.", str(config))
        if self.config.get("extensions.worktreeconfig", ["false"])[0].lower() != "false":
            raise DiscoveryError("repository.config", "Worktree-specific Git config is unsupported; resolve its identity explicitly.", str(config))
        if self.config.get("core.bare", ["false"])[0].lower() in {"true", "yes", "on", "1"}:
            raise DiscoveryError("repository.bare", "Select a non-bare checkout for roadmap discovery.", str(config))

    def _run(self, arguments: list[str], *, optional: bool = False, binary: bool = False):
        env = {
            "PATH": os.defpath, "HOME": "/dev/null", "XDG_CONFIG_HOME": "/dev/null",
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1",
        }
        command = [self.executable, "--no-pager", "--no-optional-locks", f"--git-dir={self.git_dir}", f"--work-tree={self.root}",
                   "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", *arguments]
        try:
            result = subprocess.run(command, cwd=self.root, env=env, check=False, capture_output=True, text=not binary, timeout=10)
        except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
            raise DiscoveryError("repository.git", "Local Git inspection failed or timed out; inspect repository metadata.", str(self.root)) from exc
        if result.returncode:
            if optional and result.returncode == 1:
                return b"" if binary else ""
            raise DiscoveryError("repository.metadata", "Cannot resolve local Git evidence; ensure HEAD/default refs and config are valid. No fetch was attempted.", str(self.root))
        return result.stdout if binary else result.stdout.rstrip("\r\n")

    def discover(self) -> dict:
        names = {key[len("remote."):].rsplit(".", 1)[0] for key in self.config if key.startswith("remote.")}
        if len(names) != 1:
            raise DiscoveryError("repository.remotes", "Provide exactly one remote with one URL; multiple/missing remotes require explicit resolution.", str(self.common_dir / "config"))
        name = next(iter(names))
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name):
            raise DiscoveryError("repository.remote", "Use a simple remote name containing letters, digits, dots, underscores or hyphens.", str(self.common_dir / "config"))
        urls = self.config.get(f"remote.{name}.url", [])
        pushes = self.config.get(f"remote.{name}.pushurl", urls)
        if len(urls) != 1 or pushes != urls:
            raise DiscoveryError("repository.remotes", "Resolve multiple fetch/push URLs into one unambiguous remote identity.", str(self.common_dir / "config"))
        url = urls[0]
        try:
            parsed = urlsplit(url)
        except ValueError as exc:
            raise DiscoveryError("repository.remote", "Correct the remote URL syntax.", str(self.common_dir / "config")) from exc
        valid = parsed.scheme in {"https", "ssh"} and bool(parsed.hostname)
        valid |= bool(re.fullmatch(r"[A-Za-z0-9._-]+@[A-Za-z0-9.-]+:[^\s]+", url))
        if not valid or re.search(r"\s", url) or parsed.password or (parsed.scheme == "https" and parsed.username) or parsed.query or parsed.fragment:
            raise DiscoveryError("repository.remote", "Use a credential-free HTTPS/SSH remote URL; local paths and remote helpers are unsupported.", str(self.common_dir / "config"))
        remote_head = self._run(["symbolic-ref", "--quiet", f"refs/remotes/{name}/HEAD"], optional=True)
        prefix = f"refs/remotes/{name}/"
        if not remote_head.startswith(prefix) or remote_head == prefix + "HEAD":
            raise DiscoveryError("repository.default", "Record the remote default branch in the local refs/remotes/<remote>/HEAD symbolic ref; discovery never guesses main or contacts the server.", str(self.root))
        default = remote_head[len(prefix):]
        default_oid = self._run(["show-ref", "--verify", "--hash", remote_head])
        head_oid = self._run(["rev-parse", "--verify", "HEAD"])
        branch_ref = self._run(["symbolic-ref", "--quiet", "HEAD"], optional=True)
        identity = hashlib.sha256(f"{self.common_dir}\0{url}".encode()).hexdigest()
        return {
            "id": identity, "root": str(self.root), "git_dir": str(self.git_dir), "common_dir": str(self.common_dir),
            "head": head_oid, "branch": branch_ref.removeprefix("refs/heads/") or None,
            "remote": {"name": name, "url": url}, "default_branch": default,
            "default_branch_oid": default_oid, "default_branch_source": f"refs/remotes/{name}/HEAD",
        }
