"""Real dependency/build/test commands, all on generated owned native projects."""

import json
import os
import unittest

from agentic_runner.approval import RunnerPolicy
from agentic_runner.native_execution import NativeExecutor, NativePolicy, native_dependency_commands
from agentic_runner.run_state import Phase
from agentic_runner.state import open_store
from agentic_runner.state_boundary import StateBoundary
from tests.support.isolation import DisposableRoot
from tests.support.projects import git_fixture, make_project


class NativeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.home = self.root.mkdir("home")
        self.codex_home = self.root.mkdir("home/.codex")
        self.policy = NativePolicy(str(self.home), str(self.codex_home), timeout=60)
        self.executor = NativeExecutor(self.policy)

    def commit(self, project):
        git_fixture(self.root, project, "add", "--", ".")
        git_fixture(self.root, project, "commit", "--no-gpg-sign", "-m", "Generated native dependency fixture")

    def run_commands(self, project, commands):
        boundary = StateBoundary.for_test(self.root, self.root.path / "state")
        with open_store(project, boundary, policy=RunnerPolicy(execution=self.policy.record())) as store:
            store.start_run()
            store.transition(1, Phase.IMPLEMENTING)
            results = []
            for argv in commands:
                result = self.executor.execute(store, store.load()["revision"], argv)
                self.assertEqual(result.returncode, 0, result.stderr.decode(errors="replace"))
                results.append(result)
            self.assertEqual(store.load()["phase"], "implementing")
            self.assertIsNone(store.load()["pending"])
            return results

    def test_python_venv_dependency_build_install_and_tests(self):
        project = make_project(self.root)
        self.root.write_text(project / "pyproject.toml", '''[project]
name = "fixturemath"
version = "0.0.0"
requires-python = ">=3.12,<3.13"
[build-system]
requires = []
build-backend = "fixture_backend"
backend-path = ["."]
''')
        # Deliberately stdlib-only generated wheel backend, so tests never fetch code.
        self.root.write_text(project / "fixture_backend.py", '''import pathlib, zipfile
def build_wheel(wheel_directory, config_settings=None, metadata_directory=None):
    pathlib.Path("build-executed").write_text("native-build")
    name = "fixturemath-0.0.0-py3-none-any.whl"
    with zipfile.ZipFile(pathlib.Path(wheel_directory) / name, "w") as wheel:
        wheel.writestr("fixturemath/__init__.py", "def add(a, b): return a + b\\n")
        wheel.writestr("fixturemath-0.0.0.dist-info/METADATA", "Metadata-Version: 2.1\\nName: fixturemath\\nVersion: 0.0.0\\n")
        wheel.writestr("fixturemath-0.0.0.dist-info/WHEEL", "Wheel-Version: 1.0\\nGenerator: fixture\\nRoot-Is-Purelib: true\\nTag: py3-none-any\\n")
        wheel.writestr("fixturemath-0.0.0.dist-info/RECORD", "")
    return name
''')
        self.root.write_text(project / "test_fixture.py", "import unittest\nfrom fixturemath import add\nclass Fixture(unittest.TestCase):\n def test_add(self): self.assertEqual(add(2,3),5)\n")
        self.commit(project)
        self.assertFalse((project / "build-executed").exists())
        result = self.run_commands(project, [*native_dependency_commands("python", offline=True),
                                  [".venv/bin/python", "-m", "pip", "check"], [".venv/bin/python", "-m", "unittest", "discover", "-v"]])
        self.assertIn(b"Ran 1 test", result[-1].stderr)
        self.assertEqual((project / "build-executed").read_text(), "native-build")

    @unittest.skipUnless(os.environ.get("AGENTIC_RUNNER_NATIVE_NODE") == "1", "explicit cached-Node Docker fixture capability required")
    def test_node_dependencies_lifecycle_build_and_test_on_host(self):
        from tests.support.native_tools import fixture_node
        project = make_project(self.root, family="node")
        provisioned = fixture_node(self.root, project)
        self.root.write_text(project / ".gitignore", ".venv/\n")
        package = {"name": "web-fixture", "version": "1.0.0", "engines": {"node": ">=22 <23"},
                   "scripts": {"install": "node lifecycle.cjs", "build": "node lifecycle.cjs", "test": "node --test example.test.cjs"}}
        self.root.write_text(project / "package.json", json.dumps(package))
        self.root.write_text(project / "package-lock.json", json.dumps({"name": "web-fixture", "version": "1.0.0", "lockfileVersion": 3,
                            "requires": True, "packages": {"": {"name": "web-fixture", "version": "1.0.0", "hasInstallScript": True, "engines": package["engines"]}}}))
        self.root.write_text(project / "lifecycle.cjs", "const fs=require('node:fs'); if(process.getuid()===0) throw Error('root'); fs.writeFileSync('native-node-lifecycle','passed');\n")
        self.root.write_text(project / "example.test.cjs", "const {test}=require('node:test'); const assert=require('node:assert/strict'); test('sum',()=>assert.equal(2+3,5));\n")
        self.commit(project)
        results = self.run_commands(project, [["node", "--version"], *native_dependency_commands("node", offline=True),
                                  ["npm", "run", "build"], ["npm", "test"]])
        self.assertTrue(results[0].stdout.startswith(b"v22."))
        self.assertEqual((project / "native-node-lifecycle").read_text(), "passed")
        self.assertIn(b"pass 1", results[-1].stdout)
        print("NATIVE NODE FIXTURE " + json.dumps(provisioned, sort_keys=True), flush=True)
