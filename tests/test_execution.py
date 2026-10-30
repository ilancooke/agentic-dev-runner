"""M4 unit tests: no Docker, accounts, network, or project code on the host."""

import json
import os
import sys
import threading
import unittest
import uuid
from pathlib import Path

from agentic_runner.approval import RunnerPolicy
from agentic_runner.codex import CodexAdapter, command, parse_events
from agentic_runner.durable import StateError
from agentic_runner.execution import ContainerExecutor, ContainerPolicy, ExecutionError, host_environment, validate_checkout
from agentic_runner.redaction import public_process, redact
from agentic_runner.run_state import Phase
from agentic_runner.state import open_store
from agentic_runner.state_boundary import StateBoundary
from agentic_runner.supervisor import ProcessResult, supervise
from tests.support.fixtures import FixtureFactory
from tests.support.isolation import DisposableRoot, IsolationError
from tests.support.projects import make_project


IMAGE = "sha256:" + "a" * 64


class ScriptedDocker:
    def __init__(self, *, fail_at=None):
        self.calls = []
        self.fail_at = fail_at

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        self.assert_clean(kwargs)
        args = argv[3:]
        verb = args[0]
        if self.fail_at == verb:
            return ProcessResult(125, b"", b"private failure")
        payload = b""
        if verb == "info":
            payload = json.dumps({"OSType": "linux", "CgroupVersion": "2", "ServerVersion": "test", "SecurityOptions": ["name=seccomp,profile=builtin", "name=apparmor,profile=default"]}).encode()
        elif verb == "image":
            payload = json.dumps([{"Id": IMAGE, "Config": {"Labels": {"org.agentic-runner.environment": "m4-v1"}}}]).encode()
        elif verb == "create":
            self.create = args
            payload = ("b" * 64 + "\n").encode()
        elif verb == "start":
            self.started = True
            payload = b"project output\n"
        elif verb == "inspect":
            if args[2] == "{{json .}}":
                create = self.create
                name = create[create.index("--name") + 1]
                mount = create[create.index("--mount") + 1]
                source = mount.split("src=", 1)[1].split(",", 1)[0]
                payload = json.dumps({"Name": "/" + name, "Image": IMAGE, "AppArmorProfile": "docker-default",
                           "Config": {"Labels": {"org.agentic-runner.operation": name}, "User": f"{os.getuid()}:{os.getgid()}"},
                           "HostConfig": {"NetworkMode": "none", "ReadonlyRootfs": True, "Privileged": False, "CapAdd": None,
                           "CapDrop": ["ALL"], "SecurityOpt": ["no-new-privileges:true", "apparmor=docker-default"], "Memory": 1024*1024*1024,
                           "PidsLimit": 128, "NanoCpus": 1000000000, "Tmpfs": {"/tmp": "rw", "/home/runner": "rw", "/workspace/.git": "ro"}},
                           "Mounts": [{"Type": "bind", "Source": source, "Destination": "/workspace", "RW": True}], "State": {"Running": False, "ExitCode": 0, "OOMKilled": False}}).encode()
            else:
                payload = json.dumps({"Running": False, "ExitCode": 0, "OOMKilled": False}).encode()
        return ProcessResult(0, payload, b"")

    @staticmethod
    def assert_clean(kwargs):
        if kwargs["env"] != host_environment() or kwargs["cwd"] != "/tmp":
            raise AssertionError("Host environment leaked")


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.project = make_project(self.root)
        self.boundary = StateBoundary.for_test(self.root, self.root.path / "state")
        self.policy = ContainerPolicy(IMAGE)

    def store(self, *, legacy=False):
        return open_store(self.project, self.boundary, policy=RunnerPolicy() if legacy else RunnerPolicy(execution=self.policy.record()))

    def begin(self, store):
        store.start_run()
        return store.transition(1, Phase.IMPLEMENTING)

    def test_intent_precedes_container_effect_and_result_is_not_verification(self):
        docker = ScriptedDocker()
        original = docker.__call__
        with self.store() as store:
            self.begin(store)
            def run(argv, **kwargs):
                if argv[3] == "create":
                    pending = store.load()["pending"]
                    self.assertEqual(pending["details"]["policy"], self.policy.record())
                    self.assertEqual(pending["expected_commit"], store.load()["approval"]["approved_revision"])
                return original(argv, **kwargs)
            result = ContainerExecutor(self.policy, runner=run).execute(store, 2, ["python", "-c", "print('private')"])
            self.assertEqual(result.returncode, 0)
            state = store.load()
            self.assertEqual(state["phase"], "implementing")
            self.assertIsNone(state["pending"])
            self.assertNotIn("private", json.dumps(store.history()))
        create = next(a for a, _ in docker.calls if a[3] == "create")
        self.assertIn("none", create)
        self.assertIn("--read-only", create)
        self.assertFalse(any("docker.sock" in a for a in create[4:]))

    def test_legacy_policy_is_readable_but_cannot_authorize_execution(self):
        docker = ScriptedDocker()
        with self.store(legacy=True) as store:
            self.begin(store)
            self.assertEqual(store.load()["approval"]["configuration"]["policy"]["version"], 1)
            with self.assertRaises(ExecutionError):
                ContainerExecutor(self.policy, runner=docker).execute(store, 2, ["python", "-V"])
        self.assertFalse(docker.calls)

    def test_execution_policy_change_invalidates_authorization(self):
        with self.store() as store:
            self.begin(store)
        policy = RunnerPolicy(execution=ContainerPolicy(IMAGE, timeout=60).record())
        with open_store(self.project, self.boundary, policy=policy) as store:
            with self.assertRaises(StateError) as caught:
                store.check_authorization(2)
            self.assertEqual(caught.exception.diagnostic.code, "approval.invalidated")
            self.assertEqual(store.load()["phase"], "approval_required")

    def test_uncertain_create_attach_inspect_or_cleanup_preserves_intent(self):
        for verb in ("create", "start", "inspect", "rm"):
            with self.subTest(verb=verb):
                boundary = StateBoundary.for_test(self.root, self.root.path / ("state-" + verb))
                with open_store(self.project, boundary, policy=RunnerPolicy(execution=self.policy.record())) as store:
                    self.begin(store)
                    docker = ScriptedDocker(fail_at=verb)
                    executor = ContainerExecutor(self.policy, runner=docker)
                    with self.assertRaises(ExecutionError):
                        executor.execute(store, 2, ["python", "-V"])
                    pending = store.load()["pending"]
                    self.assertIsNotNone(pending)
                    self.assertTrue(any(a[3] == "kill" for a, _ in docker.calls))
                    count = len(docker.calls)
                    with self.assertRaises(ExecutionError):
                        executor.execute(store, store.load()["revision"], ["python", "-V"])
                    self.assertEqual(len(docker.calls), count)

    def test_unsupported_capabilities_stop_before_intent_or_create(self):
        with self.store() as store:
            self.begin(store)
            for verb in ("info", "image"):
                docker = ScriptedDocker(fail_at=verb)
                with self.assertRaises(ExecutionError):
                    ContainerExecutor(self.policy, runner=docker).execute(store, 2, ["python", "-V"])
                self.assertIsNone(store.load()["pending"])
                self.assertFalse(any(a[3] == "create" for a, _ in docker.calls))

    def test_scope_edits_stale_revision_and_paused_run_never_launch(self):
        docker = ScriptedDocker()
        executor = ContainerExecutor(self.policy, runner=docker)
        with self.store() as store:
            self.begin(store)
            store.transition(2, Phase.PAUSED)
            for revision in (2, 3):
                with self.assertRaises(StateError):
                    executor.execute(store, revision, ["python", "-V"])
            self.root.write_text(self.project / "ROADMAP.md", (self.project / "ROADMAP.md").read_text().replace("The declared checks pass.", "Weakened scope."))
            with self.assertRaises(StateError):
                executor.execute(store, 3, ["python", "-V"])
            self.assertEqual(store.load()["phase"], "approval_required")
        self.assertFalse(any(a[3] == "create" for a, _ in docker.calls))

    def test_guard_rejects_sensitive_files_aliases_hardlinks_and_unowned_roots(self):
        with self.assertRaises(IsolationError):
            validate_checkout(Path.cwd(), self.boundary)
        for name in (".env", ".aws", ".npmrc"):
            file = self.root.write_text(self.project / name, "generated-secret")
            with self.assertRaises(ExecutionError):
                validate_checkout(self.project, self.boundary)
            file.unlink()
        alias = self.root.require(self.project / "escape")
        alias.symlink_to(self.root.path / "outside")
        with self.assertRaises(ExecutionError):
            validate_checkout(self.project, self.boundary)
        alias.unlink()
        other = self.root.write_text("outside", "sentinel")
        os.link(other, alias)
        with self.assertRaises(ExecutionError):
            validate_checkout(self.project, self.boundary)
        alias.unlink()
        alias.symlink_to(self.project / "README.md")
        self.assertEqual(validate_checkout(self.project, self.boundary), self.project)

    def test_unsafe_image_limits_and_model_downgrades_are_rejected(self):
        for policy in (ContainerPolicy("latest"), ContainerPolicy(IMAGE, pids=0), ContainerPolicy(IMAGE, timeout=True)):
            with self.assertRaises(ExecutionError):
                policy.record()
        for policy in (RunnerPolicy(requested_model="smaller"), RunnerPolicy(reasoning_effort="low")):
            with self.assertRaises(StateError):
                policy.as_dict()

    def test_weakened_created_container_is_never_started(self):
        with self.store() as store:
            self.begin(store)
            docker = ScriptedDocker()
            def compromised(argv, **kwargs):
                result = docker(argv, **kwargs)
                if argv[3] == "inspect":
                    item = json.loads(result.stdout)
                    item["HostConfig"]["Privileged"] = True
                    return ProcessResult(0, json.dumps(item).encode(), b"")
                return result
            with self.assertRaises(ExecutionError) as caught:
                ContainerExecutor(self.policy, runner=compromised).execute(store, 2, ["python", "-V"])
            self.assertEqual(caught.exception.diagnostic.code, "execution.inspect")
            self.assertFalse(any(a[3] == "start" for a, _ in docker.calls))
            self.assertIsNotNone(store.load()["pending"])


