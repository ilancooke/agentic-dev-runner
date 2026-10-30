"""Full native M4 suite with an optional cached Node runtime fixture.

No real Codex calls; all repositories, tools and state are owned disposable data.
"""

import argparse
import os
import unittest
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cached-node", action="store_true", help="Allow extraction of the pinned official Node image into an owned test fixture")
    args = parser.parse_args()
    if args.cached_node:
        os.environ["AGENTIC_RUNNER_NATIVE_NODE"] = "1"
    repository = Path(__file__).resolve().parents[2]
    suite = unittest.defaultTestLoader.discover(str(repository / "tests"), top_level_dir=str(repository))
    return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
