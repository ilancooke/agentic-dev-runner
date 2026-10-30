"""Supervised execution for the approved single-user, trusted development VM.

This adapter is deliberately not a hostile-code sandbox. The dedicated VM is the
boundary; Codex and project commands run with the development account's access.
"""

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from .execution import refuse
from .redaction import public_process
from .state_boundary import PROTECTED, overlaps
from .supervisor import supervise


@dataclass(frozen=True)
class NativePolicy:
    home: str
    codex_home: str
    timeout: int = 600
    output_limit: int = 4 * 1024 * 1024
    codex_binary: str = "/home/ilan/.local/bin/codex"
    codex_sha256: str = "b8a11fedf24b2dfb59a70c9e52b030f9a508dcd49cd2dd0d41956f4c785156b8"
    codex_sandbox: str = "disabled"

    def record(self):
        for path in (self.home, self.codex_home):
            if not isinstance(path, str) or not Path(path).is_absolute() or str(Path(path).resolve()) != path:
                refuse("native_policy", "Use explicit canonical account and Codex home paths.")
        if not isinstance(self.codex_binary, str) or not Path(self.codex_binary).is_absolute() or not re.fullmatch(r"[0-9a-f]{64}", self.codex_sha256):
            refuse("native_policy", "Pin an absolute Codex executable and its SHA-256.")
        if type(self.timeout) is not int or not 1 <= self.timeout <= 3600 or type(self.output_limit) is not int or not 1024 <= self.output_limit <= 8 * 1024 * 1024:
            refuse("native_policy", "Native execution limits are invalid.")
        if self.codex_sandbox not in {"disabled", "workspace-write"}:
            refuse("native_policy", "Unknown native sandbox policy.")
        # Preserve the earlier, never-deployed native prototype for state inspection.
        return {"version": 2 if self.codex_sandbox == "disabled" else 1, "mode": "trusted-vm", "home": self.home, "codex_home": self.codex_home,
                "timeout": self.timeout, "output_limit": self.output_limit, "user": "current-non-root",
                "codex_sandbox": self.codex_sandbox, "network": "development", "docker": "host-engine",
                "credentials": "existing-development-account", "codex_binary": self.codex_binary,
                "codex_sha256": self.codex_sha256}


class NativeExecutor:
    def __init__(self, policy, *, runner=supervise, use_account_home=False):
        self.policy = policy
        policy.record()
        self.runner = runner
        # Explicit integration capability: ordinary unit tests never consume user auth.
        self.use_account_home = use_account_home

    def guard(self, store):
        store._usable()
        root = store.repository.root
        if root.resolve() != root or any(overlaps(root, p.resolve()) for p in PROTECTED):
            refuse("native_target", "Native execution cannot target protected or aliased checkouts.")
        store.boundary.check_repository(store.repository)
        if os.getuid() == 0 or root.stat().st_uid != os.getuid():
            refuse("native_user", "Run native jobs as the non-root checkout owner.")
        if store.boundary.disposable is not None:
            store.boundary.disposable.require(root)
            if not self.use_account_home:
                store.boundary.disposable.require(self.policy.home)
                store.boundary.disposable.require(self.policy.codex_home)
            else:
                import pwd
                home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
                if Path(self.policy.home) != home or Path(self.policy.codex_home) != home / ".codex":
                    refuse("native_auth", "Real integration must use the existing development account, without copied credentials.")
        return root

    def environment(self, checkout, scratch):
        # File-backed gh/Codex auth is intentionally available under the accepted trust
        # model. Arbitrary inherited cloud/token/proxy/Git variables are not copied.
        return {"PATH": str(checkout / ".venv/bin") + os.pathsep + "/usr/local/bin:/usr/bin:/bin",
                "HOME": self.policy.home, "CODEX_HOME": self.policy.codex_home,
                "TMPDIR": str(scratch), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
                "GIT_TERMINAL_PROMPT": "0", "PIP_DISABLE_PIP_VERSION_CHECK": "1", "CI": "1"}

    def scratch(self, store):
        self.guard(store)
        path = store.path / "execution-scratch"
        store.io.mkdir(path)
        return path

    def execute(self, store, revision, argv, *, purpose="implement", input_bytes=None, cancel=None, validate=None, metadata=None):
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a and "\0" not in a for a in argv) or argv[0].startswith("-"):
            refuse("argv", "Provide a literal native argument vector.")
        if input_bytes is not None and (not isinstance(input_bytes, bytes) or len(input_bytes) > 65536):
            refuse("stdin", "Native input must be bounded bytes.")
        if purpose not in {"implement", "verify"}:
            refuse("purpose", "Unsupported native command purpose.")
        root = self.guard(store)
        state = store.check_authorization(revision)
        approved = state["approval"]["configuration"]["policy"]
        if approved.get("version") != 4 or self.policy.codex_sandbox != "disabled" or approved.get("execution") != self.policy.record():
            refuse("approval", "Native execution requires explicit policy-v4 VM-access approval; old approvals are not upgraded.")
        if state["pending"] is not None:
            refuse("pending", "Inspect and reconcile the retained command before another launch.")
        scratch = self.scratch(store)
        payload = json.dumps({"argv": argv, "stdin_sha256": hashlib.sha256(input_bytes or b"").hexdigest()}, separators=(",", ":")).encode()
        details = {"execution_version": 2, "mode": "trusted-vm", "policy": self.policy.record(),
                   "command_sha256": hashlib.sha256(payload).hexdigest(), "adapter": metadata or {"kind": "project-command"}}
        pending = store.begin_operation(revision, purpose, details)
        # Any uncertain exit/persistence/validator failure deliberately retains intent.
        self.guard(store)
        store.check_authorization(pending["revision"])
        result = self.runner(argv, cwd=root, env=self.environment(root, scratch), timeout=self.policy.timeout,
                             limit=self.policy.output_limit, cancel=cancel, input_bytes=input_bytes)
        if result.stopped:
            refuse("native_interrupted", "Native command stopped; preserve partial files and reconcile the pending operation before retrying.")
        extra = validate(result) if validate is not None else {}
        store.resolve_operation(pending["revision"], pending["pending"]["id"], "confirmed",
                                {"execution_version": 2, "mode": "trusted-vm", "process": public_process(result), **extra})
        return result


def native_dependency_commands(family, *, offline=False):
    if family == "python":
        return [["/usr/bin/python3", "-m", "venv", ".venv"],
                [".venv/bin/python", "-m", "pip", "install", *(["--no-index"] if offline else []), "."]]
    if family == "node":
        return [["npm", "ci", *(["--offline"] if offline else []), "--no-audit", "--no-fund"]]
    refuse("runtime", "Unsupported native dependency environment.")
