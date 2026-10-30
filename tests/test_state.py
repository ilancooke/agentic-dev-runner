import base64
import json
import multiprocessing
import os
import shutil
import stat
import unittest
from pathlib import Path
from unittest.mock import patch

from agentic_runner.approval import RunnerPolicy
from agentic_runner.durable import DurableIO, StateError, canonical_json
from agentic_runner.run_state import Phase
from agentic_runner.state import open_store
from agentic_runner.state_boundary import StateBoundary
from tests.support.isolation import DisposableRoot, IsolationError, PROTECTED_ROOTS
from tests.support.projects import git_fixture, make_project, make_worktree


POINTS = ("journal.opened", "journal.written", "journal.file_synced", "journal.directory_synced",
          "atomic.opened", "atomic.written", "atomic.file_synced", "atomic.replaced", "atomic.directory_synced")


def killed_writer(root, project, area, point):
    def checkpoint(name):
        if name == point:
            os._exit(72)
    with open_store(project, StateBoundary.for_test(root, area), checkpoint=checkpoint) as store:
        store.transition(1, Phase.IMPLEMENTING)
    os._exit(73)


def lock_contender(root, project, area, connection):
    try:
        with open_store(project, StateBoundary.for_test(root, area)):
            connection.send("acquired")
    except StateError as exc:
        connection.send(exc.diagnostic.code)
    finally:
        connection.close()
    os._exit(0)


class StateTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.project = make_project(self.root)
        self.area = self.root.path / "state"

    def boundary(self, area=None):
        return StateBoundary.for_test(self.root, area or self.area)

    def start(self, area=None):
        with open_store(self.project, self.boundary(area)) as store:
            state = store.start_run()
            return state, store.snapshot, store.journal

    def write(self, relative, content):
        return self.root.write_text(self.project / relative, content)

    def commit(self, *files):
        git_fixture(self.root, self.project, "add", "--", *files)
        git_fixture(self.root, self.project, "commit", "--no-gpg-sign", "-m", "Update generated requirements")

    def test_start_retains_committed_scope_configuration_and_versioned_identity(self):
        self.write("docs/spec.md", "# Required behavior\nThe feature must preserve examples.\n")
        roadmap = (self.project / "ROADMAP.md").read_text().replace("Implement the feature.", "Implement [the spec](docs/spec.md).")
        self.write("ROADMAP.md", roadmap)
        self.commit("ROADMAP.md", "docs/spec.md")
        with open_store(str(self.project), self.boundary()) as store:
            state = store.start_run()
            self.assertEqual(state["version"], 1)
            self.assertEqual(state["identity_version"], 1)
            self.assertEqual(state["phase"], Phase.APPROVED)
            approval = state["approval"]
            self.assertEqual(base64.b64decode(approval["files"]["ROADMAP.md"]["content_base64"]).decode(), roadmap)
            self.assertIn("docs/spec.md", approval["files"])
            self.assertEqual(approval["configuration"]["policy"]["requested_model"], "GPT-6.1-Sol")
            self.assertEqual(approval["configuration"]["policy"]["reasoning_effort"], "high")
            self.assertEqual(store.history()[0]["kind"], "started")
            self.assertEqual(store.load(), state)
            with self.assertRaisesRegex(StateError, "already exists"):
                store.start_run()
            state["approval"]["files"].clear()
            self.assertTrue(store.load()["approval"]["files"])

    def test_progress_and_unreferenced_evidence_do_not_invalidate_scope(self):
        state, _, _ = self.start()
        original = (self.project / "ROADMAP.md").read_text()
        self.write("ROADMAP.md", original.replace("| M2 | not started |", "| M2 | in progress |"))
        self.write("HANDOFF.md", "# Handoff\nRetained partial implementation.\n")
        self.write("CHECKPOINT.md", "# Checkpoint\nChecks pending.\n")
        self.write("docs/evidence/M2.md", "# Evidence\nA check ran successfully.\n")
        with open_store(self.project, self.boundary()) as store:
            checked = store.check_authorization(1)
            self.assertEqual(checked["approval"], state["approval"])
            self.assertEqual(checked["revision"], 1)
            self.assertEqual(len(store.history()), 1)
            # Status claims alone cannot advance either run phase or milestone.
            self.write("ROADMAP.md", original.replace("| M2 | not started |", "| M2 | complete |"))
            self.assertEqual(store.check_authorization(1)["approval"]["milestone"], "M2")
            self.assertEqual(store.load()["phase"], Phase.APPROVED)

    def test_committed_progress_updates_retain_original_authorization(self):
        original, _, _ = self.start()
        self.write("ROADMAP.md", (self.project / "ROADMAP.md").read_text().replace("not started", "in progress"))
        self.commit("ROADMAP.md")
        with open_store(self.project, self.boundary()) as store:
            current = store.check_authorization(1)
            self.assertEqual(current["approval"], original["approval"])
            self.assertEqual(current["revision"], 1)

    def test_node_project_on_non_main_branch_captures_same_state_contract(self):
        web = make_project(self.root, family="node", branch="trunk", target="repos/web")
        with open_store(web, self.boundary()) as store:
            state = store.start_run()
            self.assertEqual(state["approval"]["repository"]["default_branch"], "trunk")
            self.assertEqual(state["approval"]["configuration"]["runtime"]["family"], "node")
            self.assertEqual(state["approval"]["configuration"]["verification"][0]["argv"], ["npm", "test"])
            self.assertIn("package.json", state["approval"]["files"])

    def test_ignored_uncommitted_requirement_cannot_be_authorized(self):
        self.write(".gitignore", "docs/\n")
        self.write("docs/spec.md", "# Uncommitted requirements\nKeep the examples.\n")
        self.write("ROADMAP.md", (self.project / "ROADMAP.md").read_text().replace("Implement the feature.", "Implement [the contract](docs/spec.md)."))
        self.commit(".gitignore", "ROADMAP.md")
        with open_store(self.project, self.boundary()) as store:
            with self.assertRaises(StateError) as caught:
                store.start_run()
            self.assertEqual(caught.exception.diagnostic.code, "approval.uncommitted")
            self.assertIsNone(store.load())

    def test_scope_changes_persist_invalidation_and_require_explicit_committed_renewal(self):
        first, _, _ = self.start()
        self.write("ROADMAP.md", (self.project / "ROADMAP.md").read_text().replace("The declared checks pass.", "The declared checks and new examples pass."))
        with open_store(self.project, self.boundary()) as store:
            with self.assertRaises(StateError) as caught:
                store.transition(1, Phase.IMPLEMENTING)
            self.assertEqual(caught.exception.diagnostic.code, "approval.invalidated")
            invalidated = store.load()
            self.assertEqual(invalidated["phase"], Phase.APPROVAL_REQUIRED)
            self.assertEqual(invalidated["approval"], first["approval"])
            with self.assertRaises(StateError):
                store.renew_approval(2)
        self.commit("ROADMAP.md")
        with open_store(self.project, self.boundary()) as store:
            renewed = store.renew_approval(2)
            self.assertEqual(renewed["phase"], Phase.APPROVED)
            self.assertEqual(renewed["run_id"], first["run_id"])
            self.assertNotEqual(renewed["approval"]["scope_hash"], first["approval"]["scope_hash"])
            self.assertEqual([e["kind"] for e in store.history()], ["started", "approval_invalidated", "approval_renewed"])

    def test_referenced_evidence_is_protected_and_new_instructions_invalidate(self):
        self.write("HANDOFF.md", "# Binding requirement\nKeep the response format.\n")
        self.write("ROADMAP.md", (self.project / "ROADMAP.md").read_text().replace("Implement the feature.", "Implement [the required behavior](HANDOFF.md)."))
        self.commit("HANDOFF.md", "ROADMAP.md")
        state, _, _ = self.start()
        self.assertIn("HANDOFF.md", state["approval"]["files"])
        self.write("HANDOFF.md", "# Binding requirement\nChanged scope.\n")
        with open_store(self.project, self.boundary()) as store:
            with self.assertRaisesRegex(StateError, "Protected scope"):
                store.check_authorization(1)

    def test_runtime_directive_inside_evidence_cannot_bypass_scope_protection(self):
        self.start()
        self.write("docs/evidence/new.md", "## Runtime\n\nPython: >=3.12\n")
        with open_store(self.project, self.boundary()) as store:
            with self.assertRaises(StateError):
                store.check_authorization(1)
            self.assertEqual(store.load()["phase"], Phase.APPROVAL_REQUIRED)

    def test_agents_in_evidence_directories_are_always_protected(self):
        self.start()
        self.write("docs/evidence/AGENTS.md", "# Scoped instructions\nKeep the public interface unchanged.\n")
        with open_store(self.project, self.boundary()) as store:
            with self.assertRaises(StateError):
                store.check_authorization(1)
            self.assertEqual(store.load()["phase"], Phase.APPROVAL_REQUIRED)

    def test_changed_referenced_requirement_invalidates_without_roadmap_edit(self):
        self.write("docs/spec.md", "# Contract\nReturn a number.\n")
        self.write("ROADMAP.md", (self.project / "ROADMAP.md").read_text().replace("Implement the feature.", "Implement [the contract](docs/spec.md)."))
        self.commit("ROADMAP.md", "docs/spec.md")
        self.start()
        self.write("docs/spec.md", "# Contract\nReturn a string.\n")
        with open_store(self.project, self.boundary()) as store:
            with self.assertRaises(StateError):
                store.check_authorization(1)
            self.assertEqual(store.load()["phase"], Phase.APPROVAL_REQUIRED)

    def test_inline_requirement_assets_are_committed_and_protected(self):
        self.write("mockup.png", "Generated asset fixture bytes\n")
        self.write("ROADMAP.md", (self.project / "ROADMAP.md").read_text().replace("Implement the feature.", "Implement this view: ![Expected view](mockup.png)"))
        self.commit("ROADMAP.md", "mockup.png")
        state, _, _ = self.start()
        self.assertIn("mockup.png", state["approval"]["files"])
        self.write("mockup.png", "Changed asset fixture bytes\n")
        with open_store(self.project, self.boundary()) as store:
            with self.assertRaises(StateError):
                store.check_authorization(1)

    def test_external_inline_assets_cannot_escape_approval_coverage(self):
        self.write("ROADMAP.md", (self.project / "ROADMAP.md").read_text().replace("Implement the feature.", "Implement ![the view](https://example.invalid/changing-view.png)"))
        self.commit("ROADMAP.md")
        with open_store(self.project, self.boundary()) as store:
            with self.assertRaises(StateError) as caught:
                store.start_run()
            self.assertEqual(caught.exception.diagnostic.code, "approval.external")

    def test_configuration_change_invalidates_and_downgrades_are_rejected(self):
        self.start()
        with open_store(self.project, self.boundary(), policy=RunnerPolicy(global_concurrency=2)) as store:
            with self.assertRaises(StateError):
                store.check_authorization(1)
            self.assertEqual(store.load()["phase"], Phase.APPROVAL_REQUIRED)
        with self.assertRaises(StateError):
            RunnerPolicy(requested_model="smaller", reasoning_effort="low").as_dict()
        with self.assertRaises(StateError):
            RunnerPolicy(max_ci_repairs=True).as_dict()

    def test_ancestor_instructions_are_retained_and_changes_invalidate(self):
        self.root.write_text("AGENTS.md", "# Local operator instructions\nKeep public APIs.\n")
        state, _, _ = self.start()
        key = str(self.root.path / "AGENTS.md")
        self.assertFalse(state["approval"]["files"][key]["committed"])
        self.root.write_text("AGENTS.md", "# Local operator instructions\nChanged rules.\n")
        with open_store(self.project, self.boundary()) as store:
            with self.assertRaises(StateError):
                store.check_authorization(1)

    def test_external_requirements_and_dirty_or_staged_starts_fail(self):
        self.write("README.md", (self.project / "README.md").read_text() + "\n## References\n\n[External](https://example.invalid/requirements)\n")
        self.commit("README.md")
        with open_store(self.project, self.boundary()) as store:
            with self.assertRaises(StateError) as caught:
                store.start_run()
            self.assertEqual(caught.exception.diagnostic.code, "approval.external")
            self.assertIsNone(store.load())
        self.write("README.md", "# Fixture\n\n## Verification\n\n```sh\npython -m pytest -q\n```\n")
        for stage in (False, True):
            with self.subTest(stage=stage):
                if stage:
                    git_fixture(self.root, self.project, "add", "--", "README.md")
                with open_store(self.project, self.boundary()) as store:
                    with self.assertRaises(StateError) as caught:
                        store.start_run()
                    self.assertEqual(caught.exception.diagnostic.code, "approval.dirty")
                    self.assertIsNone(store.load())

    def test_pending_intent_is_durable_and_unknown_effects_are_never_reissued(self):
        self.start()
        with open_store(self.project, self.boundary()) as store:
            pending = store.begin_operation(1, "branch", {"branch": "agent/m2"})
            operation = pending["pending"]["id"]
            self.assertEqual(pending["revision"], 2)
        with open_store(self.project, self.boundary()) as store:
            self.assertEqual(store.load()["pending"]["id"], operation)
            with self.assertRaises(StateError):
                store.begin_operation(2, "branch")
            uncertain = store.resolve_operation(2, operation, "unknown", {"reason": "response lost"})
            self.assertEqual(uncertain["pending"]["status"], "uncertain")
            with self.assertRaises(StateError):
                store.transition(3, Phase.IMPLEMENTING)
            resolved = store.resolve_operation(3, operation, "not_applied", {"observed": "branch absent"})
            self.assertIsNone(resolved["pending"])
            self.assertEqual(resolved["phase"], Phase.APPROVED)
            self.assertEqual(store.history()[-1]["details"]["outcome"], "not_applied")

    def test_pause_resume_and_explicit_transition_rules(self):
        self.start()
        with open_store(self.project, self.boundary()) as store:
            implementing = store.transition(1, Phase.IMPLEMENTING)
            paused = store.transition(2, Phase.PAUSED)
            self.assertEqual(paused["resume_phase"], implementing["phase"])
        with open_store(self.project, self.boundary()) as store:
            self.assertEqual(store.load()["phase"], Phase.PAUSED)
            resumed = store.resume(3)
            self.assertEqual(resumed["phase"], Phase.IMPLEMENTING)
            verified = store.transition(4, Phase.VERIFICATION_PENDING)
            self.assertEqual(verified["phase"], Phase.VERIFICATION_PENDING)
            for phase in ("published", "complete", "merging", True):
                with self.subTest(phase=phase):
                    with self.assertRaises(StateError):
                        store.transition(5, phase)
            for kind in ("commit", "push", "merge"):
                with self.assertRaises(StateError):
                    store.begin_operation(5, kind)
            with self.assertRaises(StateError):
                store.transition(1, Phase.IMPLEMENTING)

    def test_aliases_linked_worktrees_and_distinct_state_roots_cannot_bypass_lock(self):
        self.start()
        alias = self.root.require("project-alias")
        alias.symlink_to(self.project, target_is_directory=True)
        linked = make_worktree(self.root, self.project)
        with open_store(self.project, self.boundary()):
            for target in (alias, linked, self.project):
                with self.subTest(target=target):
                    with self.assertRaises(StateError) as caught:
                        with open_store(target, self.boundary(self.root.path / "other-state")):
                            pass
                    self.assertEqual(caught.exception.diagnostic.code, "state.locked")
            receiving, sending = multiprocessing.Pipe(duplex=False)
            process = multiprocessing.get_context("fork").Process(target=lock_contender, args=(self.root, alias, self.root.path / "process-state", sending))
            process.start()
            sending.close()
            self.assertTrue(receiving.poll(10))
            self.assertEqual(receiving.recv(), "state.locked")
            process.join(10)
            self.assertEqual(process.exitcode, 0)
            receiving.close()
        self.assertFalse((self.root.path / "other-state").exists())
        self.assertFalse((self.root.path / "process-state").exists())

    def test_namespace_alias_recovers_same_state_and_copied_namespaces_fail(self):
        state, _, _ = self.start()
        alias = self.root.require("state-alias")
        alias.symlink_to(self.area, target_is_directory=True)
        with open_store(self.project, self.boundary(alias)) as store:
            self.assertEqual(store.load()["run_id"], state["run_id"])
        copied = self.root.require("copied-state")
        shutil.copytree(self.root.require(self.area), copied)
        with self.assertRaises(StateError) as caught:
            with open_store(self.project, self.boundary(copied)):
                pass
        self.assertEqual(caught.exception.diagnostic.code, "state.namespace")

    def test_project_binding_and_cross_project_state_cannot_be_adopted(self):
        first, _, _ = self.start()
        other = make_project(self.root, target="repos/other")
        with open_store(other, self.boundary()) as store:
            second = store.start_run()
            self.assertNotEqual(second["project"], first["project"])
            self.root.write_text(store.snapshot, canonical_json({"version": 1, "event_hash": "0" * 64, "state": first}).decode())
        with self.assertRaises(StateError):
            with open_store(other, self.boundary()):
                pass
        with open_store(self.project, self.boundary()) as store:
            self.assertEqual(store.load()["run_id"], first["run_id"])

    def test_remote_identity_change_is_not_silently_registered_again(self):
        self.start()
        self.write(".git/config", (self.project / ".git/config").read_text().replace("fixtures/project.git", "fixtures/another.git"))
        with self.assertRaises(StateError) as caught:
            with open_store(self.project, self.boundary()):
                pass
        self.assertEqual(caught.exception.diagnostic.code, "state.identity")

    def test_test_operational_reference_and_overlapping_roots_rejected_before_mutation(self):
        with patch.object(Path, "mkdir") as mkdir, patch.object(DurableIO, "atomic") as atomic:
            for path in (*PROTECTED_ROOTS, self.root.path / "unowned-operational"):
                with self.subTest(path=path):
                    with self.assertRaises(StateError):
                        StateBoundary(path)
            with self.assertRaises(IsolationError):
                StateBoundary.for_test(self.root, Path.cwd() / "must-not-exist")
            for area in (self.project / "state", self.project / ".git/state"):
                with self.assertRaises(StateError):
                    with open_store(self.project, self.boundary(area)):
                        pass
            mkdir.assert_not_called()
            atomic.assert_not_called()

    def test_fake_operational_namespace_marker_cannot_be_opened_as_test(self):
        self.root.mkdir(self.area)
        self.root.require(self.area).chmod(0o700)
        self.root.write_text(self.area / "namespace.json", json.dumps({"version": 1, "id": "00000000-0000-0000-0000-000000000000", "environment": "operational", "path": str(self.area), "test_root": None}))
        with self.assertRaises(StateError) as caught:
            with open_store(self.project, self.boundary()):
                pass
        self.assertEqual(caught.exception.diagnostic.code, "state.namespace")
        self.assertEqual({p.name for p in self.area.iterdir()}, {"namespace.json"})

    def test_incompatible_versions_unknown_flags_and_corrupt_snapshots_diagnose(self):
        _, snapshot, _ = self.start()
        original = snapshot.read_text()
        cases = [
            (lambda value: value.update(version=99), "state.version"),
            (lambda value: value["state"].update(version=99), "state.version"),
            (lambda value: value["state"].update(checks_passed=True, auto_merge=True), "state.schema"),
            (lambda value: value["state"].update(phase="publishing"), "state.schema"),
            (lambda value: value["state"].update(phase=[]), "state.schema"),
        ]
        for mutate, code in cases:
            with self.subTest(code=code):
                value = json.loads(original)
                mutate(value)
                self.root.write_text(snapshot, json.dumps(value))
                with self.assertRaises(StateError) as caught:
                    with open_store(self.project, self.boundary()):
                        pass
                self.assertEqual(caught.exception.diagnostic.code, code)
        self.root.write_text(snapshot, '{"version": 1,')
        with self.assertRaises(StateError) as caught:
            with open_store(self.project, self.boundary()):
                pass
        self.assertEqual(caught.exception.diagnostic.code, "state.corrupt")

    def test_incomplete_or_corrupt_events_never_get_truncated_or_adopted(self):
        _, snapshot, journal = self.start()
        previous = journal.read_bytes()
        snapshot_bytes = snapshot.read_bytes()
        for payload, code in ((previous + b'{"version":1', "state.incomplete_event"), (previous + b'{}\n', "state.schema")):
            with self.subTest(code=code):
                self.root.write_text(journal, payload.decode())
                with self.assertRaises(StateError) as caught:
                    with open_store(self.project, self.boundary()):
                        pass
                self.assertEqual(caught.exception.diagnostic.code, code)
                self.assertEqual(journal.read_bytes(), payload)
                self.assertEqual(snapshot.read_bytes(), snapshot_bytes)

    def test_write_failures_leave_prior_or_next_valid_snapshot_and_recover(self):
        for index, point in enumerate(POINTS):
            with self.subTest(point=point):
                area = self.root.path / f"state-{index}"
                _, snapshot, _ = self.start(area)
                def checkpoint(name):
                    if name == point:
                        raise OSError("injected persistence failure")
                with open_store(self.project, self.boundary(area), checkpoint=checkpoint) as store:
                    with self.assertRaises(OSError):
                        store.transition(1, Phase.IMPLEMENTING)
                    with self.assertRaises(StateError):
                        store.load()
                cached = json.loads(snapshot.read_text())["state"]
                self.assertIn(cached["phase"], {Phase.APPROVED, Phase.IMPLEMENTING})
                with open_store(self.project, self.boundary(area)) as store:
                    state = store.load()
                    self.assertEqual(state["phase"], Phase.APPROVED if point == "journal.opened" else Phase.IMPLEMENTING)
                    self.assertEqual(len(store.history()), state["revision"])

    def test_lost_intent_response_recovers_same_pending_operation(self):
        self.start()
        def checkpoint(name):
            if name == "journal.file_synced":
                raise OSError("lost response after durable intent")
        with open_store(self.project, self.boundary(), checkpoint=checkpoint) as store:
            with self.assertRaises(OSError):
                store.begin_operation(1, "branch", {"branch": "agent/m2"})
        with open_store(self.project, self.boundary()) as store:
            state = store.load()
            operation_id = state["pending"]["id"]
            self.assertEqual(state["revision"], 2)
            with self.assertRaises(StateError):
                store.begin_operation(1, "branch")
            with self.assertRaises(StateError):
                store.begin_operation(2, "branch")
            self.assertEqual(store.load()["pending"]["id"], operation_id)
            self.assertEqual(len(store.history()), 2)

    def test_initialization_interruption_can_reopen_without_importing_temporary_files(self):
        for index, point in enumerate(("mkdir.created", "mkdir.synced", "atomic.opened", "atomic.written", "atomic.replaced", "atomic.directory_synced")):
            area = self.root.path / f"initialization-{index}"
            def checkpoint(name):
                if name == point:
                    raise OSError("initialization interrupted")
            with self.subTest(point=point):
                with self.assertRaises(OSError):
                    with open_store(self.project, self.boundary(area), checkpoint=checkpoint):
                        pass
                with open_store(self.project, self.boundary(area)) as store:
                    self.assertIsNone(store.load())
                    self.assertEqual(store.start_run()["phase"], Phase.APPROVED)

    def test_first_durable_event_recovers_when_initial_snapshot_was_never_written(self):
        def checkpoint(name):
            if name == "journal.directory_synced":
                raise OSError("interrupted first event")
        with open_store(self.project, self.boundary(), checkpoint=checkpoint) as store:
            snapshot = store.snapshot
            with self.assertRaises(OSError):
                store.start_run()
        self.assertFalse(snapshot.exists())
        with open_store(self.project, self.boundary()) as store:
            state = store.load()
            self.assertEqual(state["revision"], 1)
            self.assertEqual(state["phase"], Phase.APPROVED)
            with self.assertRaises(StateError):
                store.start_run()

    def test_partial_snapshot_write_preserves_old_cache_and_replays_complete_event(self):
        _, snapshot, _ = self.start()
        previous = snapshot.read_bytes()
        actual = DurableIO.write_all
        writes = 0
        def partial(descriptor, data):
            nonlocal writes
            writes += 1
            if writes == 2:
                actual(descriptor, data[:23])
                raise OSError("partial snapshot temporary file")
            actual(descriptor, data)
        with open_store(self.project, self.boundary()) as store:
            with patch.object(DurableIO, "write_all", side_effect=partial):
                with self.assertRaises(OSError):
                    store.transition(1, Phase.IMPLEMENTING)
        self.assertEqual(snapshot.read_bytes(), previous)
        with open_store(self.project, self.boundary()) as store:
            self.assertEqual(store.load()["phase"], Phase.IMPLEMENTING)
            self.assertEqual(len(store.history()), 2)

    def test_unowned_test_repository_is_rejected_before_git_inspection(self):
        with patch("agentic_runner.state.Repository") as repository:
            for target in (*PROTECTED_ROOTS, Path.cwd(), self.root.path / ".." / "outside-test-root"):
                with self.assertRaises((StateError, IsolationError)):
                    with open_store(target, self.boundary()):
                        pass
            repository.assert_not_called()

    def test_actual_process_termination_releases_locks_and_recovers_prior_or_next(self):
        context = multiprocessing.get_context("fork")
        for index, point in enumerate(POINTS):
            with self.subTest(point=point):
                area = self.root.path / f"killed-state-{index}"
                _, snapshot, _ = self.start(area)
                process = context.Process(target=killed_writer, args=(self.root, self.project, area, point))
                process.start()
                process.join(10)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
                    self.fail("Termination fixture timed out")
                self.assertEqual(process.exitcode, 72)
                self.assertIn(json.loads(snapshot.read_text())["state"]["phase"], {Phase.APPROVED, Phase.IMPLEMENTING})
                with open_store(self.project, self.boundary(area)) as store:
                    state = store.load()
                    self.assertEqual(state["phase"], Phase.APPROVED if point == "journal.opened" else Phase.IMPLEMENTING)

    def test_partial_journal_write_keeps_prior_snapshot_and_stops_with_diagnostic(self):
        _, snapshot, journal = self.start()
        previous = snapshot.read_bytes()
        original = DurableIO.write_all
        def partial(descriptor, data):
            original(descriptor, data[:19])
            raise OSError("injected short append")
        with open_store(self.project, self.boundary()) as store:
            with patch.object(DurableIO, "write_all", side_effect=partial):
                with self.assertRaises(OSError):
                    store.transition(1, Phase.IMPLEMENTING)
        self.assertEqual(snapshot.read_bytes(), previous)
        with self.assertRaises(StateError) as caught:
            with open_store(self.project, self.boundary()):
                pass
        self.assertEqual(caught.exception.diagnostic.code, "state.incomplete_event")
        self.assertFalse(journal.read_bytes().endswith(b"\n"))

    def test_file_and_directory_fsync_order_and_private_permissions(self):
        self.start()
        actions = []
        actual_sync = os.fsync
        actual_replace = os.replace
        def sync(descriptor):
            actions.append("directory" if stat.S_ISDIR(os.fstat(descriptor).st_mode) else "file")
            actual_sync(descriptor)
        def replace(source, target):
            actions.append("replace")
            actual_replace(source, target)
        with open_store(self.project, self.boundary()) as store:
            with patch("os.fsync", side_effect=sync), patch("os.replace", side_effect=replace):
                store.transition(1, Phase.IMPLEMENTING)
            self.assertEqual(actions, ["file", "directory", "file", "replace", "directory"])
            self.assertEqual(stat.S_IMODE(store.path.stat().st_mode), 0o700)
            self.assertEqual(stat.S_IMODE(store.snapshot.stat().st_mode), 0o600)
            self.assertEqual(stat.S_IMODE(store.journal.stat().st_mode), 0o600)
