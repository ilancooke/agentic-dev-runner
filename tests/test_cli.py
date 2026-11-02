import contextlib
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from agentic_runner import __version__
from agentic_runner.cli import main
from tests.support.fixtures import FixtureFactory
from tests.support.isolation import DisposableRoot


class CliTests(unittest.TestCase):
    def test_entry_point_in_disposable_cwd(self):
        executable = Path(sys.executable).parent / "agentic-runner"
        self.assertTrue(executable.is_file(), "Install the package in .venv-dev first")
        with DisposableRoot() as root:
            factory = FixtureFactory(root)
            cwd = factory.state("cli-cwd")
            env = factory.environment()
            for command, arguments, expected, code in (
                ([str(executable)], [], "Run verified milestones on a development branch", 0),
                ([str(executable)], ["--help"], "--version", 0),
                ([str(executable)], ["--version"], f"agentic-runner {__version__}", 0),
                ([sys.executable, "-m", "agentic_runner"], ["--version"], f"agentic-runner {__version__}", 0),
                ([str(executable)], ["start", "--project", "/home/ilan/agentic-workspaces/milestone-test"], "invalid choice", 2),
            ):
                with self.subTest(command=command, arguments=arguments):
                    result = subprocess.run(command + arguments, cwd=root.require(cwd), env=env, capture_output=True, text=True)
                    self.assertEqual(result.returncode, code, result.stderr)
                    self.assertIn(expected, result.stdout + result.stderr)
            self.assertEqual(list(cwd.iterdir()), [])

    def test_cli_does_not_read_config_write_or_launch_processes(self):
        output = io.StringIO()
        with (
            contextlib.redirect_stdout(output),
            patch("builtins.open", side_effect=AssertionError("unexpected file read")),
            patch.object(Path, "open", side_effect=AssertionError("unexpected path read")),
            patch.object(Path, "mkdir", side_effect=AssertionError("unexpected directory creation")),
            patch("subprocess.run", side_effect=AssertionError("unexpected process")),
        ):
            self.assertEqual(main([]), 0)
        self.assertIn("Run verified milestones on a development branch", output.getvalue())

    def test_package_never_imports_prototype_or_legacy_dependencies(self):
        # Verify a fresh interpreter import, not just the already cached modules.
        script = """
import importlib.abc
import sys
class DenyLegacy(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'orchestrator', 'yaml', 'jsonschema', 'run_codex', 'milestone_discovery'}:
            raise AssertionError('Legacy import: ' + fullname)
sys.meta_path.insert(0, DenyLegacy())
from agentic_runner.cli import main
raise SystemExit(main(['--version']))
"""
        with DisposableRoot() as root:
            factory = FixtureFactory(root)
            cwd = factory.state("import-cwd")
            result = subprocess.run([sys.executable, "-c", script], cwd=root.require(cwd), env=factory.environment(), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(__version__, result.stdout)
