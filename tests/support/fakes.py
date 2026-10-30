"""Scripted in-memory external responses, without real Codex/GitHub/container I/O."""

from collections import deque
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .isolation import DisposableRoot


@dataclass(frozen=True)
class Call:
    operation: str
    target: Path


class FakeExternalAdapter:
    """Explicit scripted outcomes; unexpected calls fail rather than contacting services.

    A harness utility, not a proposed production adapter interface.
    """

    def __init__(self, root: DisposableRoot, *outcomes: Any) -> None:
        self.root = root
        self.calls: list[Call] = []
        self._outcomes = deque(deepcopy(outcomes))

    def call(self, operation: str, target: str | Path) -> Any:
        path = self.root.require(target)
        self.calls.append(Call(operation, path))
        if not self._outcomes:
            raise AssertionError(f"Unscripted external call: {operation}")
        outcome = self._outcomes.popleft()
        if isinstance(outcome, Exception):
            raise outcome
        return deepcopy(outcome)
