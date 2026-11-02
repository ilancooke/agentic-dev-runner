"""One-time setup only. Routine execution never imports or invokes these writes."""

import json
import os
import re

from .durable import decode_json
from .git_boundary import (GitBoundary, GitCommands, environment, local_config,
                           origin_url, validate_protection)
from .project import DOCUMENTS, RunnerError, fingerprint, require
from .runner import checkpoint_area
from .supervisor import supervise


class Setup(GitCommands):
    def __init__(self, project, *, process=supervise, env=None, announce=print):
        self.project, self.root, self.process = project, project.repository, process
        self.env = environment() if env is None else env
        self.announce = announce

    def call(self, argv, *, timeout=60):
        try:
            return super().call(argv, timeout=timeout)
        except RunnerError as exc:
            detail = exc.process.stderr.decode(errors="replace").strip()
            raise RunnerError(f"{exc} {detail} Resolve the command/authentication issue and rerun setup.") from exc

    def api(self, endpoint, *, method="GET", payload=None, missing=False):
        argv = ["gh", "api", "--hostname", "github.com", "--include", "--method", method, endpoint]
        if payload is not None:
            argv += ["--input", "-"]
        result = self.process(argv, cwd=self.root, env=self.env, timeout=60,
                              input_bytes=json.dumps(payload).encode() if payload is not None else None)
        # Only an actual HTTP 404 permits creation. Auth/transport errors never do.
        headers, separator, body = result.stdout.replace(b"\r\n", b"\n").partition(b"\n\n")
        match = re.match(rb"HTTP/\S+ (\d{3})\b", headers)
        status = int(match[1]) if match else None
        if status == 404 and separator and missing and not result.stopped:
            return None
        if result.stopped or result.returncode or status != 200:
            detail = result.stderr.decode(errors="replace").strip()
            raise RunnerError(f"GitHub {method} {endpoint} failed (HTTP {status}): {detail}. "
                              "Check gh authentication, repository Administration permission and GitHub plan "
                              "support for private-repository branch protection; then rerun setup. No unprotected fallback.")
        require(separator, "GitHub response lacks HTTP headers/body.")
        value = json.loads(body)
        require(isinstance(value, dict), "GitHub response must be an object.")
        return value

    def ref(self, branch):
        refs = dict(line.split(" ", 1)[::-1] for line in self.git(
            "for-each-ref", "--format=%(objectname) %(refname)", "refs/heads/").splitlines())
        return refs.get(f"refs/heads/{branch}")

    def save(self, record):
        self.io.atomic(self.state_path, json.dumps(record, indent=2).encode() + b"\n")

    def prepare(self):
        require(os.getuid() != 0 and self.root.is_dir() and self.root.stat().st_uid == os.getuid(),
                "Run setup as the non-root project directory owner.")
        self.project.documents()
        require(not self.project.development_branch.startswith("main/"),
                "Development branch cannot be below main: Git cannot store both refs.")
        self.git("check-ref-format", "--branch", self.project.development_branch)
        marker = self.root / ".git"
        if not marker.exists() and not marker.is_symlink():
            require(not any((p / ".git").is_file() or (p / ".git/HEAD").is_file() for p in self.root.parents),
                    "Refusing to initialize a nested checkout inside another repository.")
            self.git("init", "--template=", "--initial-branch=main")
        require(marker.is_dir() and not marker.is_symlink(), "Setup requires an ordinary .git directory, not a worktree or symlink.")
        config = local_config(self.root)
        self.url = origin_url(self.project, config, optional=True)
        branch = self.git("symbolic-ref", "--quiet", "HEAD")
        require(branch in {"refs/heads/main", f"refs/heads/{self.project.development_branch}"},
                "Setup needs main or the configured development branch; resolve other/detached branches manually.")

    def baseline(self, record):
        head = self.ref(self.git("symbolic-ref", "--quiet", "HEAD").removeprefix("refs/heads/"))
        switched = (record["phase"] in {"switching", "complete"} and
                    head == (record["dev"] or record["baseline"]))
        if not switched:
            require(GitBoundary.snapshot(self) == record["files"], "Setup files changed after interruption; inspect setup.json before continuing.")
        else:
            require(not self.git("status", "--porcelain"), "Setup requires a clean development checkout after switching.")
        require(switched or head in {record["head"], record.get("baseline")}, "HEAD changed during setup; intervention required.")
        if not record.get("baseline"):
            # This path is for an unborn repository only. Intent/files precede staging.
            self.git("add", "--", *sorted(record["files"]))
            tree = self.git("write-tree")
            oid = self.git("commit-tree", tree, "-m", "Establish initial project baseline")
            record["baseline"] = oid
            self.save(record)  # A lost update-ref response can now be reconciled exactly.
        baseline = record["baseline"]
        main = self.ref("main")
        require(main in {None, baseline}, "Conflicting local main; setup never moves existing history.")
        if main is None:
            self.git("update-ref", "refs/heads/main", baseline, "0" * len(baseline))
        require(not self.git("status", "--porcelain"), "Setup requires a clean baseline; no existing work is committed implicitly.")
        remote = self.remote_ref("main")
        require(remote in {None, baseline}, "Conflicting remote main; setup never reconciles or replaces history.")
        if remote is None:
            require(not self.git("ls-remote", "--refs", self.url, "refs/heads/*"),
                    "Remote has history without main; establish the intended baseline manually.")
            self.git("push", "--", self.url, f"{baseline}:refs/heads/main")
        require(self.remote_ref("main") == baseline, "Initial main publication is uncertain; rerun setup.")

    def protect(self):
        endpoint = f"repos/{self.project.name}/branches/main/protection"
        value = self.api(endpoint, missing=True)
        if value is None:
            self.api(endpoint, method="PUT", payload={
                "required_status_checks": None, "enforce_admins": True,
                "required_pull_request_reviews": {"required_approving_review_count": 1,
                    "bypass_pull_request_allowances": {"users": [], "teams": [], "apps": []}},
                "restrictions": None, "allow_force_pushes": False, "allow_deletions": False,
            })
        else:
            try:
                validate_protection(value)
            except RunnerError as exc:
                raise RunnerError(f"Existing protection is incompatible: {exc} "
                                  "Strengthen it manually without removing other rules, then rerun setup; "
                                  "setup will not replace an existing policy.") from exc
        # A successful write response alone is insufficient evidence.
        validate_protection(self.api(endpoint))

    def development(self, record):
        branch = self.project.development_branch
        expected = record["dev"] or record["baseline"]
        require(self.ref(branch) in {None, expected}, "Conflicting development branch; history retained.")
        require(self.remote_ref(branch) in {None, expected}, "Conflicting remote development branch; history retained.")
        if self.ref(branch) is None:
            self.git("branch", branch, expected)
        record.update(phase="switching", target_documents={
            name: fingerprint(self.git("show", f"{expected}:{name}", strip=False).encode()) for name in DOCUMENTS})
        self.save(record)  # A lost switch response may expose the dev version of documents.
        self.git("switch", branch)
        git = GitBoundary(self.project, process=self.process, env=self.env)
        git.guard(record["baseline"], expected)
        if self.remote_ref(branch) is None:
            git.push(record["baseline"])
        git.remote_guard(record["baseline"])
        require(self.remote_ref(branch) == expected and not self.git("status", "--porcelain"),
                "Development publication is uncertain or checkout changed; rerun setup.")

    def run(self):
        self.prepare()
        with checkpoint_area(self) as (area, io):
            self.io, self.state_path = io, area / "setup.json"
            require(not (area / "checkpoint.json").exists(),
                    "A run checkpoint exists; use run/recovery, not one-time setup.")
            identity = {"project": self.project.name, "config": str(self.project.config),
                        "config_hash": self.project.config_hash, "branch": self.project.development_branch,
                        "documents": {k: fingerprint(v.encode()) for k, v in self.project.documents().items()}}
            record = decode_json(io.read(self.state_path), self.state_path) if self.state_path.exists() else None
            if record is not None:
                require(isinstance(record, dict) and record.get("version") == 1 and
                        {"identity", "head", "baseline", "dev", "files", "phase"} <= record.keys() and
                        isinstance(record["identity"], dict) and
                        record["phase"] in {"preparing", "switching", "complete"},
                        "Invalid setup checkpoint; preserve setup.json and inspect it before continuing.")
                expected = dict(record["identity"])
                if (record["phase"] in {"switching", "complete"} and
                        self.git("symbolic-ref", "--quiet", "HEAD") == f"refs/heads/{self.project.development_branch}" and
                        self.head() == (record["dev"] or record["baseline"])):
                    expected["documents"] = record["target_documents"]
                require(expected == identity, "Setup configuration/documents changed; inspect setup.json; intervention required.")
            else:
                head = self.ref(self.git("symbolic-ref", "--quiet", "HEAD").removeprefix("refs/heads/"))
                if head:
                    require(not self.git("status", "--porcelain"), "Setup requires a clean checkout with existing history; commit intended files manually.")
                else:
                    require(self.git("symbolic-ref", "--quiet", "HEAD") == "refs/heads/main",
                            "Unborn checkout must use main for its initial baseline; resolve HEAD manually.")
                    require(not self.git("ls-files"), "Unborn checkout has staged files; resolve the index before setup.")
                files = GitBoundary.snapshot(self)
                require(set(DOCUMENTS) <= files.keys(), "Required documents must be tracked or unignored for the initial baseline.")
                main, dev = self.ref("main"), self.ref(self.project.development_branch)
                require(head or not (main or dev), "Unborn HEAD conflicts with existing branches; resolve them manually.")
                if main and dev:
                    self.git("merge-base", "--is-ancestor", main, dev)
                record = {"version": 1, "identity": identity, "head": head, "baseline": main or head,
                          "dev": dev, "files": files, "phase": "preparing"}
                self.save(record)
            try:
                user = self.api("user")
                require(isinstance(user.get("id"), int) and user["id"] > 0 and
                        isinstance(user.get("login"), str) and re.fullmatch(r"[A-Za-z0-9-]+", user["login"]),
                        "Authenticated GitHub account lacks a valid numeric id/login.")
                name, email = user["login"], f"{user['id']}+{user['login']}@users.noreply.github.com"
                # Repeating these writes is safe, and never touches global identity.
                self.git("config", "--local", "--replace-all", "user.name", name)
                self.git("config", "--local", "--replace-all", "user.email", email)
                repository = self.api(f"repos/{self.project.name}", missing=True)
                if repository is None:
                    require(self.url is None, "Existing origin is inaccessible; verify access rather than creating a replacement.")
                    record["create_private"] = True
                    self.save(record)
                    self.call(["gh", "repo", "create", self.project.name, "--private"])
                    repository = self.api(f"repos/{self.project.name}")
                if record.get("create_private"):
                    require(repository.get("private") is True, "New repository was not private; stop for human review.")
                require(str(repository.get("full_name", "")).lower() == self.project.name.lower(), "GitHub repository identity mismatch.")
                require(isinstance(repository.get("permissions"), dict) and repository["permissions"].get("admin") is True,
                        "Setup requires repository admin permission; grant Administration access and verify private-repository protection plan support.")
                if self.url is None:
                    self.url = f"https://github.com/{self.project.name}.git"
                    self.git("remote", "add", "origin", self.url)
                self.baseline(record)
                self.protect()
                self.development(record)
                record.update(phase="complete", issue=None)
                self.save(record)
                self.announce("Setup complete: protected main and matching development branch. Launch run explicitly.")
            except (Exception, KeyboardInterrupt) as exc:
                record["issue"] = str(exc) or "Interrupted; rerun setup to reconcile existing effects."
                self.save(record)
                raise
