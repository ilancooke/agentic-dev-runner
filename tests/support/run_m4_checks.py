"""Single explicitly authorized entry point for offline M4 container testing.

This module never accepts credentials, launches real inference or changes host
security policy. Every job uses the existing generated disposable-root guards.
"""

import argparse
import os
import re
import unittest
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Reviewed immutable runner image ID (sha256:...)")
    arguments = parser.parse_args()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", arguments.image):
        parser.error("Use the immutable image ID, never a tag")
    os.environ["AGENTIC_RUNNER_M4_IMAGE"] = arguments.image
    repository = Path(__file__).resolve().parents[2]
    suite = unittest.defaultTestLoader.discover(str(repository / "tests"), top_level_dir=str(repository))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
