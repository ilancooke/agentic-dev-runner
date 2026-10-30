"""Locked, versioned journal authority plus atomic materialized run state.

No execution/publication adapter exists here. Reconciliation never performs an
external effect. A write error poisons this handle until it is closed/reopened.
"""

import copy
import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .approval import RunnerPolicy, capture_approval, digest, scope_snapshot
from .diagnostics import DiscoveryError
from .durable import DurableIO, StateError, canonical_json, decode_json
from .repository import Repository
from .run_state import OPERATION_PHASES, TRANSITIONS, Phase, exact, uuid_value, validate_state
from .state_boundary import PROTECTED, directory_lock, overlaps


EVENT_KINDS = {"started", "transitioned", "resumed", "operation_began", "operation_resolved", "operation_uncertain", "approval_invalidated", "approval_renewed"}


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def inode(path):
    info = path.stat()
    return [info.st_dev, info.st_ino]


@contextmanager
def open_store(repository_path, boundary, *, policy=None, checkpoint=None):
    target = Path(repository_path).resolve()
    if boundary.disposable is not None:
        boundary.disposable.require(target)
    if any(overlaps(target, path.resolve()) for path in PROTECTED):
        raise StateError("state.protected", "Reference/legacy targets cannot be registered.", str(target))
    repository = Repository(target)
    boundary.check_repository(repository)

    def repository_guard(path):
        boundary.check_repository(repository)
        if boundary.disposable is not None:
            boundary.disposable.require(path)

    # The Git common directory inode is shared across state roots and worktrees.
    with directory_lock(repository.common_dir, repository_guard):
        identity = repository.discover()
        io = DurableIO(boundary.guard, checkpoint)
        io.mkdir(boundary.path)
        io.sync_dir(boundary.path.parent)
        boundary.bind_inode()
        with directory_lock(boundary.path, boundary.guard):
            store = RunStore(repository, identity, boundary, io, policy or RunnerPolicy())
            try:
                store.load()
                yield store
            finally:
                store.closed = True


