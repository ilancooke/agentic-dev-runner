"""Native Codex integration for the accepted dedicated, trusted VM design."""

import hashlib
import json
import uuid
from pathlib import Path

from .codex import EFFORT, MODEL, REPORT_SCHEMA, parse_events
from .execution import ExecutionError, refuse


def native_settings(checkout, scratch, home=None):
    values = {"model": MODEL, "model_reasoning_effort": EFFORT, "approval_policy": "never",
              "sandbox_mode": "danger-full-access",
              "shell_environment_policy.inherit": "none",
              "shell_environment_policy.set.PATH": str(checkout / ".venv/bin") + ":/usr/local/bin:/usr/bin:/bin",
              "shell_environment_policy.set.HOME": str(home or Path.home()),
              "shell_environment_policy.set.TMPDIR": str(scratch)}
    return [arg for key, value in values.items() for arg in ("-c", key + "=" + json.dumps(value))]


def native_command(policy, checkout, scratch, schema, *, resume_id=None):
    if policy.codex_sandbox != "disabled":
        refuse("approval", "This adapter requires the explicitly authorized no-sandbox VM policy.")
    argv = [policy.codex_binary, *native_settings(checkout, scratch, policy.home), "exec"]
    if resume_id is not None:
        try:
            if str(uuid.UUID(resume_id)) != resume_id:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            refuse("session", "Native resume requires the exact recorded session UUID.")
        argv += ["resume", resume_id]
    argv += ["--dangerously-bypass-approvals-and-sandbox", "--ignore-user-config", "--ignore-rules", "--strict-config", "--json", "--model", MODEL,
             "--output-schema", str(schema), "-"]
    return argv


class NativeCodexAdapter:
    def __init__(self, executor):
        self.executor = executor

    def inspect(self, store):
        binary = Path(self.executor.policy.codex_binary)
        try:
            sha = hashlib.sha256(binary.read_bytes()).hexdigest()
        except OSError:
            refuse("codex_binary", "Pinned Codex executable is unavailable.")
        if sha != self.executor.policy.codex_sha256:
            refuse("codex_binary", "Codex binary changed; review capabilities and renew execution approval.")
        def run(arguments):
            return self.executor.execute(store, store.load()["revision"], [str(binary), *arguments])
        version = run(["--version"])
        if version.returncode or version.stdout.strip() != b"codex-cli 0.166.0":
            refuse("codex_version", "This native adapter requires a reviewed CLI 0.166.0 contract.")
        catalog = run(["debug", "models", "--bundled"])
        try:
            matches = [m for m in json.loads(catalog.stdout)["models"] if m["slug"] == MODEL]
            if catalog.returncode or len(matches) != 1 or EFFORT not in [r["effort"] for r in matches[0]["supported_reasoning_levels"]]:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            refuse("model", "The pinned native CLI does not advertise the exact requested model and effort.")
        for args in (["exec", "--help"], ["exec", "resume", "--help"]):
            result = run(args)
            if result.returncode or not all(x in result.stdout for x in (b"--json", b"--output-schema", b"--ignore-user-config", b"--ignore-rules", b"--dangerously-bypass-approvals-and-sandbox")):
                refuse("codex_cli", "Required native exec/resume controls are unavailable.")
        return {"cli": "0.166.0", "binary_sha256": sha, "model": MODEL, "reasoning_effort": EFFORT,
                "sandbox": "disabled", "approval_policy": "never", "network": "development"}

    def generate(self, store, revision, prompt, *, resume_id=None, cancel=None):
        if not isinstance(prompt, str) or not prompt.strip() or len(prompt.encode()) > 65536:
            refuse("prompt", "Provide a nonempty bounded native prompt.")
        state = store.check_authorization(revision)
        if resume_id is not None:
            owned = any(event.get("details", {}).get("evidence", {}).get("codex", {}).get("session_id") == resume_id
                        for event in store.history())
            if not owned:
                refuse("session", "Resume ID is not recorded for this run; foreign sessions cannot be adopted.")
        self.inspect(store)
        scratch = self.executor.scratch(store)
        schema = scratch / "codex-report-schema.json"
        store.io.atomic(schema, json.dumps(REPORT_SCHEMA).encode() + b"\n")
        parsed = None
        def validate(result):
            nonlocal parsed
            if result.returncode:
                error = ExecutionError("execution.native_codex_failed", "Codex exited unsuccessfully; preserve private diagnostics and pending intent. No fallback or retry.", "native Codex")
                error.process = result  # Private caller diagnostics, never journal/public logs.
                raise error
            try:
                parsed = parse_events(result.stdout, milestone=state["approval"]["milestone"], expected_session=resume_id)
            except ExecutionError as error:
                error.process = result
                raise
            return {"codex": {k: parsed[k] for k in ("version", "session_id", "model", "reasoning_effort", "usage")},
                    "report_sha256": hashlib.sha256(json.dumps(parsed["report"], sort_keys=True).encode()).hexdigest()}
        argv = native_command(self.executor.policy, store.repository.root, scratch, schema, resume_id=resume_id)
        self.executor.execute(store, store.load()["revision"], argv, input_bytes=prompt.encode(), cancel=cancel, validate=validate,
                              metadata={"kind": "codex", "model": MODEL, "effort": EFFORT, "resume_id": resume_id})
        return parsed
