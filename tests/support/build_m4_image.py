"""Explicit trusted image build; not imported/run by the default unit suite."""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from tests.support.isolation import DisposableRoot


def main():
    repository = Path(__file__).resolve().parents[2]
    binary = Path("/home/ilan/.local/bin/codex").resolve(strict=True)
    with DisposableRoot() as root:
        context = root.mkdir("image")
        for source, name in ((repository / "containers/m4/Dockerfile", "Dockerfile"), (binary, "codex")):
            shutil.copyfile(source, root.require(context / name))
        root.require(context / "codex").chmod(0o755)
        print("Codex binary SHA-256:", hashlib.sha256(binary.read_bytes()).hexdigest(), flush=True)
        result = subprocess.run(["/usr/bin/docker", "--host", "unix:///var/run/docker.sock", "build", "--tag", "agentic-runner-m4:local", str(root.require(context))],
                                cwd=root.require(context), env={"PATH": os.defpath, "HOME": str(root.mkdir("home"))}, check=False)
        return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
