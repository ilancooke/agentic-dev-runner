"""Milestone-runner prototype. One command; default settings do not publish or merge.

Restricted to the disposable milestone-test repository until reviewed for wider use.
Project specs, config.yaml, skill, and JSON schema remain separate data files.
"""
import argparse
import fcntl
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import yaml
from jsonschema import Draft7Validator

ROOT = Path(__file__).resolve().parent
PROJECT_NAME = "milestone-test"  # Intentional prototype allowlist
ALLOWED_FILES = {"README.md", "ROADMAP.md", "CHECKPOINT.md", "HANDOFF.md",
                 "calculator.py", "tests/test_calculator.py", "requirements-dev.txt",
                 ".gitignore", ".github/workflows/tests.yml"}
CHECK_NAME = "test"


def cmd(args, cwd, *, env=None, capture=True):
    proc = subprocess.run(args, cwd=cwd, env=env, text=True,
                          capture_output=capture, check=False)
    if proc.returncode:
        raise RuntimeError(f"Command failed ({proc.returncode}): {args}\n{proc.stderr if capture else ''}")
    # Preserve leading spaces: Git porcelain v1 uses fixed-width status columns.
    return proc.stdout.rstrip("\r\n") if capture else ""


def git(project, *args):
    return cmd(["git", *args], project)


def gh(project, *args):
    return cmd(["gh", *args], project)


def git_sha(project, ref="HEAD"):
    return git(project, "rev-parse", "--verify", ref)


def load_config():
    config = yaml.safe_load((ROOT / "config.yaml").read_text())
    if not isinstance(config, dict):
        raise ValueError("Invalid config.yaml")
    for section in ("runner", "codex", "execution", "git", "safety"):
        if not isinstance(config.get(section), dict):
            raise ValueError(f"Missing config section: {section}")
    for flag in ("auto_commit", "auto_push", "auto_merge"):
        if type(config["git"].get(flag)) is not bool:
            raise ValueError(f"git.{flag} must be a boolean")
    if config["git"]["auto_merge"] and not (config["git"]["auto_commit"] and config["git"]["auto_push"]):
        raise ValueError("auto_merge requires auto_commit and auto_push")
    if config["git"]["auto_push"] and not config["git"]["auto_commit"]:
        raise ValueError("auto_push requires auto_commit")
    execution = config["execution"]
    for key, default in (("ci_timeout_seconds", 600), ("ci_poll_seconds", 10)):
        value = execution.get(key, default)
        if type(value) is not int or value < 1:
            raise ValueError(f"execution.{key} must be a positive integer")
    if execution.get("ci_poll_seconds", 10) > execution.get("ci_timeout_seconds", 600):
        raise ValueError("CI polling interval cannot exceed timeout")
    schema = json.loads((ROOT / "schemas/milestone-result.json").read_text())
    Draft7Validator.check_schema(schema)
    return config, schema


def state_file(cfg):
    return Path(cfg["runner"]["state_root"]) / f"{PROJECT_NAME}-state.json"


def save_state(cfg, data):
    path = state_file(cfg)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=".state-", delete=False) as f:
        name = f.name
        json.dump(data, f, indent=2)
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(name, path)


def load_state(cfg):
    path = state_file(cfg)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    if data.get("project") != PROJECT_NAME or data.get("status") not in {
        "running", "blocked", "awaiting_commit", "committed", "awaiting_ci", "awaiting_merge"}:
        raise RuntimeError("Invalid saved state")
    for field in ("milestone", "branch", "base_commit"):
        if not isinstance(data.get(field), str) or not data[field]:
            raise RuntimeError(f"Missing state field: {field}")
    return data


def next_milestone(path):
    content = path.read_text()
    match = re.search(r"^## Milestone Progress\s*$([\s\S]*?)(?=^## |\Z)", content, re.M)
    if not match:
        raise RuntimeError("Milestone Progress table missing")
    lines = [x.strip() for x in match.group(1).splitlines() if x.strip().startswith("|")]
    if len(lines) < 3 or [x.strip().lower() for x in lines[0].strip("|").split("|")] != ["milestone", "status"]:
        raise RuntimeError("Invalid progress table heading")
    rows = []
    for line in lines[2:]:
        parts = [x.strip() for x in line.strip("|").split("|")]
        if len(parts) != 2 or parts[1].lower() not in {"complete", "in progress", "not started"}:
            raise RuntimeError(f"Unrecognized milestone row: {line}")
        rows.append((parts[0], parts[1].lower()))
    if not rows or len({r[0] for r in rows}) != len(rows):
        raise RuntimeError("Missing or duplicate milestones")
    incomplete = [(i, name, status) for i, (name, status) in enumerate(rows) if status != "complete"]
    if not incomplete:
        return None
    first = incomplete[0]
    if any(status == "complete" for _, status in rows[first[0]+1:]):
        raise RuntimeError("Milestones completed out of order")
    return f"Milestone {first[1]}", first[2]


