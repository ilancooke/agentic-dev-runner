"""Small POSIX persistence primitives with explicit failure-injection boundaries."""

import json
import os
import stat
import uuid
from pathlib import Path

from .diagnostics import DiscoveryError


class StateError(DiscoveryError):
    """Invalid, incompatible, or unavailable durable runner state."""


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def decode_json(data: bytes, source: Path):
    try:
        return json.loads(data, object_pairs_hook=unique_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    except (ValueError, UnicodeError) as exc:
        raise StateError("state.corrupt", "Invalid/truncated JSON; preserve the files and inspect recovery evidence.", str(source)) from exc


class DurableIO:
    """Every mutation is checked by the boundary guard; hooks are for trusted tests."""

    def __init__(self, guard, checkpoint=None):
        self.guard = guard
        self.checkpoint = checkpoint or (lambda name: None)

    def sync_dir(self, path: Path):
        self.guard(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def read(self, path: Path) -> bytes:
        self.guard(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
        try:
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise StateError("state.path", "State files must be regular, unaliased files.", str(path))
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                data = stream.read(64 * 1024 * 1024 + 1)
            if len(data) > 64 * 1024 * 1024:
                raise StateError("state.size", "State file exceeds the 64 MiB limit; retain it for offline archival.", str(path))
            return data
        finally:
            os.close(descriptor)

    def atomic(self, path: Path, data: bytes, *, temporary_directory: Path | None = None, mode=0o600):
        self.guard(path)
        temporary = (temporary_directory or path.parent) / f".tmp-{uuid.uuid4().hex}"
        self.guard(temporary)
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        try:
            self.checkpoint("atomic.opened")
            self.write_all(descriptor, data)
            os.fchmod(descriptor, mode)
            self.checkpoint("atomic.written")
            os.fsync(descriptor)
            self.checkpoint("atomic.file_synced")
        finally:
            os.close(descriptor)
        self.guard(temporary)
        self.guard(path)
        os.replace(temporary, path)
        self.checkpoint("atomic.replaced")
        self.sync_dir(path.parent)
        if temporary.parent != path.parent:
            self.sync_dir(temporary.parent)
        self.checkpoint("atomic.directory_synced")

    @staticmethod
    def write_all(descriptor, data):
        view = memoryview(data)
        while view:
            written = os.write(descriptor, view)
            if written <= 0:
                raise OSError("Short durable write")
            view = view[written:]
