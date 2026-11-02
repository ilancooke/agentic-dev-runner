"""Owned local repositories and bare remotes; no GitHub accounts or model calls."""

import copy
import json
import subprocess
import sys
import unittest

from agentic_runner.git_boundary import GitBoundary
from agentic_runner.project import DOCUMENTS, Project, RunnerError
from agentic_runner.runner import Loop, checkpoint_area
from agentic_runner.setup import Setup
from agentic_runner.supervisor import ProcessResult, supervise
from tests.support.fixtures import FixtureFactory
from tests.support.isolation import DisposableRoot
from tests.support.projects import ROADMAP
from tests.test_runner import PROTECTION


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.repo = self.root.mkdir("project")
        self.env = FixtureFactory(self.root).environment()
        for name in DOCUMENTS:
            self.root.write_text(self.repo / name, ROADMAP if name == "ROADMAP.md" else f"# {name}\nFixture.\n")
        self.remote = self.root.require("remote.git")
        self.git("init", "--bare", str(self.remote))
        self.filename = self.root.write_text("project.toml", f'''[project]
name = "fixtures/project"
repository = "{self.repo}"
development_branch = "development"
verification = [["{sys.executable}", "-c", "pass"]]
''')
        self.project = Project.load(self.filename)
        self.repository = None
        self.protection = None
        self.calls = []
        self.fail = self.lose = None
        self.http_fail = None
        self.bad_readback = False

    def git(self, *args):
        self.root.require(self.repo)
        result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args],
                                cwd=self.repo, env=self.env, capture_output=True, text=True, check=True)
        return result.stdout.strip()

    def metadata(self):
        return {"full_name": "fixtures/project", "private": True, "permissions": {"admin": True}}

    def process(self, argv, **kwargs):
        self.root.require(kwargs["cwd"])
        self.assertEqual(kwargs["env"]["HOME"], self.env["HOME"])
        self.calls.append(list(argv))
        if argv[0] == "git":
            verb = next((a for a in argv if a in {"init", "commit-tree", "update-ref", "push", "switch", "remote", "config", "branch"}), "read")
            operation = "git:" + verb
            if verb == "push":
                operation += ":" + argv[-1].split(":refs/heads/")[-1]
        elif argv[1] == "repo":
            operation = "create"
        else:
            operation = "protect" if "PUT" in argv else argv[-1]
        if self.fail == operation:
            return ProcessResult(1, b"", b"injected failure")
        if argv[:3] == ["gh", "repo", "create"]:
            self.assertEqual(argv[3:], ["fixtures/project", "--private"])
            self.assertIsNone(self.repository)
            self.repository = self.metadata()
            result = ProcessResult(0, b"created", b"")
        elif argv[0] == "gh":
            endpoint = argv[argv.index("--method") + 2] if "--method" in argv else argv[-1]
            method = argv[argv.index("--method") + 1] if "--method" in argv else "GET"
            code = 200
            if endpoint == "user":
                value = {"id": 123, "login": "fixture"}
            elif endpoint == "repos/fixtures/project":
                value = self.repository
            else:
                self.assertEqual(endpoint, "repos/fixtures/project/branches/main/protection")
                if method == "PUT":
                    payload = json.loads(kwargs["input_bytes"])
                    self.assertTrue(payload["enforce_admins"])
                    self.assertFalse(payload["allow_force_pushes"])
                    self.assertFalse(payload["allow_deletions"])
                    self.assertIsNone(self.protection, "Never replace existing protection")
                    self.protection = copy.deepcopy(PROTECTION)
                    if self.bad_readback:
                        self.protection["enforce_admins"]["enabled"] = False
                value = self.protection
            if value is None:
                code, value = 404, {"message": "Not Found"}
            if self.http_fail and endpoint == self.http_fail[0]:
                code = self.http_fail[1]
            data = json.dumps(value).encode()
            if "--include" in argv:
                data = f"HTTP/2.0 {code} Response\r\ncontent-type: application/json\r\n\r\n".encode() + data
            result = ProcessResult(int(code != 200), data, b"" if code == 200 else b"GitHub permission/plan error")
        else:
            if "push" in argv or "ls-remote" in argv:
                argv = [str(self.remote) if a == "https://github.com/fixtures/project.git" else a for a in argv]
            result = supervise(argv, **kwargs)
        if self.lose == operation:
            return ProcessResult(1, b"", b"lost response")
        return result

    def setup(self):
        Setup(self.project, process=self.process, env=self.env, announce=lambda m: None).run()

    def state(self):
        return json.loads((self.repo / ".git/ralph/setup.json").read_text())

    def prepared(self):
        self.setup()
        self.calls.clear()
        return self.git("rev-parse", "main")

    def test_new_private_repository_baseline_identity_and_idempotency(self):
        self.setup()
        self.assertTrue(self.repository["private"])
        self.assertEqual(self.git("branch", "--show-current"), "development")
        self.assertEqual(self.git("config", "--local", "user.email"), "123+fixture@users.noreply.github.com")
        self.assertEqual(self.git("config", "--local", "user.name"), "fixture")
        main = self.git("rev-parse", "main")
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1")
        self.assertEqual(self.git("ls-remote", str(self.remote), "refs/heads/main").split()[0], main)
        self.assertEqual(self.git("status", "--porcelain"), "")
        self.calls.clear()
        self.setup()
        self.assertEqual(self.git("rev-parse", "main"), main)
        self.assertFalse(any("push" in a or "commit-tree" in a or "PUT" in a or "create" in a for a in self.calls))
        self.assertEqual(self.state()["phase"], "complete")

    def test_existing_history_without_origin_is_connected_and_preserved(self):
        self.git("init", "--initial-branch=main")
        self.git("config", "user.name", "Original")
        self.git("config", "user.email", "original@example.invalid")
        self.git("add", ".")
        self.git("commit", "-m", "Existing history")
        original = self.git("rev-parse", "HEAD")
        self.repository = self.metadata()
        self.setup()
        self.assertEqual(self.git("rev-parse", "HEAD"), original)
        self.assertEqual(self.git("rev-list", "--count", "HEAD"), "1")
        self.assertFalse(any(a[:3] == ["gh", "repo", "create"] for a in self.calls))

    def test_matching_origin_existing_main_and_stronger_protection_are_unchanged(self):
        main = self.prepared()
        self.protection.update(required_status_checks={"strict": True, "contexts": ["required"]},
                               required_linear_history={"enabled": True})
        self.protection["required_pull_request_reviews"]["required_approving_review_count"] = 3
        before = copy.deepcopy(self.protection)
        self.git("switch", "main")
        self.setup()
        self.assertEqual(self.protection, before)
        self.assertEqual(self.git("rev-parse", "main"), main)
        self.assertFalse(any("push" in a or "PUT" in a for a in self.calls))

    def test_mismatched_or_ambiguous_origin_stops_before_account_access(self):
        self.git("init", "--initial-branch=main")
        self.git("remote", "add", "origin", "https://github.com/other/project.git")
        with self.assertRaisesRegex(RunnerError, "Origin does not match"):
            self.setup()
        self.assertFalse(any(a[0] == "gh" for a in self.calls))
        self.assertEqual(self.git("remote", "get-url", "origin"), "https://github.com/other/project.git")

    def test_missing_docs_prevents_git_init_or_github(self):
        self.root.write_text(self.repo / "SPEC.md", "")
        with self.assertRaisesRegex(RunnerError, "empty"):
            self.setup()
        self.assertFalse((self.repo / ".git").exists())
        self.assertEqual(self.calls, [])

    def test_dirty_existing_repository_is_not_committed(self):
        main = self.prepared()
        self.root.write_text(self.repo / "partial.txt", "retain me")
        with self.assertRaisesRegex(RunnerError, "clean development"):
            self.setup()
        self.assertEqual(self.git("rev-parse", "main"), main)
        self.assertEqual((self.repo / "partial.txt").read_text(), "retain me")

    def test_conflicting_local_and_remote_branches_are_never_replaced(self):
        main = self.prepared()
        self.git("commit", "--allow-empty", "-m", "Unrelated dev update")
        changed = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(RunnerError, "HEAD changed"):
            self.setup()
        self.assertEqual(self.git("rev-parse", "HEAD"), changed)
        self.assertEqual(self.git("rev-parse", "main"), main)
        self.git("push", str(self.remote), "HEAD:refs/heads/development")
        self.git("switch", "main")
        # Local branch conflict remains visible even when current HEAD matches setup.
        with self.assertRaisesRegex(RunnerError, "Conflicting development"):
            self.setup()
        self.assertEqual(self.git("ls-remote", str(self.remote), "refs/heads/development").split()[0], changed)

    def test_existing_incompatible_protection_is_never_replaced(self):
        self.repository = self.metadata()
        self.protection = copy.deepcopy(PROTECTION)
        self.protection.update(required_status_checks={"strict": True, "contexts": ["required"]})
        self.protection["enforce_admins"]["enabled"] = False
        before = copy.deepcopy(self.protection)
        with self.assertRaisesRegex(RunnerError, "Strengthen it manually"):
            self.setup()
        self.assertEqual(self.protection, before)
        self.assertFalse(any("PUT" in a or a[-1].endswith(":refs/heads/development") for a in self.calls))

    def test_http_permission_errors_never_trigger_creation_or_dev_execution(self):
        self.http_fail = ("repos/fixtures/project", 403)
        with self.assertRaisesRegex(RunnerError, "Administration permission.*plan"):
            self.setup()
        self.assertIsNone(self.repository)
        self.assertFalse(any("create" in a or "push" in a for a in self.calls))

    def test_protection_plan_failure_and_bad_readback_block_dev(self):
        self.repository = self.metadata()
        self.http_fail = ("repos/fixtures/project/branches/main/protection", 403)
        with self.assertRaisesRegex(RunnerError, "No unprotected fallback"):
            self.setup()
        self.assertIsNone(self.remote_branch("development"))
        self.http_fail = None
        self.bad_readback = True
        with self.assertRaisesRegex(RunnerError, "protection"):
            self.setup()
        self.assertIsNone(self.remote_branch("development"))

    def remote_branch(self, branch):
        output = self.git("ls-remote", str(self.remote), "refs/heads/" + branch)
        return output.split()[0] if output else None

    def test_failed_and_lost_responses_resume_without_duplicate_history(self):
        # A fresh fixture per injected boundary, including both main and dev pushes.
        for operation in ("git:init", "create", "git:remote", "git:config", "git:commit-tree", "git:update-ref",
                          "git:push:main", "git:push:development", "git:branch", "git:switch", "protect"):
            for mode in ("fail", "lose"):
                with self.subTest(operation=operation, mode=mode):
                    case = SetupTests("test_new_private_repository_baseline_identity_and_idempotency")
                    case.setUp()
                    try:
                        setattr(case, mode, operation)
                        with self.assertRaises(RunnerError):
                            case.setup()
                        setattr(case, mode, None)
                        case.setup()
                        self.assertEqual(case.state()["phase"], "complete")
                        self.assertEqual(case.git("rev-list", "--count", "HEAD"), "1")
                        self.assertEqual(case.remote_branch("main"), case.git("rev-parse", "main"))
                        self.assertEqual(case.remote_branch("development"), case.git("rev-parse", "HEAD"))
                    finally:
                        case.doCleanups()

    def test_switch_to_existing_descendant_dev_recovers_its_documents(self):
        main = self.prepared()
        self.root.write_text(self.repo / "feature.txt", "Existing dev work\n")
        self.root.write_text(self.repo / "PROGRESS.md", "# Existing development progress\n")
        self.git("add", ".")
        self.git("commit", "-m", "Existing development work")
        dev = self.git("rev-parse", "HEAD")
        self.git("push", str(self.remote), "HEAD:refs/heads/development")
        self.git("switch", "main")
        # Convert this owned fixture into a preexisting repo without setup state.
        self.root.require(self.repo / ".git/ralph/setup.json").unlink()
        self.lose = "git:switch"
        with self.assertRaises(RunnerError):
            self.setup()
        self.lose = None
        self.setup()
        self.setup()
        self.assertEqual(self.git("rev-parse", "HEAD"), dev)
        self.assertEqual(self.git("rev-parse", "main"), main)
        self.assertEqual((self.repo / "PROGRESS.md").read_text(), "# Existing development progress\n")

    def test_conflicting_remote_main_is_not_updated(self):
        main = self.prepared()
        changed = self.git("commit-tree", "HEAD^{tree}", "-p", main, "-m", "Remote main advanced")
        self.git("push", str(self.remote), f"{changed}:refs/heads/main")
        with self.assertRaisesRegex(RunnerError, "Conflicting remote main"):
            self.setup()
        self.assertEqual(self.remote_branch("main"), changed)
        self.assertEqual(self.git("rev-parse", "main"), main)
        self.assertFalse(any("push" in a for a in self.calls))

    def test_conflicting_remote_dev_is_not_updated(self):
        main = self.prepared()
        changed = self.git("commit-tree", "HEAD^{tree}", "-p", main, "-m", "Remote dev advanced")
        self.git("push", str(self.remote), f"{changed}:refs/heads/development")
        with self.assertRaisesRegex(RunnerError, "Conflicting remote development"):
            self.setup()
        self.assertEqual(self.remote_branch("development"), changed)
        self.assertEqual(self.git("rev-parse", "HEAD"), main)
        self.assertFalse(any("push" in a for a in self.calls))

    def test_changed_controls_or_invalid_checkpoint_require_intervention(self):
        self.prepared()
        self.root.write_text(self.repo / "SPEC.md", "Changed scope\n")
        with self.assertRaisesRegex(RunnerError, "configuration/documents changed"):
            self.setup()
        self.root.write_text(self.repo / ".git/ralph/setup.json", "{}")
        with self.assertRaisesRegex(RunnerError, "Invalid setup checkpoint"):
            self.setup()

    def test_inaccessible_existing_origin_is_not_recreated(self):
        self.git("init", "--initial-branch=main")
        self.git("remote", "add", "origin", "https://github.com/fixtures/project.git")
        with self.assertRaisesRegex(RunnerError, "Existing origin is inaccessible"):
            self.setup()
        self.assertIsNone(self.repository)
        self.assertFalse(any("create" in a for a in self.calls))

    def test_ambiguous_push_origin_is_not_replaced(self):
        self.git("init", "--initial-branch=main")
        self.git("remote", "add", "origin", "https://github.com/fixtures/project.git")
        self.git("config", "remote.origin.pushurl", "https://github.com/other/project.git")
        with self.assertRaisesRegex(RunnerError, "identical fetch/push"):
            self.setup()
        self.assertFalse(any(a[0] == "gh" for a in self.calls))

    def test_invalid_dev_ref_stops_before_initialization(self):
        self.root.write_text(self.filename, self.filename.read_text().replace('"development"', '"development/"'))
        self.project = Project.load(self.filename)
        with self.assertRaisesRegex(RunnerError, "not a valid branch name"):
            self.setup()
        self.assertFalse((self.repo / ".git").exists())
        self.assertFalse(any(a[0] == "gh" for a in self.calls))

    def test_unborn_dev_requires_manual_main_selection(self):
        self.git("init", "--initial-branch=development")
        with self.assertRaisesRegex(RunnerError, "Unborn checkout must use main"):
            self.setup()
        self.assertFalse(any(a[0] == "gh" for a in self.calls))
        self.assertIsNone(self.remote_branch("main"))

    def test_missing_admin_permission_blocks_baseline_publication(self):
        self.repository = self.metadata()
        self.repository["permissions"]["admin"] = False
        with self.assertRaisesRegex(RunnerError, "admin permission"):
            self.setup()
        self.assertIsNone(self.remote_branch("main"))
        self.assertFalse(any("push" in a or "PUT" in a for a in self.calls))

    def test_lock_shared_with_run(self):
        self.prepared()
        with checkpoint_area(GitBoundary(self.project, process=self.process, env=self.env)):
            with self.assertRaisesRegex(RunnerError, "lock"):
                self.setup()

    def test_setup_followed_by_run_preserves_main(self):
        main = self.prepared()
        def agent(project, milestone, documents, env):
            self.root.write_text(self.repo / "feature.txt", "implemented")
            self.root.write_text(self.repo / "PROGRESS.md", documents["PROGRESS.md"] + "\nImplemented.\n")
            return {"milestone": milestone.id, "status": "success", "summary": "Implemented fixture",
                    "blockers": [], "commit_message": "Implement fixture"}
        Loop(self.project, git=GitBoundary(self.project, process=self.process, env=self.env),
             agent=agent, announce=lambda m: None).run()
        self.assertEqual(self.git("rev-parse", "main"), main)
        self.assertEqual(self.remote_branch("main"), main)
        self.assertNotEqual(self.remote_branch("development"), main)
        with self.assertRaisesRegex(RunnerError, "run checkpoint exists"):
            self.setup()


if __name__ == "__main__":
    unittest.main()