def check_clean(project):
    return not bool(git(project, "status", "--porcelain", "--untracked-files=all"))


def check_expected_files(project):
    files = git(project, "status", "--porcelain", "--untracked-files=all").splitlines()
    paths = set()
    for line in files:
        # Standard porcelain v1; rename/copy is deliberately rejected in this prototype.
        if line[:2].strip() in {"R", "C"} or " -> " in line:
            raise RuntimeError("Rename/copy detected; manual review required")
        paths.add(line[3:].strip('"'))
    extras = paths - ALLOWED_FILES
    if extras:
        raise RuntimeError(f"Changes outside prototype allowlist: {sorted(extras)}")
    return paths


def verify(project, cfg, schema, state):
    report_path = Path(cfg["runner"]["state_root"]) / state.get("last_result", f"{PROJECT_NAME}-result.json")
    if not report_path.is_file():
        raise RuntimeError(f"Missing completion report: {report_path}")
    report = json.loads(report_path.read_text())
    Draft7Validator(schema).validate(report)
    if (report["milestone"] != state["milestone"] or report["status"] != "complete"
            or not report["checks_passed"] or not report["acceptance_criteria_met"] or report["blockers"]):
        raise RuntimeError("Milestone report does not confirm expected completion")
    files = check_expected_files(project)
    if not files:
        raise RuntimeError("No milestone changes to verify")
    python = project / ".venv/bin/python"
    if not python.is_file():
        raise RuntimeError("Missing project .venv/bin/python")
    print("Independent pytest verification:", flush=True)
    cmd([str(python), "-m", "pytest", "-q"], project, capture=False)
    # Temporary index includes untracked files without modifying the user's real index.
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
        cmd(["git", "read-tree", "HEAD"], project, env=env)
        cmd(["git", "add", "-A"], project, env=env)
        cmd(["git", "diff", "--cached", "--check"], project, env=env)
    print(f"Verified milestone {state['milestone']} ({len(files)} changed files).")


def codex_run(project, cfg, schema, state):
    # Agent must not receive GitHub credentials; the sandbox disallows network by default.
    output = Path(cfg["runner"]["state_root"]) / f"{PROJECT_NAME}-result.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        output.unlink()
    state["last_result"] = output.name
    save_state(cfg, state)
    skill = ROOT / "skills/milestone-runner/SKILL.md"
    prompt = (f"Implement or resume only {state['milestone']} in ROADMAP.md. "
              f"Read and follow the workflow at {skill} and relevant AGENTS.md. "
              "Preserve existing work. Use .venv/bin/python -m pytest -q. "
              "Do not commit, push, merge, deploy, change secrets, or perform destructive operations. "
              "Update README/ROADMAP and handoff. Return the required JSON completion report.")
    command = [cfg["codex"].get("command", "codex"), "exec", "--sandbox", "workspace-write",
               "--output-schema", str(ROOT / "schemas/milestone-result.json"),
               "--output-last-message", str(output), prompt]
    print(f"Starting Codex: {state['milestone']}", flush=True)
    cmd(command, project, capture=False)
    if not output.exists():
        raise RuntimeError("Codex did not write structured output")
    report = json.loads(output.read_text())
    Draft7Validator(schema).validate(report)
    if report["milestone"] != state["milestone"]:
        raise RuntimeError("Codex returned a different milestone")
    if report["status"] != "complete":
        state["status"] = "blocked"
        save_state(cfg, state)
        print(json.dumps(report, indent=2))
        return False
    state["status"] = "awaiting_commit"
    save_state(cfg, state)
    return True


def commit_or_recover(project, cfg, state):
    base = git_sha(project, state["base_commit"])
    head = git_sha(project)
    if head != base:
        if git(project, "rev-list", "--count", f"{base}..HEAD") != "1" or not check_clean(project):
            raise RuntimeError("Unexpected history after partial commit; inspect manually")
        if cmd(["git", "merge-base", "--is-ancestor", base, head], project) != "":
            raise RuntimeError("Unexpected ancestry")
        state.update(status="committed", commit_sha=head)
        save_state(cfg, state)
        return
    check_expected_files(project)
    if git(project, "diff", "--cached", "--name-only"):
        raise RuntimeError("Unexpected pre-staged changes")
    git(project, "add", "-A")
    staged = set(git(project, "diff", "--cached", "--name-only").splitlines())
    if not staged or staged - ALLOWED_FILES:
        raise RuntimeError("Invalid staged file set; review manually")
    git(project, "diff", "--cached", "--check")
    # Respect user's configured git identity; fail if absent rather than substituting one.
    git(project, "var", "GIT_AUTHOR_IDENT")
    git(project, "commit", "-m", f"Complete {state['milestone']}")
    if not check_clean(project):
        raise RuntimeError("Uncommitted work remains after commit")
    state.update(status="committed", commit_sha=git_sha(project))
    save_state(cfg, state)
    print(f"Committed: {state['commit_sha']}")


