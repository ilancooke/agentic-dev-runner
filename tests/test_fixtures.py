import unittest
from pathlib import Path
from unittest.mock import patch

from tests.support.fakes import FakeExternalAdapter
from tests.support.fixtures import FixtureFactory
from tests.support.isolation import DisposableRoot, IsolationError, PROTECTED_ROOTS


class FixtureTests(unittest.TestCase):
    def test_repository_and_state_are_separate_disposable_fixtures(self):
        with DisposableRoot() as root:
            factory = FixtureFactory(root)
            repository = factory.repository()
            state = factory.state()
            self.assertTrue((repository / ".git/HEAD").is_file())
            self.assertEqual((repository / ".git/HEAD").read_text().strip(), "ref: refs/heads/main")
            self.assertEqual(list((repository / ".git/hooks").glob("*")), [])
            self.assertNotIn("remote", (repository / ".git/config").read_text())
            self.assertFalse(repository.is_relative_to(state))
            self.assertFalse(state.is_relative_to(repository))
            root.write_text(repository / "README.md", "Generated fixture\n")
            root.write_text(state / "result.json", "{}\n")
            with self.assertRaises(IsolationError):
                factory.repository(repository)
        self.assertFalse(root.path.exists())

    def test_git_uses_sanitized_environment_and_no_template(self):
        with DisposableRoot() as root:
            with patch("tests.support.fixtures.subprocess.run") as run:
                repository = FixtureFactory(root).repository()
            args, kwargs = run.call_args
            self.assertIn("--template=", args[0])
            self.assertIn("core.hooksPath=/dev/null", args[0])
            self.assertEqual(kwargs["cwd"], repository)
            self.assertEqual(kwargs["env"]["GIT_CONFIG_GLOBAL"], "/dev/null")
            self.assertEqual(kwargs["env"]["GIT_CONFIG_NOSYSTEM"], "1")

    def test_fakes_record_success_failure_and_unscripted_calls_without_io(self):
        with DisposableRoot() as root:
            state = FixtureFactory(root).state()
            for name in ("codex", "github", "container"):
                with self.subTest(adapter=name):
                    expected = {"adapter": name, "status": "complete"}
                    fake = FakeExternalAdapter(root, expected, RuntimeError("injected failure"))
                    with patch("subprocess.run") as run, patch.object(Path, "write_text") as write:
                        result = fake.call("run", state)
                        result["status"] = "changed"
                        self.assertEqual(expected["status"], "complete")
                        with self.assertRaisesRegex(RuntimeError, "injected failure"):
                            fake.call("retry", state)
                        with self.assertRaisesRegex(AssertionError, "Unscripted"):
                            fake.call("unexpected", state)
                        run.assert_not_called()
                        write.assert_not_called()
                    self.assertEqual([c.operation for c in fake.calls], ["run", "retry", "unexpected"])

    def test_fake_rejects_unsafe_targets_without_consuming_response(self):
        with DisposableRoot() as root:
            fake = FakeExternalAdapter(root, "ready")
            for target in PROTECTED_ROOTS:
                with self.assertRaises(IsolationError):
                    fake.call("run", target)
            self.assertEqual(fake.calls, [])
            self.assertEqual(fake.call("run", FixtureFactory(root).state()), "ready")
