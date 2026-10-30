"""Help/version and read-only discovery. No execution commands."""

import argparse
import json
from collections.abc import Sequence

from . import __version__


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="agentic-runner",
        description="Milestone development runner. Read-only repository and roadmap discovery.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    preflight = subparsers.add_parser("discover", help="Inspect local evidence without executing project code")
    preflight.add_argument("repository", help="Checkout directory (or a directory inside it)")
    args = parser.parse_args(argv)
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