class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.cwd = self.root.mkdir("worker")
        self.environment = FixtureFactory(self.root).environment()

    def run_python(self, source, **kwargs):
        return supervise([sys.executable, "-I", "-c", source], cwd=self.root.require(self.cwd), env=self.environment, **kwargs)

    def test_captures_both_streams_and_passes_bounded_stdin(self):
        result = self.run_python("import sys; print(sys.stdin.read()); print('diagnostic', file=sys.stderr)", input_bytes=b"prompt")
        self.assertEqual(result.stdout, b"prompt\n")
        self.assertEqual(result.stderr, b"diagnostic\n")
        self.assertIsNone(result.stopped)

    def test_timeout_and_process_group_descendant_cleanup(self):
        result = self.run_python("import os, time; p=os.fork(); print(p, flush=True); time.sleep(30)", timeout=0.2)
        self.assertEqual(result.stopped, "timeout")
        # A descendant must not keep stdout/stderr open for 30 seconds.
        self.assertLess(len(result.stdout), 100)

    def test_cancellation_and_output_limit(self):
        cancel = threading.Event()
        cancel.set()
        self.assertEqual(self.run_python("while True: pass", cancel=cancel).stopped, "cancelled")
        result = self.run_python("import os;\nwhile True: os.write(1, b'x'*65536)", limit=8192)
        self.assertEqual(result.stopped, "output_limit")
        self.assertEqual(len(result.stdout) + len(result.stderr), 8192)

    def test_unread_stdin_is_bounded_by_timeout(self):
        result = self.run_python("import time; time.sleep(30)", timeout=0.2, input_bytes=b"x" * 65536)
        self.assertEqual(result.stopped, "timeout")


