"""Optional cached-Node fixture provisioning; never installs host-wide tools."""

import hashlib
import json
import os
import shlex
import subprocess
import uuid

from tests.support.fixtures import FixtureFactory


NODE_IMAGE = "node@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da"


def fixture_node(root, project):
    project = root.require(project)
    tools = root.mkdir("node-tools")
    binary = root.require(project / ".venv/bin/node")
    root.mkdir(binary.parent)
    environment = FixtureFactory(root).environment()
    docker = ["/usr/bin/docker", "--host", "unix:///var/run/docker.sock"]
    def run(args):
        root.require(project)
        return subprocess.run([*docker, *args], cwd=root.require(project), env=environment,
                              capture_output=True, text=True, check=True, timeout=60).stdout
    info = json.loads(run(["image", "inspect", NODE_IMAGE]))[0]
    assert NODE_IMAGE in info["RepoDigests"]
    name = "adr-m4-node-" + uuid.uuid4().hex
    try:
        run(["create", "--name", name, "--pull", "never", "--network", "none", "--read-only", "--cap-drop", "ALL",
             "--security-opt", "no-new-privileges:true", "--user", f"{os.getuid()}:{os.getgid()}",
             "--label", "org.agentic-runner.native-node=" + name, "--entrypoint", "/bin/true", NODE_IMAGE])
        run(["cp", name + ":/usr/local/bin/node", str(root.require(binary))])
        run(["cp", name + ":/usr/local/lib/node_modules/npm", str(root.require(tools / "npm"))])
    finally:
        # It was never started; remove only this exact uniquely labeled fixture.
        inspected = subprocess.run([*docker, "inspect", "--format", '{{index .Config.Labels "org.agentic-runner.native-node"}}', name],
                                   cwd=root.require(project), env=environment, capture_output=True, text=True, timeout=30)
        if inspected.returncode == 0:
            assert inspected.stdout.strip() == name
            run(["rm", name])
    wrapper = root.write_text(project / ".venv/bin/npm", "#!/bin/sh\nexec " + shlex.quote(str(binary)) + " " +
                             shlex.quote(str(root.require(tools / "npm/bin/npm-cli.js"))) + ' "$@"\n')
    wrapper.chmod(0o700)
    return {"source": NODE_IMAGE, "node_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
