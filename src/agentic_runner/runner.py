"""Small sequential loop; Git effects belong to the runner, never to Codex."""

import fcntl
import json
from contextlib import contextmanager
from datetime import datetime, timezone

from .durable import DurableIO, decode_json
from .git_boundary import GitBoundary
from .headless import generate, validate_report
from .project import CONTROLS, RunnerError, check_process, fingerprint, require
from .roadmap import parse_roadmap


@contextmanager
def checkpoint_area(git):
    area = git.root / ".git/ralph"
    require(not area.is_symlink(), "Checkpoint directory cannot be a symlink.")
    area.mkdir(mode=0o700, exist_ok=True)

    def guard(path):
        require(not area.is_symlink() and path.resolve().is_relative_to(area), "Unsafe checkpoint path.")

    lock = area / "lock"
    require(not lock.is_symlink(), "Checkpoint lock cannot be a symlink.")
    with lock.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RunnerError("Another runner holds the repository lock.") from exc
        yield area, DurableIO(guard)


def completed_roadmap(text, milestone):
    parsed = parse_roadmap(text)
    target = next(m for m in parsed.milestones if m.id == milestone)
    lines = text.splitlines(keepends=True)
    # Use the parser's structural progress heading, not a regex over fenced examples.
    from .markdown import structure
    _, headings, _ = structure(text, "ROADMAP.md")
    start = next(h.index for h in headings if h.level == 2 and h.title == "Milestone Progress")
    stop = next((h.index for h in headings if h.level == 2 and h.index > start), len(lines))
    matches = [i for i in range(start + 1, stop) if len(lines[i].split("|")) >= 3 and
               lines[i].split("|")[1].strip() == milestone]
    require(len(matches) == 1 and target.status != "complete", "Cannot uniquely complete selected milestone.")
    lines[matches[0]] = f"| {milestone} | complete |\n"
    result = "".join(lines)
    parse_roadmap(result)
    return result


