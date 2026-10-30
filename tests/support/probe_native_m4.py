"""Authorized disposable native-M4 probe. No publication or host-policy changes.

Default: no account usage. --real-codex uses the existing user's Codex auth and
creates at most a fresh session plus one exact-ID resume, with fixed model/effort.
--docker builds/runs/removes only a uniquely labeled generated test image.
"""

import argparse
import json
import os
import pwd
import uuid
from pathlib import Path

from agentic_runner.approval import RunnerPolicy
from agentic_runner.native_codex import NativeCodexAdapter
from agentic_runner.native_execution import NativeExecutor, NativePolicy
from agentic_runner.run_state import Phase
from agentic_runner.state import open_store
from agentic_runner.state_boundary import StateBoundary
from tests.support.isolation import DisposableRoot
from tests.support.projects import git_fixture, make_project


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--real-codex", action="store_true")
    parser.add_argument("--docker", action="store_true")
    args = parser.parse_args()
    with DisposableRoot() as root:
        project = make_project(root)
        outside = root.mkdir("outside") / "allowed-vm-write"
        fake_auth = root.write_text("fake-auth", "FAKE_DEVELOPMENT_AUTH_NEVER_LOG")
        source = f'''import pathlib, sys
project = pathlib.Path({str(project)!r})
outside = pathlib.Path({str(outside)!r})
assert pathlib.Path({str(fake_auth)!r}).read_text() == "FAKE_DEVELOPMENT_AUTH_NEVER_LOG"
assert pathlib.Path.cwd() == project
assert sys.argv[1] in ["fresh", "resumed", "offline"]
outside.write_text("M4_VM_USER_ACCESS_OK")
(project / ("probe-" + sys.argv[1])).write_text("M4_NATIVE_OK")
print("M4_NATIVE_BOUNDARY_OK")
'''
        root.write_text(project / "native_probe.py", source)
        git_fixture(root, project, "add", "--", "native_probe.py")
        git_fixture(root, project, "commit", "--no-gpg-sign", "-m", "Generated native VM probe")
        if args.real_codex:
            home = Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
            codex_home = home / ".codex"
        else:
            home = root.mkdir("home")
            codex_home = root.mkdir("home/.codex")
        policy = NativePolicy(str(home), str(codex_home), timeout=180)
        executor = NativeExecutor(policy, use_account_home=args.real_codex)
        boundary = StateBoundary.for_test(root, root.path / "state")
        result = {"mode": "trusted-vm", "real_codex": args.real_codex, "docker": args.docker}
        with open_store(project, boundary, policy=RunnerPolicy(execution=policy.record())) as store:
            store.start_run()
            store.transition(1, Phase.IMPLEMENTING)
            adapter = NativeCodexAdapter(executor)
            result["capabilities"] = adapter.inspect(store)
            if args.real_codex:
                initial = adapter.generate(store, store.load()["revision"],
                    "Generated milestone M2 only. Execute `/usr/bin/python3 native_probe.py fresh` exactly once. "
                    "It checks checkout writes, full VM-user writes to another owned fixture directory and a readable fake auth fixture. "
                    "Do not edit any files or retry the command if it fails. Do not invoke GitHub, deployment, credentials, "
                    "other agents or change permissions/model/effort. Return the requested JSON schema: milestone M2, "
                    "status reported if the command passed, otherwise blocked, and a concise summary without file contents.")
                assert (project / "probe-fresh").read_text() == "M4_NATIVE_OK"
                resumed = adapter.generate(store, store.load()["revision"],
                    "Continue the same generated milestone M2. Execute `/usr/bin/python3 native_probe.py resumed` exactly once. "
                    "Do not edit files, retry, publish, change permissions or invoke other agents. Return the same JSON schema "
                    "with milestone M2, status reported if the command passed, otherwise blocked, and a concise summary.",
                    resume_id=initial["session_id"])
                assert (project / "probe-resumed").read_text() == "M4_NATIVE_OK"
                assert resumed["session_id"] == initial["session_id"]
                result["session_id"] = resumed["session_id"]
                result["usage"] = {"fresh": initial["usage"], "resumed": resumed["usage"]}
            else:
                probe = executor.execute(store, store.load()["revision"],
                    ["/usr/bin/python3", "native_probe.py", "offline"])
                assert probe.returncode == 0, probe.stderr.decode()
                assert (project / "probe-offline").read_text() == "M4_NATIVE_OK"
            assert outside.read_text() == "M4_VM_USER_ACCESS_OK"
            if args.docker:
                tag = "adr-m4-native-" + uuid.uuid4().hex + ":test"
                label = tag.split(":")[0]
                root.write_text(project / "app.py", "from pathlib import Path\nassert not Path('/var/run/docker.sock').exists()\nprint('M4_NATIVE_DOCKER_OK')\n")
                root.write_text(project / "Dockerfile", 'FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337\n'
                                'COPY app.py /app.py\nLABEL org.agentic-runner.native-probe="' + label + '"\nCMD ["python", "/app.py"]\n')
                docker = ["/usr/bin/docker", "--host", "unix:///var/run/docker.sock"]
                def run(arguments):
                    return executor.execute(store, store.load()["revision"], [*docker, *arguments])
                try:
                    built = run(["build", "--network", "none", "--tag", tag, "."])
                    assert built.returncode == 0, built.stderr.decode()
                    executed = run(["run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--security-opt", "no-new-privileges:true", "--user", str(os.getuid()) + ":" + str(os.getgid()), tag])
                    assert executed.returncode == 0 and executed.stdout == b"M4_NATIVE_DOCKER_OK\n", executed.stderr.decode()
                    result["docker_application"] = "build/run/test passed; no socket mount"
                finally:
                    # Exact generated tag and label only; never prune shared images.
                    inspected = executor.runner([*docker, "image", "inspect", "--format", '{{index .Config.Labels "org.agentic-runner.native-probe"}}', tag],
                                               cwd=root.require(project), env=executor.environment(project, executor.scratch(store)))
                    if inspected.returncode == 0:
                        assert inspected.stdout.strip().decode() == label
                        cleaned = executor.runner([*docker, "image", "rm", tag], cwd=root.require(project), env=executor.environment(project, executor.scratch(store)))
                        assert cleaned.returncode == 0
            result["revision"] = store.load()["revision"]
            result["phase"] = store.load()["phase"]
            assert store.load()["pending"] is None
            assert "FAKE_DEVELOPMENT_AUTH_NEVER_LOG" not in json.dumps(store.history())
        print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
