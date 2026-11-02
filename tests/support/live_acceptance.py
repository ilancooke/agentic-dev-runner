"""Explicit opt-in acceptance. Never loaded by unittest discovery.

Real Codex uses the existing account with a generated local repository. GitHub
acceptance creates a uniquely named private repository and deletes only that
observed creation. These are separate checks; neither implies the other passed.
"""

import argparse
import json
import sys
import uuid

from agentic_runner.git_boundary import GitBoundary, environment
from agentic_runner.headless import MODEL, generate
from agentic_runner.project import DOCUMENTS, Project, RunnerError, check_process, require
from agentic_runner.runner import Loop
from agentic_runner.setup import Setup
from agentic_runner.supervisor import supervise
from tests import test_runner as fixtures
from tests.support.fixtures import FixtureFactory
from tests.support.isolation import DisposableRoot
from tests.support.projects import ROADMAP


LIVE_ROADMAP = """# Selective live Codex acceptance

## Milestone Progress

| Milestone | Status |
| --- | --- |
| M1 | not started |

## M1 — Write an answer

### Deliverables

Create answer.txt containing exactly 42 followed by a newline.
Update PROGRESS.md with the check result. Use no Git or GitHub operations.

### Acceptance criteria

The configured Python verification confirms answer.txt is exactly 42 plus newline.
"""


def real_codex():
    case = fixtures.RunnerTests()
    case.setUp()
    try:
        case.root.write_text(case.repo / "ROADMAP.md", LIVE_ROADMAP)
        case.local_git("add", "ROADMAP.md")
        case.local_git("commit", "-m", "Prepare generated live acceptance")
        case.local_git("push", str(case.remote), "HEAD:refs/heads/development")
        command = [sys.executable, "-c", "from pathlib import Path; assert Path('answer.txt').read_bytes() == b'42\\n'"]
        config = case.filename.read_text().split("verification =")[0]
        case.root.write_text(case.filename, config + "verification = " + json.dumps([command]) + "\n")
        case.project = Project.load(case.filename)
        sessions = []
        def agent(project, milestone, documents, env):
            case.root.require(project.repository)
            sessions.append(milestone.id)
            live_env = environment()
            live_env["TMPDIR"] = str(case.root.mkdir("codex-tmp"))
            return generate(project, milestone, documents, live_env)
        loop = case.loop(live_agent=agent)
        loop.run()
        loop.run()  # A complete rerun must not consume another model call.
        case.assert_main_untouched()
        require(sessions == ["M1"], "Unexpected live session count.")
        return {"check": "real-codex-local-publication", "status": "passed", "model": MODEL,
                "effort": "high", "sandbox": "disabled", "sessions": sessions,
                "main_unchanged": True, "publication": "real local bare remote; fake GitHub protection",
                "commit": case.checkpoint()["commit"]}
    finally:
        case.doCleanups()


