import os
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.support.fixtures import FixtureFactory
from tests.support.isolation import DisposableRoot, IsolationError, PROTECTED_ROOTS


class IsolationTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.factory = FixtureFactory(self.root)

    def assert_rejected_before_mutation(self, target):
        with (
            patch.object(Path, "mkdir") as mkdir,
            patch.object(Path, "write_text") as write,
            patch("tests.support.fixtures.subprocess.run") as run,
        ):
            for action in (self.root.mkdir, self.factory.state, self.factory.repository):
                with self.assertRaises(IsolationError):
                    action(target)
            with self.assertRaises(IsolationError):
                self.root.write_text(target, "must never be written")
            mkdir.assert_not_called()
            write.assert_not_called()
            run.assert_not_called()

    def test_operational_reference_and_other_paths_rejected_before_mutation(self):
        for target in (*PROTECTED_ROOTS, Path.cwd(), Path("/etc"), Path("/tmp"), self.root.path):
            with self.subTest(target=target):
                self.assert_rejected_before_mutation(target)

    def test_traversal_and_absolute_aliases_rejected(self):
        targets = [
            "../outside-test-root/file",
            self.root.path / ".." / "outside-test-root/file",
            Path("/home/ilan/agentic-workspaces/../agentic-workspaces/milestone-test/new-file"),
            Path("/home/ilan/agentic-runner-data/../agentic-runner-data/new-file"),
        ]
        for target in targets:
            with self.subTest(target=target):
                self.assert_rejected_before_mutation(target)

    def test_symlink_escapes_and_dangling_symlinks_rejected(self):
        # Links are created only inside an owned root; never write through them.
        with DisposableRoot() as other:
            destinations = [*PROTECTED_ROOTS, Path.cwd(), other.path, other.path / "missing"]
            for number, destination in enumerate(destinations):
                alias = self.root.require(f"alias-{number}")
                alias.symlink_to(destination, target_is_directory=True)
                with self.subTest(destination=destination):
                    self.assert_rejected_before_mutation(alias / "must-not-exist")
            self.assertEqual(list(other.path.iterdir()), [])

    def test_another_disposable_root_is_not_owned(self):
        with DisposableRoot() as other:
            self.assert_rejected_before_mutation(other.path / "file")

    def test_root_symlink_replacement_rejected(self):
        with DisposableRoot() as other:
            original = self.root.path
            moved = original.with_name(original.name + "-moved")
            original.rename(moved)
            try:
                original.symlink_to(other.path, target_is_directory=True)
                self.assert_rejected_before_mutation(original / "file")
            finally:
                original.unlink()
                moved.rename(original)

    def test_same_path_replaced_directory_rejected(self):
        original = self.root.path
        moved = original.with_name(original.name + "-moved")
        original.rename(moved)
        try:
            original.mkdir()
            self.assert_rejected_before_mutation(original / "file")
        finally:
            original.rmdir()
            moved.rename(original)

    def test_internal_alias_resolves_inside_owned_root(self):
        directory = self.root.mkdir("real")
        alias = self.root.require("alias")
        alias.symlink_to(directory, target_is_directory=True)
        result = self.root.write_text(alias / "file", "fixture")
        self.assertEqual(result, directory / "file")
        self.assertEqual(result.read_text(), "fixture")

    def test_hardlink_write_rejected_without_changing_original(self):
        with DisposableRoot() as other:
            original = other.write_text("original", "preserve")
            alias = self.root.require("hardlink")
            os.link(original, alias)
            with self.assertRaises(IsolationError):
                self.root.write_text(alias, "overwrite")
            self.assertEqual(original.read_text(), "preserve")

    def test_environment_cannot_redirect_root_or_supply_credentials(self):
        with patch.dict(os.environ, {"TMPDIR": str(PROTECTED_ROOTS[1]), "GH_TOKEN": "fake-secret", "GIT_DIR": "/etc"}):
            with DisposableRoot() as root:
                env = FixtureFactory(root).environment()
                self.assertEqual(root.path.parent, Path("/tmp").resolve())
                self.assertNotIn("GH_TOKEN", env)
                self.assertNotIn("GIT_DIR", env)
                self.assertTrue(Path(env["HOME"]).is_relative_to(root.path))
                self.assertTrue(Path(env["TMPDIR"]).is_relative_to(root.path))

    def test_closed_root_rejected(self):
        root = DisposableRoot()
        target = root.path / "file"
        root.close()
        with self.assertRaises(IsolationError):
            root.write_text(target, "must not recreate root")
        self.assertFalse(root.path.exists())

    def test_caller_cannot_enroll_an_existing_root(self):
        with self.assertRaises(TypeError):
            DisposableRoot(PROTECTED_ROOTS[0])
