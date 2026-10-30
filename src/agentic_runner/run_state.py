"""Version-one run schema. Publication phases intentionally require later gates."""

import base64
import hashlib
import re
import uuid
from enum import StrEnum
from pathlib import Path

from .approval import RunnerPolicy, digest, roadmap_scope
from .durable import StateError, canonical_json


class Phase(StrEnum):
    APPROVED = "approved"
    IMPLEMENTING = "implementing"
    VERIFICATION_PENDING = "verification_pending"
    PAUSED = "paused"
    APPROVAL_REQUIRED = "approval_required"
    FAILED = "failed"


TRANSITIONS = {
    Phase.APPROVED: {Phase.IMPLEMENTING, Phase.PAUSED, Phase.FAILED},
    Phase.IMPLEMENTING: {Phase.VERIFICATION_PENDING, Phase.PAUSED, Phase.FAILED},
    Phase.VERIFICATION_PENDING: {Phase.IMPLEMENTING, Phase.PAUSED, Phase.FAILED},
    Phase.PAUSED: set(),  # Explicit resume restores the recorded phase only.
    Phase.APPROVAL_REQUIRED: set(),  # Explicit renewal is required.
    Phase.FAILED: set(),
}
OPERATION_PHASES = {"branch": {Phase.APPROVED, Phase.IMPLEMENTING}, "implement": {Phase.IMPLEMENTING}, "verify": {Phase.VERIFICATION_PENDING}}


def fail(message):
    raise StateError("state.schema", message, "run state")


def exact(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        fail("State has missing/unknown fields; no implicit boolean flags or schema migration is allowed.")


def uuid_value(value):
    try:
        if str(uuid.UUID(value)) != value:
            fail("Expected a canonical UUID.")
    except (ValueError, TypeError, AttributeError):
        fail("Expected a canonical UUID.")


def validate_state(state, project):
    exact(state, {"version", "identity_version", "project", "run_id", "revision", "phase", "resume_phase", "approval", "pending", "invalidation"})
    if type(state["version"]) is not int or state["version"] != 1 or type(state["identity_version"]) is not int or state["identity_version"] != 1:
        raise StateError("state.version", "Unsupported run/identity schema; preserve state and use an explicit migration.", "run state")
    if state["project"] != project or type(state["revision"]) is not int or state["revision"] < 1:
        fail("Project identity/revision mismatch.")
    uuid_value(state["run_id"])
    if state["phase"] not in {p.value for p in Phase}:
        fail("Unknown phase; publication/completion phases are not supported by M3.")
    resumable = {Phase.APPROVED, Phase.IMPLEMENTING, Phase.VERIFICATION_PENDING}
    if (state["phase"] == Phase.PAUSED and state["resume_phase"] not in resumable) or (state["phase"] != Phase.PAUSED and state["resume_phase"] is not None):
        fail("Only paused runs have an explicit resumable phase.")
    if (state["phase"] == Phase.APPROVAL_REQUIRED) != (isinstance(state["invalidation"], str) and bool(state["invalidation"])):
        fail("Approval-required phase needs an invalidation reason.")
    if state["phase"] != Phase.APPROVAL_REQUIRED and state["invalidation"] is not None:
        fail("Unexpected invalidation reason.")
    approval = state["approval"]
    exact(approval, {"version", "approved_revision", "repository", "files", "scope_hash", "configuration", "configuration_hash", "milestone"})
    if type(approval["version"]) is not int or approval["version"] != 1:
        raise StateError("state.version", "Unsupported approval schema.", "approval")
    if not isinstance(approval["repository"], dict) or approval["repository"].get("id") != project or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", approval["approved_revision"] or ""):
        fail("Approval repository/revision mismatch.")
    exact(approval["repository"], {"id", "root", "git_dir", "common_dir", "head", "branch", "remote", "default_branch", "default_branch_oid", "default_branch_source"})
    exact(approval["configuration"], {"policy", "runtime", "verification"})
    policy = approval["configuration"]["policy"]
    exact(policy, {"version", "requested_model", "reasoning_effort", "max_ci_repairs", "global_concurrency"})
    if type(policy["version"]) is not int or policy["version"] != 1:
        fail("Unsupported policy schema.")
    RunnerPolicy(**{k: v for k, v in policy.items() if k != "version"}).as_dict()
    exact(approval["configuration"]["runtime"], {"family", "version_line", "baseline_version", "constraints", "selection_source", "package_manager"})
    commands = approval["configuration"]["verification"]
    if not isinstance(commands, list) or not commands:
        fail("Approval must retain verification declarations.")
    for command in commands:
        exact(command, {"argv", "sources"})
        if not all(isinstance(command[k], list) and command[k] and all(isinstance(v, str) and v for v in command[k]) for k in ("argv", "sources")):
            fail("Invalid verification declaration.")
    if not isinstance(approval["milestone"], str) or not re.fullmatch(r"M[1-9][0-9]*", approval["milestone"]):
        fail("Invalid approved milestone.")
    files = approval["files"]
    if not isinstance(files, dict) or "ROADMAP.md" not in files:
        fail("Approval must retain the committed roadmap and requirement bytes.")
    for path, record in files.items():
        if not isinstance(record, dict) or type(record.get("committed")) is not bool:
            fail("Invalid requirement record.")
        exact(record, {"sha256", "scope_sha256", "committed", "content_base64"} | ({"blob_oid"} if record["committed"] else set()))
        if record["committed"] == Path(path).is_absolute() or ".." in Path(path).parts or ".git" in Path(path).parts:
            fail("Invalid approval source path.")
        try:
            data = base64.b64decode(record["content_base64"], validate=True)
            normalized = roadmap_scope(data.decode()).encode() if path == "ROADMAP.md" else data
        except (ValueError, TypeError, UnicodeError):
            fail("Invalid retained requirement bytes.")
        if hashlib.sha256(data).hexdigest() != record["sha256"] or hashlib.sha256(normalized).hexdigest() != record["scope_sha256"]:
            fail("Retained requirement digest mismatch.")
        if record["committed"]:
            oid = record["blob_oid"]
            if not isinstance(oid, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", oid):
                fail("Invalid committed blob identity.")
            algorithm = hashlib.sha1 if len(oid) == 40 else hashlib.sha256
            if algorithm(f"blob {len(data)}\0".encode() + data).hexdigest() != oid:
                fail("Retained bytes do not match their committed blob.")
    if digest({k: v["scope_sha256"] for k, v in files.items()}) != approval["scope_hash"] or digest(approval["configuration"]) != approval["configuration_hash"]:
        fail("Approval scope/configuration digest mismatch.")
    pending = state["pending"]
    if pending is not None:
        exact(pending, {"id", "kind", "project", "run_id", "expected_commit", "details", "status"})
        uuid_value(pending["id"])
        if pending["kind"] not in OPERATION_PHASES or pending["project"] != project or pending["run_id"] != state["run_id"] or pending["expected_commit"] != approval["approved_revision"] or pending["status"] not in {"pending", "uncertain"} or not isinstance(pending["details"], dict):
            fail("Pending-operation identity or kind mismatch.")
    canonical_json(state)