def github(owner):
    with DisposableRoot() as root:
        repo = FixtureFactory(root).repository()
        env = environment()
        name = f"{owner}/agentic-runner-acceptance-{uuid.uuid4().hex}"
        created = False
        evidence = {"check": "protected-github", "repository": name, "status": "failed"}

        def process(argv, **kwargs):
            nonlocal created
            root.require(kwargs["cwd"])
            result = supervise(argv, **kwargs)
            if list(argv[:3]) == ["gh", "repo", "create"] and result.returncode == 0 and not result.stopped:
                created = True
            return result

        def call(argv):
            result = process(argv, cwd=repo, env=env, timeout=60)
            check_process(result, "Live acceptance command failed")
            return result.stdout.decode().strip()

        try:
            login = json.loads(call(["gh", "api", "--hostname", "github.com", "user"]))["login"]
            require(login.lower() == owner.lower(), "Use the authenticated user's login as --github-owner.")
            # Git's global config stays disabled. Use the existing gh account only
            # through this checkout-local credential helper; never copy its token.
            call(["git", "config", "--local", "credential.helper", "!gh auth git-credential"])
            for doc in DOCUMENTS:
                root.write_text(repo / doc, ROADMAP.replace("| M1 | complete |", "| M1 | not started |")
                                if doc == "ROADMAP.md" else f"# {doc}\nGenerated disposable acceptance.\n")
            config = root.write_text("project.toml", f'''[project]
name = "{name}"
repository = "{repo}"
development_branch = "development"
verification = [["{sys.executable}", "-c", "from pathlib import Path; assert Path('feature-M1.txt').is_file()"]]
''')
            project = Project.load(config)
            Setup(project, process=process, env=env).run()
            git = GitBoundary(project, process=process, env=env)
            main = git.git("rev-parse", "refs/heads/main")
            blocked, sessions = True, []
            def agent(project, milestone, documents, env):
                sessions.append(milestone.id)
                root.write_text(repo / f"feature-{milestone.id}.txt", "generated acceptance\n")
                root.write_text(repo / "PROGRESS.md", documents["PROGRESS.md"] + f"\nWorked on {milestone.id}.\n")
                stop = milestone.id == "M2" and blocked
                return {"milestone": milestone.id, "status": "blocked" if stop else "success",
                        "summary": "Generated acceptance", "blockers": ["manual continuation exercise"] if stop else [],
                        "commit_message": f"Implement {milestone.id}"}
            try:
                Loop(project, git=git, agent=agent).run()
            except RunnerError as exc:
                require("Codex blocked" in str(exc), str(exc))
            else:
                raise RunnerError("Expected the second milestone to block.")
            blocked = False
            Loop(project, git=git, agent=agent).run()
            Loop(project, git=git, agent=agent).run()
            require(sessions == ["M1", "M2", "M2"], "Unexpected acceptance session order.")
            require(git.git("rev-parse", "refs/heads/main") == main and git.remote_ref("main") == main,
                    "Main changed during live acceptance.")
            require(git.head() == git.remote_ref("development"), "Dev was not published.")
            evidence.update(status="passed", sessions=sessions, main_unchanged=True,
                            protection="real GitHub read/write/read-back", agent="fake", commit=git.head())
        except (Exception, KeyboardInterrupt) as exc:
            evidence["issue"] = str(exc) or type(exc).__name__
        finally:
            evidence["created"] = created
            if created:
                try:
                    call(["gh", "api", "--hostname", "github.com", "--method", "DELETE", f"repos/{name}"])
                    evidence["cleanup"] = "deleted the generated repository"
                except (Exception, KeyboardInterrupt) as exc:
                    evidence["cleanup"] = "manual deletion required: " + (str(exc) or type(exc).__name__)
                    if hasattr(exc, "process"):
                        # The generated repository's deletion endpoint returns no secrets.
                        evidence["cleanup_detail"] = exc.process.stderr.decode(errors="replace").strip()
            else:
                evidence["cleanup"] = "no confirmed creation to delete"
        return evidence


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--real-codex", action="store_true", help="One paid/account-backed Codex session; local Git only")
    choice.add_argument("--github-owner", help="Create/delete a generated private GitHub repo under this authenticated login")
    args = parser.parse_args()
    try:
        evidence = real_codex() if args.real_codex else github(args.github_owner)
    except (Exception, KeyboardInterrupt) as exc:
        evidence = {"check": "real-codex-local-publication", "status": "failed", "issue": str(exc) or type(exc).__name__}
        if hasattr(exc, "report") and isinstance(exc.report, dict):
            message = exc.report.get("commit_message", "")
            evidence["report_diagnostic"] = {"status": exc.report.get("status"),
                                             "blocker_count": len(exc.report.get("blockers", [])),
                                             "commit_message_length": len(message),
                                             "commit_message_has_controls": any(ord(c) < 32 for c in message)}
    print(json.dumps(evidence, indent=2))
    return int(evidence["status"] != "passed" or "manual deletion required" in evidence.get("cleanup", ""))


if __name__ == "__main__":
    raise SystemExit(main())
