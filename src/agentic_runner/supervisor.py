"""Bounded subprocess capture, cancellation and whole-process-group cleanup.

The runner supplies literal argv for trusted native project execution.
Raw captures stay in memory and must never be sent to public logs.
"""

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: bytes
    stderr: bytes
    stopped: str | None = None


def supervise(argv, *, cwd, env, timeout=60, limit=4 * 1024 * 1024, cancel=None, input_bytes=None):
    if not argv or not all(isinstance(a, str) and a and "\0" not in a for a in argv):
        raise ValueError("Expected an explicit argument vector")
    if timeout <= 0 or limit <= 0 or input_bytes is not None and len(input_bytes) > 65536:
        raise ValueError("Invalid supervision limits")
    process = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, close_fds=True)
    selector = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    stopped = None
    deadline = time.monotonic() + timeout
    killed_at = None

    def terminate(sig):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass

    try:
        for name in buffers:
            stream = getattr(process, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        if input_bytes is not None:
            # Small bounded prompts; pipe writes are also supervised (a child may not read).
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        pending = memoryview(input_bytes or b"")
        while selector.get_map() or process.poll() is None:
            now = time.monotonic()
            reason = "cancelled" if cancel is not None and cancel.is_set() else "timeout" if now >= deadline else None
            if reason and stopped is None:
                stopped = reason
                terminate(signal.SIGTERM)
                killed_at = now
            if killed_at is not None and now - killed_at >= 0.25:
                terminate(signal.SIGKILL)
                # A hostile detached descendant can hold pipes open. Never wait on it forever.
                if now - killed_at >= 1:
                    break
            for key, _ in selector.select(0.05):
                if key.data == "stdin":
                    try:
                        count = os.write(key.fd, pending[:4096]) if pending else 0
                        pending = pending[count:]
                    except BrokenPipeError:
                        pending = memoryview(b"")
                    if not pending:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                size = sum(len(b) for b in buffers.values())
                buffers[key.data].extend(chunk[:max(0, limit - size)])
                if size + len(chunk) > limit and stopped is None:
                    stopped = "output_limit"
                    terminate(signal.SIGTERM)
                    killed_at = time.monotonic()
        terminate(signal.SIGKILL)  # Also reap descendants left behind by a successful parent.
        process.wait(timeout=2)
        return ProcessResult(process.returncode, bytes(buffers["stdout"]), bytes(buffers["stderr"]), stopped)
    finally:
        terminate(signal.SIGKILL)
        process.wait(timeout=2)
        selector.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
