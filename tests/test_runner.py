"""Real local Git publication; fake Codex/GitHub; owned disposable targets only."""

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from agentic_runner.git_boundary import GitBoundary
from agentic_runner.headless import generate
from agentic_runner.project import Project, RunnerError
from agentic_runner.runner import Loop, checkpoint_area
from agentic_runner.roadmap import parse_roadmap
from agentic_runner.supervisor import ProcessResult, supervise
from tests.support.fixtures import FixtureFactory
from tests.support.isolation import DisposableRoot
from tests.support.projects import ROADMAP, git_fixture, make_project


PROTECTION = {"enforce_admins": {"enabled": True}, "required_pull_request_reviews": {},
              "allow_force_pushes": {"enabled": False}, "allow_deletions": {"enabled": False}}


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.factory = FixtureFactory(self.root)
        self.repo = make_project(self.root)
        self.env = self.factory.environment()
        self.protection = copy.deepcopy(PROTECTION)
        self.calls, self.sessions = [], []
        self.agent_action = self.check_action = None
        self.fail_push = self.lost_push = self.lost_commit = False
        for name in ("AGENTS.md", "SPEC.md", "ARCHITECTURE.md", "PROGRESS.md"):
            self.root.write_text(self.repo / name, f"# {name}\nGenerated fixture.\n")
        self.root.write_text(self.repo / "ROADMAP.md", ROADMAP.replace("| M1 | complete |", "| M1 | not started |"))
        config = self.repo / ".git/config"
        self.root.write_text(config, config.read_text().replace("https://example.invalid/fixtures/project.git", "https://github.com/fixtures/project.git").replace("fixture@example.invalid", "123+fixture@users.noreply.github.com"))
        git_fixture(self.root, self.repo, "add", "--all")
        git_fixture(self.root, self.repo, "commit", "-m", "Prepared documents")
        self.remote = self.root.mkdir("remote.git")
        self.local_git("init", "--bare", str(self.remote))
        self.local_git("push", str(self.remote), "HEAD:refs/heads/main")
        self.main = self.local_git("rev-parse", "main").strip()
        self.local_git("switch", "-c", "development")
        self.local_git("push", str(self.remote), "HEAD:refs/heads/development")
        self.filename = self.root.write_text("project.toml", f'''[project]
name = "fixtures/project"
repository = "{self.repo}"
development_branch = "development"
verification = [["{sys.executable}", "-c", "pass"]]
''')
        self.project = Project.load(self.filename)

    def local_git(self, *args):
        self.root.require(self.repo)
        self.root.require(self.repo / ".git")
        result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", *args],
                                cwd=self.repo, env=self.env, capture_output=True, text=True, check=True)
        return result.stdout

    def process(self, argv, **kwargs):
        self.root.require(kwargs["cwd"])
        self.assertEqual(kwargs["env"]["HOME"], self.env["HOME"])
        self.calls.append(list(argv))
        if argv[0] == "gh":
            self.assertEqual(argv[1:], ["api", "--hostname", "github.com", "repos/fixtures/project/branches/main/protection"])
            return ProcessResult(0, json.dumps(self.protection).encode(), b"")
        if argv[0] == "git":
            if "push" in argv and self.fail_push:
                return ProcessResult(1, b"", b"injected push failure")
            argv = [str(self.remote) if a == "https://github.com/fixtures/project.git" else a for a in argv]
            result = supervise(argv, **kwargs)
            if "push" in argv and self.lost_push:
                return ProcessResult(1, b"", b"lost successful push response")
            if "commit" in argv and self.lost_commit:
                return ProcessResult(1, b"", b"lost successful commit response")
            return result
        if self.check_action:
            self.check_action()
        return supervise(argv, **kwargs)

    def agent(self, project, milestone, documents, env):
        self.root.require(project.repository)
        self.sessions.append(milestone.id)
        self.root.write_text(self.repo / f"feature-{milestone.id}.txt", "partial then complete\n")
        progress = self.repo / "PROGRESS.md"
        self.root.write_text(progress, progress.read_text() + f"\nImplemented {milestone.id}.\n")
        report = {"milestone": milestone.id, "status": "success", "summary": "Implemented fixture",
                  "blockers": [], "commit_message": f"Implement {milestone.id}"}
        if self.agent_action:
            return self.agent_action(report)
        return report

    def loop(self, *, live_agent=None):
        return Loop(self.project, git=GitBoundary(self.project, process=self.process, env=self.env),
                    agent=live_agent or self.agent, announce=lambda message: None)

    def checkpoint(self):
        return json.loads((self.repo / ".git/ralph/checkpoint.json").read_text())

    def assert_main_untouched(self):
        self.assertEqual(self.local_git("rev-parse", "main").strip(), self.main)
        self.assertEqual(self.local_git("ls-remote", str(self.remote), "refs/heads/main").split()[0], self.main)
        for args in self.calls:
            if "push" in args:
                self.assertEqual(args[-1], "HEAD:refs/heads/development")

    def test_two_milestones_commit_push_and_completed_rerun(self):
        self.loop().run()
        self.assertEqual(self.sessions, ["M1", "M2"])
        self.assertEqual(self.checkpoint()["phase"], "complete")
        self.assertEqual(self.local_git("rev-list", "--count", f"{self.main}..HEAD").strip(), "2")
        self.assertEqual(self.local_git("status", "--porcelain"), "")
        self.assertEqual(self.local_git("ls-remote", str(self.remote), "refs/heads/development").split()[0], self.local_git("rev-parse", "HEAD").strip())
        self.assert_main_untouched()
        self.loop().run()
        self.assertEqual(self.sessions, ["M1", "M2"])

    def test_failed_verification_preserves_work_and_fresh_manual_run_resumes(self):
        def fail():
            raise RunnerError("injected required check failure")
        self.check_action = fail
        with self.assertRaisesRegex(RunnerError, "required check"):
            self.loop().run()
        self.assertEqual(self.sessions, ["M1"])
        self.assertTrue((self.repo / "feature-M1.txt").exists())
        self.assertIn("| M1 | not started |", (self.repo / "ROADMAP.md").read_text())
        self.assertIn("required check", self.checkpoint()["issue"])
        self.assertIn("Runner stopped", (self.repo / "PROGRESS.md").read_text())
        self.assertEqual(self.local_git("rev-parse", "HEAD").strip(), self.main)
        self.check_action = None
        self.loop().run()
        self.assertEqual(self.sessions, ["M1", "M1", "M2"])
        self.assert_main_untouched()

    def test_real_nonzero_check_cannot_publish(self):
        self.root.write_text(self.filename, self.filename.read_text().replace('"pass"', '"raise SystemExit(7)"'))
        self.project = Project.load(self.filename)
        with self.assertRaisesRegex(RunnerError, "Verification failed"):
            self.loop().run()
        self.assertEqual(self.sessions, ["M1"])
        self.assertEqual(self.local_git("rev-parse", "HEAD").strip(), self.main)
        self.assertTrue((self.repo / ".git/ralph/last-failure.stderr").exists())

    def test_agent_process_failure_preserves_partial_work(self):
        def crash(report):
            raise RunnerError("Codex failed")
        self.agent_action = crash
        with self.assertRaisesRegex(RunnerError, "Codex failed"):
            self.loop().run()
        self.assertTrue((self.repo / "feature-M1.txt").exists())
        self.agent_action = None
        self.loop().run()
        self.assertEqual(self.sessions, ["M1", "M1", "M2"])

    def test_blocked_and_malformed_reports_cannot_publish(self):
        for change in (lambda r: r.update(status="blocked", blockers=["Need input"]),
                       lambda r: r.update(blockers=["contradictory success"]),
                       lambda r: r.update(milestone="M99"), lambda r: r.update(commit_message="bad\nmessage"),
                       lambda r: r.pop("summary")):
            def action(report):
                change(report)
                return report
            self.agent_action = action
            with self.assertRaises(RunnerError):
                self.loop().run()
            self.assertEqual(self.local_git("rev-parse", "HEAD").strip(), self.main)
        self.assert_main_untouched()

    def test_agent_staging_or_control_edit_is_rejected(self):
        def stage(report):
            self.local_git("add", "feature-M1.txt")
            return report
        self.agent_action = stage
        with self.assertRaisesRegex(RunnerError, "staged"):
            self.loop().run()
        self.assertEqual(self.sessions, ["M1"])
        self.assert_main_untouched()

    def test_agent_control_edit_preserved_with_checkpoint_issue(self):
        def change(report):
            self.root.write_text(self.repo / "SPEC.md", "Changed scope\n")
            return report
        self.agent_action = change
        with self.assertRaisesRegex(RunnerError, "Protected"):
            self.loop().run()
        self.assertEqual((self.repo / "SPEC.md").read_text(), "Changed scope\n")
        self.assertIn("Protected", self.checkpoint()["issue"])
        self.assert_main_untouched()

    def test_success_without_session_progress_update_is_rejected(self):
        original = (self.repo / "PROGRESS.md").read_text()
        def omit_progress(report):
            self.root.write_text(self.repo / "PROGRESS.md", original)
            return report
        self.agent_action = omit_progress
        with self.assertRaisesRegex(RunnerError, "must update PROGRESS"):
            self.loop().run()
        self.assertEqual(self.sessions, ["M1"])
        self.assert_main_untouched()

    def test_agent_branch_change_does_not_write_progress_on_main(self):
        def change(report):
            self.local_git("switch", "main")
            self.progress_at_violation = (self.repo / "PROGRESS.md").read_bytes()
            return report
        self.agent_action = change
        with self.assertRaisesRegex(RunnerError, "Wrong branch"):
            self.loop().run()
        self.assertEqual((self.repo / "PROGRESS.md").read_bytes(), self.progress_at_violation)
        self.assert_main_untouched()

    def test_unexpected_commit_not_adopted(self):
        def commit(report):
            self.local_git("add", "--all")
            self.local_git("commit", "-m", "Agent violated Git contract")
            return report
        self.agent_action = commit
        with self.assertRaisesRegex(RunnerError, "HEAD"):
            self.loop().run()
        self.assertEqual(self.sessions, ["M1"])
        self.assertEqual(self.checkpoint()["phase"], "implementing")
        self.assert_main_untouched()

    def test_verification_mutation_rejected(self):
        self.check_action = lambda: self.root.write_text(self.repo / "feature-M1.txt", "changed by check\n")
        with self.assertRaisesRegex(RunnerError, "modified publishable"):
            self.loop().run()
        self.assertEqual(self.local_git("rev-parse", "HEAD").strip(), self.main)

    def test_symlink_rejected_before_verification(self):
        def link(report):
            self.root.require(self.repo / "link").symlink_to(self.repo / "SPEC.md")
            return report
        self.agent_action = link
        with self.assertRaisesRegex(RunnerError, "Symlink"):
            self.loop().run()
        self.assertEqual(self.local_git("rev-parse", "HEAD").strip(), self.main)

    def test_push_failure_manual_retry_finishes_publication_first(self):
        self.fail_push = True
        with self.assertRaises(RunnerError):
            self.loop().run()
        self.assertEqual(self.sessions, ["M1"])
        commit = self.local_git("rev-parse", "HEAD").strip()
        self.assertNotEqual(commit, self.main)
        self.assertEqual(self.checkpoint()["phase"], "publishing")
        self.fail_push = False
        self.loop().run()
        self.assertEqual(self.sessions, ["M1", "M2"])
        self.assertEqual(self.local_git("rev-parse", "HEAD^").strip(), commit)
        self.assert_main_untouched()

    def test_successful_push_with_lost_response_is_reconciled(self):
        self.lost_push = True
        with self.assertRaises(RunnerError):
            self.loop().run()
        self.lost_push = False
        self.loop().run()
        self.assertEqual(self.sessions, ["M1", "M2"])
        self.assert_main_untouched()

    def test_successful_commit_with_lost_response_is_reconciled(self):
        self.lost_commit = True
        with self.assertRaises(RunnerError):
            self.loop().run()
        self.lost_commit = False
        self.loop().run()
        self.assertEqual(self.sessions, ["M1", "M2"])
        self.assert_main_untouched()

    def test_changed_publishing_files_stop_without_next_agent(self):
        self.fail_push = True
        with self.assertRaises(RunnerError):
            self.loop().run()
        self.root.write_text(self.repo / "unrelated.txt", "Human edit\n")
        self.fail_push = False
        with self.assertRaisesRegex(RunnerError, "Uncommitted"):
            self.loop().run()
        self.assertEqual(self.sessions, ["M1"])

    def test_wrong_branch_and_dirty_start(self):
        self.local_git("switch", "main")
        with self.assertRaisesRegex(RunnerError, "Wrong branch"):
            self.loop().run()
        self.assertFalse((self.repo / ".git/ralph").exists())
        self.local_git("switch", "development")
        self.root.write_text(self.repo / "unrelated.txt", "dirty\n")
        with self.assertRaisesRegex(RunnerError, "clean checkout"):
            self.loop().run()
        self.assertEqual(self.sessions, [])

    def test_missing_required_document_prevents_agent_launch(self):
        self.root.write_text(self.repo / "SPEC.md", "")
        with self.assertRaisesRegex(RunnerError, "document is empty"):
            self.loop().run()
        self.assertEqual(self.sessions, [])

    def test_main_ref_change_detected_without_automatic_repair(self):
        def change(report):
            git_fixture(self.root, self.repo, "update-ref", "refs/heads/main", "HEAD^")
            return report
        self.agent_action = change
        with self.assertRaisesRegex(RunnerError, "Local main changed"):
            self.loop().run()
        self.assertEqual(self.sessions, ["M1"])
        self.assertFalse(any("push" in args for args in self.calls))

    def test_config_change_blocks_manual_resume(self):
        self.check_action = lambda: (_ for _ in ()).throw(RunnerError("pause"))
        with self.assertRaises(RunnerError):
            self.loop().run()
        self.root.write_text(self.filename, self.filename.read_text() + "\n# changed\n")
        self.project = Project.load(self.filename)
        with self.assertRaisesRegex(RunnerError, "identity/version"):
            self.loop().run()
        self.assertEqual(self.sessions, ["M1"])

    def test_interrupted_before_commit_resumes_exact_verified_changes(self):
        original = self.process
        def fail_commit(argv, **kwargs):
            if argv[0] == "git" and "commit" in argv:
                return ProcessResult(1, b"", b"commit not issued")
            return original(argv, **kwargs)
        with patch.object(self, "process", side_effect=fail_commit):
            with self.assertRaises(RunnerError):
                self.loop().run()
        self.assertEqual(self.local_git("rev-parse", "HEAD").strip(), self.main)
        self.assertIn("| M1 | complete |", (self.repo / "ROADMAP.md").read_text())
        self.loop().run()
        self.assertEqual(self.sessions, ["M1", "M2"])
        self.assert_main_untouched()

    def test_unsafe_protection_never_launches_codex(self):
        for mutate in (lambda p: p.update(enforce_admins={"enabled": False}),
                       lambda p: p.update(required_pull_request_reviews=None),
                       lambda p: p.update(allow_force_pushes={"enabled": True}),
                       lambda p: p.update(allow_deletions={"enabled": True}),
                       lambda p: p.update(required_pull_request_reviews={"bypass_pull_request_allowances": {"users": [{"login": "fixture"}]}})):
            self.protection = copy.deepcopy(PROTECTION)
            mutate(self.protection)
            with self.assertRaises(RunnerError):
                self.loop().run()
        self.assertEqual(self.sessions, [])
        self.assert_main_untouched()

    def test_repository_lock_prevents_second_run(self):
        git = self.loop().git
        with checkpoint_area(git):
            with self.assertRaisesRegex(RunnerError, "lock"):
                self.loop().run()
        self.assertEqual(self.sessions, [])

    def test_config_rejects_main_and_missing_checks(self):
        for old, new in (("development", "main"), ('verification = [[', 'unknown = [[')):
            self.root.write_text("invalid.toml", self.filename.read_text().replace(old, new))
            with self.assertRaises(RunnerError):
                Project.load(self.root.path / "invalid.toml")

    def test_native_codex_launch_contract_and_strict_result(self):
        scratch = self.root.mkdir("codex-scratch")
        report = {"milestone": "M1", "status": "success", "summary": "Done", "blockers": [], "commit_message": "Implement M1"}
        def codex(argv, **kwargs):
            self.assertEqual(argv[:2], ["codex", "exec"])
            self.assertIn("--dangerously-bypass-approvals-and-sandbox", argv)
            self.assertIn('model_reasoning_effort="high"', argv)
            self.assertEqual([argv[i + 1] for i, arg in enumerate(argv) if arg == "--disable"], ["multi_agent", "multi_agent_v2"])
            self.assertEqual(argv[argv.index("--model") + 1], "gpt-6.1-sol")
            self.assertNotIn("resume", argv)
            self.assertIn(b"Perform NO Git or GitHub operations", kwargs["input_bytes"])
            self.root.write_text(Path(argv[argv.index("--output-last-message") + 1]), json.dumps(report))
            return ProcessResult(0, b"", b"")
        milestone = parse_roadmap((self.repo / "ROADMAP.md").read_text()).milestones[0]
        with patch("agentic_runner.headless.tempfile.TemporaryDirectory") as temporary:
            temporary.return_value.__enter__.return_value = str(scratch)
            self.assertEqual(generate(self.project, milestone, self.project.documents(), self.env, process=codex), report)


if __name__ == "__main__":
    unittest.main()