class RunStore:
    def __init__(self, repository, identity, boundary, io, policy):
        self.repository = repository
        self.identity = identity
        self.boundary = boundary
        self.io = io
        self.policy = policy
        self.closed = False
        self.poisoned = False
        namespace_path = boundary.path / "namespace.json"
        expected = {"version": 1, "environment": boundary.environment, "path": str(boundary.path),
                    "test_root": str(boundary.disposable.path) if boundary.disposable is not None else None}
        if namespace_path.exists() or namespace_path.is_symlink():
            namespace = decode_json(io.read(namespace_path), namespace_path)
            exact(namespace, {*expected, "id"})
            if any(namespace[k] != v or type(namespace[k]) is not type(v) for k, v in expected.items()):
                raise StateError("state.namespace", "State namespace/version/environment/path mismatch; do not copy or import legacy state.", str(namespace_path))
            uuid_value(namespace["id"])
        else:
            if any(p.name != namespace_path.name and not p.name.startswith(".tmp-") for p in boundary.path.iterdir()):
                raise StateError("state.namespace", "Refusing to adopt a nonempty, unversioned state directory.", str(boundary.path))
            namespace = {**expected, "id": str(uuid.uuid4())}
            io.atomic(namespace_path, canonical_json(namespace) + b"\n")
        self.namespace = namespace
        self.project = identity["id"]
        self.path = boundary.path / self.project
        # Bind each common Git directory to its original project identity in this namespace.
        binding_path = boundary.path / f"binding-{digest(inode(repository.common_dir))}.json"
        self.binding = {"version": 1, "identity_version": 1, "namespace_id": namespace["id"],
                        "project": self.project, "common_dir": str(repository.common_dir), "common_inode": inode(repository.common_dir),
                        "checkout": str(repository.root), "checkout_inode": inode(repository.root), "remote": identity["remote"]}
        if binding_path.exists() or binding_path.is_symlink():
            actual = decode_json(io.read(binding_path), binding_path)
            if canonical_json(actual) != canonical_json(self.binding):
                raise StateError("state.identity", "Repository/checkout/remote binding changed; explicit migration is required.", str(binding_path))
        else:
            if self.path.exists():
                raise StateError("state.identity", "Project state exists without its namespace binding; preserve it for recovery.", str(self.path))
            io.atomic(binding_path, canonical_json(self.binding) + b"\n")
        io.mkdir(self.path)
        io.sync_dir(boundary.path)
        self.journal = self.path / "events.jsonl"
        self.snapshot = self.path / "state.json"

    def _usable(self):
        if self.closed or self.poisoned:
            raise StateError("state.handle", "Close/reopen the store after release or uncertain persistence; reconcile before acting.", str(self.path))
        self.boundary.guard(self.path)
        if inode(self.repository.common_dir) != self.binding["common_inode"] or inode(self.repository.root) != self.binding["checkout_inode"]:
            raise StateError("state.identity", "Repository directory identity changed while locked.", str(self.path))

    def _validate(self, state):
        try:
            validate_state(state, self.project)
            approved = state["approval"]["repository"]
            if any(approved[key] != self.identity[key] for key in ("id", "root", "common_dir", "remote")):
                raise StateError("state.identity", "Approval is bound to another checkout/repository.", str(self.path))
        except DiscoveryError:
            raise
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            raise StateError("state.schema", "Malformed state schema; preserve files for inspection.", str(self.path)) from exc

    @staticmethod
    def _delta(previous, state, kind):
        if previous is None:
            if kind != "started" or state["phase"] != Phase.APPROVED or state["pending"] is not None:
                raise StateError("state.transition", "First event must start an approved run without pending effects.", "events")
            return
        if kind == "started" or state["run_id"] != previous["run_id"]:
            raise StateError("state.transition", "A run cannot be replaced or implicitly restarted.", "events")
        changed = {key for key in state if key != "revision" and state[key] != previous[key]}
        allowed = set()
        valid = True
        if kind == "transitioned":
            allowed = {"phase", "resume_phase"}
            valid = state["phase"] in TRANSITIONS[previous["phase"]] and (previous["pending"] is None or state["phase"] == Phase.PAUSED)
            if state["phase"] == Phase.PAUSED:
                valid &= state["resume_phase"] == previous["phase"]
        elif kind == "resumed":
            allowed = {"phase", "resume_phase"}
            valid = previous["phase"] == Phase.PAUSED and state["phase"] == previous["resume_phase"] and previous["pending"] is None
        elif kind == "approval_invalidated":
            allowed = {"phase", "resume_phase", "invalidation"}
            valid = state["phase"] == Phase.APPROVAL_REQUIRED and previous["phase"] != Phase.FAILED
        elif kind == "approval_renewed":
            allowed = {"phase", "resume_phase", "invalidation", "approval"}
            valid = previous["phase"] == Phase.APPROVAL_REQUIRED and previous["pending"] is None and state["phase"] == Phase.APPROVED and state["approval"]["milestone"] == previous["approval"]["milestone"]
        elif kind == "operation_began":
            allowed = {"pending"}
            valid = previous["pending"] is None and state["pending"] is not None and previous["phase"] in OPERATION_PHASES[state["pending"]["kind"]]
        elif kind in {"operation_resolved", "operation_uncertain"}:
            allowed = {"pending"}
            valid = previous["pending"] is not None
            if kind == "operation_resolved":
                valid &= state["pending"] is None
            else:
                valid &= state["pending"] == {**previous["pending"], "status": "uncertain"}
        if not valid or not changed.issubset(allowed):
            raise StateError("state.transition", "Event violates the documented transition/intent rules.", "events")

    def _events(self):
        try:
            return self._read_events()
        except DiscoveryError:
            raise
        except (TypeError, ValueError, KeyError, AttributeError) as exc:
            raise StateError("state.schema", "Malformed event schema; preserve journal and snapshot.", str(self.journal)) from exc

    def _read_events(self):
        self._usable()
        data = self.io.read(self.journal) if self.journal.exists() or self.journal.is_symlink() else b""
        if data and not data.endswith(b"\n"):
            raise StateError("state.incomplete_event", "Journal has an incomplete trailing event; snapshot remains evidence. Preserve both files; no automatic truncation or advancement.", str(self.journal))
        events = []
        previous_hash = None
        previous_state = None
        for line in data.splitlines():
            event = decode_json(line, self.journal)
            exact(event, {"version", "seq", "id", "at", "kind", "previous", "state", "hash", "details"})
            if type(event["version"]) is not int or event["version"] != 1:
                raise StateError("state.version", "Unsupported event schema; explicit migration is required.", str(self.journal))
            if type(event["seq"]) is not int or event["seq"] != len(events) + 1 or event["previous"] != previous_hash or event["kind"] not in EVENT_KINDS:
                raise StateError("state.history", "Broken event order, identity, or hash chain.", str(self.journal))
            uuid_value(event["id"])
            if not isinstance(event["at"], str) or not isinstance(event["details"], dict):
                raise StateError("state.history", "Invalid event metadata.", str(self.journal))
            payload = {k: v for k, v in event.items() if k != "hash"}
            if digest(payload) != event["hash"]:
                raise StateError("state.history", "Event digest mismatch; no history is discarded.", str(self.journal))
            self._validate(event["state"])
            if event["state"]["revision"] != event["seq"]:
                raise StateError("state.history", "State/event revision mismatch.", str(self.journal))
            self._delta(previous_state, event["state"], event["kind"])
            events.append(event)
            previous_hash, previous_state = event["hash"], event["state"]
        return events

    def load(self):
        events = self._events()
        cached = None
        if self.snapshot.exists() or self.snapshot.is_symlink():
            cached = decode_json(self.io.read(self.snapshot), self.snapshot)
            exact(cached, {"version", "event_hash", "state"})
            if type(cached["version"]) is not int or cached["version"] != 1:
                raise StateError("state.version", "Unsupported snapshot schema.", str(self.snapshot))
            self._validate(cached["state"])
            index = cached["state"]["revision"] - 1
            if index >= len(events) or cached["event_hash"] != events[index]["hash"] or cached["state"] != events[index]["state"]:
                raise StateError("state.snapshot", "Snapshot does not match a complete journal event; preserve evidence.", str(self.snapshot))
        if not events:
            return None
        latest = {"version": 1, "event_hash": events[-1]["hash"], "state": events[-1]["state"]}
        if latest != cached:
            # A full event with a lost response is authoritative only after re-sync.
            try:
                self.boundary.guard(self.journal)
                descriptor = os.open(self.journal, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
                try:
                    os.fsync(descriptor)
                finally:
                    os.close(descriptor)
                self.io.sync_dir(self.path)
                self.io.atomic(self.snapshot, canonical_json(latest) + b"\n")
            except BaseException:
                self.poisoned = True
                raise
        return copy.deepcopy(latest["state"])

    def history(self):
        return copy.deepcopy(self._events())

    def _commit(self, state, kind, details=None):
        events = self._events()
        state = copy.deepcopy(state)
        state["revision"] = len(events) + 1
        self._validate(state)
        self._delta(events[-1]["state"] if events else None, state, kind)
        event = {"version": 1, "seq": state["revision"], "id": str(uuid.uuid4()), "at": timestamp(),
                 "kind": kind, "previous": events[-1]["hash"] if events else None, "state": state, "details": details or {}}
        event["hash"] = digest(event)
        data = canonical_json(event) + b"\n"
        if len(data) > 8 * 1024 * 1024 or len(canonical_json(events)) + len(data) > 60 * 1024 * 1024:
            raise StateError("state.size", "Journal retention limit reached; preserve history for explicit archival/migration.", str(self.journal))
        try:
            self.io.append(self.journal, data)
            self.io.atomic(self.snapshot, canonical_json({"version": 1, "event_hash": event["hash"], "state": state}) + b"\n")
        except BaseException:
            self.poisoned = True
            raise
        return copy.deepcopy(state)

    def _current(self, revision):
        state = self.load()
        if state is None or type(revision) is not int or revision != state["revision"]:
            raise StateError("state.stale", "Read current state/reconcile pending intent before retrying a stale control request.", str(self.path))
        return state

    def start_run(self):
        if self.load() is not None:
            raise StateError("state.exists", "A run already exists; inspect it instead of starting duplicate work.", str(self.path))
        approval = capture_approval(self.repository, self.policy)
        state = {"version": 1, "identity_version": 1, "project": self.project, "run_id": str(uuid.uuid4()), "revision": 1,
                 "phase": Phase.APPROVED, "resume_phase": None, "approval": approval, "pending": None, "invalidation": None}
        return self._commit(state, "started", {"authorization": "explicit start_run request"})

    def check_authorization(self, revision):
        state = self._current(revision)
        if state["phase"] in {Phase.APPROVAL_REQUIRED, Phase.FAILED}:
            raise StateError("approval.required", "This run requires explicit renewed approval or failure recovery.", str(self.path))
        try:
            current = scope_snapshot(self.repository, self.policy)
            approved = state["approval"]
            valid = all(current["repository"][key] == approved["repository"][key] for key in ("id", "root", "common_dir", "remote", "default_branch"))
            valid &= current["scope_hash"] == approved["scope_hash"] and current["configuration_hash"] == approved["configuration_hash"]
            valid &= self.repository._run(["merge-base", approved["approved_revision"], current["repository"]["head"]]) == approved["approved_revision"]
            if valid:
                return state
            reason = "Protected scope, identity, ancestry or execution configuration changed."
        except DiscoveryError as exc:
            reason = f"Required approval evidence is unavailable or invalid ({exc.diagnostic.code})."
        state.update(phase=Phase.APPROVAL_REQUIRED, resume_phase=None, invalidation=reason)
        self._commit(state, "approval_invalidated", {"reason": reason})
        raise StateError("approval.invalidated", reason + " Inspect the retained approval and explicitly renew.", str(self.path))

    def transition(self, revision, phase):
        if not isinstance(phase, (str, Phase)) or phase not in {p.value for p in Phase}:
            raise StateError("state.transition", "Unknown phase; publication is not implemented in M3.", str(self.path))
        state = self.check_authorization(revision)
        state.update(phase=phase, resume_phase=state["phase"] if phase == Phase.PAUSED else None)
        return self._commit(state, "transitioned")

    def resume(self, revision):
        state = self.check_authorization(revision)
        if state["phase"] != Phase.PAUSED:
            raise StateError("state.transition", "Only explicitly paused runs can resume.", str(self.path))
        state.update(phase=state["resume_phase"], resume_phase=None)
        return self._commit(state, "resumed")

    def begin_operation(self, revision, kind, details=None):
        if kind not in OPERATION_PHASES or not isinstance(details or {}, dict):
            raise StateError("state.operation", "Only branch/implement/verify intents are supported in M3; details must be an object.", str(self.path))
        state = self.check_authorization(revision)
        if state["pending"] is not None:
            raise StateError("state.pending", "Reconcile the existing operation before issuing another effect.", str(self.path))
        state["pending"] = {"id": str(uuid.uuid4()), "kind": kind, "project": self.project, "run_id": state["run_id"],
                            "expected_commit": state["approval"]["approved_revision"], "details": copy.deepcopy(details or {}), "status": "pending"}
        return self._commit(state, "operation_began")

    def resolve_operation(self, revision, operation_id, outcome, evidence):
        state = self._current(revision)
        if state["pending"] is None or state["pending"]["id"] != operation_id or outcome not in {"confirmed", "not_applied", "unknown"} or not isinstance(evidence, dict) or not evidence:
            raise StateError("state.operation", "Match the pending ID and provide reconciliation evidence plus an explicit outcome.", str(self.path))
        if outcome == "unknown":
            state["pending"]["status"] = "uncertain"
        else:
            state["pending"] = None
        return self._commit(state, "operation_uncertain" if outcome == "unknown" else "operation_resolved", {"outcome": outcome, "operation_id": operation_id, "evidence": evidence})

    def renew_approval(self, revision):
        state = self._current(revision)
        if state["phase"] != Phase.APPROVAL_REQUIRED or state["pending"] is not None:
            raise StateError("approval.required", "Renew only an invalidated run after reconciling all pending effects.", str(self.path))
        approval = capture_approval(self.repository, self.policy)
        state.update(approval=approval, phase=Phase.APPROVED, resume_phase=None, invalidation=None)
        return self._commit(state, "approval_renewed", {"authorization": "explicit renew_approval request"})