class CodexContractTests(unittest.TestCase):
    def events(self, session=None):
        return [dict(type="thread.started", thread_id=session or str(uuid.uuid4())), dict(type="turn.started"),
                dict(type="item.completed", item=dict(type="agent_message", text=json.dumps(dict(milestone="M2", summary="Generated report", status="reported")))),
                dict(type="turn.completed", usage={"input_tokens": 15, "output_tokens": 9})]

    def encode(self, events):
        return ("\n".join(json.dumps(e) for e in events) + "\n").encode()

    def test_reports_retain_session_and_usage_without_authorizing_publication(self):
        events = self.events()
        result = parse_events(self.encode(events), milestone="M2", expected_session=events[0]["thread_id"])
        self.assertEqual(result["session_id"], events[0]["thread_id"])
        self.assertEqual(result["reasoning_effort"], "high")
        self.assertEqual(result["model"], "gpt-6.1-sol")
        self.assertNotIn("verified", result)

    def test_incomplete_failures_wrong_sessions_and_invalid_reports_stop(self):
        events = self.events()
        cases = [self.encode(events[:-1]), self.encode(events)[:-1], b"not-json\n",
                 self.encode([*events, events[-1]]), self.encode([*events[:-1], dict(type="turn.failed")])]
        for data in cases:
            with self.subTest(data=data):
                with self.assertRaises(ExecutionError):
                    parse_events(data, milestone="M2")
        for kwargs in ({"milestone": "M3"}, {"milestone": "M2", "expected_session": str(uuid.uuid4())}):
            with self.assertRaises(ExecutionError):
                parse_events(self.encode(events), **kwargs)

    def test_resume_reasserts_identical_permissions_and_exact_model(self):
        session = str(uuid.uuid4())
        fresh = command()
        resumed = command(resume_id=session)
        self.assertEqual(fresh[1:fresh.index("exec")], resumed[1:resumed.index("exec")])
        self.assertIn('approval_policy="never"', resumed)
        self.assertIn('model_reasoning_effort="high"', resumed)
        self.assertFalse(any("bypass" in a or a == "--last" for a in resumed))
        for value in ("last", "", "name", None):
            if value is not None:
                with self.assertRaises(ExecutionError):
                    command(resume_id=value)
        with self.assertRaises(ExecutionError):
            CodexAdapter(None).generate()

    def test_log_redaction_and_public_output_omission(self):
        raw = 'Bearer abc-secret api_key="key-secret" access_token: token-secret ghp_abcdefgh sk-project-secret https://name:pass@example.invalid/'
        cleaned = redact(raw, ["arbitrary-secret"])
        for secret in ("abc-secret", "key-secret", "token-secret", "ghp_abcdefgh", "sk-project-secret", "name:pass"):
            self.assertNotIn(secret, cleaned)
        self.assertNotIn("arbitrary-secret", redact("arbitrary-secret", ["arbitrary-secret"]))
        public = public_process(ProcessResult(1, b"arbitrary-secret", b"private payload"))
        self.assertNotIn("secret", json.dumps(public))
