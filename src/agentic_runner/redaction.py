"""Conservative public diagnostics: no raw model/tool output in public logs."""

import re


def redact(value, secrets=()):
    text = str(value)
    for secret in sorted((s for s in secrets if s), key=len, reverse=True):
        text = text.replace(secret, "[REDACTED]")
    text = re.sub(r"(?i)(Bearer\s+)[^\s\"']+", r"\1[REDACTED]", text)
    text = re.sub(r"\b(?:sk-[A-Za-z0-9_-]+|gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|AKIA[A-Z0-9]{16})\b", "[REDACTED]", text)
    text = re.sub(r"(?i)((?:access_token|refresh_token|api_key|password|secret)[\"']?\s*[:=]\s*[\"']?)[^\s\"',}]+", r"\1[REDACTED]", text)
    text = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)
    return text


def public_process(result):
    # Even perfect pattern matching cannot identify arbitrary project secrets.
    return {"returncode": result.returncode, "stopped": result.stopped,
            "stdout_bytes": len(result.stdout), "stderr_bytes": len(result.stderr)}
