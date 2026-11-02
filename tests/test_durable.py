"""Persistence primitives retained after retirement of the old state framework."""

import os
import stat
import unittest
from unittest.mock import patch

from agentic_runner.durable import DurableIO, StateError, decode_json
from tests.support.isolation import DisposableRoot


class DurableTests(unittest.TestCase):
    def setUp(self):
        self.root = DisposableRoot()
        self.addCleanup(self.root.close)
        self.area = self.root.mkdir("private")
        self.path = self.root.write_text(self.area / "checkpoint.json", '{"old": true}\n')
        self.io = DurableIO(self.root.require)

    def test_partial_write_preserves_previous_checkpoint(self):
        def partial(descriptor, data):
            os.write(descriptor, data[:3])
            raise OSError("interrupted write")
        with patch.object(DurableIO, "write_all", side_effect=partial):
            with self.assertRaisesRegex(OSError, "interrupted"):
                self.io.atomic(self.path, b'{"new": true}\n')
        self.assertEqual(decode_json(self.io.read(self.path), self.path), {"old": True})
        self.io.atomic(self.path, b'{"new": true}\n')
        self.assertEqual(decode_json(self.io.read(self.path), self.path), {"new": True})

    def test_atomic_write_private_mode_and_sync_order(self):
        events = []
        self.io.checkpoint = events.append
        self.io.atomic(self.path, b'{}\n')
        self.assertEqual(events, ["atomic.opened", "atomic.written", "atomic.file_synced", "atomic.replaced", "atomic.directory_synced"])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)

    def test_duplicate_nonfinite_and_truncated_json_are_rejected(self):
        for value in (b'{"key":1,"key":2}', b'{"key":NaN}', b'{"key":Infinity}', b'{', b'\xff'):
            with self.subTest(value=value), self.assertRaises(StateError):
                decode_json(value, self.path)

    def test_aliased_checkpoint_and_boundary_escape_are_rejected(self):
        alias = self.root.require(self.area / "alias")
        os.link(self.path, alias)
        with self.assertRaises(StateError):
            self.io.read(alias)
        with self.assertRaises(ValueError):
            self.io.read(self.root.path / "../outside")
