"""Trusted-VM execution on owned fixtures; no accounts/network/Docker needed."""

import json
import hashlib
import os
import sys
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from agentic_runner.approval import RunnerPolicy
from agentic_runner.durable import StateError
from agentic_runner.execution import ExecutionError
from agentic_runner.native_codex import NativeCodexAdapter, native_command
from agentic_runner.native_execution import NativeExecutor, NativePolicy
from agentic_runner.run_state import Phase
from agentic_runner.state import open_store
from agentic_runner.state_boundary import StateBoundary
from tests.support.isolation import DisposableRoot, IsolationError
from tests.support.projects import make_project


class NativeExecutionTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.project = make_project(self.root)
        self.home = self.root.mkdir("home")
        self.codex_home = self.root.mkdir("home/.codex")
        self.policy = NativePolicy(str(self.home), str(self.codex_home), timeout=5)
        self.boundary = StateBoundary.for_test(self.root, self.root.path / "state")

    def store(self, policy=None):
        return open_store(self.project, self.boundary, policy=RunnerPolicy(execution=(policy or self.policy).record()))

    def begin(self, store):
        store.start_run()
        store.transition(1, Phase.IMPLEMENTING)

    def test_native_execution_records_intent_and_uses_fixture_cwd(self):
        with self.store() as store:
            self.begin(store)
            result = NativeExecutor(self.policy).execute(store, 2, [sys.executable, "-I", "-c", "from pathlib import Path; Path('changed').write_text('retained'); print('PRIVATE_OUTPUT')"])
            self.assertEqual(result.returncode, 0)
            self.assertEqual((self.project / "changed").read_text(), "retained")
            self.assertEqual(store.load()["phase"], "implementing")
            self.assertIsNone(store.load()["pending"])
            self.assertNotIn("PRIVATE_OUTPUT", json.dumps(store.history()))
            self.assertEqual(store.history()[-2]["state"]["pending"]["details"]["mode"], "trusted-vm")

    def test_environment_drops_inherited_tokens_but_exposes_approved_fake_account(self):
        secret = "FAKE_ACCOUNT_CONTENT"
        self.root.write_text(self.home / "development-auth", secret)
        with self.store() as store:
            self.begin(store)
            source = "import os,pathlib; assert 'AWS_SECRET_ACCESS_KEY' not in os.environ; assert 'GH_TOKEN' not in os.environ; assert (pathlib.Path(os.environ['HOME'])/'development-auth').read_text()=='FAKE_ACCOUNT_CONTENT'"
            with patch.dict(os.environ, {"GH_TOKEN": "FAKE_GH", "AWS_SECRET_ACCESS_KEY": "FAKE_CLOUD"}):
                result = NativeExecutor(self.policy).execute(store, 2, [sys.executable, "-I", "-c", source])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn(secret, json.dumps(store.history()))

    def test_timeout_retains_partial_work_and_same_pending_operation(self):
        policy = NativePolicy(str(self.home), str(self.codex_home), timeout=1)
        with self.store(policy) as store:
            self.begin(store)
            executor = NativeExecutor(policy)
            with self.assertRaises(ExecutionError):
                executor.execute(store, 2, [sys.executable, "-I", "-c", "import time; from pathlib import Path; Path('partial').write_text('keep'); time.sleep(30)"])
            pending = store.load()["pending"]
            self.assertEqual((self.project / "partial").read_text(), "keep")
            with self.assertRaises(ExecutionError):
                executor.execute(store, store.load()["revision"], [sys.executable, "-V"])
            self.assertEqual(store.load()["pending"]["id"], pending["id"])

    def test_cancel_and_validator_failure_keep_pending(self):
        with self.store() as store:
            self.begin(store)
            executor = NativeExecutor(self.policy)
            def reject(result):
                raise ValueError("missing valid agent report")
            with self.assertRaises(ValueError):
                executor.execute(store, 2, [sys.executable, "-V"], validate=reject)
            self.assertIsNotNone(store.load()["pending"])

    def test_cancel_and_output_exhaustion_are_durable_until_reconciliation(self):
        for kind in ("cancel", "output"):
            with self.subTest(kind=kind):
                policy = NativePolicy(str(self.home), str(self.codex_home), timeout=5, output_limit=1024)
                boundary = StateBoundary.for_test(self.root, self.root.path / ("state-" + kind))
                with open_store(self.project, boundary, policy=RunnerPolicy(execution=policy.record())) as store:
                    self.begin(store)
                    cancel = threading.Event()
                    if kind == "cancel":
                        cancel.set()
                    with self.assertRaises(ExecutionError):
                        NativeExecutor(policy).execute(store, 2, [sys.executable, "-I", "-c", "import os;\nwhile True: os.write(1,b'x'*8192)"], cancel=cancel)
                    pending = store.load()["pending"]["id"]
                with open_store(self.project, boundary, policy=RunnerPolicy(execution=policy.record())) as store:
                    self.assertEqual(store.load()["pending"]["id"], pending)
                    resolved = store.resolve_operation(store.load()["revision"], pending, "confirmed", {"observed": "supervised child group terminated; partial output retained privately"})
                    self.assertIsNone(resolved["pending"])
                    self.assertEqual(resolved["phase"], "implementing")

    def test_native_codex_validates_reports_and_owns_resume_identity(self):
        session = str(uuid.uuid4())
        launched = []
        sha = hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
        policy = NativePolicy(str(self.home), str(self.codex_home), codex_binary=sys.executable, codex_sha256=sha)
        from agentic_runner.supervisor import ProcessResult
        def runner(argv, **kwargs):
            if argv[1:] == ["--version"]:
                output = b"codex-cli 0.166.0\n"
            elif argv[1:3] == ["debug", "models"]:
                output = json.dumps({"models": [{"slug": "gpt-6.1-sol", "supported_reasoning_levels": [{"effort": "high"}]}]}).encode()
            elif "--help" in argv:
                output = b"--json --output-schema --ignore-user-config --ignore-rules --dangerously-bypass-approvals-and-sandbox"
            else:
                self.assertIsNotNone(store.load()["pending"])
                launched.append(argv)
                output = ("\n".join(json.dumps(item) for item in [
                    {"type": "thread.started", "thread_id": session},
                    {"type": "item.completed", "item": {"type": "agent_message", "text": json.dumps({"milestone": "M2", "status": "reported", "summary": "PRIVATE_AGENT_SUMMARY"})}},
                    {"type": "turn.completed", "usage": {"input_tokens": 1, "output_tokens": 1}}]) + "\n").encode()
            return ProcessResult(0, output, b"")
        with self.store(policy) as store:
            self.begin(store)
            adapter = NativeCodexAdapter(NativeExecutor(policy, runner=runner))
            first = adapter.generate(store, 2, "private first prompt")
            self.assertEqual(first["session_id"], session)
            resumed = adapter.generate(store, store.load()["revision"], "private resume prompt", resume_id=session)
            self.assertEqual(resumed["session_id"], session)
            with self.assertRaises(ExecutionError):
                adapter.generate(store, store.load()["revision"], "foreign resume", resume_id=str(uuid.uuid4()))
            self.assertEqual(len(launched), 2)
            self.assertNotIn("PRIVATE_AGENT_SUMMARY", json.dumps(store.history()))
            self.assertNotIn("private first prompt", json.dumps(store.history()))
            self.assertEqual(store.load()["phase"], "implementing")

    def test_native_codex_bad_report_retains_private_diagnostic_and_intent(self):
        from agentic_runner.supervisor import ProcessResult
        policy = NativePolicy(str(self.home), str(self.codex_home))
        with self.store(policy) as store:
            self.begin(store)
            adapter = NativeCodexAdapter(NativeExecutor(policy, runner=lambda *a, **k: ProcessResult(0, b"incomplete", b"private diagnostic")))
            with patch.object(adapter, "inspect", return_value={}):
                with self.assertRaises(ExecutionError) as caught:
                    adapter.generate(store, 2, "generated test prompt")
            self.assertEqual(caught.exception.process.stderr, b"private diagnostic")
            self.assertIsNotNone(store.load()["pending"])
            self.assertNotIn("private diagnostic", json.dumps(store.history()))

    def test_invalidated_scope_old_policy_and_unowned_homes_never_launch(self):
        with self.store() as store:
            self.begin(store)
            executor = NativeExecutor(self.policy)
            with patch.object(executor, "runner") as run:
                self.root.write_text(self.project / "ROADMAP.md", (self.project / "ROADMAP.md").read_text().replace("The declared checks pass.", "Changed requirements."))
                with self.assertRaises(StateError):
                    executor.execute(store, 2, [sys.executable, "-V"])
                run.assert_not_called()
        wrong = NativeExecutor(NativePolicy("/home/ilan", "/home/ilan/.codex"))
        with self.store() as store:
            with self.assertRaises(IsolationError):
                wrong.guard(store)

    def test_native_policy_version_roundtrips_and_cannot_change_silently(self):
        with self.store() as store:
            self.begin(store)
            self.assertEqual(store.load()["approval"]["configuration"]["policy"]["version"], 4)
        changed = NativePolicy(str(self.home), str(self.codex_home), timeout=6)
        with self.store(changed) as store:
            with self.assertRaises(StateError):
                store.check_authorization(2)
            self.assertEqual(store.load()["phase"], "approval_required")

    def test_fresh_resume_explicitly_disable_sandbox_without_model_downgrade(self):
        scratch = self.root.mkdir("scratch")
        fresh = native_command(self.policy, self.project, scratch, scratch / "schema.json")
        resumed = native_command(self.policy, self.project, scratch, scratch / "schema.json", resume_id=str(uuid.uuid4()))
        self.assertEqual(fresh[:fresh.index("exec")], resumed[:resumed.index("exec")])
        self.assertIn('model_reasoning_effort="high"', fresh)
        self.assertIn('sandbox_mode="danger-full-access"', fresh)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", fresh)
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", resumed)
        self.assertNotIn("--last", resumed)
        self.assertFalse(any("permissions.runner" in a for a in resumed))

    def test_old_sandbox_policy_is_readable_but_cannot_launch(self):
        old = NativePolicy(str(self.home), str(self.codex_home), codex_sandbox="workspace-write")
        self.assertEqual(RunnerPolicy(execution=old.record()).as_dict()["version"], 3)
        with self.store(old) as store:
            self.begin(store)
            with self.assertRaises(ExecutionError):
                NativeExecutor(old).execute(store, 2, [sys.executable, "-V"])

    def test_legacy_policy_is_not_native_execution_authorization(self):
        with open_store(self.project, self.boundary) as store:
            self.begin(store)
            with self.assertRaises(ExecutionError):
                NativeExecutor(self.policy).execute(store, 2, [sys.executable, "-V"])

    def test_native_root_and_invalid_configuration_rejected(self):
        for policy in (NativePolicy("relative", str(self.codex_home)), NativePolicy(str(self.home), str(self.codex_home), timeout=True)):
            with self.assertRaises(ExecutionError):
                policy.record()
        with self.store() as store:
            with patch("os.getuid", return_value=0):
                with self.assertRaises(ExecutionError):
                    NativeExecutor(self.policy).guard(store)
