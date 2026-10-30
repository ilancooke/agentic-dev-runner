"""Support python -m agentic_runner using the same CLI entry point."""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
