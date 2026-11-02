"""Abrupt process loss against owned repositories, not exception-only recovery."""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from agentic_runner.durable import DurableIO
from agentic_runner.headless import generate
from agentic_runner.project import RunnerError
from agentic_runner.supervisor import ProcessResult
from tests import test_runner as fixtures


class RecoveryTests(unittest.TestCase):
    def case(self):
        case = fixtures.RunnerTests()
        case.setUp()
        self.addCleanup(case.doCleanups)
        return case

    def crash(self, action):
        pid = os.fork()
        if pid == 0:
            try:
                action()
            except BaseException:
                os._exit(98)
            os._exit(99)  # The selected crash boundary must actually be reached.
        _, status = os.waitpid(pid, 0)
        self.assertEqual(os.waitstatus_to_exitcode(status), 73)

    def test_process_exit_before_and_after_each_run_effect(self):
        for boundary in ("initial", "agent", "verification", "intent", "completion", "stage",
                         "tree", "commit", "commit_record", "push", "complete_record"):
            for when in ("before", "after"):
                with self.subTest(boundary=boundary, when=when):
                    case = self.case()

                    def child():
                        loop = case.loop()

                        def wrap(original, name):
                            def call(*args, **kwargs):
                                selected = name
                                if name == "save":
                                    record = args[0]
                                    selected = ("initial" if record["phase"] == "implementing" else
                                                "complete_record" if record["phase"] == "complete" else
                                                "commit_record" if "commit" in record else
                                                "tree" if "tree" in record else "intent")
                                elif name == "git":
                                    selected = "stage" if args[0] == "add" else args[0]
                                if selected == boundary and when == "before":
                                    os._exit(73)
                                result = original(*args, **kwargs)
                                if selected == boundary and when == "after":
                                    os._exit(73)
                                return result
                            return call

                        for obj, attribute, name in ((loop, "agent", "agent"), (loop, "verify", "verification"),
                                                     (loop, "save", "save"), (loop, "write_completion", "completion"),
                                                     (loop.git, "git", "git"), (loop.git, "push", "push")):
                            setattr(obj, attribute, wrap(getattr(obj, attribute), name))
                        loop.run()

                    self.crash(child)
                    state = case.repo / ".git/ralph/checkpoint.json"
                    phase = json.loads(state.read_text())["phase"] if state.exists() else None
                    case.assert_main_untouched()
                    case.loop().run()  # Also proves the dead process released flock.
                    self.assertEqual(case.sessions, ["M1", "M2"] if phase in {None, "implementing"} else ["M2"])
                    self.assertEqual(case.local_git("rev-list", "--count", f"{case.main}..HEAD").strip(), "2")
                    self.assertEqual(case.checkpoint()["phase"], "complete")
                    case.assert_main_untouched()

    def test_completion_atomic_write_process_loss_recovers_without_new_agent(self):
        for point in ("atomic.opened", "atomic.written", "atomic.file_synced", "atomic.replaced", "atomic.directory_synced"):
            with self.subTest(point=point):
                case = self.case()

                def child():
                    def atomic(io, path, data, **kwargs):
                        if path.name == "ROADMAP.md":
                            io.checkpoint = lambda name: os._exit(73) if name == point else None
                        return original(io, path, data, **kwargs)
                    original = DurableIO.atomic
                    with patch.object(DurableIO, "atomic", atomic):
                        case.loop().run()

                self.crash(child)
                self.assertEqual(case.checkpoint()["phase"], "publishing")
                case.loop().run()
                self.assertEqual(case.sessions, ["M2"])
                self.assertEqual(case.local_git("status", "--porcelain"), "")
                case.assert_main_untouched()

    def test_publication_checkpoint_atomic_process_loss_recovers_old_or_new_intent(self):
        for point in ("atomic.opened", "atomic.written", "atomic.file_synced", "atomic.replaced", "atomic.directory_synced"):
            with self.subTest(point=point):
                case = self.case()

                def child():
                    def atomic(io, path, data, **kwargs):
                        if path.name == "checkpoint.json" and json.loads(data)["phase"] == "publishing":
                            io.checkpoint = lambda name: os._exit(73) if name == point else None
                        return original(io, path, data, **kwargs)
                    original = DurableIO.atomic
                    with patch.object(DurableIO, "atomic", atomic):
                        case.loop().run()

                self.crash(child)
                phase = case.checkpoint()["phase"]
                case.loop().run()
                self.assertEqual(case.sessions, ["M1", "M2"] if phase == "implementing" else ["M2"])
                case.assert_main_untouched()

    def test_blocked_second_milestone_resumes_only_unfinished_work(self):
        case = self.case()
        def block(report):
            if report["milestone"] == "M2":
                report.update(status="blocked", blockers=["operator input required"])
            return report
        case.agent_action = block
        with self.assertRaisesRegex(RunnerError, "blocked"):
            case.loop().run()
        first = case.local_git("rev-parse", "HEAD").strip()
        self.assertEqual(case.sessions, ["M1", "M2"])
        self.assertEqual(case.checkpoint()["milestone"], "M2")
        self.assertTrue((case.repo / "feature-M2.txt").exists())
        case.agent_action = None
        case.loop().run()
        self.assertEqual(case.sessions, ["M1", "M2", "M2"])
        self.assertEqual(case.local_git("rev-parse", "HEAD^").strip(), first)
        case.assert_main_untouched()

    def test_changes_during_completion_cannot_enter_verified_tree(self):
        case = self.case()
        loop = case.loop()
        original = loop.write_completion
        def mutate(record):
            original(record)
            case.root.write_text(case.repo / "feature-M1.txt", "unverified replacement\n")
        loop.write_completion = mutate
        with self.assertRaisesRegex(RunnerError, "during roadmap completion"):
            loop.run()
        self.assertEqual(case.sessions, ["M1"])
        self.assertEqual(case.checkpoint()["phase"], "publishing")
        self.assertEqual(case.local_git("rev-parse", "HEAD").strip(), case.main)
        case.assert_main_untouched()

    def test_completion_preserves_document_permissions(self):
        case = self.case()
        case.root.require(case.repo / "ROADMAP.md").chmod(0o755)
        case.local_git("add", "ROADMAP.md")
        case.local_git("commit", "-m", "Fixture document mode")
        case.local_git("push", str(case.remote), "HEAD:refs/heads/development")
        case.loop().run()
        self.assertEqual((case.repo / "ROADMAP.md").stat().st_mode & 0o777, 0o755)
        case.assert_main_untouched()

    def test_completed_rerun_rechecks_remote_main_dev_and_protection(self):
        for violation in ("main", "development", "protection", "commit"):
            with self.subTest(violation=violation):
                case = self.case()
                case.loop().run()
                if violation in {"main", "development"}:
                    case.local_git("--git-dir", str(case.remote), "update-ref", f"refs/heads/{violation}", case.main)
                    if violation == "main":
                        case.local_git("--git-dir", str(case.remote), "update-ref", "refs/heads/main",
                                       case.local_git("rev-parse", "HEAD").strip())
                elif violation == "commit":
                    case.local_git("commit", "--allow-empty", "-m", "Unrelated human commit")
                else:
                    case.protection["enforce_admins"]["enabled"] = False
                with self.assertRaises(RunnerError):
                    case.loop().run()
                self.assertEqual(case.sessions, ["M1", "M2"])

    def test_recorded_commit_cannot_be_replaced_by_same_tree_and_message(self):
        case = self.case()
        case.fail_push = True
        with self.assertRaises(RunnerError):
            case.loop().run()
        original = case.checkpoint()["commit"]
        tree = case.local_git("rev-parse", "HEAD^{tree}").strip()
        # Different metadata produces a different commit with identical intended content.
        replacement = case.local_git("commit-tree", tree, "-p", case.main, "-m", "Implement M1", "-m", "").strip()
        self.assertNotEqual(replacement, original)
        case.local_git("update-ref", "refs/heads/development", replacement)
        case.fail_push = False
        with self.assertRaisesRegex(RunnerError, "publication intent"):
            case.loop().run()
        self.assertEqual(case.sessions, ["M1"])
        case.assert_main_untouched()

    def test_keyboard_interrupt_during_agent_or_verification_preserves_work(self):
        for attribute in ("agent_action", "check_action"):
            with self.subTest(attribute=attribute):
                case = self.case()
                def interrupt(*args):
                    raise KeyboardInterrupt
                setattr(case, attribute, interrupt)
                with self.assertRaises(KeyboardInterrupt):
                    case.loop().run()
                self.assertIn("KeyboardInterrupt", case.checkpoint()["issue"])
                self.assertTrue((case.repo / "feature-M1.txt").exists())
                setattr(case, attribute, None)
                case.loop().run()
                self.assertEqual(case.sessions, ["M1", "M1", "M2"])
                case.assert_main_untouched()

    def test_failed_lost_and_invalid_headless_responses_retain_work_and_private_evidence(self):
        for response in ("timeout", "missing", "invalid"):
            with self.subTest(response=response):
                case = self.case()
                scratch = case.root.mkdir("headless-scratch")
                def process(argv, **kwargs):
                    case.root.write_text(case.repo / "partial-model-work.txt", "preserve me\n")
                    if response == "timeout":
                        return ProcessResult(-15, b"private partial output", b"private failure", "timeout")
                    if response == "invalid":
                        report = {"milestone": "M1", "status": "success", "summary": "Done",
                                  "blockers": [], "commit_message": "bad\nmessage"}
                        case.root.write_text(Path(argv[argv.index("--output-last-message") + 1]), json.dumps(report))
                    return ProcessResult(0, b"", b"")
                def agent(project, milestone, documents, env):
                    return generate(project, milestone, documents, env, process=process)
                with patch("agentic_runner.headless.tempfile.TemporaryDirectory") as temporary:
                    temporary.return_value.__enter__.return_value = str(scratch)
                    with self.assertRaises(RunnerError):
                        case.loop(live_agent=agent).run()
                self.assertEqual(case.local_git("rev-parse", "HEAD").strip(), case.main)
                self.assertEqual(case.checkpoint()["phase"], "implementing")
                self.assertTrue((case.repo / "partial-model-work.txt").exists())
                if response in {"timeout", "invalid"}:
                    private = case.repo / ".git/ralph" / ("last-failure.stderr" if response == "timeout" else "last-report.json")
                    self.assertTrue(private.is_file())
                    self.assertEqual(private.stat().st_mode & 0o777, 0o600)
                case.loop().run()
                self.assertEqual(case.sessions, ["M1", "M2"])
                case.assert_main_untouched()
