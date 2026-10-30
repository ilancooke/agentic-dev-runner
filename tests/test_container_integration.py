"""Opt-in *real* Docker checks, exclusively in live owned generated fixtures.

Set AGENTIC_RUNNER_M4_IMAGE to the reviewed immutable image ID. No account calls
or credentials are used. An unavailable sandbox is an explicit capability result,
never acceptance evidence that real Codex generation works.
"""

import json
import os
import re
import unittest
from unittest.mock import patch

from agentic_runner.approval import RunnerPolicy
from agentic_runner.codex import CodexAdapter
from agentic_runner.execution import ContainerExecutor, ContainerPolicy, ExecutionError, dependency_commands
from agentic_runner.run_state import Phase
from agentic_runner.state import open_store
from agentic_runner.state_boundary import StateBoundary
from agentic_runner.supervisor import supervise
from tests.support.isolation import DisposableRoot
from tests.support.projects import git_fixture, make_project


IMAGE = os.environ.get("AGENTIC_RUNNER_M4_IMAGE", "")


@unittest.skipUnless(re.fullmatch(r"sha256:[0-9a-f]{64}", IMAGE), "explicit immutable M4 Docker image capability required")
class ContainerIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.policy = ContainerPolicy(IMAGE, timeout=60)
        self.names = []
        self.executor = ContainerExecutor(self.policy, runner=self.track_process)
        self.project = make_project(self.root, family="node" if "node" in self._testMethodName else "python")
        self.boundary = StateBoundary.for_test(self.root, self.root.path / "state")
        self.addCleanup(self.cleanup_containers)

    def track_process(self, argv, **kwargs):
        if argv[3] == "create":
            self.names.append(argv[argv.index("--name") + 1])
        return supervise(argv, **kwargs)

    def cleanup_containers(self):
        for name in self.names:
            observed = self.executor._docker(["inspect", "--format", "{{json .}}", name])
            if observed.returncode:
                continue
            item = json.loads(observed.stdout)
            self.assertEqual(item["Config"]["Labels"]["org.agentic-runner.operation"], name)
            self.assertEqual(item["Image"], IMAGE)
            binds = [m for m in item["Mounts"] if m["Type"] == "bind"]
            self.assertEqual(len(binds), 1)
            self.assertEqual(binds[0]["Source"], str(self.root.require(self.project)))
            result = self.executor._docker(["rm", "--force", name])
            self.assertEqual(result.returncode, 0)

    def write(self, name, value):
        return self.root.write_text(self.project / name, value)

    def commit(self):
        git_fixture(self.root, self.project, "add", "--", ".")
        git_fixture(self.root, self.project, "commit", "--no-gpg-sign", "-m", "Generated M4 execution fixture")

    def store(self):
        return open_store(self.project, self.boundary, policy=RunnerPolicy(execution=self.policy.record()))

    def begin(self, store):
        store.start_run()
        store.transition(1, Phase.IMPLEMENTING)

    def run_command(self, store, argv, **kwargs):
        return self.executor.execute(store, store.load()["revision"], argv, **kwargs)

    def test_protected_files_secrets_state_socket_git_and_network_are_denied(self):
        host_secret = self.root.write_text("private/credential", "GENERATED_FAKE_GITHUB_AND_CLOUD_SECRET")
        operational = self.root.write_text("private/operational/state.json", "GENERATED_FAKE_STATE")
        script = '''import json, os, pathlib, socket
assert os.getuid() != 0
status = pathlib.Path('/proc/self/status').read_text()
assert 'NoNewPrivs:\t1' in status and 'Seccomp:\t2' in status
assert 'CapEff:\t0000000000000000' in status
for path in HOST_PATHS + ['/var/run/docker.sock', '/run/docker.sock', '/home/ilan/.aws/credentials', '/home/ilan/.codex/auth.json', '/home/runner/.codex/auth.json']:
    assert not pathlib.Path(path).exists(), path
assert not any(k in os.environ for k in ['GITHUB_TOKEN', 'GH_TOKEN', 'AWS_SECRET_ACCESS_KEY', 'OPENAI_API_KEY', 'DOCKER_HOST'])
for path in ['/workspace/.git/config', '/workspace/.git/HEAD', '/workspace/.git/refs/new']:
    try:
        pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
        pathlib.Path(path).write_text('forbidden')
    except OSError:
        pass
    else:
        raise AssertionError('Git metadata writable')
try:
    pathlib.Path('/workspace/.git').rename('/workspace/stolen-git')
except OSError:
    pass
else:
    raise AssertionError('Git mount replaceable')
for destination in ['169.254.169.254', '10.0.0.1', '192.168.1.1', '1.1.1.1', '172.17.0.1']:
    try:
        socket.create_connection((destination, 443), timeout=0.15).close()
    except OSError:
        pass
    else:
        raise AssertionError('network reachable: ' + destination)
try:
    socket.getaddrinfo('github.com', 443)
except OSError:
    pass
else:
    raise AssertionError('external DNS available')
pathlib.Path('/workspace/boundary-passed').write_text(str(os.getuid()))
print(json.dumps({'denied': True, 'uid': os.getuid()}))
'''
        self.write("boundary.py", "HOST_PATHS = " + repr([str(host_secret), str(operational), str(self.boundary.path)]) + "\n" + script)
        self.commit()
        git_bytes = {str(p.relative_to(self.project)): p.read_bytes() for p in (self.project / ".git").rglob("*") if p.is_file()}
        with self.store() as store:
            self.begin(store)
            with patch.dict(os.environ, {"GITHUB_TOKEN": "GENERATED_GITHUB_TOKEN", "GH_TOKEN": "GENERATED_GH_TOKEN",
                                        "AWS_SECRET_ACCESS_KEY": "GENERATED_AWS_SECRET", "OPENAI_API_KEY": "GENERATED_API_KEY",
                                        "DOCKER_HOST": "tcp://prohibited.invalid:2375", "DOCKER_CONTEXT": "prohibited"}):
                result = self.run_command(store, ["python", "boundary.py"])
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertEqual(json.loads(result.stdout)["uid"], os.getuid())
        self.assertEqual((self.project / "boundary-passed").stat().st_uid, os.getuid())
        for path, data in git_bytes.items():
            self.assertEqual((self.project / path).read_bytes(), data)
        self.assertEqual(host_secret.read_text(), "GENERATED_FAKE_GITHUB_AND_CLOUD_SECRET")
        self.assertEqual(operational.read_text(), "GENERATED_FAKE_STATE")

    def test_python_dependencies_build_and_tests_execute_offline_inside_boundary(self):
        self.write("setup.py", '''import os, pathlib, socket
from setuptools import setup
assert os.getuid() != 0
assert not pathlib.Path('/var/run/docker.sock').exists()
assert not pathlib.Path('/home/ilan/.aws').exists()
try:
    socket.create_connection(('169.254.169.254', 80), timeout=.1)
except OSError:
    pass
else:
    raise AssertionError('build escaped network')
pathlib.Path('build-boundary-passed').write_text(str(os.getuid()))
setup(name='fixture', version='0.0.0', py_modules=['example'])
''')
        self.write("example.py", "def add(a, b):\n    return a + b\n")
        self.write("test_example.py", "import unittest\nfrom example import add\nclass Example(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n")
        self.commit()
        self.assertFalse((self.project / "build-boundary-passed").exists())
        with self.store() as store:
            self.begin(store)
            for argv in dependency_commands("python"):
                result = self.run_command(store, argv)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
            result = self.run_command(store, ["python", "-m", "unittest", "discover", "-v"])
            self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / "build-boundary-passed").read_text(), str(os.getuid()))

    def test_node_install_lifecycle_build_and_tests_execute_offline_inside_boundary(self):
        package = {"name": "web-fixture", "version": "1.0.0", "engines": {"node": ">=22 <23"},
                   "scripts": {"install": "node boundary.cjs", "build": "node boundary.cjs", "test": "node --test example.test.cjs"}}
        self.write("package.json", json.dumps(package))
        self.write("package-lock.json", json.dumps({"name": "web-fixture", "version": "1.0.0", "lockfileVersion": 3, "requires": True,
                   "packages": {"": {"name": "web-fixture", "version": "1.0.0", "hasInstallScript": True, "engines": {"node": ">=22 <23"}}}}))
        self.write("boundary.cjs", '''const fs = require('node:fs');
const assert = require('node:assert/strict');
assert.notEqual(process.getuid(), 0);
for (const p of ['/var/run/docker.sock', '/home/ilan/.aws/credentials', '/home/ilan/.codex/auth.json']) assert.equal(fs.existsSync(p), false);
assert.equal(process.env.GITHUB_TOKEN, undefined);
fs.writeFileSync('node-boundary-passed', String(process.getuid()));
''')
        self.write("example.test.cjs", "const {test}=require('node:test'); const assert=require('node:assert/strict'); test('sum',()=>assert.equal(2+3,5));\n")
        self.commit()
        with self.store() as store:
            self.begin(store)
            for argv in [*dependency_commands("node"), ["npm", "run", "build"], ["npm", "test"]]:
                result = self.run_command(store, argv)
                self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual((self.project / "node-boundary-passed").read_text(), str(os.getuid()))

    def test_container_stdin_and_nonzero_exit_are_supervised(self):
        with self.store() as store:
            self.begin(store)
            result = self.run_command(store, ["python", "-c", "import sys; print(sys.stdin.read()); sys.exit(7)"], input_bytes=b"bounded prompt")
            self.assertEqual(result.returncode, 7)
            self.assertEqual(result.stdout, b"bounded prompt\n")
            self.assertIsNone(store.load()["pending"])
            self.assertEqual(store.load()["phase"], "implementing")

    def test_timeout_stops_container_preserves_partial_work_and_pending_identity(self):
        self.policy = ContainerPolicy(IMAGE, timeout=1)
        self.executor = ContainerExecutor(self.policy, runner=self.track_process)
        with self.store() as store:
            self.begin(store)
            with self.assertRaises(ExecutionError):
                self.run_command(store, ["python", "-c", "import pathlib,time; pathlib.Path('partial-work').write_text('retained'); time.sleep(30)"])
            state = store.load()
            self.assertEqual(state["phase"], "implementing")
            self.assertIsNotNone(state["pending"])
            name = state["pending"]["details"]["container"]
            result = self.executor._docker(["inspect", "--format", "{{json .State}}", name])
            self.assertFalse(json.loads(result.stdout)["Running"])
            self.assertEqual((self.project / "partial-work").read_text(), "retained")
            with self.assertRaises(ExecutionError):
                self.run_command(store, ["python", "-V"])
            self.assertEqual(store.load()["pending"]["id"], state["pending"]["id"])

    def test_codex_capability_probe_reports_sandbox_support_without_fallback(self):
        with self.store() as store:
            self.begin(store)
            try:
                capability = CodexAdapter(self.executor).inspect(store)
            except ExecutionError as exc:
                self.assertEqual(exc.diagnostic.code, "execution.codex_sandbox")
                self.skipTest("Codex sandbox unavailable; real generation/auth/resume acceptance remains BLOCKED")
            else:
                self.assertFalse(capability["generation_ready"])
                print("M4 CAPABILITY: offline sandbox supported; live authentication/resume remains UNVERIFIED", flush=True)
            self.assertIsNone(store.load()["pending"])

    def test_browser_capability_retains_chromium_sandbox(self):
        self.write("browser.html", "<!doctype html><title>M4</title><p>M4_BROWSER_OK</p>\n")
        self.commit()
        with self.store() as store:
            self.begin(store)
            result = self.run_command(store, ["chromium", "--headless", "--disable-gpu", "--dump-dom", "file:///workspace/browser.html"])
            if result.returncode:
                self.assertTrue(b"Operation not permitted" in result.stderr or b"No usable sandbox!" in result.stderr, result.stderr)
                self.skipTest("Chromium namespace sandbox unavailable; browser acceptance remains BLOCKED")
            else:
                self.assertIn(b"M4_BROWSER_OK", result.stdout)
                print("M4 CAPABILITY: Chromium sandboxed rendering supported", flush=True)
