import contextlib
import hashlib
import io
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from agentic_runner.cli import main
from agentic_runner.diagnostics import DiscoveryError
from agentic_runner.discovery import discover
from tests.support.fixtures import FixtureFactory
from tests.support.isolation import DisposableRoot
from tests.support.projects import git_fixture, make_project, make_worktree


def snapshot(root):
    return {str(p.relative_to(root)): (p.stat().st_mode, p.stat().st_mtime_ns, hashlib.sha256(p.read_bytes()).hexdigest())
            for p in root.rglob("*") if p.is_file() and not p.is_symlink()}


class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)

    def write(self, project, name, text):
        return self.root.write_text(project / name, text)

    def assert_error(self, project, code):
        with self.assertRaises(DiscoveryError) as caught:
            discover(project)
        self.assertEqual(caught.exception.diagnostic.code, code, caught.exception)
        self.assertNotIn("roadmap", caught.exception.as_dict())
        self.assertNotIn("verification", caught.exception.as_dict())

    def test_python_identity_default_branch_and_inspectable_sources(self):
        project = make_project(self.root, branch="trunk")
        result = discover(project)
        self.assertTrue(result["ok"])
        self.assertEqual(result["repository"]["default_branch"], "trunk")
        self.assertEqual(result["repository"]["branch"], "trunk")
        self.assertEqual(result["repository"]["remote"]["name"], "origin")
        self.assertEqual(result["runtime"]["family"], "python")
        self.assertEqual(result["runtime"]["version_line"], "3.12")
        self.assertEqual(result["verification"], [{"argv": ["python", "-m", "pytest", "-q"], "sources": ["README.md"]}])
        self.assertEqual(result["roadmap"]["next_milestone"], "M2")
        docs = {d["path"]: d for d in result["documents"]}
        self.assertEqual(docs["README.md"]["sha256"], hashlib.sha256((project / "README.md").read_bytes()).hexdigest())
        child = self.root.mkdir(project / "src")
        self.assertEqual(discover(child)["repository"]["id"], result["repository"]["id"])
        alias = self.root.require("alias")
        alias.symlink_to(project, target_is_directory=True)
        self.assertEqual(discover(alias)["repository"], result["repository"])

    def test_web_uses_package_test_and_static_node_evidence(self):
        project = make_project(self.root, family="node", branch="release/stable")
        self.write(project, ".nvmrc", "v22\n")
        self.write(project, "package-lock.json", '{"lockfileVersion": 3}\n')
        result = discover(project)
        self.assertEqual(result["runtime"]["family"], "node")
        self.assertEqual(result["runtime"]["version_line"], "22")
        self.assertEqual(result["verification"][0]["argv"], ["npm", "test"])
        self.assertEqual(result["repository"]["default_branch"], "release/stable")

    def test_applicable_instructions_and_recursive_requirement_links(self):
        project = make_project(self.root)
        self.root.write_text("AGENTS.md", "# Ancestor instructions\nUse the project style.\n")
        self.write(project, "AGENTS.md", "# Root instructions\n\n## Verification\n\n```sh\npython -m pytest -q\n```\n")
        self.write(project, "src/AGENTS.md", "# Scoped instructions\nPreserve public interfaces.\n")
        self.write(project, "docs/spec.md", '# Requirements\n\nSee [nested](more/detail.md) and [external](https://example.invalid/spec).\n')
        self.write(project, "docs/more/detail.md", '# Details\n\n[back]: ../spec.md\n')
        roadmap = (project / "ROADMAP.md").read_text().replace("Implement the feature.", "Implement [the specification][spec].\n\n[spec]: docs/spec.md#details")
        self.write(project, "ROADMAP.md", roadmap)
        result = discover(project)
        docs = {d["path"]: d for d in result["documents"]}
        self.assertEqual(docs["src/AGENTS.md"]["scope"], "src")
        self.assertEqual(docs[str(self.root.path / "AGENTS.md")]["kind"], "instructions")
        self.assertIn("docs/more/detail.md", docs)
        self.assertEqual(result["external_links"], ["https://example.invalid/spec"])
        self.assertEqual(result["verification"][0]["sources"], ["AGENTS.md", "README.md"])

    def test_parent_child_verification_conflicts_fail_without_selection(self):
        project = make_project(self.root)
        self.root.write_text("AGENTS.md", "## Verification\n\n```sh\npython -m unittest\n```\n")
        self.assert_error(project, "instructions.conflict")

    def test_scoped_instruction_conflict_is_reported(self):
        project = make_project(self.root)
        self.write(project, "tests/AGENTS.md", "## Verification\n\n```sh\npython -m pytest -x\n```\n")
        self.assert_error(project, "instructions.conflict")

    def test_multiple_and_missing_remotes_fail(self):
        for name, addition in (("multiple", '[remote "backup"]\nurl = https://example.invalid/backup.git\n'),
                               ("multiple URLs", '[remote "origin"]\nurl = https://example.invalid/other.git\n'),
                               ("different push URL", '[remote "origin"]\npushurl = https://example.invalid/push.git\n')):
            with self.subTest(name=name):
                project = make_project(self.root, target=f"repos/{name.replace(' ', '-')}")
                config = (project / ".git/config").read_text()
                self.write(project, ".git/config", config + addition)
                self.assert_error(project, "repository.remotes")
        project = FixtureFactory(self.root).repository("repos/no-remote")
        self.assert_error(project, "repository.remotes")

    def test_no_main_guess_when_cached_default_head_is_missing(self):
        project = make_project(self.root)
        self.root.require(project / ".git/refs/remotes/origin/HEAD").unlink()
        self.assert_error(project, "repository.default")

    def test_packed_refs_are_supported(self):
        project = make_project(self.root)
        git_fixture(self.root, project, "pack-refs", "--all", "--prune")
        self.assertEqual(discover(project)["repository"]["default_branch"], "main")

    def test_linked_worktree_uses_common_repository_identity(self):
        project = make_project(self.root)
        linked = make_worktree(self.root, project)
        before = snapshot(self.root.path)
        primary = discover(project)
        result = discover(linked)
        self.assertEqual(result["repository"]["id"], primary["repository"]["id"])
        self.assertEqual(result["repository"]["common_dir"], str(project / ".git"))
        self.assertIsNone(result["repository"]["branch"])
        self.assertEqual(snapshot(self.root.path), before)

    def test_symlinked_instructions_and_source_directories_cannot_hide_scope(self):
        project = make_project(self.root)
        instructions = self.root.write_text("instructions.md", "# Instructions\n")
        alias = self.root.require(project / "AGENTS.md")
        alias.symlink_to(instructions)
        self.assert_error(project, "instructions.symlink")
        # Unlink the owned alias itself, without following its external destination.
        self.root.require(project).joinpath("AGENTS.md").unlink()
        directory = self.root.mkdir("other-source")
        self.root.require(project / "src").symlink_to(directory, target_is_directory=True)
        self.assert_error(project, "source.symlink_directory")

    def test_oversized_evidence_fails_with_diagnostic(self):
        project = make_project(self.root)
        self.write(project, "README.md", "x" * (1024 * 1024 + 1))
        self.assert_error(project, "source.size")

    def test_remote_names_with_dots_are_supported(self):
        project = make_project(self.root)
        self.write(project, ".git/config", (project / ".git/config").read_text().replace('remote "origin"', 'remote "up.stream"'))
        git_fixture(self.root, project, "update-ref", "refs/remotes/up.stream/main", "HEAD")
        git_fixture(self.root, project, "symbolic-ref", "refs/remotes/up.stream/HEAD", "refs/remotes/up.stream/main")
        self.assertEqual(discover(project)["repository"]["remote"]["name"], "up.stream")

    def test_remote_helpers_and_credentials_fail_without_leaking_url(self):
        for index, url in enumerate(("ext::sh -c unsafe", "https://token:fake-secret@example.invalid/project.git")):
            project = make_project(self.root, target=f"repos/unsafe-{index}")
            self.write(project, ".git/config", (project / ".git/config").read_text().replace("https://example.invalid/fixtures/project.git", url))
            self.assert_error(project, "repository.remote")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["discover", str(project)]), 2)
            self.assertNotIn("fake-secret", output.getvalue())

    def test_config_includes_and_rewrites_are_ambiguities(self):
        for index, addition in enumerate(('[include]\npath = /must/not/read\n', '[url "https://example.invalid/"]\ninsteadOf = short:\n')):
            project = make_project(self.root, target=f"repos/config-{index}")
            self.write(project, ".git/config", (project / ".git/config").read_text() + addition)
            self.assert_error(project, "repository.config")

    def test_unsupported_python_node_and_mixed_requirements_fail(self):
        python = make_project(self.root)
        self.write(python, "pyproject.toml", '[project]\nrequires-python = ">=3.13"\n')
        self.assert_error(python, "runtime.unsupported")
        node = make_project(self.root, family="node", target="repos/web")
        self.write(node, ".node-version", "18\n")
        self.assert_error(node, "runtime.unsupported")
        self.write(python, "package.json", "{}\n")
        self.assert_error(python, "runtime.ambiguous")

    def test_unknown_versions_managers_and_invalid_metadata_fail(self):
        cases = [
            ("python", "pyproject.toml", "not valid toml", "runtime.metadata"),
            ("python", ".python-version", "latest\n", "runtime.syntax"),
            ("node", "package.json", "{ broken", "runtime.metadata"),
            ("node", "package.json", '[]', "runtime.metadata"),
            ("node", "package.json", '{"scripts": []}', "runtime.metadata"),
            ("node", "package.json", '{"scripts": {"test": "one", "test": "two"}}', "runtime.metadata"),
            ("node", "package.json", '{"packageManager": "pnpm@9.0.0"}', "runtime.manager"),
        ]
        for index, (family, file, text, code) in enumerate(cases):
            with self.subTest(file=file, text=text):
                project = make_project(self.root, family=family, target=f"repos/bad-{index}")
                self.write(project, file, text)
                self.assert_error(project, code)

    def test_runtime_instructions_conflicting_with_metadata_fail(self):
        project = make_project(self.root)
        self.write(project, "AGENTS.md", "## Runtime\n\nNode: 22\n")
        self.assert_error(project, "instructions.conflict")

    def test_missing_and_ambiguous_verification_never_choose_a_command(self):
        project = make_project(self.root)
        self.write(project, "README.md", "# No verification declared\n")
        self.assert_error(project, "verification.missing")
        self.write(project, "README.md", "## Verification\n\n```sh\npython -m pytest && echo done\n```\n")
        self.assert_error(project, "verification.shell")
        self.write(project, "README.md", "## Verification\nRun some tests.\n")
        self.assert_error(project, "verification.syntax")
        self.write(project, "README.md", "## Verification\n\n```sh\npython -m pytest\n```\n\n## Verification\n\n```sh\npython -m unittest\n```\n")
        self.assert_error(project, "verification.duplicate")

    def test_missing_and_escaping_linked_requirements_fail(self):
        project = make_project(self.root)
        original = (project / "ROADMAP.md").read_text()
        self.write(project, "ROADMAP.md", original.replace("Implement the feature.", "Read [missing](missing.md)."))
        self.assert_error(project, "source.read")
        outside = self.root.write_text("outside.md", "Private fixture data\n")
        alias = self.root.require(project / "alias.md")
        alias.symlink_to(outside)
        self.write(project, "ROADMAP.md", original.replace("Implement the feature.", "Read [outside](alias.md)."))
        self.assert_error(project, "source.escape")

    def test_ci_files_are_inventory_only(self):
        project = make_project(self.root)
        self.write(project, ".github/workflows/tests.yml", "on: push\njobs:\n  test:\n    steps:\n      - run: echo not-executed\n")
        result = discover(project)
        self.assertIn(".github/workflows/tests.yml", [d["path"] for d in result["documents"] if d["kind"] == "ci"])
        self.assertEqual(result["verification"][0]["argv"], ["python", "-m", "pytest", "-q"])

    def test_no_mutation_project_execution_or_inherited_git_environment(self):
        project = make_project(self.root, family="node")
        marker = project / "executed"
        hook = self.write(project, ".git/hooks/reference-transaction", f"#!/bin/sh\ntouch {marker}\n")
        self.root.require(hook).chmod(0o755)
        monitor = self.write(project, "monitor", f"#!/bin/sh\ntouch {marker}\n")
        self.root.require(monitor).chmod(0o755)
        self.write(project, ".git/config", (project / ".git/config").read_text() + f"[core]\nfsmonitor = {monitor}\n")
        self.write(project, "setup.py", f"from pathlib import Path\nPath({str(marker)!r}).touch()\n")
        package = json.loads((project / "package.json").read_text())
        package["scripts"]["test"] = f"touch {marker}"
        self.write(project, "package.json", json.dumps(package))
        before = snapshot(project)
        with patch.dict(os.environ, {"GIT_DIR": "/must/not/use", "GH_TOKEN": "fixture-secret", "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.fsmonitor", "GIT_CONFIG_VALUE_0": str(monitor)}):
            with patch("agentic_runner.repository.subprocess.run", wraps=subprocess.run) as run:
                discover(project)
                for call in run.call_args_list:
                    argv = call.args[0]
                    self.assertIn("core.fsmonitor=false", argv)
                    self.assertFalse(set(call.kwargs["env"]) & {"GH_TOKEN", "GIT_DIR", "GIT_CONFIG_COUNT"})
                    self.assertIn(argv[-1] if "config" in argv else next(x for x in argv if x in {"symbolic-ref", "show-ref", "rev-parse"}), {"--list", "symbolic-ref", "show-ref", "rev-parse"})
        self.assertEqual(snapshot(project), before)
        self.assertFalse(marker.exists())

    def test_installed_cli_success_and_error_are_json_and_read_only(self):
        project = make_project(self.root)
        factory = FixtureFactory(self.root)
        env = factory.environment()
        executable = str(Path(sys.executable).parent / "agentic-runner")
        before = snapshot(project)
        result = subprocess.run([executable, "discover", str(project)], cwd=self.root.require(project), env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])
        self.assertEqual(snapshot(project), before)
        self.write(project, "ROADMAP.md", "# Invalid roadmap\n")
        before = snapshot(project)
        result = subprocess.run([executable, "discover", str(project)], cwd=self.root.require(project), env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        report = json.loads(result.stdout)
        self.assertFalse(report["ok"])
        self.assertEqual(report["diagnostics"][0]["code"], "roadmap.progress")
        self.assertNotIn("roadmap", report)
        self.assertEqual(snapshot(project), before)
