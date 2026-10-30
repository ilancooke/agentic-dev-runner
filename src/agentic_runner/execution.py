"""Trusted Docker launcher. No daemon control or orchestrator secrets enter jobs.

All project commands, including dependency installers, use exactly this boundary.
The only initial network policy is offline; missing artifacts stop installation.
"""

import hashlib
import json
import os
import re
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path

from .durable import StateError
from .redaction import public_process
from .state_boundary import PROTECTED, overlaps
from .supervisor import supervise


class ExecutionError(StateError):
    pass


def refuse(code, message):
    raise ExecutionError("execution." + code, message, "container execution")


def host_environment():
    # In particular: no DOCKER_HOST/context, Git, proxy, cloud, or account variables.
    return {"PATH": os.defpath, "HOME": "/nonexistent", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"}


@dataclass(frozen=True)
class ContainerPolicy:
    image: str
    timeout: int = 120
    memory_mb: int = 1024
    cpus: int = 1
    pids: int = 128

    def record(self):
        if not isinstance(self.image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", self.image):
            refuse("image", "Pin a locally inspected runner image by immutable image ID.")
        for value, low, high in ((self.timeout, 1, 3600), (self.memory_mb, 128, 4096), (self.cpus, 1, 4), (self.pids, 16, 512)):
            if type(value) is not int or not low <= value <= high:
                refuse("limits", "Container limits exceed supported policy.")
        return {"version": 1, "image": self.image, "timeout": self.timeout, "memory_mb": self.memory_mb,
                "cpus": self.cpus, "pids": self.pids, "network": "none", "git": "hidden-read-only",
                "credentials": "none", "rootfs": "read-only", "capabilities": "none"}


def validate_checkout(path, boundary):
    path = Path(path)
    if boundary.disposable is not None:
        boundary.disposable.require(path)
    if path.resolve() != path or not path.is_dir() or any(overlaps(path, p.resolve()) for p in PROTECTED):
        refuse("checkout", "Use a canonical owned checkout outside protected roots.")
    if overlaps(path, boundary.path):
        refuse("state", "Execution checkout and runner state must not overlap.")
    git = path / ".git"
    if git.is_symlink() or not git.is_dir():
        refuse("git", "This execution policy supports ordinary checkouts only; linked worktrees require a separate mount policy.")
    if os.getuid() == 0 or path.stat().st_uid != os.getuid():
        refuse("owner", "Run the trusted launcher as the non-root checkout owner.")
    count = 0
    def scan_error(error):
        refuse("scan", "Cannot inventory every checkout path; execution is refused.")
    for parent, directories, files in os.walk(path, followlinks=False, onerror=scan_error):
        if Path(parent) == path:
            directories.remove(".git")
        for name in directories + files:
            item = Path(parent) / name
            info = item.lstat()
            if name in {".git", ".aws", ".ssh", ".codex", ".docker", ".netrc", ".npmrc", ".pypirc", ".git-credentials"} or name == ".env" or name.startswith(".env."):
                refuse("sensitive", "Remove private configuration from the execution checkout; it is not mounted selectively.")
            if stat.S_ISLNK(info.st_mode):
                if not item.resolve().is_relative_to(path) or item.resolve().is_relative_to(git):
                    refuse("alias", "Checkout symlinks must stay inside project content.")
            elif not (stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode)) or stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                refuse("file_type", "Special files and hard-linked files cannot enter execution.")
            elif stat.S_ISDIR(info.st_mode) and os.path.ismount(item):
                refuse("mount", "Nested host mounts cannot enter execution.")
            count += 1
            if count > 100000:
                refuse("size", "Checkout inventory exceeds the execution policy limit.")
    return path


class ContainerExecutor:
    def __init__(self, policy, *, runner=supervise):
        self.policy = policy
        self.policy.record()
        self.runner = runner

    def _docker(self, arguments, *, timeout=30, limit=4 * 1024 * 1024, cancel=None, input_bytes=None):
        return self.runner(["/usr/bin/docker", "--host", "unix:///var/run/docker.sock", *arguments], cwd="/tmp",
                           env=host_environment(), timeout=timeout, limit=limit, cancel=cancel, input_bytes=input_bytes)

    def capabilities(self):
        result = self._docker(["info", "--format", "{{json .}}"])
        try:
            info = json.loads(result.stdout)
        except ValueError:
            refuse("daemon", "Docker capability inspection failed; no execution is allowed.")
        options = info.get("SecurityOptions", [])
        if result.returncode or result.stopped or info.get("OSType") != "linux" or info.get("CgroupVersion") != "2" or "name=seccomp,profile=builtin" not in options or "name=apparmor,profile=default" not in options:
            refuse("security", "Linux, cgroups v2, seccomp and AppArmor are required; no weaker fallback exists.")
        image = self._docker(["image", "inspect", self.policy.image])
        try:
            value = json.loads(image.stdout)[0]
            valid = value["Id"] == self.policy.image and value["Config"]["Labels"]["org.agentic-runner.environment"] == "m4-v1"
        except (ValueError, KeyError, IndexError, TypeError):
            valid = False
        if image.returncode or image.stopped or not valid:
            refuse("image", "The pinned runner-provided M4 image is unavailable or mislabeled.")
        return {"docker": info.get("ServerVersion"), "security": info["SecurityOptions"], "image": self.policy.image}

    def assert_created(self, name, checkout):
        result = self._docker(["inspect", "--format", "{{json .}}", name])
        try:
            item = json.loads(result.stdout)
            host = item["HostConfig"]
            config = item["Config"]
            binds = [m for m in item["Mounts"] if m["Type"] == "bind"]
            valid = (item["Name"] == "/" + name and item["Image"] == self.policy.image
                     and item["AppArmorProfile"] in {"", "docker-default"}
                     and config["Labels"]["org.agentic-runner.operation"] == name
                     and config["User"] == f"{os.getuid()}:{os.getgid()}"
                     and host["NetworkMode"] == "none" and host["ReadonlyRootfs"] is True
                     and host["Privileged"] is False and not host["CapAdd"] and host["CapDrop"] == ["ALL"]
                     and set(host["SecurityOpt"]) == {"no-new-privileges:true", "apparmor=docker-default"} and not host.get("Devices")
                     and not host.get("PidMode") and not host.get("Binds") and not host.get("PortBindings")
                     and host["Memory"] == self.policy.memory_mb * 1024 * 1024
                     and host["PidsLimit"] == self.policy.pids and host["NanoCpus"] == self.policy.cpus * 1000000000
                     and len(binds) == 1 and binds[0]["Source"] == str(checkout)
                     and binds[0]["Destination"] == "/workspace" and binds[0]["RW"] is True
                     and set(host["Tmpfs"]) == {"/tmp", "/home/runner", "/workspace/.git"}
                     and "ro" in host["Tmpfs"]["/workspace/.git"].split(",")
                     and not item["State"]["Running"])
        except (ValueError, KeyError, IndexError, TypeError):
            valid = False
        if result.returncode or result.stopped or not valid:
            refuse("inspect", "Created container does not match the enforced policy; it will not be started.")

    def create_arguments(self, checkout, name):
        uid, gid = os.getuid(), os.getgid()
        return ["create", "--interactive", "--name", name, "--label", "org.agentic-runner.operation=" + name,
                "--pull", "never", "--init", "--network", "none", "--user", f"{uid}:{gid}",
                "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--security-opt", "apparmor=docker-default",
                "--pids-limit", str(self.policy.pids), "--memory", f"{self.policy.memory_mb}m", "--memory-swap", f"{self.policy.memory_mb}m",
                "--cpus", str(self.policy.cpus), "--ulimit", "nofile=256:256", "--stop-timeout", "1",
                "--log-driver", "none", "--workdir", "/workspace", "--entrypoint", "/usr/bin/env",
                "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=256m,mode=1777",
                "--tmpfs", f"/home/runner:rw,nosuid,nodev,size=256m,uid={uid},gid={gid},mode=700",
                "--mount", f"type=bind,src={checkout},dst=/workspace,bind-propagation=rprivate",
                "--tmpfs", "/workspace/.git:ro,nosuid,nodev,noexec,size=64k,mode=555"]

    @staticmethod
    def environment():
        return ["-i", "PATH=/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin", "HOME=/home/runner",
                "CODEX_HOME=/home/runner/.codex", "LANG=C.UTF-8", "TMPDIR=/tmp", "CI=1", "PIP_NO_INDEX=1",
                "PIP_CONFIG_FILE=/dev/null", "PIP_DISABLE_PIP_VERSION_CHECK=1", "npm_config_offline=true",
                "npm_config_userconfig=/dev/null", "npm_config_cache=/workspace/.runner-npm-cache",
                "GIT_CONFIG_NOSYSTEM=1", "GIT_CONFIG_GLOBAL=/dev/null", "GIT_TERMINAL_PROMPT=0"]

    def execute(self, store, revision, argv, *, purpose="implement", cancel=None, input_bytes=None):
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a and "\0" not in a for a in argv) or argv[0].startswith("-"):
            refuse("argv", "Provide a literal project command argument vector.")
        if purpose not in {"implement", "verify"}:
            refuse("purpose", "Unsupported execution purpose.")
        state = store.check_authorization(revision)
        if state["approval"]["configuration"]["policy"].get("execution") != self.policy.record():
            refuse("approval", "The exact execution policy must be explicitly approved using policy v2 before launch.")
        checkout = validate_checkout(store.repository.root, store.boundary)
        if any(c in str(checkout) for c in (",", "\n")):
            refuse("path", "Checkout path cannot be represented by the constrained mount policy.")
        if state["pending"] is not None:
            refuse("pending", "Reconcile the retained operation; it cannot be relaunched automatically.")
        self.capabilities()
        name = "adr-m4-" + str(uuid.uuid4())
        specification = self.policy.record()
        # Command contents may contain private project text: retain only a digest in state.
        command_hash = hashlib.sha256(json.dumps(argv, separators=(",", ":")).encode()).hexdigest()
        pending = store.begin_operation(revision, purpose, {"execution_version": 1, "container": name,
                                        "policy": specification, "argv_sha256": command_hash})
        operation_id = pending["pending"]["id"]
        # Never resolve automatically after interruption, malformed Docker responses or uncertain cleanup.
        try:
            store.check_authorization(pending["revision"])
            validate_checkout(checkout, store.boundary)
            created = self._docker([*self.create_arguments(checkout, name), self.policy.image, *self.environment(),
                                    "/bin/sh", "-c", 'mkdir -m 700 -p /home/runner/.codex && exec "$@"', "runner", *argv])
            if created.returncode or created.stopped or not re.fullmatch(rb"[0-9a-f]{64}\n?", created.stdout):
                refuse("create", "Container creation is uncertain; inspect the recorded operation name before retrying.")
            self.assert_created(name, checkout)
            result = self._docker(["start", "--attach", "--interactive", name], timeout=self.policy.timeout, cancel=cancel, input_bytes=input_bytes)
            inspected = self._docker(["inspect", "--format", "{{json .}}", name])
            try:
                actual = json.loads(inspected.stdout)
                observed = actual["State"]
                if inspected.returncode or inspected.stopped or observed["Running"] or type(observed["ExitCode"]) is not int or actual["AppArmorProfile"] != "docker-default":
                    raise ValueError()
            except (ValueError, KeyError, TypeError):
                refuse("uncertain", "Container status is uncertain; preserve and reconcile the pending operation.")
            if result.stopped or result.returncode != observed["ExitCode"] or observed.get("OOMKilled"):
                refuse("interrupted", "Execution was interrupted or exhausted a limit; preserve partial work and reconcile intent.")
            removed = self._docker(["rm", "--force", name])
            if removed.returncode or removed.stopped:
                refuse("cleanup", "Container cleanup is uncertain; the operation remains pending.")
            store.resolve_operation(pending["revision"], operation_id, "confirmed", {"execution_version": 1,
                                    "container": name, "process": public_process(result), "policy": specification})
            return result
        except BaseException:
            # Best effort process stop; retain the intent regardless of the stop response.
            self._docker(["kill", name], timeout=5)
            raise


def dependency_commands(family):
    if family == "python":
        return [["/usr/local/bin/python", "-m", "venv", "--copies", "--system-site-packages", "/workspace/.venv"],
                ["/workspace/.venv/bin/python", "-m", "pip", "install", "--no-index", "--no-build-isolation", "."]]
    if family == "node":
        return [["npm", "ci", "--offline", "--no-audit", "--no-fund"]]
    refuse("runtime", "Unsupported dependency environment.")