def push_and_pr(project, cfg, state):
    sha = state.get("commit_sha") or git_sha(project)
    if sha != git_sha(project):
        raise RuntimeError("Committed SHA does not match HEAD")
    # Push is idempotent; never force push or overwrite a remote branch.
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    cmd(["git", "push", "-u", "origin", state["branch"]], project, env=env, capture=False)
    # Find an existing PR by head; only create when none exists.
    prs = json.loads(gh(project, "pr", "list", "--head", state["branch"], "--state", "open",
                       "--json", "number,headRefOid,baseRefName"))
    if len(prs) > 1:
        raise RuntimeError("Multiple open PRs for the milestone branch")
    if not prs:
        gh(project, "pr", "create", "--base", "main", "--head", state["branch"],
           "--title", state["milestone"], "--body", "Automated milestone implementation; verified locally.")
        prs = json.loads(gh(project, "pr", "list", "--head", state["branch"], "--state", "open",
                           "--json", "number,headRefOid,baseRefName"))
    if len(prs) != 1 or prs[0]["headRefOid"] != sha or prs[0]["baseRefName"] != "main":
        raise RuntimeError("PR does not match expected head and base")
    state.update(status="awaiting_ci", pr_number=prs[0]["number"])
    save_state(cfg, state)
    print(f"PR #{state['pr_number']} created/found; awaiting CI")


def github_gate(project, state):
    """Return (repository, check_state). Pending states are never mergeable."""
    pr_num = state.get("pr_number")
    if not isinstance(pr_num, int):
        raise RuntimeError("PR number missing")
    pr = json.loads(gh(project, "pr", "view", str(pr_num), "--json",
                       "state,headRefOid,baseRefName,mergeable,mergeStateStatus,url"))
    if pr["state"] != "OPEN" or pr["headRefOid"] != state["commit_sha"] or pr["baseRefName"] != "main":
        raise RuntimeError("PR changed since push; refusing merge")
    repo = json.loads(gh(project, "repo", "view", "--json", "nameWithOwner"))["nameWithOwner"]
    checks = json.loads(gh(project, "api", f"repos/{repo}/commits/{state['commit_sha']}/check-runs?per_page=100"))
    if checks.get("total_count", 0) > len(checks.get("check_runs", [])):
        raise RuntimeError("Check results paginated; cannot establish complete gate")
    hits = [c for c in checks.get("check_runs", []) if c["name"] == CHECK_NAME
            and c.get("head_sha") == state["commit_sha"]
            and c.get("app", {}).get("slug") == "github-actions"]
    if len(hits) > 1:
        raise RuntimeError("Ambiguous CI checks on exact PR head")
    if not hits:
        return repo, "pending"  # GitHub may not have created the run yet.
    check = hits[0]
    if check["status"] != "completed":
        return repo, "pending"
    if check["conclusion"] != "success":
        raise RuntimeError(f"Required exact-commit CI failed: {check['conclusion']}")
    if pr["mergeable"] == "UNKNOWN" or pr["mergeStateStatus"] == "UNKNOWN":
        return repo, "pending"  # GitHub is still calculating mergeability.
    if pr["mergeable"] != "MERGEABLE" or pr["mergeStateStatus"] != "CLEAN":
        raise RuntimeError(f"PR not cleanly mergeable: {pr['mergeStateStatus']}")
    return repo, "ready"


def wait_for_ci(project, cfg, state):
    """Poll exact-commit checks up to a bounded timeout, retaining awaiting_ci on failure."""
    timeout = cfg["execution"].get("ci_timeout_seconds", 600)
    interval = cfg["execution"].get("ci_poll_seconds", 10)
    deadline = time.monotonic() + timeout
    while True:
        repo, check_state = github_gate(project, state)
        if check_state == "ready":
            print(f"CI and mergeability verified for {state['commit_sha'][:12]}.", flush=True)
            return repo
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError(
                f"CI/mergeability did not become ready within {timeout}s; "
                "state retained as awaiting_ci. Rerun later."
            )
        print(f"CI/mergeability pending; rechecking in {min(interval, remaining):.0f}s...", flush=True)
        time.sleep(min(interval, remaining))


