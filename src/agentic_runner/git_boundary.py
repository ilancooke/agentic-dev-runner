"""Runner-owned Git effects, always confined to the configured development ref."""

import json
import os
import stat
from pathlib import Path

from .project import check_process, fingerprint, require
from .repository import Repository
from .supervisor import supervise


def environment():
    env = {k: os.environ[k] for k in ("PATH", "HOME", "CODEX_HOME", "SSH_AUTH_SOCK", "XDG_CONFIG_HOME") if k in os.environ}
    env.update(LANG="C.UTF-8", LC_ALL="C.UTF-8", GIT_TERMINAL_PROMPT="0",
               GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
               GIT_NO_REPLACE_OBJECTS="1", GIT_NO_LAZY_FETCH="1", CI="1")
    return env


class GitBoundary:
    def __init__(self, project, *, process=supervise, env=None):
        self.project, self.process = project, process
        self.root = project.repository
        self.env = environment() if env is None else env
        require(os.getuid() != 0 and self.root.stat().st_uid == os.getuid(), "Run as the non-root checkout owner.")
        require((self.root / ".git").is_dir() and not (self.root / ".git").is_symlink(), "Run requires an ordinary prepared Git checkout; run setup first.")
        repository = Repository(self.root)
        config = repository.config
        require(not any(k.startswith(("filter.", "extensions.")) or k in {"core.sshcommand", "core.gitproxy", "core.worktree"} for k in config),
                "Unsupported Git filters/extensions/command overrides; resolve local config first.")
        urls = config.get("remote.origin.url", [])
        require(len(urls) == 1 and config.get("remote.origin.pushurl", urls) == urls, "Origin must have one identical fetch/push URL.")
        name = project.name
        require(urls[0] in {f"https://github.com/{name}", f"https://github.com/{name}.git", f"git@github.com:{name}.git"}, "Origin does not match the configured GitHub project.")
        require(config.get("remote.origin.mirror", ["false"]) == ["false"], "Mirrored origin is unsupported.")
        self.url = urls[0]
        self.config_hash = fingerprint((self.root / ".git/config").read_bytes())
        require(config.get("user.name", [""])[0].strip() and
                config.get("user.email", [""])[0].endswith("@users.noreply.github.com"), "Configure a repository-local GitHub noreply identity with setup first.")

    def call(self, argv, *, timeout=60):
        result = self.process(list(argv), cwd=self.root, env=self.env, timeout=timeout)
        check_process(result, f"Command failed: {argv[0]} {argv[1]}")
        return result.stdout.decode()

    def git(self, *argv):
        return self.call(["git", "--literal-pathspecs", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
                          "-c", "commit.gpgsign=false", "-c", "core.attributesFile=/dev/null", *argv]).rstrip("\n")

    def head(self):
        return self.git("rev-parse", "HEAD")

    def guard(self, main=None, head=None):
        require(self.git("symbolic-ref", "--quiet", "HEAD") == f"refs/heads/{self.project.development_branch}", "Wrong branch: switch to the configured development branch manually; main is forbidden.")
        require(fingerprint((self.root / ".git/config").read_bytes()) == self.config_hash, "Git configuration changed during execution.")
        if main:
            require(self.git("rev-parse", "refs/heads/main") == main, "Local main changed; intervention required.")
        if head:
            require(self.head() == head, "Unexpected HEAD change; Codex and checks must perform no Git operations.")

    def remote_ref(self, branch):
        text = self.git("ls-remote", "--refs", self.url, f"refs/heads/{branch}")
        rows = text.splitlines()
        require(len(rows) <= 1, "Ambiguous remote ref.")
        return rows[0].split()[0] if rows else None

    def protection(self):
        value = json.loads(self.call(["gh", "api", "--hostname", "github.com", f"repos/{self.project.name}/branches/main/protection"]))
        require(isinstance(value, dict), "GitHub did not return a protection object.")
        reviews = value.get("required_pull_request_reviews")
        require(isinstance(value.get("enforce_admins"), dict) and value["enforce_admins"].get("enabled") is True and isinstance(reviews, dict),
                "Main protection must require pull requests and enforce administrators; run setup or fix protection.")
        bypass = reviews.get("bypass_pull_request_allowances", {})
        require(isinstance(bypass, dict) and not any(bypass.values()), "Main protection has PR bypass allowances.")
        require(all(isinstance(value.get(k), dict) and value[k].get("enabled") is False for k in ("allow_force_pushes", "allow_deletions")), "Main must prohibit force pushes and deletion.")

    def remote_guard(self, main):
        self.protection()
        require(self.remote_ref("main") == main, "Remote main changed; stop for human review.")

    def snapshot(self):
        names = self.git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")
        result = {}
        for name in set(names) - {""}:
            path = self.root / name
            require(path.resolve().is_relative_to(self.root), "Path escapes cannot be published.")
            # Check ancestors explicitly; Git can list files below a replaced directory.
            require(not any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(self.root)), "Symlink changes cannot be published.")
            if not path.exists():
                continue
            info = path.stat()
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, f"Only regular unaliased files are supported: {name}")
            result[name] = [fingerprint(path.read_bytes()), bool(info.st_mode & 0o111)]
        return result

    def index_clean(self):
        require(not self.git("diff", "--cached", "--name-only"), "Unexpected staged changes; Codex must not stage files.")

    def push(self, main):
        self.guard(main)
        self.remote_guard(main)
        self.git("push", "--", self.url, f"HEAD:refs/heads/{self.project.development_branch}")
        require(self.remote_ref(self.project.development_branch) == self.head(), "Push result is uncertain; manual rerun must reconcile it.")
