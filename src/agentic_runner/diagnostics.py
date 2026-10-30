"""Actionable discovery failures with stable machine-readable codes."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Diagnostic:
    code: str
    message: str
    source: str
    line: int | None = None


class DiscoveryError(ValueError):
    def __init__(self, code: str, message: str, source: str, line: int | None = None):
        self.diagnostic = Diagnostic(code, message, source, line)
        super().__init__(message)

    def as_dict(self) -> dict:
        return {"ok": False, "diagnostics": [asdict(self.diagnostic)]}
