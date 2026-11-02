"""Manual foreground execution and preserved read-only discovery."""

import argparse
import json
from collections.abc import Sequence

from . import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentic-runner",
        description="Run verified milestones on a development branch.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    preflight = subparsers.add_parser("discover", help="Inspect local evidence without executing project code")
    preflight.add_argument("repository", help="Checkout directory (or a directory inside it)")
    run = subparsers.add_parser("run", help="Run milestones in an already prepared, protected repository")
    run.add_argument("--config", required=True, help="Runner-owned project TOML configuration")
    args = parser.parse_args(argv)
    if args.command == "run":
        from .diagnostics import DiscoveryError
        from .project import Project, RunnerError
        from .runner import Loop

        try:
            Loop(Project.load(args.config)).run()
        except KeyboardInterrupt:
            print("Stopped; partial work and checkpoint retained.")
            return 130
        except (RunnerError, DiscoveryError, OSError, ValueError) as exc:
            print(f"Stopped: {exc}")
            return 1
        return 0
    if args.command == "discover":
        from .diagnostics import DiscoveryError
        from .discovery import discover

        try:
            result = discover(args.repository)
        except DiscoveryError as exc:
            print(json.dumps(exc.as_dict(), indent=2, sort_keys=True))
            return 2
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    parser.print_help()
    return 0