def complete_merge(project, cfg, state):
    repo = wait_for_ci(project, cfg, state)
    pr_num = state["pr_number"]
    # GitHub enforces exact head SHA in merge endpoint.
    state["status"] = "awaiting_merge"
    save_state(cfg, state)
    gh(project, "api", "--method", "PUT", f"repos/{repo}/pulls/{pr_num}/merge",
       "-f", "merge_method=squash", "-f", f"sha={state['commit_sha']}",
       "-f", f"commit_title={state['milestone']}")
    finish_merged(project, cfg, state)


def finish_merged(project, cfg, state):
    pr = json.loads(gh(project, "pr", "view", str(state["pr_number"]),
                       "--json", "state,mergeCommit"))
    if pr["state"] != "MERGED":
        raise RuntimeError("Merge not confirmed")
    merge_commit = pr.get("mergeCommit")
    if not isinstance(merge_commit, dict) or not merge_commit.get("oid"):
        raise RuntimeError("Merged PR has no merge commit")
    if not check_clean(project):
        raise RuntimeError("Local worktree not clean; cannot switch main")
    git(project, "switch", "main")
    git(project, "pull", "--ff-only", "origin", "main")
    if git_sha(project) != merge_commit["oid"]:
        raise RuntimeError("Local main does not match merge commit")
    # The state is no longer needed after the merge is confirmed and main synced.
    # A retry after an interrupted cleanup must not fail on a missing file.
    state_file(cfg).unlink(missing_ok=True)
    print("Merged, synchronized main, and cleared completed state.")


def run_once(project, cfg, schema):
    state = load_state(cfg)
    branch = git(project, "branch", "--show-current")
    if state is None:
        if branch != "main" or not check_clean(project):
            raise RuntimeError("New execution requires clean main")
        item = next_milestone(project / "ROADMAP.md")
        if item is None:
            print("All milestones complete.")
            return False
        milestone, _ = item
        slug = re.sub(r"[^a-z0-9]+", "-", milestone.lower()).strip("-")
        target = f"agent/{slug.replace('milestone-', '', 1)}"
        if git(project, "branch", "--list", target):
            raise RuntimeError(f"Branch already exists without recorded state: {target}")
        base = git_sha(project)
        git(project, "switch", "-c", target)
        state = dict(project=PROJECT_NAME, milestone=milestone, branch=target,
                     base_commit=base, status="running", last_result=f"{PROJECT_NAME}-result.json")
        save_state(cfg, state)
    else:
        if state["status"] == "awaiting_merge":
            finish_merged(project, cfg, state)
            return True
        if branch != state["branch"]:
            raise RuntimeError("Current Git branch differs from saved execution")
        if git_sha(project, "main") != git_sha(project, state["base_commit"]):
            raise RuntimeError("Main moved since milestone began; manual reconciliation required")
    print(f"Milestone: {state['milestone']} | State: {state['status']}", flush=True)
    if state["status"] in {"running", "blocked"}:
        # A prior crash can leave changes. Codex is explicitly instructed to resume them.
        state["status"] = "running"
        save_state(cfg, state)
        if not codex_run(project, cfg, schema, state):
            return False
    if state["status"] == "awaiting_commit":
        # Important: recovery after commit must happen before rerunning a verifier that expects changed files.
        if git_sha(project) != git_sha(project, state["base_commit"]):
            if not cfg["git"]["auto_commit"]:
                print("Commit already exists, but auto_commit is disabled; manual review")
                return False
            commit_or_recover(project, cfg, state)
        else:
            verify(project, cfg, schema, state)
            if not cfg["git"]["auto_commit"]:
                print("Milestone verified; waiting for auto_commit or manual action.")
                return False
            commit_or_recover(project, cfg, state)
    if state["status"] == "committed":
        if not cfg["git"]["auto_push"]:
            print("Milestone committed; auto_push is disabled.")
            return False
        push_and_pr(project, cfg, state)
    if state["status"] == "awaiting_ci":
        if not cfg["git"]["auto_merge"]:
            print("PR created; auto_merge is disabled.")
            return False
        complete_merge(project, cfg, state)
        # complete_merge() already invokes finish_merged() and clears state.
        # Do not fall through and attempt the same cleanup again.
        return True
    if state["status"] == "awaiting_merge":
        finish_merged(project, cfg, state)
        return True
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=PROJECT_NAME, choices=[PROJECT_NAME])
    args = parser.parse_args()
    cfg, schema = load_config()
    project = Path(cfg["runner"]["workspace_root"]) / args.project
    if not (project / ".git").exists():
        raise RuntimeError("Expected existing Git repository")
    with open(Path(cfg["runner"]["state_root"]) / ".orchestrator.lock", "a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        limit = int(cfg["execution"].get("max_milestones_per_run", 1))
        if limit < 1:
            raise ValueError("max_milestones_per_run must be positive")
        for _ in range(limit):
            if not run_once(project, cfg, schema):
                break


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"STOPPED: {exc}", file=sys.stderr)
        sys.exit(1)
