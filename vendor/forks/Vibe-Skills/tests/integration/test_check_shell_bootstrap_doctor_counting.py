from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


class CheckShellBootstrapDoctorCountingTests(unittest.TestCase):
    def test_check_shell_delegates_to_simplified_cli_check(self) -> None:
        content = (REPO_ROOT / "check.sh").read_text(encoding="utf-8")

        self.assertIn("vgo_cli.main check", content)
        self.assertNotIn("vibe bootstrap doctor gate", content)
        self.assertNotIn("FAIL=$((FAIL+1))", content)
        self.assertNotIn("WARN=$((WARN+1))", content)


if __name__ == "__main__":
    unittest.main()
