"""Own disposable roots; validate canonical targets before fixture mutation.

This is a guard against test mistakes, not a sandbox for hostile project code.
Do not execute legacy scripts or arbitrary project commands through this harness.
"""

import tempfile
from pathlib import Path


PROTECTED_ROOTS = (
    Path("/home/ilan/agentic-workspaces/milestone-test"),
    Path("/home/ilan/agentic-runner-data"),
)


class IsolationError(ValueError):
    """The requested test target is outside the owned disposable boundary."""


def _overlaps(left: Path, right: Path) -> bool:
    return left.is_relative_to(right) or right.is_relative_to(left)


class DisposableRoot:
    """Create a new private root; existing paths cannot be enrolled as test roots."""

    def __init__(self) -> None:
        # Ignore TMPDIR and caller-selected paths. Never adopt an existing directory.
        parent = Path("/tmp").resolve(strict=True)
        self._protected = tuple(p.resolve() for p in PROTECTED_ROOTS)
        if any(_overlaps(parent, p) for p in self._protected):
            raise IsolationError("Temporary parent overlaps a protected root")
        self._temporary = tempfile.TemporaryDirectory(prefix="agentic-runner-test-", dir=parent)
        self.path = Path(self._temporary.name)
        stat = self.path.stat()
        self._identity = (stat.st_dev, stat.st_ino)
        self._closed = False

    def _check_root(self) -> None:
        if self._closed:
            raise IsolationError("Disposable root is closed")
        try:
            stat = self.path.lstat()
            if self.path.resolve(strict=True) != self.path or self.path.is_symlink():
                raise IsolationError("Disposable root was aliased or replaced")
            if (stat.st_dev, stat.st_ino) != self._identity or not self.path.is_dir():
                raise IsolationError("Disposable root was replaced")
        except OSError as exc:
            raise IsolationError("Disposable root is unavailable") from exc

    def require(self, target: str | Path) -> Path:
        """Return a canonical descendant, rejecting escapes before any mutation."""
        self._check_root()
        candidate = Path(target)
        if not candidate.is_absolute():
            candidate = self.path / candidate
        try:
            resolved = candidate.resolve()
        except (OSError, RuntimeError) as exc:
            raise IsolationError("Cannot resolve test target") from exc
        if any(_overlaps(resolved, p) for p in self._protected):
            raise IsolationError(f"Protected test target: {target}")
        if resolved == self.path or not resolved.is_relative_to(self.path):
            raise IsolationError(f"Target is not a disposable descendant: {target}")
        return resolved

    def mkdir(self, target: str | Path) -> Path:
        path = self.require(target)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_text(self, target: str | Path, content: str) -> Path:
        path = self.require(target)
        # Reject hard-linked files too: a safe pathname can share an external inode.
        if path.exists() and path.stat().st_nlink > 1:
            raise IsolationError("Refusing to write a hard-linked test target")
        if path.parent != self.path:
            self.mkdir(path.parent)
        path = self.require(path)
        path.write_text(content, encoding="utf-8")
        return path

    def close(self) -> None:
        self._check_root()
        self._temporary.cleanup()
        self._closed = True

    def __enter__(self) -> "DisposableRoot":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
