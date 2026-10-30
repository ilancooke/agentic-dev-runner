"""Codex CLI 0.166 capability checks and strict, non-authoritative reports.

Generation is gated separately from offline capability inspection. Never infer
authentication isolation or resume permissions from the name of a sandbox.
"""

import json
import uuid

from .execution import refuse


MODEL = "gpt-6.1-sol"
EFFORT = "high"
PROFILE = "runner-m4"
REPORT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {"milestone": {"type": "string"}, "summary": {"type": "string"},
                   "status": {"type": "string", "enum": ["reported", "blocked"]}},
    "required": ["milestone", "summary", "status"],
}


def settings():
    # New permission profiles: never mix these with the legacy --sandbox flag.
    values = {
        "model": MODEL, "model_reasoning_effort": EFFORT, "approval_policy": "never",
        "default_permissions": PROFILE, "features.use_legacy_landlock": False,
        f'permissions.{PROFILE}.filesystem.":root"': "read",
        f'permissions.{PROFILE}.filesystem."/workspace"': "write",
        f'permissions.{PROFILE}.filesystem."/workspace/.git"': "deny",
        f'permissions.{PROFILE}.filesystem."/home/runner/.codex"': "deny",
        f'permissions.{PROFILE}.filesystem."/run/runner-api"': "deny",
        f'permissions.{PROFILE}.filesystem."/proc"': "deny",
        f'permissions.{PROFILE}.network.enabled': False,
        "shell_environment_policy.inherit": "none",
        "shell_environment_policy.set": {"PATH": "/workspace/.venv/bin:/usr/local/bin:/usr/bin:/bin", "HOME": "/home/runner", "TMPDIR": "/tmp"},
    }
    arguments = []
    for key, value in values.items():
        if isinstance(value, dict):
            literal = "{ " + ", ".join(json.dumps(k) + " = " + json.dumps(v) for k, v in value.items()) + " }"
        else:
            literal = json.dumps(value)
        arguments.extend(["-c", key + "=" + literal])
    return arguments


def command(*, resume_id=None):
    argv = ["codex", *settings(), "exec"]
    if resume_id is not None:
        try:
            if str(uuid.UUID(resume_id)) != resume_id:
                raise ValueError()
        except (ValueError, TypeError, AttributeError):
            refuse("session", "Resume requires the exact recorded UUID, never --last or a session name.")
        argv += ["resume", resume_id]
    argv += ["--ignore-user-config", "--ignore-rules", "--strict-config", "--json", "--skip-git-repo-check", "--model", MODEL, "-"]
    return argv


def parse_events(data, *, milestone, expected_session=None):
    if len(data) > 4 * 1024 * 1024 or not data.endswith(b"\n"):
        refuse("events", "Codex event stream is incomplete or too large.")
    session = None
    usage = None
    report_text = None
    completed = False
    for line in data.splitlines():
        try:
            event = json.loads(line)
            kind = event["type"]
            if completed:
                raise ValueError()
            if kind == "thread.started":
                if session is not None:
                    raise ValueError()
                session = str(uuid.UUID(event["thread_id"]))
                if event["thread_id"] != session or expected_session is not None and session != expected_session:
                    raise ValueError()
            elif kind == "turn.completed":
                if session is None:
                    raise ValueError()
                usage = event.get("usage")
                if usage is not None and (not isinstance(usage, dict) or any(type(v) is not int or v < 0 for v in usage.values())):
                    raise ValueError()
                completed = True
            elif kind in {"error", "turn.failed"}:
                refuse("codex_failed", "Codex reported a failure; preserve partial work. No retry or model fallback is authorized here.")
            elif kind == "item.completed" and event.get("item", {}).get("type") == "agent_message":
                # Only the final structured message is used as the agent report.
                report_text = event["item"]["text"]
            elif kind not in {"turn.started", "item.started", "item.updated", "item.completed"}:
                raise ValueError()
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            refuse("events", "Unexpected Codex event contract; retain private diagnostics and recheck installed capabilities.")
    try:
        report = json.loads(report_text) if report_text is not None else None
    except (ValueError, TypeError):
        report = None
    if not completed or session is None or not isinstance(report, dict) or set(report) != set(REPORT_SCHEMA["required"]) or report["milestone"] != milestone or report["status"] not in {"reported", "blocked"} or not isinstance(report["summary"], str) or not report["summary"]:
        refuse("report", "Missing or mismatched Codex report; agent claims cannot advance verification/publication.")
    return {"version": 1, "session_id": session, "model": MODEL, "reasoning_effort": EFFORT,
            "usage": usage, "report": report}


class CodexAdapter:
    def __init__(self, executor):
        self.executor = executor

    def inspect(self, store):
        def run(argv):
            return self.executor.execute(store, store.load()["revision"], argv)
        version = run(["codex", "--version"])
        if version.returncode or version.stdout.strip() != b"codex-cli 0.166.0":
            refuse("codex_version", "This adapter contract requires capability review for a different Codex version.")
        catalog = run(["codex", "debug", "models", "--bundled"])
        try:
            models = [m for m in json.loads(catalog.stdout)["models"] if m["slug"] == MODEL]
            if catalog.returncode or len(models) != 1 or EFFORT not in [r["effort"] for r in models[0]["supported_reasoning_levels"]]:
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            refuse("model", "The installed catalog does not support the exact requested model/effort. No fallback is allowed.")
        for argv, required in ((["codex", "exec", "--help"], ("--json", "--output-schema", "--ignore-user-config", "--ignore-rules", "--strict-config")),
                               (["codex", "exec", "resume", "--help"], ("[SESSION_ID]", "--ignore-user-config", "--ignore-rules", "--json"))):
            result = run(argv)
            if result.returncode or not all(s.encode() in result.stdout for s in required):
                refuse("codex_cli", "Installed Codex lacks required controls; do not infer resume permission behavior.")
        # This must execute the sentinel. Printing a configuration is insufficient.
        probe = run(["codex", *settings(), "sandbox", "--permission-profile", PROFILE, "-C", "/workspace", "--", "/bin/sh", "-c", "printf M4_SANDBOX_OK"])
        if probe.returncode or probe.stdout != b"M4_SANDBOX_OK":
            refuse("codex_sandbox", "The constrained container cannot execute the required Codex sandbox. Preserve this capability result; do not disable sandboxing, seccomp or AppArmor.")
        return {"version": 1, "cli": "0.166.0", "model": MODEL, "reasoning_effort": EFFORT, "sandbox": PROFILE,
                "generation_ready": False, "remaining": "Real authentication and explicit-ID resume permission checks require an authorized disposable probe and isolated transport."}

    def generate(self, *args, **kwargs):
        # No unsafe partial live implementation. The transport must keep authentication
        # outside project code and be actually boundary-tested before this gate opens.
        refuse("codex_transport", "Live generation is unavailable until credential-isolated transport and real sandbox/resume probes pass. No credentials are accepted or mounted.")
