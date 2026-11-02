"""Retained bounded native subprocess checks using owned fixtures."""

import sys
import threading
import unittest

from agentic_runner.supervisor import supervise
from tests.support.fixtures import FixtureFactory
from tests.support.isolation import DisposableRoot


class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.cwd = self.root.mkdir("worker")
        self.environment = FixtureFactory(self.root).environment()

    def run_python(self, source, **kwargs):
        return supervise([sys.executable, "-I", "-c", source], cwd=self.root.require(self.cwd), env=self.environment, **kwargs)

    def test_captures_both_streams_and_passes_bounded_stdin(self):
        result = self.run_python("import sys; print(sys.stdin.read()); print('diagnostic', file=sys.stderr)", input_bytes=b"prompt")
        self.assertEqual(result.stdout, b"prompt\n")
        self.assertEqual(result.stderr, b"diagnostic\n")
        self.assertIsNone(result.stopped)

    def test_timeout_and_process_group_descendant_cleanup(self):
        result = self.run_python("import os, time; p=os.fork(); print(p, flush=True); time.sleep(30)", timeout=0.2)
        self.assertEqual(result.stopped, "timeout")
        # A descendant must not keep stdout/stderr open for 30 seconds.
        self.assertLess(len(result.stdout), 100)

    def test_cancellation_and_output_limit(self):
        cancel = threading.Event()
        cancel.set()
        self.assertEqual(self.run_python("while True: pass", cancel=cancel).stopped, "cancelled")
        result = self.run_python("import os;\nwhile True: os.write(1, b'x'*65536)", limit=8192)
        self.assertEqual(result.stopped, "output_limit")
        self.assertEqual(len(result.stdout) + len(result.stderr), 8192)

    def test_unread_stdin_is_bounded_by_timeout(self):
        result = self.run_python("import time; time.sleep(30)", timeout=0.2, input_bytes=b"x" * 65536)
        self.assertEqual(result.stopped, "timeout")
