"""Fresh structured Codex sessions on the trusted VM, without its sandbox."""

import json
import tempfile
from pathlib import Path

from .project import RunnerError, check_process, require
from .supervisor import supervise


MODEL = "gpt-6.1-sol"
REPORT_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "milestone": {"type": "string"},
        "status": {"type": "string", "enum": ["success", "blocked", "failed"]},
        "summary": {"type": "string"},
        "blockers": {"type": "array", "items": {"type": "string"}},
        "commit_message": {"type": "string"},
    },
    "required": ["milestone", "status", "summary", "blockers", "commit_message"],
}


def validate_report(value, milestone):
    require(isinstance(value, dict) and set(value) == set(REPORT_SCHEMA["required"]), "Missing or unexpected report fields.")
    require(all(isinstance(value[k], str) for k in ("milestone", "status", "summary", "commit_message")), "Report strings are invalid.")
    require(value["milestone"] == milestone and value["status"] in {"success", "blocked", "failed"}, "Mismatched milestone or report status.")
    require(value["summary"].strip() and isinstance(value["blockers"], list) and
            all(isinstance(b, str) and b.strip() for b in value["blockers"]), "Summary/blockers are invalid.")
    message = value["commit_message"]
    require(value["status"] != "success" or not value["blockers"] and message.strip() and
            len(message) <= 200 and not any(ord(c) < 32 for c in message), "Success requires no blockers and a one-line commit message.")
    return value


def generate(project, milestone, documents, env, *, process=supervise):
    prompt = (
        f"Implement or resume ONLY {milestone.id}: {milestone.title}.\n"
        "You are in a trusted Ubuntu VM with no Codex sandbox. Work may be partially implemented.\n"
        "Run the required tests and update PROGRESS.md. Return the structured report.\n"
        "Perform NO Git or GitHub operations, including staging, commits, branches, pushes or merges.\n"
        "Do not use subagents. Do not modify AGENTS.md, SPEC.md, ARCHITECTURE.md, ROADMAP.md or runner configuration.\n"
        "The runner independently verifies, marks completion, commits and pushes to dev.\n"
        f"Deliverables:\n{milestone.deliverables}\nAcceptance:\n{milestone.acceptance_criteria}\n"
        f"Required verification argv: {json.dumps(project.verification)}\n"
        + "\n".join(f"\n--- {name} ---\n{text}" for name, text in documents.items())
    ).encode()
    require(len(prompt) <= 65536, "Project documents exceed the 64 KiB prompt limit; shorten the documents.")
    with tempfile.TemporaryDirectory(prefix="ralph-codex-") as temporary:
        schema, output = Path(temporary) / "schema.json", Path(temporary) / "result.json"
        schema.write_text(json.dumps(REPORT_SCHEMA))
        argv = ["codex", "exec", "--ignore-user-config", "--ignore-rules", "--strict-config",
                "--dangerously-bypass-approvals-and-sandbox", "--model", MODEL,
                "-c", 'model_reasoning_effort="high"', "--disable", "multi_agent", "--disable", "multi_agent_v2",
                "--output-schema", str(schema),
                "--output-last-message", str(output), "-"]
        result = process(argv, cwd=project.repository, env=env, timeout=3600, input_bytes=prompt)
        check_process(result, "Codex failed or exceeded its execution/output limit")
        try:
            value = json.loads(output.read_text())
        except (OSError, ValueError) as exc:
            raise RunnerError("Codex did not return a valid structured result; partial work retained.") from exc
    return validate_report(value, milestone.id)
