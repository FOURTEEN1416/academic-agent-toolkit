from __future__ import annotations

import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PYTHON_HELPERS = REPO_ROOT / "scripts" / "common" / "python_helpers.sh"


class ShellEntrypointCompatibilityTests(unittest.TestCase):
    def test_install_entrypoints_are_bash_parseable(self) -> None:
        for relpath in ("install.sh", "check.sh", "scripts/bootstrap/one-shot-setup.sh"):
            result = subprocess.run(
                ["bash", "-n", str(REPO_ROOT / relpath)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, result.returncode, f"{relpath} should parse cleanly: {result.stderr}")

    def test_install_entrypoints_avoid_mapfile(self) -> None:
        for relpath in ("install.sh", "check.sh", "scripts/bootstrap/one-shot-setup.sh"):
            content = (REPO_ROOT / relpath).read_text(encoding="utf-8")
            self.assertNotIn("mapfile", content, relpath)

    def test_install_entrypoints_declare_python_310_floor(self) -> None:
        helper_content = PYTHON_HELPERS.read_text(encoding="utf-8")
        self.assertIn("PYTHON_MIN_MAJOR=3", helper_content)
        self.assertIn("PYTHON_MIN_MINOR=10", helper_content)
        self.assertIn("requires Python ${PYTHON_MIN_MAJOR}.${PYTHON_MIN_MINOR}+", helper_content)
        self.assertIn("python3 --version", helper_content)
        for relpath in ("install.sh", "check.sh"):
            content = (REPO_ROOT / relpath).read_text(encoding="utf-8")
            self.assertIn("PYTHON_MIN_MAJOR=3", content, relpath)
            self.assertIn("PYTHON_MIN_MINOR=10", content, relpath)
            self.assertIn("scripts/common/python_helpers.sh", content, relpath)

    def test_one_shot_wrappers_do_not_reference_mcp_report(self) -> None:
        for relpath in ("scripts/bootstrap/one-shot-setup.sh", "scripts/bootstrap/one-shot-setup.ps1"):
            content = (REPO_ROOT / relpath).read_text(encoding="utf-8")
            self.assertNotIn("MCP auto-provision summary", content)

    def test_check_sh_rejects_python_below_floor_before_helper_dispatch(self) -> None:
        if os.name == "nt":
            self.skipTest("Windows shell frontends now hand off to PowerShell before Python floor checks")

        with tempfile.TemporaryDirectory() as tempdir:
            bin_dir = Path(tempdir)
            fake_python = bin_dir / "python3"
            fake_python.write_text(
                "#!/bin/sh\n"
                "if [ \"$1\" = \"-\" ]; then\n"
                "  cat >/dev/null\n"
                "  echo \"3.9.18\"\n"
                "  exit 0\n"
                "fi\n"
                "echo \"unexpected helper dispatch\" >&2\n"
                "exit 23\n",
                encoding="utf-8",
            )
            fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

            fake_python_alias = bin_dir / "python"
            fake_python_alias.write_text(fake_python.read_text(encoding="utf-8"), encoding="utf-8")
            fake_python_alias.chmod(fake_python_alias.stat().st_mode | stat.S_IXUSR)

            env = dict(os.environ)
            env["PATH"] = f"{bin_dir}:{env.get('PATH', '')}"
            result = subprocess.run(
                ["bash", str(REPO_ROOT / "check.sh"), "--skills-dir", str(Path(tempdir) / "skills")],
                cwd=REPO_ROOT,
                env=env,
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(0, result.returncode)
        self.assertIn("requires Python 3.10+", result.stderr)
        self.assertIn("Detected python3", result.stderr)
        self.assertNotIn("unexpected helper dispatch", result.stderr)


if __name__ == "__main__":
    unittest.main()
