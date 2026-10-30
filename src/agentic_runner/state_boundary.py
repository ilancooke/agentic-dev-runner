"""Separate test/operational namespaces and canonical cooperating-process locks."""

import fcntl
import os
import stat
from contextlib import contextmanager
from pathlib import Path

from .durable import StateError


PROTECTED = (Path("/home/ilan/agentic-workspaces/milestone-test"), Path("/home/ilan/agentic-runner-data"))


def overlaps(left, right):
    return left.is_relative_to(right) or right.is_relative_to(left)


class StateBoundary:
    def __init__(self, path: Path, *, disposable=None):
        self.path = Path(path).resolve()
        self.disposable = disposable
        self.environment = "test" if disposable is not None else "operational"
        self._identity = None
        if any(overlaps(self.path, p.resolve()) for p in PROTECTED):
            raise StateError("state.protected", "Use a new state namespace outside protected reference/legacy roots.", str(path))
        if disposable is not None:
            disposable.require(self.path)
            if disposable.path.parent != Path("/tmp").resolve() or not disposable.path.name.startswith("agentic-runner-test-"):
                raise StateError("state.test_root", "Tests require a live owned DisposableRoot capability.", str(path))
        elif overlaps(self.path, Path("/tmp").resolve()) or any(part.startswith("agentic-runner-test-") for part in self.path.parts):
            raise StateError("state.environment", "Operational state cannot use temporary/disposable roots.", str(path))
        if not self.path.parent.is_dir():
            raise StateError("state.parent", "Create/select an existing dedicated parent for the new state namespace.", str(path))

    @classmethod
    def for_test(cls, disposable, path):
        return cls(path, disposable=disposable)

    def guard(self, path):
        path = Path(path)
        if self.disposable is not None:
            # The root itself can be fsynced; it cannot be adopted or replaced.
            self.disposable.require(self.disposable.path / ".boundary-probe")
            if path != self.disposable.path:
                self.disposable.require(path)
        if path != self.path.parent and not path.is_relative_to(self.path):
            raise StateError("state.escape", "Mutation escaped the configured state namespace.", str(path))
        resolved = path.resolve()
        if resolved != path:
            raise StateError("state.alias", "State entries cannot contain symlinks or unresolved traversal.", str(path))
        if self._identity is not None:
            info = self.path.stat()
            if (info.st_dev, info.st_ino) != self._identity:
                raise StateError("state.replaced", "State namespace directory was replaced.", str(self.path))

    def bind_inode(self):
        info = self.path.stat()
        if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise StateError("state.permissions", "State namespace must be owned by this user with mode 0700.", str(self.path))
        self._identity = (info.st_dev, info.st_ino)

    def check_repository(self, repository):
        for path in (repository.root, repository.common_dir, repository.git_dir):
            if self.disposable is not None:
                self.disposable.require(path)
            if any(overlaps(path, p.resolve()) for p in PROTECTED):
                raise StateError("state.protected", "Reference/legacy roots cannot be registered for runner mutation.", str(path))
            if overlaps(self.path, path):
                raise StateError("state.overlap", "Keep state outside the checkout and Git metadata, in a separate namespace.", str(self.path))
            if self.environment == "operational" and (path.is_relative_to(Path("/tmp").resolve()) or any(p.startswith("agentic-runner-test-") for p in path.parts)):
                raise StateError("state.environment", "Operational state cannot enroll disposable repositories.", str(path))


@contextmanager
def directory_lock(path: Path, guard):
    """flock on the directory inode: no repository lock file or Git mutation."""
    guard(path)
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StateError("state.locked", "Another runner holds this repository/namespace lock; retry after it releases ownership.", str(path)) from exc
        yield
    finally:
        os.close(descriptor)
