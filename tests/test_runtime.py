import unittest

from agentic_runner.diagnostics import DiscoveryError
from agentic_runner.runtime import parse_commands, supports


class RuntimeTests(unittest.TestCase):
    def test_supported_version_ranges(self):
        for family, requirements in (
            ("python", [">=3.11,<3.13", "~=3.11", "~=3.12.0", "==3.12.*", "!=3.11.*", "3.12"]),
            ("node", [">=20 <23", "^22.0.0", "~22.0", "20 || 22", "22.x", "*"]),
        ):
            for requirement in requirements:
                with self.subTest(family=family, requirement=requirement):
                    self.assertTrue(supports(requirement, family, "fixture"))

    def test_unsupported_ranges(self):
        for family, requirements in (("python", ["<3.12", ">=3.13", "==3", "==3.11.*", "!=3.12.*", "3.12.1"]), ("node", ["^20.0.0", ">=24", "~22.1", "18 || 20"])):
            for requirement in requirements:
                with self.subTest(family=family, requirement=requirement):
                    self.assertFalse(supports(requirement, family, "fixture"))

    def test_unknown_syntax_cannot_be_silently_accepted(self):
        for family, requirement in (("python", "^3.12"), ("python", "~=3"), ("python", ">=3.12 garbage"), ("python", ["3.12"]), ("node", "22 || unknown"), ("node", "22.0.0-beta"), ("node", "22 ||")):
            with self.subTest(family=family, requirement=requirement):
                with self.assertRaises(DiscoveryError):
                    supports(requirement, family, "fixture")

    def test_literal_checks_preserve_argument_boundaries(self):
        commands = parse_commands('```bash\n# A comment\npython -m pytest "tests/some file.py"\npython -m compileall src\n```', "fixture")
        self.assertEqual(commands, [["python", "-m", "pytest", "tests/some file.py"], ["python", "-m", "compileall", "src"]])

    def test_shell_or_empty_checks_fail(self):
        for command in ("python -m pytest; true", "$(unsafe)", "X=1 pytest", "npm test | cat", "python > result", "# empty"):
            with self.subTest(command=command):
                with self.assertRaises(DiscoveryError):
                    parse_commands(f"```sh\n{command}\n```", "fixture")