class Loop:
    def __init__(self, project, *, git=None, agent=generate, announce=print):
        self.project = project
        self.git = git or GitBoundary(project)
        self.agent, self.announce = agent, announce

    def controls(self):
        docs = self.project.documents()
        require(fingerprint(self.project.config.read_bytes()) == self.project.config_hash, "Project configuration changed.")
        return {name: fingerprint(docs[name].encode()) for name in CONTROLS}

    def save(self, record):
        self.io.atomic(self.state_path, json.dumps(record, indent=2).encode() + b"\n")

    def invariants(self, record, *, publishing=False):
        git = self.git
        git.guard(record["main"], None if publishing else record["base"])
        controls = self.controls()
        expected = dict(record["controls"])
        if publishing and controls["ROADMAP.md"] == fingerprint(record["completed_roadmap"].encode()):
            expected["ROADMAP.md"] = controls["ROADMAP.md"]
        require(controls == expected, "Protected project documents changed; human review required.")

    def verify(self, record, progress_before):
        git = self.git
        self.invariants(record)
        git.index_clean()
        before = git.snapshot()
        require(before["PROGRESS.md"][0] != fingerprint(progress_before.encode()), "Codex must update PROGRESS.md before reporting success.")
        for command in self.project.verification:
            self.announce(f"{record['milestone']}: verify {json.dumps(command)}")
            result = git.process(list(command), cwd=git.root, env=git.env, timeout=1800)
            check_process(result, f"Verification failed: {json.dumps(command)}")
        self.invariants(record)
        git.index_clean()
        require(git.snapshot() == before, "Verification modified publishable files; inspect changes before resuming.")
        git.remote_guard(record["remote_main"])
        return before

    def write_completion(self, record):
        root, area = self.git.root, self.state_path.parent

        def guard(path):
            require(not path.is_symlink() and (path in {root, root / "ROADMAP.md", area} or
                    path.parent == area), "Unsafe roadmap completion path.")

        # Keep interrupted temporary files inside private Git metadata, outside the
        # publishable inventory. Rename leaves either original or completed text.
        DurableIO(guard).atomic(root / "ROADMAP.md", record["completed_roadmap"].encode(),
                                temporary_directory=area, mode=(root / "ROADMAP.md").stat().st_mode & 0o777)

    def committed(self, record):
        git, head = self.git, self.git.head()
        require(record.get("commit", head) == head and record.get("tree") and
                git.git("rev-parse", "HEAD^{tree}") == record["tree"] and
                git.git("rev-list", "--parents", "-n", "1", "HEAD") == f"{head} {record['base']}" and
                git.git("log", "-1", "--format=%B").strip() == record["report"]["commit_message"],
                "Commit does not match recorded publication intent; human review required.")
        require(not git.git("status", "--porcelain"), "Uncommitted changes after commit; inspect before pushing.")
        return head

    def publish(self, record):
        git = self.git
        self.invariants(record, publishing=True)
        git.remote_guard(record["remote_main"])
        head = git.head()
        if head == record["base"]:
            files = git.snapshot()
            expected = dict(record["files"])
            if (git.root / "ROADMAP.md").read_text() == record["completed_roadmap"]:
                expected["ROADMAP.md"] = [fingerprint(record["completed_roadmap"].encode()), record["files"]["ROADMAP.md"][1]]
            require(files == expected, "Files changed since verification; publication needs human review.")
            git.guard(record["main"], record["base"])
            self.write_completion(record)
            expected["ROADMAP.md"] = [fingerprint(record["completed_roadmap"].encode()), record["files"]["ROADMAP.md"][1]]
            require(git.snapshot() == expected, "Files changed during roadmap completion; human review required.")
            paths = sorted(name for name in set(expected) | set(record["initial_files"])
                           if expected.get(name) != record["initial_files"].get(name))
            require(paths, "No verified changes to commit.")
            git.guard(record["main"], record["base"])
            git.git("add", "--all", "--", *paths)
            require(set(git.git("diff", "--cached", "--name-only", "-z").split("\0")) - {""} == set(paths), "Staged paths differ from verified changes.")
            # Refuse clean/smudge/EOL conversion that changes the verified bytes.
            for name in paths:
                if name in expected:
                    require(git.git("rev-parse", f":{name}") == git.git("hash-object", "--no-filters", "--", name), "Staging transformed verified content; inspect Git attributes/config.")
                    mode = git.git("ls-files", "--stage", "--", name).split()[0]
                    require(mode == ("100755" if expected[name][1] else "100644"), "Staged mode differs from verified file mode.")
            require(git.snapshot() == expected and not git.git("diff", "--name-only"), "Files changed during staging.")
            tree = git.git("write-tree")
            require(record.get("tree", tree) == tree, "Recovered index does not match the recorded tree.")
            record["tree"] = tree
            self.save(record)  # Exact tree and intent are durable before commit.
            git.guard(record["main"], record["base"])
            git.git("commit", "--no-gpg-sign", "-m", record["report"]["commit_message"])
            head = git.head()
        record["commit"] = head = self.committed(record)
        self.save(record)
        git.push(record["remote_main"])
        record.update(phase="complete", issue=None)
        self.save(record)
        self.announce(f"{record['milestone']}: committed and pushed {head} to {self.project.development_branch}")

    def failure(self, record, error):
        record["issue"] = str(error) or type(error).__name__
        if hasattr(error, "report"):
            self.io.atomic(self.state_path.with_name("last-report.json"), json.dumps(error.report).encode() + b"\n")
            record["issue"] += " Invalid structured report: .git/ralph/last-report.json."
        if hasattr(error, "process"):
            for name in ("stdout", "stderr"):
                self.io.atomic(self.state_path.with_name(f"last-failure.{name}"), getattr(error.process, name))
            record["issue"] += " Private command output: .git/ralph/last-failure.stdout and last-failure.stderr."
        self.save(record)
        # Never alter progress after verification/publication intent or on the wrong branch.
        if record["phase"] == "implementing":
            try:
                self.invariants(record)
                path = self.git.root / "PROGRESS.md"
                with path.open("a") as stream:
                    stream.write(f"\nRunner stopped {datetime.now(timezone.utc).isoformat()} ({record['milestone']}): {error}\n")
            except (RunnerError, OSError):
                pass  # The checkpoint still explains the issue when project writes are unsafe.

    def run(self):
        git = self.git
        git.guard()
        self.project.documents()
        with checkpoint_area(git) as (area, io):
            self.io, self.state_path = io, area / "checkpoint.json"
            record = decode_json(io.read(self.state_path), self.state_path) if self.state_path.exists() else None
            if record is not None:
                require(isinstance(record, dict) and record.get("version") == 1 and
                        record.get("config_hash") == self.project.config_hash and record.get("repository") == str(git.root),
                        "Checkpoint identity/version mismatch; inspect it before resuming.")
                require(record.get("git_config_hash") == git.config_hash, "Git configuration differs from the checkpoint; review before resuming.")
                require(record.get("phase") in {"implementing", "publishing", "complete"}, "Unknown checkpoint phase.")
                require({"milestone", "base", "main", "remote_main", "controls", "initial_files"} <= record.keys(), "Checkpoint is incomplete; retain it for review.")
                if record["phase"] in {"publishing", "complete"}:
                    require({"files", "report", "completed_roadmap"} <= record.keys(), "Publication checkpoint is incomplete.")
                    validate_report(record["report"], record["milestone"])
                    require(record["report"]["status"] == "success", "Publication requires a successful report.")
            while True:
                if record is not None and record["phase"] == "complete":
                    try:
                        self.invariants(record, publishing=True)
                        require(record.get("commit"), "Completed checkpoint lacks its published commit.")
                        self.committed(record)
                        git.remote_guard(record["remote_main"])
                        require(git.remote_ref(self.project.development_branch) == record["commit"],
                                "Completed publication differs from remote development branch; human review required.")
                    except (Exception, KeyboardInterrupt) as exc:
                        self.failure(record, exc)
                        raise
                if record is None or record["phase"] == "complete":
                    require(not git.git("status", "--porcelain"), "A new milestone requires a clean checkout; only matching partial checkpoints may resume.")
                    documents = self.project.documents()
                    roadmap = parse_roadmap(documents["ROADMAP.md"])
                    if roadmap.next_milestone is None:
                        self.announce("All milestones complete.")
                        return
                    git.guard()
                    main = git.git("rev-parse", "refs/heads/main")
                    git.remote_guard(main)
                    git.git("merge-base", "--is-ancestor", "refs/heads/main", "HEAD")
                    require(git.remote_ref(self.project.development_branch) == git.head(), "Development branch must match its remote before a new milestone; inspect/push existing work manually.")
                    record = {"version": 1, "repository": str(git.root), "config_hash": self.project.config_hash, "git_config_hash": git.config_hash,
                              "milestone": roadmap.next_milestone, "phase": "implementing", "base": git.head(),
                              "main": main, "remote_main": main, "controls": self.controls(),
                              "initial_files": git.snapshot(), "issue": None}
                    self.save(record)
                try:
                    if record["phase"] == "implementing":
                        self.invariants(record)
                        git.index_clean()
                        git.remote_guard(record["remote_main"])
                        documents = self.project.documents()
                        roadmap = parse_roadmap(documents["ROADMAP.md"])
                        require(roadmap.next_milestone == record["milestone"], "Checkpoint no longer selects the first unfinished milestone.")
                        milestone = next(m for m in roadmap.milestones if m.id == record["milestone"])
                        self.announce(f"{milestone.id}: fresh Codex session")
                        report = validate_report(self.agent(self.project, milestone, documents, git.env), milestone.id)
                        self.invariants(record)
                        require(report["status"] == "success", f"Codex {report['status']}: {report['summary']}; blockers: {json.dumps(report['blockers'])}")
                        files = self.verify(record, documents["PROGRESS.md"])
                        record.update(phase="publishing", files=files, report=report,
                                      completed_roadmap=completed_roadmap(documents["ROADMAP.md"], milestone.id))
                        self.save(record)  # Intent precedes roadmap/staging/commit effects.
                    self.publish(record)
                except (Exception, KeyboardInterrupt) as exc:
                    self.failure(record, exc)
                    raise
